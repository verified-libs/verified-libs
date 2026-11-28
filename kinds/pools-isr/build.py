#!/usr/bin/env python3
"""Build the board images of the pools concurrency series (main.c) and their
bundle, for one or more boards, inside the toolchain image (onebuild.sh runs
it). No board is touched and nothing is written to a board.

One image per configuration (main.c with POOL_ISR_ADAPTER), each in a slot
of SLOT bytes, all of a board in one bundle (BUNDLES) behind the first
series' boot stub, which starts the image the host selects: the bundle,
its ELF and its manifest are made by the first series' own code
(firmware/nrf5340-rb-bench/onebundle.py bundle(), through
kinds/pools/bench/onepool.py), so the runner (run-isr.py) selects and reads
an image as run-pools.py does. The objects are the first series'
(onepool.objects(): its compiler flags, every adapter and library of the
kind, the Rust library for the board's core); this directory adds main.c and
the two broken interrupts-off builds of the reference (broken_isr.c).
Imported, not changed.

Two bundles (BUNDLES): 300, the series of 2026-11-27, and 301, C_Allocator
with its interrupt-masking lock and the controls again
(lab/plans/2026-11-28-pools-isr-cal-lock.md). Bundle 300 is built as it was
at its series commit, byte for byte: its records hold the bundle's checksum.

Usage: python3 -I build.py [--bundle N] BOARD...   (N: 300, the default, or 301;
       boards nrf5340 stm32g0b1 stm32g474 stm32h723 samd20 rp2350)
Output: build/v1/<board>/ (bundle 300) or build/b<N>/<board>/ (OUT):
img/<adapter>/fw.elf, .bin, fw.map, nm.txt; bundle<N>.elf and .json (the
first series' manifest, kind "pools-isr"). Exit 1 on any error.
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pools", "bench"))
import onepool as op   # noqa: E402

# main.c's adapters, in the order of the bundle (decode.py CLASS): the controls, ours, the libraries
CONFIGS = [("adapter_ref", "c"), ("adapter_broken_isr_alloc", "c"), ("adapter_broken_isr_free", "c"),
           ("adapter_ref_primask", "c"), ("adapter_etl", "cpp"), ("adapter_riot", "c"), ("adapter_threadx", "c"),
           ("adapter_cmsis_rtx", "c"), ("adapter_contiki", "c"), ("adapter_c_allocator", "c"), ("adapter_lwip", "c"),
           ("adapter_memorypool", "cpp"), ("adapter_atomic_pool", "rust"), ("adapter_heapless", "rust")]
# Bundle 301: C_Allocator with its lock option, with the three controls and our interrupts-off row before it, so that
# the run proves itself as bundle 300's did (isrrecords.py: no record of a board whose controls are not all caught).
CONFIGS_301 = [("adapter_ref", "c"), ("adapter_broken_isr_alloc", "c"), ("adapter_broken_isr_free", "c"),
               ("adapter_ref_primask", "c"), ("adapter_c_allocator_lock", "c")]
SLOT = 16 * 1024
# numbers of their own: the first series' bundles are 12 to 204
BUNDLES = {300: CONFIGS, 301: CONFIGS_301}
OUT = {300: "v1", 301: "b301"}
# A configuration built from another one's adapter, with its library's object built again with other defines:
# id -> (the adapter's symbol, the library source under LIBS, the defines, the object it takes the place of).
# C_Allocator's lock (LockGuard.cpp:104-113 at 497b465): CMSIS-Core's __get_PRIMASK, __disable_irq and __set_PRIMASK,
# from the pinned CMSIS 6 already on the include path; ALLOC_LOCK_NONE of the kind's flags is undefined first, as the
# library allows one option only (LockGuard.cpp:29-33). __PROGRAM_START=_start: CMSIS 6's default start function
# (m-profile/cmsis_gcc_m.h:37-81, defined unless __PROGRAM_START is) declares local types in extern declarations, which
# this g++ refuses in C++ ("declared using local type ..., is used but never defined"); with __PROGRAM_START set, as
# CMSIS sets it itself for picolibc (cmsis_gcc_m.h:32-33), that function is not defined. The image's start-up is the
# boards' own (startup.o) either way: nothing of that function would be linked.
VARIANTS = {"adapter_c_allocator_lock": ("adapter_c_allocator", "c-allocator/src/LockGuard.cpp",
                                         ["-UALLOC_LOCK_NONE", "-DALLOC_LOCK_CMSIS_RTOS2", "-D__PROGRAM_START=_start"],
                                         "lib_LockGuard.o")}
RESULT_WORDS = None   # from decode.py, below


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(" ".join(cmd)[:300] + "\n" + r.stdout[-2000:] + r.stderr[-3000:])
    return r.stdout


def configs_of(board, bundle=300):
    return [(a, k) for a, k in BUNDLES[bundle] if not (a == "adapter_heapless" and board.cpu == "cortex-m0plus")]


def build(bname, bundle=300):
    sys.path.insert(0, HERE)
    import decode
    board = op.Board(bname)
    work = os.path.join(HERE, "build", "work", bname)
    out = os.path.join(HERE, "build", OUT[bundle], bname)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    objs = op.objects(board, work)
    cflags, _ = op.flags(board)
    cflags = [f"-I{HERE}"] + cflags
    broken = {}
    for n, v in (("adapter_broken_isr_alloc", 1), ("adapter_broken_isr_free", 2)):
        broken[n] = f"{work}/{n}.o"
        sh(["arm-none-eabi-gcc"] + cflags + [f"-DBROKEN_ISR={v}", "-c", f"{HERE}/broken_isr.c", "-o", broken[n]])
    variant = {}
    for a, kind in configs_of(board, bundle):
        if a in VARIANTS:
            _sym, src, defs, _instead = VARIANTS[a]
            _, cxxflags = op.flags(board)
            variant[a] = f"{work}/{a}_{os.path.basename(src).rsplit('.', 1)[0]}.o"
            sh(["arm-none-eabi-g++"] + cxxflags + ["-w"] + defs + ["-c", f"{op.LIBS}/{src}", "-o", variant[a]])
    jobs, sel = [], set()
    base = board.fbase + op.BOOT_LEN
    for a, kind in configs_of(board, bundle):
        sym = VARIANTS[a][0] if a in VARIANTS else a
        if base + SLOT > board.fbase + board.flen:
            sys.exit(f"{bname}: the images do not fit in flash")
        d = f"{out}/img/{a}"
        os.makedirs(d)
        ld = open(board.ld).read()
        ld, n = re.subn(r"^(\s*FLASH\s+\(rx\)\s*:\s*)ORIGIN = [^,]+, LENGTH = \S+",
                        lambda m: f"{m.group(1)}ORIGIN = {base:#x}, LENGTH = {SLOT}", ld, flags=re.M)
        if n != 1:
            sys.exit(f"{board.ld}: no FLASH region")
        with open(f"{d}/slot.ld", "w") as fh:
            fh.write(ld)
        sh(["arm-none-eabi-gcc"] + cflags + [f"-DPOOL_ISR_ADAPTER={sym}", "-DADAPTER_CONST=" + ("" if kind == "rust" else "const"),
            "-c", f"{HERE}/main.c", "-o", f"{d}/main.o"])
        elf = f"{d}/fw.elf"
        sh(["arm-none-eabi-g++"] + board.arch.split() + [op.OPT, "-nostartfiles", "--specs=nano.specs", "--specs=nosys.specs",
            "-Wl,--gc-sections", "-Wl,-n", "-T", f"{d}/slot.ld", f"-Wl,-Map={d}/fw.map", f"{d}/main.o", f"{work}/startup.o",
            f"{work}/ref_pool.o"] + ([broken[a]] if a in broken else []) + ([variant[a]] if a in variant else []) +
           ["-Wl,--start-group", objs["lib"], "-Wl,--end-group", "-Wl,-lc_nano"] + ([objs["rust"]] if kind == "rust" else []) +
           ["-o", elf])
        img = op.ob.image(elf, base)
        if len(img) > SLOT:
            sys.exit(f"{elf}: {len(img)} bytes, its slot has {SLOT}")
        syms = {name: (addr, size) for addr, size, _t, name in op.ob.symbols(elf)}
        if a in variant:   # the library's object of the variant, and not the archive's, is the one linked
            fmap = open(f"{d}/fw.map").read()
            if os.path.basename(variant[a]) not in fmap or f"({VARIANTS[a][3]})" in fmap:
                sys.exit(f"{elf}: not linked with {os.path.basename(variant[a])} in place of {VARIANTS[a][3]}")
        need = [sym, "results", "isr_sweep", "adapter_ref"]
        if [s for s in need if s not in syms]:
            sys.exit(f"{elf}: symbols missing: {[s for s in need if s not in syms]}")
        if syms["results"][1] != 4 * decode.words_needed():
            sys.exit(f"{elf}: results is {syms['results'][1]} bytes, decode.py reads {4 * decode.words_needed()}")
        if syms["results"][0] != board.rbase:
            sys.exit(f"{elf}: results at {syms['results'][0]:#x}, not at the start of RAM {board.rbase:#x}")
        sel.add(board.sel_fixed if board.sel_fixed is not None else syms.get("vl_select", (None,))[0])
        sh(["sh", "-c", f"arm-none-eabi-nm -S --size-sort -C {elf} > {d}/nm.txt"])
        jobs.append({"adapter": a, "kind": kind, "name": a, "place": 0, "base": base, "slot_bytes": SLOT, "elf": elf,
                     "bytes": len(img), "sha256": op.ob.sha256(open(elf, "rb").read()), "image_sha256": op.ob.sha256(img),
                     "class": decode.CLASS[a]})
        base += SLOT
    if len(sel) != 1 or None in sel:
        sys.exit(f"{bname}: the selection words are not at one place in every image ({sel})")
    info = {"select_addr": sel.pop(), "fixed_bytes": 0, "fixed_sha256": op.ob.sha256(b"")}
    extra = {"kind": "pools-isr", "bundle": bundle, "result_bytes": 4 * decode.words_needed(),
             "results_addr": f"{board.rbase:#010x}", "slot_bytes": SLOT}
    op.ob.bundle(board, jobs, info, out, f"bundle{bundle}", extra)
    print(f"{bname}: {len(jobs)} images, {min(j['bytes'] for j in jobs)} to {max(j['bytes'] for j in jobs)} bytes", flush=True)


def main():
    args, bundle = sys.argv[1:], 300
    if args[:1] == ["--bundle"] and len(args) >= 2:
        bundle, args = int(args[1]), args[2:]
    if bundle not in BUNDLES or any(a.startswith("-") for a in args):
        sys.exit(__doc__)
    for b in args or ["nrf5340", "stm32g0b1", "stm32g474", "stm32h723", "samd20", "rp2350"]:
        build(b, bundle)


if __name__ == "__main__":
    main()
