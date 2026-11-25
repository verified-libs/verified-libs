#!/usr/bin/env python3
"""Build the CRC kind's benchmark images, one per configuration and
placement, each linked for its own slot in flash, and the bundles written
to a board, by the method of version 2 (firmware/nrf5340-rb-bench/
onebundle.py; lab/plans/2026-11-22-bench-image-per-library.md). The boot
stub, the bundle's ELF and its manifest are made by onebundle.py's own
functions, unchanged; the board support (firmware/common/<board>: board.h
with time_call, startup.c, the flash linker script) is used unchanged.
Runs inside the toolchain image with the repository at /work and the
libraries at LIBS (onebuild.sh does that). No board is touched.

Usage: python3 -I onecrc.py sizes  BOARD [--out DIR]
       python3 -I onecrc.py table  BOARD [--bundle N[,N...]] [--out DIR]
       python3 -I onecrc.py layout BOARD FILE [--out DIR]

sizes   every configuration of ../configs.txt once, at the largest placement:
        DIR/sizes.json, which crcslots.py assign reads.
table   the images of ../slots.txt and the bundles that hold them (a bundle
        holds as many 256 KB segments as the board's flash has room for).
layout  the images of a layout file, for experiments, one per line:
            <adapter> <placement bytes> <slot address> <slot bytes>

Output in DIR (default ../build/v2/<board>): img/<adapter>-p<placement>/
fw.elf, fw.bin, nm.txt; boot.elf; bundle<N>.elf and bundle<N>.json (the
manifest of onebundle.py, with result_bytes added); fixed.txt.

An image: the fixed part, the same code at the same offsets in every image
of the board (vector table, harness and time_call, the C library's memory
functions with memcpy on a 32-byte boundary, main, the reference: the
baseline, all three of its CRCs in every image, start-up code); then the
placement bytes (.bench_place); then the configuration's adapter code (every
adapter_*.o; a library of headers is compiled into its adapter and stays
there, as in version 2); then FAR bytes (.bench_shift); then everything
else: the library's code and all constant data, its table too. So the
placement moves the adapter and the library alike, and with them the loop of
a library of headers, which lies in the adapter; the distance between the
adapter and the library is FAR in every image, but for code that its compiler
aligns to more than 4 bytes: that lies on its own boundary, up to 4 bytes
off, and so in fewer positions (check() prints which). (In version 2's ring-buffer
images the placement bytes lie behind the adapter, with FAR, and the adapter
does not move.)

Checked for every image: it fits its slot; the fixed part is the same as in
every other image of the board and holds memcpy (on a 32-byte boundary),
memmove, memset, memcmp, time_call, main and the reference; the selection
words are where the stub reads them; the adapter's code starts exactly the
placement behind the fixed part; the adapter's functions (the descriptor's
init and crc) lie before the gap and other code at least FAR bytes behind
it; everything behind the fixed part (code and constant data) lies at the
same offsets from the adapter's start as in the configuration's other
images, exactly in the adapter's code and within less than 8 bytes behind
the gap, so the placement moves all of it; the result
block lies at the start of RAM and has the size the host reads (run-crc.py).
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
RESULT_WORDS = 9 + 6 + 2 + 2 * (2 * 6 * 2 * 5 + 1) + 4 + 2   # struct results in main.c
FIXED_NAMES = ("memcpy", "memmove", "memset", "memcmp", "time_call", "main", "ref_crc", "ref32_crc", "ref16_crc", "ref8_crc")
MEMSYMS = ("memcpy memmove memset memcmp __aeabi_memcpy __aeabi_memcpy4 __aeabi_memcpy8 __aeabi_memmove "
           "__aeabi_memmove4 __aeabi_memmove8 __aeabi_memset __aeabi_memset4 __aeabi_memset8 __aeabi_memclr "
           "__aeabi_memclr4 __aeabi_memclr8").split()   # firmware/common/rust.mk RUST_MEMSYMS
RUST_TARGET = {"cortex-m0plus": "thumbv6m-none-eabi", "cortex-m4": "thumbv7em-none-eabi",
               "cortex-m7": "thumbv7em-none-eabi", "cortex-m33": "thumbv8m.main-none-eabi"}

OWN_C = ["adapter_zlib.c", "adapter_libcrc.c", "adapter_zephyr.c", "adapter_crcany.c", "adapter_rust.c"]
OWN_CXX = ["adapter_etl.cpp", "adapter_acecrc.cpp", "adapter_crcpp.cpp"]
LIB_C = [f"{LIBS}/zlib/crc32.c", f"{LIBS}/libcrc/src/crc32.c", f"{LIBS}/libcrc/src/crcccitt.c",
         f"{LIBS}/zephyr/subsys/crc/crc32_sw.c", f"{LIBS}/zephyr/subsys/crc/crc16_sw.c",
         f"{LIBS}/zephyr/subsys/crc/crc8_sw.c",
         f"{GEN}/crc32iso_hdlc.c", f"{GEN}/crc16ibm_3740.c", f"{GEN}/crc8smbus.c"]
LIB_CXX = [f"{LIBS}/acecrc/src/ace_crc/crc8_byte.cpp"]

FIXED = (". = ALIGN(32); *libc_a-memcpy.o(.text*) *libc_a-memcpy-stub.o(.text*) *libc_a-memmove.o(.text*) "
         "*libc_a-memset.o(.text*) *libc_a-memcmp.o(.text*) *libc_a-aeabi_mem*.o(.text*) "
         "*main.o(.text*) *main.o(.rodata .rodata.[!s]*) *ref_crc.o(.text*) *ref_crc.o(.rodata .rodata.[!s]*) "
         "*startup.o(.text*) *startup.o(.rodata .rodata.[!s]*) _bench_fixed_end = .;")
# Not the strings (.rodata.str*): the linker merges equal strings of all objects into the first such
# section it places, so another configuration's names would land in the fixed part. They are only names.
NEAR = "KEEP(*(.bench_place)) _bench_near_start = .; *adapter_*.o(.text*) _bench_near_end = .;"


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


def ref_of(adapter):
    """The reference of the configuration's CRC (as bench/build.sh)."""
    a = adapter[len("adapter_"):]
    if "crc32" in a or a.startswith("zlib_"):
        return "adapter_ref32"
    if "crc16" in a or "ccitt_ffff" in a or a.startswith("crcpp_"):
        return "adapter_ref16"
    return "adapter_ref8"


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
    inc = [f"-I{HERE}", f"-I{board.common}", f"-I{FW}/common", f"-I{KIND}", f"-I{GEN}", f"-I{LIBS}/etl/include",
           f"-I{LIBS}/zlib", f"-I{LIBS}/libcrc/include", f"-I{KIND}/shims/zephyr", f"-I{LIBS}/zephyr/include",
           f"-I{KIND}/shims/acecrc", f"-I{LIBS}/acecrc/src", f"-I{LIBS}/crcpp/inc"]
    # the flags of the version 2 benchmark (firmware/nrf5340-rb-bench/Makefile COMMONF)
    common = board.arch.split() + [OPT, "-g", "-Wall", "-Wextra", "-Wno-missing-field-initializers",
                                   "-Wno-unused-function", "-DNDEBUG", "-ffunction-sections", "-fdata-sections",
                                   "-DCRC_ONESHOT_ONLY"] + inc
    cflags = common + ["-ffreestanding", "-std=c11"]
    # C++ without -ffreestanding, as the bench builds its C++ adapters
    cxxflags = common + ["-std=c++20", "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics"]
    return cflags, cxxflags


def objects(board, work):
    """Everything an image links but main.o, once per board: startup.o,
    ref_crc.o, the archive of adapters and libraries, the Rust library."""
    cflags, cxxflags = flags(board)
    o = f"{work}/o"
    os.makedirs(o, exist_ok=True)
    jobs = [(["arm-none-eabi-gcc"] + cflags + ["-fno-tree-loop-distribute-patterns", "-c",
              f"{board.common}/startup.c", "-o", f"{work}/startup.o"]),
            (["arm-none-eabi-gcc"] + cflags + ["-c", f"{KIND}/ref_crc.c", "-o", f"{work}/ref_crc.o"])]
    arch = []
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
    env = dict(os.environ, CARGO_PROFILE_RELEASE_OPT_LEVEL="2", RUSTFLAGS=f"-C target-cpu={board.cpu}")
    subprocess.run(["cargo", "build", "-q", "--offline", "--locked", "--release", "--target", rt,
                    "--target-dir", f"{work}/rust"], cwd=f"{KIND}/rust", env=env, check=True)
    return {"lib": lib, "rust": f"{work}/rust/{rt}/release/libvl_crc_rust.a"}


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
    ob.sh(["arm-none-eabi-gcc"] + cflags + [f"-DBENCH_CRC={j['adapter']}", f"-DBENCH_REF={ref_of(j['adapter'])}",
           f"-DBENCH_PLACE={j['place']}", f"-DBENCH_SHIFT={FAR}", "-c", f"{HERE}/main.c", "-o", f"{od}/main.o"])
    us = [f"-Wl,-u,{s}" for s in MEMSYMS + ["adapter_ref32", "adapter_ref16", "adapter_ref8"]]
    ob.sh(["arm-none-eabi-g++"] + board.arch.split() + [OPT, "-nostartfiles", "--specs=nano.specs",
           "--specs=nosys.specs", "-Wl,--gc-sections", "-Wl,-n", "-T", f"{od}/slot.ld", f"-Wl,-Map={od}/fw.map"] + us +
          [f"{od}/main.o", f"{work}/startup.o", f"{work}/ref_crc.o", "-Wl,--start-group", objs["lib"], "-Wl,--end-group",
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
    # the adapter's functions before the gap: the words of its descriptor (crc.h crc_adapter) that point
    # to a function (init and crc; the streaming calls are NULL in these images)
    desc = [(a, s) for a, s, t, n in syms if n == j["adapter"] and s]
    if len(desc) != 1:
        sys.exit(f"{elf}: no descriptor {j['adapter']}")
    w = words_of(elf, desc[0][0], desc[0][1] // 4)
    funcs_at = {a for a, s, t, n in syms if t in "tTwW"}
    if w is None:
        sys.exit(f"{elf}: the descriptor {j['adapter']} is not in a loaded segment")
    fns = [x & ~1 for x in w if x & 1 and (x & ~1) in funcs_at]
    if not fns:
        sys.exit(f"{elf}: the descriptor {j['adapter']} names no function")
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


def build(board, jobs, out, work):
    objs = objects(board, work)
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
        elfs = list(pool.map(lambda j: link_one(board, objs, j, work), jobs))
    state = {}
    for j, src in zip(jobs, elfs):
        d = f"{out}/img/{j['adapter']}-p{j['place']}"
        os.makedirs(d, exist_ok=True)
        elf = f"{d}/fw.elf"
        shutil.copyfile(src, elf)
        img = ob.image(elf, j["base"])
        if len(img) > j["slot_bytes"]:
            sys.exit(f"{elf}: {len(img)} bytes, its slot has {j['slot_bytes']}")
        syms = ob.symbols(elf)
        check(board, j, elf, syms, state)
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
    if not os.path.exists(os.path.join(KIND, "build/gen/ok")):
        sys.exit("the generated crcany code is missing: make build/gen/ok first")
    board = Board(bname)
    out = out or os.path.join(KIND, "build/v2", bname)
    work = os.path.join(KIND, "build/one", bname)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    configs = read_configs()
    kinds = {a: k for a, k, _ in configs}
    names = {a: n for a, _, n in configs}

    if mode == "sizes":
        jobs = [{"adapter": a, "kind": k, "name": n, "place": SIZES_PLACE, "base": board.fbase + BOOT_LEN,
                 "slot_bytes": min(board.flen, SEG) - BOOT_LEN} for a, k, n in configs]
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
                jobs.append({"adapter": f[0], "kind": kinds[f[0]], "name": names[f[0]], "place": int(f[1]),
                             "base": int(f[2], 0), "slot_bytes": int(f[3], 0)})
        groups = {"bundle": jobs}
    else:
        numbered = {}
        for a, place, seg, off, length in read_slots():
            if a not in kinds:
                sys.exit(f"slots.txt: {a} is not in configs.txt")
            if off % UNIT or length % UNIT or off < BOOT_LEN or off + length > SEG:
                sys.exit(f"slots.txt: {a} p{place}: not a slot on {UNIT}-byte boundaries behind the first "
                         f"{BOOT_LEN} bytes of a segment")
            b = seg // board.per_bundle
            if only is None or b in only:
                numbered.setdefault(b, []).append(
                    {"adapter": a, "kind": kinds[a], "name": names[a], "place": place, "segment": seg, "offset": off,
                     "base": board.fbase + (seg % board.per_bundle) * SEG + off, "slot_bytes": length})
        if not numbered:
            sys.exit("no images in the slots asked for (crcslots.py assign first)")
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
        extra = {"kind": "crc", "far_bytes": FAR, "layout": LAYOUT, "result_bytes": 4 * RESULT_WORDS,
                 "results_addr": f"{board.rbase:#010x}"}
        if mode != "layout":
            extra.update(bundle=int(name[6:]), segment_bytes=SEG, segments_per_bundle=board.per_bundle)
        ob.bundle(board, jobs, info, out, name, extra)


if __name__ == "__main__":
    main()
