#!/usr/bin/env python3
"""Build the board images of the pools concurrency series (main.c) and their
bundle, for one or more boards, inside the toolchain image (onebuild.sh runs
it). No board is touched and nothing is written to a board.

One image per configuration (main.c with POOL_ISR_ADAPTER), each in a slot
of SLOT bytes, all of a board in one bundle (BUNDLE) behind the first
series' boot stub, which starts the image the host selects: the bundle,
its ELF and its manifest are made by the first series' own code
(firmware/nrf5340-rb-bench/onebundle.py bundle(), through
kinds/pools/bench/onepool.py), so the runner (run-isr.py) selects and reads
an image as run-pools.py does. The objects are the first series'
(onepool.objects(): its compiler flags, every adapter and library of the
kind, the Rust library for the board's core); this directory adds main.c and
the two broken interrupts-off builds of the reference (broken_isr.c).
Imported, not changed.

Usage: python3 -I build.py BOARD...      (nrf5340 stm32g0b1 stm32g474 stm32h723 samd20 rp2350)
Output: build/v1/<board>/: img/<adapter>/fw.elf, .bin, fw.map, nm.txt;
bundle<BUNDLE>.elf and .json (the first series' manifest, kind
"pools-isr"). Exit 1 on any error.
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
SLOT = 16 * 1024
BUNDLE = 300          # a number of its own: the first series' bundles are 12 to 204
RESULT_WORDS = None   # from decode.py, below


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(" ".join(cmd)[:300] + "\n" + r.stdout[-2000:] + r.stderr[-3000:])
    return r.stdout


def configs_of(board):
    return [(a, k) for a, k in CONFIGS if not (a == "adapter_heapless" and board.cpu == "cortex-m0plus")]


def build(bname):
    sys.path.insert(0, HERE)
    import decode
    board = op.Board(bname)
    work = os.path.join(HERE, "build", "work", bname)
    out = os.path.join(HERE, "build", "v1", bname)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    objs = op.objects(board, work)
    cflags, _ = op.flags(board)
    cflags = [f"-I{HERE}"] + cflags
    broken = {}
    for n, v in (("adapter_broken_isr_alloc", 1), ("adapter_broken_isr_free", 2)):
        broken[n] = f"{work}/{n}.o"
        sh(["arm-none-eabi-gcc"] + cflags + [f"-DBROKEN_ISR={v}", "-c", f"{HERE}/broken_isr.c", "-o", broken[n]])
    jobs, sel = [], set()
    base = board.fbase + op.BOOT_LEN
    for a, kind in configs_of(board):
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
        sh(["arm-none-eabi-gcc"] + cflags + [f"-DPOOL_ISR_ADAPTER={a}", "-DADAPTER_CONST=" + ("" if kind == "rust" else "const"),
            "-c", f"{HERE}/main.c", "-o", f"{d}/main.o"])
        elf = f"{d}/fw.elf"
        sh(["arm-none-eabi-g++"] + board.arch.split() + [op.OPT, "-nostartfiles", "--specs=nano.specs", "--specs=nosys.specs",
            "-Wl,--gc-sections", "-Wl,-n", "-T", f"{d}/slot.ld", f"-Wl,-Map={d}/fw.map", f"{d}/main.o", f"{work}/startup.o",
            f"{work}/ref_pool.o"] + ([broken[a]] if a in broken else []) +
           ["-Wl,--start-group", objs["lib"], "-Wl,--end-group", "-Wl,-lc_nano"] + ([objs["rust"]] if kind == "rust" else []) +
           ["-o", elf])
        img = op.ob.image(elf, base)
        if len(img) > SLOT:
            sys.exit(f"{elf}: {len(img)} bytes, its slot has {SLOT}")
        syms = {name: (addr, size) for addr, size, _t, name in op.ob.symbols(elf)}
        need = [a, "results", "isr_sweep", "adapter_ref"]
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
    extra = {"kind": "pools-isr", "bundle": BUNDLE, "result_bytes": 4 * decode.words_needed(),
             "results_addr": f"{board.rbase:#010x}", "slot_bytes": SLOT}
    op.ob.bundle(board, jobs, info, out, f"bundle{BUNDLE}", extra)
    print(f"{bname}: {len(jobs)} images, {min(j['bytes'] for j in jobs)} to {max(j['bytes'] for j in jobs)} bytes", flush=True)


def main():
    for b in sys.argv[1:] or ["nrf5340", "stm32g0b1", "stm32g474", "stm32h723", "samd20", "rp2350"]:
        build(b)


if __name__ == "__main__":
    main()
