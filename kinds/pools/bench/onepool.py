#!/usr/bin/env python3
"""Build the pools kind's benchmark images, one per configuration and placement, each linked for its own slot
in flash, and the bundles written to a board: kinds/crc/bench/onecrc.py with the kind's own parts changed
(lab/plans/2026-11-26-pools-kind.md, step 3). The boot stub, the bundle's ELF and its manifest are made by
onebundle.py's own functions, unchanged; the board support (firmware/common/<board>) is used unchanged.
Runs inside the toolchain image with the repository at /work and the libraries at LIBS (onebuild.sh does
that). No board is touched.

Usage: python3 -I onepool.py sizes  BOARD [--out DIR]
       python3 -I onepool.py table  BOARD [--bundle N[,N...]] [--out DIR]
       python3 -I onepool.py layout BOARD FILE [--out DIR]

An image, as the CRC kind's: the fixed part (vector table, harness and time_call, the C library's memory
functions with memcpy on a 32-byte boundary, main, the reference free list (../adapter_ref.c as ref_pool.o),
start-up code); then the placement bytes; then the configuration's adapter code (adapter_*.o, our lwIP port
as adapter_lwip_port.o); then FAR bytes; then the library. ../boards.txt names configurations that exist on
some boards only (heapless's pool: not on Cortex-M0+). The checks are onecrc.py's.

Every image's manifest entry carries the configuration's sizes (sizes_of): its input sections in the link
map against those of a null image (null_pool.c, linked once per board, never flashed), by object and
section; they must be the same at every placement.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(KIND, "../.."))
FW = os.path.join(REPO, "firmware")
sys.path.insert(0, os.path.join(FW, "nrf5340-rb-bench"))
import onebundle as ob  # noqa: E402  (image, symbols, stub, bundle, region, sha256, sh)

LIBS = os.environ.get("LIBS", "/libs")
GEN = os.path.join(KIND, "build/gen/src")
UNIT, BOOT_LEN, SEG = ob.UNIT, ob.BOOT_LEN, ob.SEG
SIZES_PLACE = ob.SIZES_PLACE
FAR = 6144            # as version 2 (firmware/nrf5340-rb-bench/Makefile FAR)
OPT = "-O2"           # as version 2
ALIGN_SLACK = 8       # check(): code behind the gap lies less than this off the placement
LAYOUT = "fixed, placement, adapter, far, library"   # the order in an image, in the manifest and the run files
RESULT_WORDS = 9 + 2 * (5 * 2 * 6 * 2 + 5 * 2 + 1) + 4 + 2   # struct results in main.c
FIXED_NAMES = ("memcpy", "memmove", "memset", "memcmp", "time_call", "main", "adapter_ref", "ref_alloc", "ref_free", "ref_init")
MEMSYMS = ("memcpy memmove memset memcmp __aeabi_memcpy __aeabi_memcpy4 __aeabi_memcpy8 __aeabi_memmove "
           "__aeabi_memmove4 __aeabi_memmove8 __aeabi_memset __aeabi_memset4 __aeabi_memset8 __aeabi_memclr "
           "__aeabi_memclr4 __aeabi_memclr8").split()   # firmware/common/rust.mk RUST_MEMSYMS
RUST_TARGET = {"cortex-m0plus": "thumbv6m-none-eabi", "cortex-m4": "thumbv7em-none-eabi",
               "cortex-m7": "thumbv7em-none-eabi", "cortex-m33": "thumbv8m.main-none-eabi"}

OWN_C = ["adapter_riot.c", "adapter_threadx.c", "tx_kernel_stubs.c", "adapter_cmsis_rtx.c", "adapter_contiki.c",
         "adapter_c_allocator.c", "adapter_lwip.c", "adapter_rust.c"]
OWN_CXX = ["adapter_etl.cpp", "adapter_memorypool.cpp"]
# object names of our own files that are not called adapter_*: the lwIP port belongs to the adapter's code
OBJ_NAME = {"shims/lwip/sys_arch.c": "adapter_lwip_port"}
LIB_C = [f"{LIBS}/riot/sys/memarray/memarray.c", f"{LIBS}/contiki-ng/os/lib/memb.c", f"{LIBS}/c-allocator/src/fb_allocator.c",
         f"{LIBS}/lwip/src/core/memp.c", f"{LIBS}/cmsis-rtx/Source/rtx_mempool.c",
         f"{LIBS}/threadx/common/src/tx_block_allocate.c", f"{LIBS}/threadx/common/src/tx_block_release.c",
         f"{LIBS}/threadx/common/src/tx_block_pool_create.c", f"{LIBS}/threadx/common/src/tx_block_pool_delete.c"]
LIB_CXX = [f"{LIBS}/c-allocator/src/LockGuard.cpp"]
# per core: ThreadX's port, CMSIS's device header and its define (as kinds/pools/cross.sh)
CORE_PORT = {"cortex-m0plus": ("cortex_m0", "ARMCM0plus", "ARMCM0P"), "cortex-m4": ("cortex_m4", "ARMCM4", "ARMCM4"),
             "cortex-m7": ("cortex_m7", "ARMCM7", "ARMCM7"), "cortex-m33": ("cortex_m33", "ARMCM33", "ARMCM33")}

FIXED = (". = ALIGN(32); *libc_a-memcpy.o(.text*) *libc_a-memcpy-stub.o(.text*) *libc_a-memmove.o(.text*) "
         "*libc_a-memset.o(.text*) *libc_a-memcmp.o(.text*) *libc_a-aeabi_mem*.o(.text*) "
         "*main.o(.text*) *main.o(.rodata .rodata.[!s]*) *ref_pool.o(.text*) *ref_pool.o(.rodata .rodata.[!s]*) "
         "*startup.o(.text*) *startup.o(.rodata .rodata.[!s]*) _bench_fixed_end = .;")
# Not the strings (.rodata.str*): the linker merges equal strings of all objects into the first such
# section it places, so another configuration's names would land in the fixed part. They are only names.
NEAR = "KEEP(*(.bench_place)) _bench_near_start = .; *adapter_*.o(.text*) _bench_near_end = .;"


def read_boards():
    """boards.txt: {adapter: set of boards} for the configurations that exist on some boards only."""
    out = {}
    for n, ln in enumerate(open(os.path.join(KIND, "boards.txt")), 1):
        f = ln.split("#")[0].split()
        if f:
            if len(f) < 2 or f[0] in out:
                sys.exit(f"boards.txt:{n}: an adapter (once) and its boards expected")
            out[f[0]] = set(f[1:])
    return out


def read_ramtables_unused():
    """ramtables.txt: {configuration: (the configuration whose code it is, [table symbols])}."""
    out = {}
    for n, ln in enumerate(open(os.path.join(KIND, "ramtables.txt")), 1):
        ln = ln.split("#", 1)[0] if ln.lstrip().startswith("#") else ln
        f = ln.split(None, 2)
        if not f:
            continue
        if len(f) != 3 or f[0] in out:
            sys.exit(f"ramtables.txt:{n}: configuration (once), the configuration of its code and the table symbols expected")
        out[f[0]] = (f[1], [x.strip() for x in f[2].split(" | ") if x.strip()])
    return out


def on_board(adapter, board, boards):
    return adapter not in boards or board in boards[adapter]


def read_configs():
    out = []
    for n, ln in enumerate(open(os.path.join(KIND, "configs.txt")), 1):
        f = ln.split("#")[0].split(None, 2)
        if not f:
            continue
        if len(f) != 3 or f[1] not in ("c", "cpp", "rust"):
            sys.exit(f"configs.txt:{n}: adapter, kind (c, cpp or rust) and name expected")
        out.append((f[0], f[1], f[2].strip()))
    if len({c[0] for c in out}) != len(out):
        sys.exit("configs.txt: an adapter is listed twice")
    return out


def read_slots():
    out = []
    for n, ln in enumerate(open(os.path.join(KIND, "slots.txt")), 1):
        f = ln.split("#")[0].split()
        if f:
            if len(f) != 5:
                sys.exit(f"slots.txt:{n}: five fields expected")
            out.append((f[0], int(f[1]), int(f[2]), int(f[3], 0), int(f[4], 0)))
    return out


def ram_archive(src, dst, names, work):
    """A copy of the archive src at dst in which every member that defines one of names (as
    arm-none-eabi-nm -C names it) has that symbol's input section renamed from .rodata.* to .data.*.
    Returns the names found."""
    found = set()
    tmp = f"{work}.x"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    shutil.copyfile(src, dst)
    members = ob.sh(["arm-none-eabi-ar", "t", src]).split()
    if len(set(members)) != len(members):
        sys.exit(f"{src}: two members of one name")
    ob.sh(["arm-none-eabi-ar", "x", "--output", tmp, src])
    changed = []
    for m in members:
        obj = f"{tmp}/{m}"
        ren = {}
        for ln in ob.sh(["arm-none-eabi-objdump", "-t", "-C", obj]).splitlines():
            if "\t" not in ln:
                continue
            left, right = ln.split("\t", 1)
            sec, rest = left.split()[-1], right.split(None, 1)
            if len(rest) == 2 and rest[1] in names and sec != "*UND*":
                if not sec.startswith(".rodata."):
                    sys.exit(f"{src}({m}): {rest[1]} is in {sec}, not a section of its own under .rodata")
                ren[sec] = ".data." + sec[len(".rodata."):]
                found.add(rest[1])
        if ren:
            ob.sh(["arm-none-eabi-objcopy"] + [a for o, n in sorted(ren.items())
                                               for a in ("--rename-section", f"{o}={n},alloc,load,data,contents")] + [obj])
            changed.append(obj)
    if changed:
        ob.sh(["arm-none-eabi-ar", "r", dst] + changed)
    shutil.rmtree(tmp)
    return found


def ram_objects(board, objs, work, cfg, code, names, kind):
    """The archives a configuration with its table in RAM links: copies with the table sections renamed."""
    d = f"{work}/ram/{cfg}"
    os.makedirs(d, exist_ok=True)
    out = dict(objs)
    found = ram_archive(objs["lib"], f"{d}/objs.a", names, f"{d}/lib")
    if kind == "rust":
        out["rust"] = f"{d}/libvl_crc_rust.a"
        found |= ram_archive(objs["rust"], out["rust"], names, f"{d}/rust")
    out["lib"] = f"{d}/objs.a"
    missing = [n for n in names if n not in found]
    if missing:
        sys.exit(f"{board.name}: {cfg}: no object defines {', '.join(missing)} (ramtables.txt)")
    return out


def read_ramtables():
    """This kind has no table moved to RAM."""
    return {}


class Board:
    """What onebundle.py's stub() and bundle() read of a board, from the
    board support under firmware/common (board.mk, the flash linker script,
    board_uart.h), the same files the ring-buffer images use."""

    def __init__(self, name):
        self.name = name
        self.common = os.path.join(FW, "common", name)
        mk = open(os.path.join(self.common, "board.mk")).read()
        self.arch = re.search(r"^ARCH\s*=\s*(.+)$", mk, re.M).group(1).strip()
        self.ld = os.path.join(self.common, re.search(r"^LD_FLASH\s*=\s*\$\(COMMON\)/(\S+)", mk, re.M).group(1))
        self.fbase, self.flen = ob.region(self.ld, "FLASH")
        self.rbase, self.rlen = ob.region(self.ld, "RAM")
        self.per_bundle = self.flen // SEG
        self.far = FAR
        m = re.search(r"^#define\s+BOARD_SELECT_ADDR\s+(0x[0-9A-Fa-f]+)",
                      open(os.path.join(self.common, "board_uart.h")).read(), re.M)
        self.sel_fixed = int(m.group(1), 16) if m else None
        self.cpu = re.search(r"-mcpu=(\S+)", self.arch).group(1)


def flags(board):
    txp, dev, devmacro = CORE_PORT[board.cpu]
    inc = [f"-I{HERE}", f"-I{board.common}", f"-I{FW}/common", f"-I{KIND}", f"-I{LIBS}/etl/include",
           f"-I{KIND}/shims/riot", f"-I{LIBS}/riot/sys/include", f"-I{LIBS}/threadx/common/inc",
           f"-I{LIBS}/threadx/ports/{txp}/gnu/inc", f"-I{KIND}/shims/contiki", f"-I{LIBS}/contiki-ng/os",
           f"-I{LIBS}/c-allocator/src", f"-I{KIND}/shims/lwip", f"-I{LIBS}/lwip/src/include", f"-I{KIND}/shims",
           f"-I{LIBS}/cmsis-rtx/Include", f"-I{LIBS}/cmsis-rtx/Source", f"-I{LIBS}/cmsis-rtx/Config",
           f"-I{LIBS}/cmsis6/CMSIS/Core/Include", f"-I{LIBS}/cmsis6/CMSIS/RTOS2/Include",
           f"-I{LIBS}/cortex-dfp/Device/{dev}/Include", f"-I{LIBS}/memorypool-head/src",
           "-DALLOC_LOCK_NONE", "-DOS_EVR_MEMORY=0", f"-D{devmacro}", f'-DCMSIS_device_header="{dev}.h"']
    # the flags of the version 2 benchmark (firmware/nrf5340-rb-bench/Makefile COMMONF)
    common = board.arch.split() + [OPT, "-g", "-Wall", "-Wextra", "-Wno-missing-field-initializers",
                                   "-Wno-unused-function", "-DNDEBUG", "-ffunction-sections", "-fdata-sections"] + inc
    cflags = common + ["-ffreestanding", "-std=c11"]
    # C++ without -ffreestanding, as the bench builds its C++ adapters
    cxxflags = common + ["-std=c++20", "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics"]
    return cflags, cxxflags


def objects(board, work):
    """Everything an image links but main.o, once per board: startup.o,
    ref_pool.o (the reference), the archive of adapters (the PRIMASK row too) and libraries, the Rust library."""
    cflags, cxxflags = flags(board)
    o = f"{work}/o"
    os.makedirs(o, exist_ok=True)
    jobs = [(["arm-none-eabi-gcc"] + cflags + ["-fno-tree-loop-distribute-patterns", "-c",
              f"{board.common}/startup.c", "-o", f"{work}/startup.o"]),
            (["arm-none-eabi-gcc"] + cflags + ["-c", f"{KIND}/adapter_ref.c", "-o", f"{work}/ref_pool.o"]),
            (["arm-none-eabi-gcc"] + cflags + ["-DPOOL_PRIMASK=1", "-c", f"{KIND}/adapter_ref.c", "-o", f"{o}/adapter_ref_primask.o"]),
            (["arm-none-eabi-gcc"] + cflags + ["-c", f"{KIND}/shims/lwip/sys_arch.c", "-o", f"{o}/adapter_lwip_port.o"]),
            (["arm-none-eabi-gcc"] + cflags + ["-c", f"{HERE}/null_pool.c", "-o", f"{o}/adapter_null.o"])]
    # adapter_null.o: the null configuration of the size measure (sizes_of); no image links it, as nothing names it
    arch = [f"{o}/adapter_ref_primask.o", f"{o}/adapter_lwip_port.o", f"{o}/adapter_null.o"]
    for f in OWN_C + LIB_C:
        src = f if f.startswith("/") else f"{KIND}/{f}"
        dst = f"{o}/{os.path.basename(f)[:-2]}.o" if f in OWN_C else f"{o}/lib_{os.path.basename(os.path.dirname(f))}_{os.path.basename(f)[:-2]}.o"
        jobs.append(["arm-none-eabi-gcc"] + cflags + (["-w"] if f in LIB_C else []) + ["-c", src, "-o", dst])
        arch.append(dst)
    for f in OWN_CXX + LIB_CXX:
        src = f if f.startswith("/") else f"{KIND}/{f}"
        dst = f"{o}/{os.path.basename(f)[:-4]}.o" if f in OWN_CXX else f"{o}/lib_{os.path.basename(f)[:-4]}.o"
        jobs.append(["arm-none-eabi-g++"] + cxxflags + (["-w"] if f in LIB_CXX else []) + ["-c", src, "-o", dst])
        arch.append(dst)
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
        list(pool.map(ob.sh, jobs))
    lib = f"{work}/objs.a"
    if os.path.exists(lib):
        os.remove(lib)
    ob.sh(["arm-none-eabi-ar", "rcs", lib] + arch)
    # the Rust configuration: the crate for the core's soft-float target, opt-level 2 (-O2), as common/rust.mk
    rt = RUST_TARGET[board.cpu]
    env = dict(os.environ, CARGO_PROFILE_RELEASE_OPT_LEVEL="2", RUSTFLAGS=f"-C target-cpu={board.cpu} --cap-lints warn")
    feat = ["--no-default-features"] if board.cpu == "cortex-m0plus" else []   # heapless's pool needs LDREX/STREX
    subprocess.run(["cargo", "build", "-q", "--offline", "--locked", "--release", "--target", rt] + feat +
                   ["--target-dir", f"{work}/rust"], cwd=f"{KIND}/rust", env=env, check=True)
    return {"lib": lib, "rust": f"{work}/rust/{rt}/release/libvl_pools_rust.a"}


def link_one(board, objs, j, work):
    cflags, _ = flags(board)
    od = f"{work}/one/{j['adapter']}-p{j['place']}-{j['base']:#x}"
    os.makedirs(od, exist_ok=True)
    ld = open(board.ld).read()
    ld, n1 = re.subn(r"^(\s*FLASH\s+\(rx\)\s*:\s*)ORIGIN = [^,]+, LENGTH = \S+",
                     lambda m: f"{m.group(1)}ORIGIN = {j['base']:#x}, LENGTH = {j['slot_bytes']}", ld, flags=re.M)
    ld, n2 = re.subn(re.escape("*(.text.time_call) *(.text.bench_adapter*)"), f"*(.text.time_call) {FIXED} {NEAR}", ld)
    if n1 != 1 or n2 != 1:
        sys.exit(f"{board.ld}: no FLASH region or no place for the fixed part")
    with open(f"{od}/slot.ld", "w") as fh:
        fh.write(ld)
    ob.sh(["arm-none-eabi-gcc"] + cflags + [f"-DBENCH_POOL={j['adapter']}",
           "-DADAPTER_CONST=" + ("" if j["kind"] == "rust" else "const"),
           f"-DBENCH_PLACE={j['place']}", f"-DBENCH_SHIFT={FAR}", "-c", f"{HERE}/main.c", "-o", f"{od}/main.o"])
    us = [f"-Wl,-u,{s}" for s in MEMSYMS + ["adapter_ref"]]
    ob.sh(["arm-none-eabi-g++"] + board.arch.split() + [OPT, "-nostartfiles", "--specs=nano.specs",
           "--specs=nosys.specs", "-Wl,--gc-sections", "-Wl,-n", "-T", f"{od}/slot.ld", f"-Wl,-Map={od}/fw.map"] + us +
          [f"{od}/main.o", f"{work}/startup.o", f"{work}/ref_pool.o", "-Wl,--start-group", objs["lib"], "-Wl,--end-group",
           "-Wl,-lc_nano"] + ([objs["rust"]] if j["kind"] == "rust" else []) + ["-o", f"{od}/fw.elf"])
    return f"{od}/fw.elf"


def words_of(elf, addr, count):
    """count little-endian words at addr from the loaded segments of an ELF."""
    import struct
    data = open(elf, "rb").read()
    phoff, = struct.unpack_from("<I", data, 28)
    phentsize, phnum = struct.unpack_from("<HH", data, 42)
    for k in range(phnum):
        ptype, off, vaddr, _paddr, filesz = struct.unpack_from("<5I", data, phoff + k * phentsize)
        if ptype == 1 and vaddr <= addr and addr + 4 * count <= vaddr + filesz:
            return struct.unpack_from(f"<{count}I", data, off + addr - vaddr)
    return None


def check(board, j, elf, syms, state):
    end = [a for a, _, _, n in syms if n == "_bench_fixed_end"]
    start = [a for a, _, _, n in syms if n == "_bench_near_start"]
    near = [a for a, _, _, n in syms if n == "_bench_near_end"]
    if len(end) != 1 or len(start) != 1 or len(near) != 1:
        sys.exit(f"{elf}: no end of the fixed part or no start or end of the adapter's code")
    if start[0] - end[0] != j["place"]:
        sys.exit(f"{elf}: the adapter's code starts {start[0] - end[0]} bytes behind the fixed part, not {j['place']}")
    part = [(a - j["base"], s, n) for a, s, t, n in syms if j["base"] <= a < end[0] and s is not None and t in "tTrRdD"]
    part.append((end[0] - j["base"], 0, "_bench_fixed_end"))
    where = {n: a for a, s, n in part}
    for n in FIXED_NAMES:
        if n not in where:
            sys.exit(f"{elf}: {n} is not in the fixed part")
    if where["memcpy"] % 32:
        sys.exit(f"{elf}: memcpy at offset {where['memcpy']:#x}, not on a 32-byte boundary")
    if state.get("fixed") is None:
        state["fixed"], state["first"] = part, j
    elif part != state["fixed"]:
        f = state["first"]
        sys.exit(f"{elf}: its fixed part differs from that of {f['adapter']} p{f['place']}: "
                 + ", ".join(f"{a:#x} {n}" for a, s, n in sorted(set(part) ^ set(state["fixed"]))[:6]))
    sel = [a for a, _, _, n in syms if n == "vl_select"]
    if board.sel_fixed is not None:
        if sel:
            sys.exit(f"{elf}: selection words in RAM, the board keeps them at {board.sel_fixed:#x}")
        state["sel"] = board.sel_fixed
    elif len(sel) != 1 or state.get("sel") not in (None, sel[0]):
        sys.exit(f"{elf}: selection words at {sel}, other images {state.get('sel')}")
    else:
        state["sel"] = sel[0]
    res = [(a, s) for a, s, _, n in syms if n == "results"]
    if res != [(board.rbase, 4 * RESULT_WORDS)]:
        sys.exit(f"{elf}: the result block {res}, expected {4 * RESULT_WORDS} bytes at {board.rbase:#x}")
    # the adapter's functions before the gap: the words of its descriptor (pool.h pool_adapter) that point
    # to a function (init, alloc, free, region)
    code = j.get("code", j["adapter"])
    desc = [(a, s) for a, s, t, n in syms if n == code and s]
    if len(desc) != 1:
        sys.exit(f"{elf}: no descriptor {code}")
    w = words_of(elf, desc[0][0], desc[0][1] // 4)
    funcs_at = {a for a, s, t, n in syms if t in "tTwW"}
    if w is None:
        sys.exit(f"{elf}: the descriptor {code} is not in a loaded segment")
    fns = [x & ~1 for x in w if x & 1 and (x & ~1) in funcs_at]
    if not fns:
        sys.exit(f"{elf}: the descriptor {code} names no function")
    j["adapter_functions"] = len(fns)
    late = [f for f in fns if not start[0] <= f < near[0]]
    if late:
        sys.exit(f"{elf}: functions of the adapter not between the placement bytes and the gap: "
                 f"{', '.join(hex(f) for f in late)}")
    behind = [a for a, s, t, n in syms if t in "tTwW" and s and a >= near[0] and n != "bench_shift"]
    if behind and min(behind) - near[0] < FAR:
        sys.exit(f"{elf}: code {min(behind) - near[0]} bytes behind the adapter, less than {FAR}")
    # the placement moves everything behind the fixed part: the offsets from the adapter's start are those of
    # the configuration's other images, exactly in the adapter's code, and behind the gap within less than
    # ALIGN_SLACK bytes (code that its compiler aligns to 8 bytes cannot follow a placement of 4)
    top = j["base"] + j["slot_bytes"]
    moved = sorted((n, s, a - start[0], a < near[0]) for a, s, t, n in syms
                   if start[0] <= a < top and s and t in "tTwWrRdD" and n not in ("bench_place", "bench_shift"))
    first = state.setdefault("moved", {}).setdefault(j["adapter"], (moved, j["place"]))
    off = [(n, a, a0) for (n, s, a, nr), (n0, s0, a0, nr0) in zip(moved, first[0])
           if (n, s, nr) != (n0, s0, nr0) or abs(a - a0) >= (1 if nr else ALIGN_SLACK)]
    if len(moved) != len(first[0]) or off:
        sys.exit(f"{elf}: behind the fixed part not as at placement {first[1]} ({len(moved)} and {len(first[0])} "
                 "symbols): " + ", ".join(f"{n} {a:#x} {a0:#x}" for n, a, a0 in off[:6]))
    j["place_slack"] = max((abs(a - a0) for (_, _, a, _), (_, _, a0, _) in zip(moved, first[0])), default=0)
    j["far_code_bytes"] = (max(a + (s or 0) for a, s, t, n in syms if t in "tTwW" and a >= min(behind)) - min(behind)) if behind else 0


def ram_check(board, j, elf):
    """Every table symbol of a configuration of ramtables.txt lies in RAM, once."""
    names = j.get("ram_tables")
    if not names:
        return
    at = {}
    for ln in ob.sh(["arm-none-eabi-nm", "-n", "-S", "-C", elf]).splitlines():
        f = ln.split(None, 3)
        if len(f) == 4 and f[3] in names:
            at.setdefault(f[3], []).append(int(f[0], 16))
    for n in names:
        a = at.get(n, [])
        if len(a) != 1 or not board.rbase <= a[0] < board.rbase + board.rlen:
            sys.exit(f"{elf}: {n} at {[hex(x) for x in a]}, not once in RAM ({board.rbase:#x}, {board.rlen} bytes)")
    j["ram_tables_at"] = {n: f"{at[n][0]:#010x}" for n in names}


def pool_h(name):
    return int(re.search(rf"^#define {name} (\d+)u", open(os.path.join(KIND, "pool.h")).read(), re.M).group(1))


# the blocks and the canaries around the pool's memory (pool.h): 32 x 32 + 2 x 4 words = 1056 bytes
POOL_STORAGE = pool_h("POOL_BLOCKS") * pool_h("POOL_BLOCK_SIZE") + 2 * 4 * pool_h("POOL_CANARY_WORDS")
MAP_LINE = re.compile(r"^ (\.\S+)(?:\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+(\S+))?$")
MAP_REST = re.compile(r"^\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+(\S+)$")


def map_sections(path):
    """{(object, input section): bytes} of a link map's memory map: the object as its file name (an archive
    member by its own name, e.g. adapter_riot.o), each input section that has bytes."""
    out, lines, pending = {}, open(path).read().split("Linker script and memory map", 1)[1].splitlines(), None
    for ln in lines:
        m = MAP_LINE.match(ln)
        if m and m.group(4):
            sec, size, obj = m.group(1), int(m.group(3), 16), m.group(4)
        elif m:
            pending = m.group(1)
            continue
        elif pending and MAP_REST.match(ln):
            r = MAP_REST.match(ln)
            sec, size, obj = pending, int(r.group(2), 16), r.group(3)
        else:
            pending = None
            continue
        pending = None
        if size:
            mm = re.search(r"\(([^()]+)\)$", obj)
            key = (mm.group(1) if mm else os.path.basename(obj), sec)
            out[key] = out.get(key, 0) + size
    return out


def sizes_of(mapfile, null, descriptor):
    """The configuration's sizes in its image, from the link map: the input sections the image has and the
    null image (null_pool.c, the same harness and reference with a pool that does nothing) has not, by object
    and section, so the harness, the reference, the start-up code and what the C library gives all of them
    count for neither. Not counted: the descriptor (the adapter's own .rodata/.data section of that name), the
    placement and gap bytes, and strings (.rodata.str*: names, which the linker merges across objects).
    code: .text* sections; const: .rodata* (constant data in flash); flash = code + const; ram: .data* and
    .bss*, the 32 blocks of 32 bytes and the canaries (POOL_STORAGE, 1056 bytes) included; ram_overhead =
    ram - POOL_STORAGE, what the pool needs beyond them (the measure of ../sizes.py, there by symbol)."""
    code = const = ram = 0
    for (obj, sec), size in map_sections(mapfile).items():
        if ((obj, sec) in null or sec in (".bench_place", ".bench_shift") or sec.startswith(".rodata.str")
                or sec.rsplit(".", 1)[-1] == descriptor):
            continue
        if sec.startswith(".text"):
            code += size
        elif sec.startswith(".rodata"):
            const += size
        elif sec.startswith((".data", ".bss")):
            ram += size
    return {"code_bytes": code, "const_bytes": const, "flash_bytes": code + const, "ram_bytes": ram,
            "ram_overhead_bytes": ram - POOL_STORAGE}


def build(board, jobs, out, work):
    objs = objects(board, work)
    ram = {}
    for j in jobs:
        if "code" in j and j["adapter"] not in ram:
            ram[j["adapter"]] = ram_objects(board, objs, work, j["adapter"], j["code"], j["ram_tables"], j["kind"])
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
        elfs = list(pool.map(lambda j: link_one(board, ram.get(j["adapter"], objs), j, work), jobs))
    j0 = jobs[0]
    null_elf = link_one(board, objs, {"adapter": "adapter_null", "kind": "c", "place": j0["place"],
                                      "base": j0["base"], "slot_bytes": j0["slot_bytes"]}, work)
    null = map_sections(os.path.join(os.path.dirname(null_elf), "fw.map"))
    state = {}
    for j, src in zip(jobs, elfs):
        j["_map"] = os.path.join(os.path.dirname(src), "fw.map")
        d = f"{out}/img/{j['adapter']}-p{j['place']}"
        os.makedirs(d, exist_ok=True)
        elf = f"{d}/fw.elf"
        shutil.copyfile(src, elf)
        img = ob.image(elf, j["base"])
        if len(img) > j["slot_bytes"]:
            sys.exit(f"{elf}: {len(img)} bytes, its slot has {j['slot_bytes']}")
        syms = ob.symbols(elf)
        check(board, j, elf, syms, state)
        ram_check(board, j, elf)
        j["sizes"] = sizes_of(j.pop("_map"), null, j["adapter"])
        first = state.setdefault("sizes", {}).setdefault(j["adapter"], (j["sizes"], j["place"]))
        if first[0] != j["sizes"]:
            sys.exit(f"{elf}: sizes {j['sizes']}, at placement {first[1]} {first[0]}")
        ob.sh(["sh", "-c", f"arm-none-eabi-nm -S --size-sort -C {elf} > {d}/nm.txt"])
        j.update(bytes=len(img), elf=elf, sha256=ob.sha256(open(elf, "rb").read()), image_sha256=ob.sha256(img))
    for a in sorted({j["adapter"] for j in jobs if j["place_slack"]}):
        at = sorted(j["place"] for j in jobs if j["adapter"] == a and j["place_slack"])
        print(f"{board.name}: {a}: its code behind the gap lies {max(j['place_slack'] for j in jobs if j['adapter'] == a)} "
              f"bytes off the placement at placements {at} (its alignment)", flush=True)
    with open(f"{out}/fixed.txt", "w") as fh:
        fh.write("".join(f"{a:#07x} {s:5d} {n}\n" for a, s, n in state["fixed"]))
    return {"select_addr": state["sel"], "fixed_bytes": state["fixed"][-1][0],
            "fixed_sha256": ob.sha256(open(f"{out}/fixed.txt", "rb").read())}


def main():
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ("sizes", "table", "layout"):
        sys.exit(__doc__)
    mode, bname, args = args[0], args[1], args[2:]
    layout = args.pop(0) if mode == "layout" and args else None
    out, only = None, None
    while args:
        o = args.pop(0)
        if o == "--out" and args:
            out = args.pop(0)
        elif o == "--bundle" and args and mode == "table":
            only = [int(n) for n in args.pop(0).split(",")]
        else:
            sys.exit(__doc__)
    if mode == "layout" and layout is None:
        sys.exit(__doc__)
    if not os.path.isdir(os.path.join(FW, "common", bname)):
        sys.exit(f"unknown board {bname}")
    board = Board(bname)
    out = out or os.path.join(KIND, "build/v2", bname)
    work = os.path.join(KIND, "build/one", bname)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    boards = read_boards()
    rams = read_ramtables()
    every = read_configs()
    for a in list(boards) + list(rams):
        if a not in {c[0] for c in every}:
            sys.exit(f"{a} (boards.txt or ramtables.txt) is not in configs.txt")
    for a, (code, _) in rams.items():
        if code not in {c[0] for c in every} or code in rams:
            sys.exit(f"ramtables.txt: {a}: {code} is not a configuration of its own in configs.txt")
    configs = [c for c in every if on_board(c[0], bname, boards)]
    kinds = {a: k for a, k, _ in configs}
    names = {a: n for a, _, n in configs}

    def ram_fields(j):
        if j["adapter"] in rams:
            j["code"], j["ram_tables"] = rams[j["adapter"]]
        return j

    if mode == "sizes":
        jobs = [ram_fields({"adapter": a, "kind": k, "name": n, "place": SIZES_PLACE, "base": board.fbase + BOOT_LEN,
                            "slot_bytes": min(board.flen, SEG) - BOOT_LEN}) for a, k, n in configs]
        info = build(board, jobs, f"{out}/sizes", work)
        with open(f"{out}/sizes.json", "w") as fh:
            json.dump({"board": bname, "flash_bytes": board.flen, "place": SIZES_PLACE, "far_bytes": FAR,
                       "fixed_bytes": info["fixed_bytes"], "bytes": {j["adapter"]: j["bytes"] for j in jobs}}, fh, indent=1)
            fh.write("\n")
        shutil.rmtree(f"{out}/sizes")
        big = max(jobs, key=lambda j: j["bytes"])
        print(f"{bname}: {len(jobs)} configurations, fixed part {info['fixed_bytes']} bytes, images "
              f"{min(j['bytes'] for j in jobs)} to {big['bytes']} bytes ({big['adapter']}), {out}/sizes.json")
        return

    if mode == "layout":
        jobs = []
        for n, ln in enumerate(open(layout), 1):
            f = ln.split("#")[0].split()
            if f:
                if len(f) != 4:
                    sys.exit(f"{layout}:{n}: four fields expected")
                if f[0] not in kinds:
                    sys.exit(f"{layout}:{n}: {f[0]} is not in configs.txt")
                jobs.append(ram_fields({"adapter": f[0], "kind": kinds[f[0]], "name": names[f[0]], "place": int(f[1]),
                                        "base": int(f[2], 0), "slot_bytes": int(f[3], 0)}))
        groups = {"bundle": jobs}
    else:
        numbered = {}
        for a, place, seg, off, length in read_slots():
            if a not in {c[0] for c in every}:
                sys.exit(f"slots.txt: {a} is not in configs.txt")
            if a not in kinds:
                continue                       # a configuration of other boards (boards.txt)
            if off % UNIT or length % UNIT or off < BOOT_LEN or off + length > SEG:
                sys.exit(f"slots.txt: {a} p{place}: not a slot on {UNIT}-byte boundaries behind the first "
                         f"{BOOT_LEN} bytes of a segment")
            b = seg // board.per_bundle
            if only is None or b in only:
                numbered.setdefault(b, []).append(ram_fields(
                    {"adapter": a, "kind": kinds[a], "name": names[a], "place": place, "segment": seg, "offset": off,
                     "base": board.fbase + (seg % board.per_bundle) * SEG + off, "slot_bytes": length}))
        if not numbered:
            sys.exit("no images in the slots asked for (poolslots.py assign first)")
        if only and set(only) - set(numbered):
            sys.exit(f"no images in bundle {sorted(set(only) - set(numbered))}")
        groups = {f"bundle{b}": numbered[b] for b in sorted(numbered)}

    alljobs = [j for g in groups.values() for j in g]
    if len({(j["adapter"], j["place"]) for j in alljobs}) != len(alljobs):
        sys.exit("an image (adapter and placement) is listed twice")
    for g in groups.values():
        end = board.fbase + BOOT_LEN
        for j in sorted(g, key=lambda j: j["base"]):
            if j["base"] % UNIT or j["slot_bytes"] % UNIT or j["base"] < end or j["base"] + j["slot_bytes"] > board.fbase + board.flen:
                sys.exit(f"{j['adapter']} p{j['place']} at {j['base']:#x}: not a free slot on a {UNIT}-byte boundary in flash")
            end = j["base"] + j["slot_bytes"]
    for f in os.listdir(out):
        if re.fullmatch(r"bundle\d*\.(elf|json)", f) and (only is None or f.split(".")[0] in groups):
            os.remove(f"{out}/{f}")
    if only is None and os.path.isdir(f"{out}/img"):
        keep = {f"{j['adapter']}-p{j['place']}" for j in alljobs}
        for d in os.listdir(f"{out}/img"):
            if d not in keep:
                shutil.rmtree(f"{out}/img/{d}")

    info = build(board, alljobs, out, work)
    for name, jobs in groups.items():
        extra = {"kind": "pools", "far_bytes": FAR, "layout": LAYOUT, "result_bytes": 4 * RESULT_WORDS,
                 "results_addr": f"{board.rbase:#010x}"}
        if mode != "layout":
            extra.update(bundle=int(name[6:]), segment_bytes=SEG, segments_per_bundle=board.per_bundle)
        ob.bundle(board, jobs, info, out, name, extra)


if __name__ == "__main__":
    main()
