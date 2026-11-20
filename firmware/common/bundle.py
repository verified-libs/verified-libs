#!/usr/bin/env python3
"""Build one firmware image per library and put them side by side in flash
("bundle"), with the boot stub slotboot.c in front that starts the image the
host selected. Generic: any test firmware whose Makefile builds one library's
image with ONLY=<n>, linked for SLOT_BASE/SLOT_LEN, into build/lib<n>/fw.elf,
and prints its variables with "make print-<VAR>" (nrf5340-rb-stress does).
Runs inside the toolchain image, in the firmware's directory.

Why one bundle instead of flashing each library's image before it runs: the
boards' flash wears out (10k erase cycles on most, fewer on some), and a
campaign runs every library many times. A bundle is flashed once and then
stays on the board as long as no image changes (the host flashes with
--preverify); during development only the slots whose image changed are
written (bundle.json lists every slot's image and checksum).

Usage:
  python3 -I bundle.py --libs 0-39 --sel-symbol results --sel-from-end 16 \\
      [--sel-addr 0x400D800C] [--align 4096] [--boot-len 4096] -- MAKEARGS...

  --libs          the image indices, e.g. 0-39 or 0,5,11
  --sel-addr      address of the selection words (magic, index, ~index), or
  --sel-symbol/--sel-from-end: that many bytes before the end of a symbol
                  of the images (the same in every image: checked)
  --align         slot alignment (default 4096: a flash page on every board
                  but the H723, whose 128 KB sectors are written with
                  --restore-unwritten)
  --boot-len      flash kept for the stub at the start (default 4096; the
                  RP2350 needs its boot block inside the first 4 KB)
  --index-base    the selection index of image n is base + n (default 0):
                  the index the stub's table, bundle.json and "run <n>" use
  --with DIR LIBS BASE MAKEARGS   (repeatable) the images of another
                  firmware in the same bundle, after this one's: its
                  directory (relative), its image indices, its index base
                  (its firmware's VLS_SEL_BASE: rb-mp-stress 64) and its make
                  arguments (one string). Its images keep their place in
                  flash only as long as everything before them does.

Layout: the images in index order, each at the next multiple of --align
after the one before; when flash is full a new bundle starts (the SAM D20's
256 KB hold about half of the 40 libraries: two bundles, flashed in turn).
A library's base address therefore moves only when an image before it grows
or shrinks across an alignment boundary; its image is otherwise unchanged by
other libraries (bundle.json records base and sha256 per image).

Output in build/:
  lib<n>/fw.elf, fw.map, fw.lst   the image of library n (at its slot)
  boot<k>.elf                     the stub of bundle k
  bundle<k>.elf                   bundle k: stub and images, one ELF
  bundle.json                     layout and checksums
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.stderr.write(r.stdout[-4000:] + r.stderr[-4000:])
        sys.exit(f"failed: {' '.join(cmd)}")
    return r.stdout


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def parse_libs(s):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += range(int(a), int(b) + 1)
        elif part:
            out.append(int(part))
    return sorted(set(out))


def region(ld, name):
    m = re.search(rf"^\s*{name}\s+\(\w+\)\s*:\s*ORIGIN\s*=\s*(0x[0-9a-fA-F]+),\s*LENGTH\s*=\s*(\d+)([KM]?)",
                  open(ld).read(), re.M)
    if not m:
        sys.exit(f"{ld}: no {name} region")
    return int(m.group(1), 16), int(m.group(2)) * {"": 1, "K": 1024, "M": 1 << 20}[m.group(3)]


def image(elf, base):
    """Flash bytes of an image: its loadable content from base, as binary."""
    b = elf[:-4] + ".bin"
    sh(["arm-none-eabi-objcopy", "-O", "binary", "--gap-fill", "0xff", elf, b])
    # the binary starts at the lowest load address: it must be the slot base
    lo = None
    for ln in sh(["arm-none-eabi-readelf", "-lW", elf]).splitlines():
        f = ln.split()
        if f and f[0] == "LOAD" and int(f[4], 16):   # FileSiz
            pa = int(f[3], 16)
            lo = pa if lo is None else min(lo, pa)
    if lo != base:
        sys.exit(f"{elf}: loads at {lo:#x}, not at its slot {base:#x}")
    return open(b, "rb").read()


def symbol(elf, name):
    for ln in sh(["arm-none-eabi-nm", "-S", elf]).splitlines():
        f = ln.split()
        if len(f) == 4 and f[3] == name:
            return int(f[0], 16), int(f[1], 16)
    sys.exit(f"{elf}: no symbol {name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--libs", required=True)
    ap.add_argument("--sel-addr")
    ap.add_argument("--sel-symbol")
    ap.add_argument("--sel-from-end", type=int, default=0)
    ap.add_argument("--align", type=lambda x: int(x, 0), default=4096)
    ap.add_argument("--boot-len", type=lambda x: int(x, 0), default=4096)
    ap.add_argument("--index-base", type=int, default=0)
    ap.add_argument("--with", dest="also", nargs=4, action="append", default=[],
                    metavar=("DIR", "LIBS", "BASE", "MAKEARGS"))
    ap.add_argument("make", nargs="*")
    a = ap.parse_args()
    make = ["make", "-s"] + a.make
    # parts: (directory relative to here, make command, [(index, local n)])
    parts = [(".", make, [(a.index_base + n, n) for n in parse_libs(a.libs)])]
    for d, ls, base, margs in a.also:
        parts.append((d, ["make", "-s"] + shlex.split(margs), [(int(base) + n, n) for n in parse_libs(ls)]))
    where = {}
    for d, mk, ids in parts:
        for g, n in ids:
            if g in where:
                sys.exit(f"selection index {g} twice")
            where[g] = (d, mk, n)
    libs = [g for _, _, ids in parts for g, _ in ids]   # bundle order: part by part

    def var(name):
        return sh(make + [f"print-{name}"]).strip()
    ld, arch, board = var("LDSCRIPT"), var("ARCH"), var("BOARD")
    fbase, flen = region(ld, "FLASH")
    rbase, rlen = region(ld, "RAM")
    first = fbase + a.boot_len
    end = fbase + flen

    def build(l, base):
        pd, mk, n = where[l]
        d = os.path.normpath(f"{pd}/build/lib{n}")
        for f in ("slot.ld", "fw.elf"):
            if os.path.exists(f"{d}/{f}"):
                os.remove(f"{d}/{f}")
        sh(mk + [f"ONLY={n}", f"SLOT_BASE={base:#x}", f"SLOT_LEN={end - base}"], cwd=pd)
        return f"{d}/fw.elf"

    # 1. sizes (every image linked at the first slot), 2. layout, 3. link at the slot
    size = {l: len(image(build(l, first), first)) for l in libs}
    up = lambda x: (x + a.align - 1) // a.align * a.align
    bundles, cur, at = [], [], first
    for l in libs:
        if at + size[l] > end:
            if not cur:
                sys.exit(f"library {l}: {size[l]} bytes do not fit in flash")
            bundles.append(cur); cur, at = [], first
        cur.append((l, at)); at = up(at + size[l])
    bundles.append(cur)
    info, sel = {}, None
    for k, b in enumerate(bundles):
        for l, base in b:
            elf = build(l, base)
            img = image(elf, base)
            if len(img) != size[l]:
                sys.exit(f"library {l}: {len(img)} bytes at its slot, {size[l]} at the first")
            if a.sel_symbol:
                s, n = symbol(elf, a.sel_symbol)
                addr = s + n - a.sel_from_end
                if sel is not None and addr != sel:
                    sys.exit(f"library {l}: selection at {addr:#x}, other images {sel:#x}")
                sel = addr
            info[l] = {"bundle": k, "base": f"{base:#010x}", "bytes": len(img), "elf": elf,
                       "sha256": sha256(elf), "image_sha256": hashlib.sha256(img).hexdigest()}
            if where[l][0] != ".":       # an image of another firmware (--with)
                info[l].update({"dir": where[l][0], "only": where[l][2]})
    if a.sel_addr:
        sel = int(a.sel_addr, 0)
    if sel is None:
        sys.exit("--sel-addr or --sel-symbol needed")

    out = []
    for k, b in enumerate(bundles):
        stub_ld = f"build/boot{k}.ld"
        with open(stub_ld, "w") as fh:
            fh.write(f"MEMORY {{ FLASH (rx) : ORIGIN = {fbase:#x}, LENGTH = {a.boot_len}\n"
                     f"         RAM (rwx) : ORIGIN = {rbase:#x}, LENGTH = {rlen} }}\n"
                     "_estack = ORIGIN(RAM) + LENGTH(RAM);\nENTRY(Reset_Handler)\n"
                     "SECTIONS { .isr_vector : { KEEP(*(.isr_vector)) KEEP(*(.embedded_block)) } > FLASH\n"
                     "  .text : { *(.text*) *(.rodata*) } > FLASH\n"
                     "  .data : { *(.data*) *(.bss*) *(COMMON) } > RAM\n"
                     "  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) } }\n")
        table = ",".join(f"{{{l}u,{base:#x}u}}" for l, base in b)
        boot = f"build/boot{k}.elf"
        sh(["arm-none-eabi-gcc"] + arch.split() + ["-O2", "-g", "-Wall", "-Wextra", "-ffreestanding", "-nostdlib",
            "-ffunction-sections", "-Wl,--gc-sections", f"-DSLOTBOOT_SEL_ADDR={sel:#x}u",
            f"-DSLOTBOOT_TABLE={table}"] + (["-DSLOTBOOT_RP2350"] if board == "rp2350" else []) +
           ["-T", stub_ld, os.path.join(HERE, "slotboot.c"), "-o", boot])
        for ln in sh(["arm-none-eabi-size", "-A", boot]).splitlines():
            f = ln.split()
            if f and f[0] == ".data" and int(f[1]):
                sys.exit(f"{boot}: the stub must not use RAM (.data {f[1]} bytes)")
        stub = image(boot, fbase)
        if len(stub) > a.boot_len:
            sys.exit(f"{boot}: {len(stub)} bytes, more than --boot-len")
        top = max(int(info[l]["base"], 16) + info[l]["bytes"] for l, _ in b)
        blob = bytearray(b"\xff" * (top - fbase))
        blob[0:len(stub)] = stub
        for l, base in b:
            img = open(info[l]["elf"][:-4] + ".bin", "rb").read()
            blob[base - fbase:base - fbase + len(img)] = img
        bin_ = f"build/bundle{k}.bin"
        open(bin_, "wb").write(blob)
        elf = f"build/bundle{k}.elf"
        # an executable ELF with one loadable segment (probe-rs and OpenOCD
        # flash program segments; objcopy -I binary makes none)
        bld = f"build/bundle{k}.ld"
        with open(bld, "w") as fh:
            fh.write(f"SECTIONS {{ .text {fbase:#x} : {{ *(.data) }} }}\n")
        obj = f"build/bundle{k}.o"
        sh(["arm-none-eabi-objcopy", "-I", "binary", "-O", "elf32-littlearm", "-B", "arm", bin_, obj])
        sh(["arm-none-eabi-ld", "-n", "-T", bld, obj, "-o", elf])
        out.append({"bundle": k, "elf": elf, "sha256": sha256(elf), "boot_elf": boot, "boot_sha256": sha256(boot),
                    "flash_bytes": len(blob), "libs": [l for l, _ in b]})
    manifest = {"board": board, "flash": [f"{fbase:#010x}", flen], "boot_len": a.boot_len, "align": a.align,
                "select_addr": f"{sel:#010x}", "bundles": out, "libs": {str(l): info[l] for l in libs}}
    json.dump(manifest, open("build/bundle.json", "w"), indent=1)
    for o in out:
        print(f"bundle {o['bundle']}: {len(o['libs'])} images, {o['flash_bytes']} bytes, {o['elf']}")


if __name__ == "__main__":
    main()
