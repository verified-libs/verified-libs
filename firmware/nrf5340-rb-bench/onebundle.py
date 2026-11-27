#!/usr/bin/env python3
"""Build the benchmark images of version 2, one per configuration and
placement (lab/plans/2026-11-22-bench-image-per-library.md), each linked for
its own slot in flash, and the bundles that are written to a board: the
boot stub ../common/benchboot.c and the images behind it.
Runs inside the toolchain image, in this directory (onebuild.sh does that).

Usage: python3 -I onebundle.py table [--bundle N[,N...]] [--out DIR] -- MAKEARGS...
       python3 -I onebundle.py sizes [--out DIR] -- MAKEARGS...
       python3 -I onebundle.py layout FILE [--out DIR] -- MAKEARGS...

table   the images of configs.txt in the slots of slots.txt. A slot is a
        segment (256 KB of flash), an offset in it and a length; the table
        is the same for every board. A board's bundle holds as many
        segments as its flash has room for (SAM D20: one, RP2350: all), so
        an image's address is
            flash start + (segment modulo segments per bundle) * 256 KB + offset
        and bundle number segment / segments per bundle holds it. --bundle:
        only these bundles (default: all).
sizes   every configuration once, at the largest placement, in a slot that
        is not in the table: how many bytes its image has on this board
        (DIR/sizes.json, read by oneslots.py when it gives out slots).
layout  the images of a layout file, for experiments. One image per line,
        "#" starts a comment:
            <adapter> <placement bytes> <slot address> <slot bytes>
        The placement is the whole distance here (FAR=0, Makefile "one").

Output in DIR (default build/v2/<board>; "make clean" leaves it alone):
  img/<adapter>-p<placement>/fw.elf, fw.bin, nm.txt   the images
  boot.elf            the stub (the same for every bundle of a board)
  bundle<N>.elf       stub and images, one loadable segment per image (so
                      that only the pages that hold an image are written)
  bundle<N>.json      the images, their slots and checksums (of each ELF
                      file and of each image's bytes in flash)
  fixed.txt           the fixed part: the symbols every image of the board
                      has at the same offset from its start (Makefile "one")

Checked for every image: it fits its slot; the fixed part is the same as
in every other image of the board, and memcpy, memmove, memset, memcmp, the
timing harness and main are in it, memcpy on a 32-byte boundary; the
selection words are where the stub reads them; every function of the
configuration's adapter table lies before the gap (Makefile "one", FAR),
and the code behind the gap starts at least FAR + placement bytes later.
"""
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT, BOOT_LEN, SEG = 4096, 4096, 256 * 1024
SIZES_PLACE = 28   # the largest placement of the series (oneslots.py PLACES)
FIXED_NAMES = ("memcpy", "memmove", "memset", "memcmp", "time_call", "main", "baseline_push_n", "baseline_pop_n")


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(r.stdout[-4000:] + r.stderr[-4000:])
        sys.exit(f"failed: {' '.join(cmd)}")
    return r.stdout


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def region(ld, name):
    m = re.search(rf"^\s*{name}\s+\(\w+\)\s*:\s*ORIGIN\s*=\s*(0x[0-9a-fA-F]+),\s*LENGTH\s*=\s*(\d+)([KM]?)",
                  open(ld).read(), re.M)
    if not m:
        sys.exit(f"{ld}: no {name} region")
    return int(m.group(1), 16), int(m.group(2)) * {"": 1, "K": 1024, "M": 1 << 20}[m.group(3)]


def image(elf, base):
    """Flash bytes of an image: the content of its loadable segments (gaps
    filled with 0xff), which must start at base. Written to <elf>.bin."""
    data = open(elf, "rb").read()
    phoff, = struct.unpack_from("<I", data, 28)
    phentsize, phnum = struct.unpack_from("<HH", data, 42)
    segs = []
    for k in range(phnum):
        ptype, off, _vaddr, paddr, filesz = struct.unpack_from("<5I", data, phoff + k * phentsize)
        if ptype == 1 and filesz:
            segs.append((paddr, data[off:off + filesz]))
    if not segs or min(p for p, _ in segs) != base:
        sys.exit(f"{elf}: does not load at {base:#x}")
    img = bytearray(b"\xff" * (max(p + len(d) for p, d in segs) - base))
    for p, d in segs:
        img[p - base:p - base + len(d)] = d
    with open(elf[:-4] + ".bin", "wb") as fh:
        fh.write(img)
    return bytes(img)


def symbols(elf):
    """[(address, size or None, type, name)] in address order."""
    out = []
    for ln in sh(["arm-none-eabi-nm", "-n", "-S", elf]).splitlines():
        f = ln.split()
        if len(f) == 4:
            out.append((int(f[0], 16), int(f[1], 16), f[2], f[3]))
        elif len(f) == 3:
            out.append((int(f[0], 16), None, f[1], f[2]))
    return out


def read_configs():
    """configs.txt: [(adapter, kind, name)]."""
    out = []
    for n, ln in enumerate(open(os.path.join(HERE, "configs.txt")), 1):
        f = ln.split("#")[0].split(None, 2)
        if not f:
            continue
        if len(f) != 3 or f[1] not in ("c", "rust", "nordic"):
            sys.exit(f"configs.txt:{n}: adapter, kind (c, rust or nordic) and name expected")
        out.append((f[0], f[1], f[2].strip()))
    if len({c[0] for c in out}) != len(out):
        sys.exit("configs.txt: an adapter is listed twice")
    return out


def read_slots():
    """slots.txt: [(adapter, placement, segment, offset, bytes)]."""
    out = []
    for n, ln in enumerate(open(os.path.join(HERE, "slots.txt")), 1):
        f = ln.split("#")[0].split()
        if not f:
            continue
        if len(f) != 5:
            sys.exit(f"slots.txt:{n}: five fields expected")
        out.append((f[0], int(f[1]), int(f[2]), int(f[3], 0), int(f[4], 0)))
    return out


def on_board(kind, board):
    return kind != "nordic" or board == "nrf5340"   # Nordic's licence: Nordic chips only


class Board:
    def __init__(self, makeargs):
        self.make = ["make", "-s"] + makeargs
        ld, self.arch, self.name, common, self.rust_lib = (
            sh(self.make + ["ONE=x", f"print-{v}"]).strip() for v in ("LD_FLASH", "ARCH", "BOARD", "COMMON", "RUST_LIB"))
        self.fbase, self.flen = region(ld, "FLASH")
        self.rbase, self.rlen = region(ld, "RAM")
        self.per_bundle = self.flen // SEG
        self.far = int(sh(self.make + ["ONE=x", "print-FAR"]).strip())
        # where the board keeps the selection words, if not in RAM (../common/select.h)
        m = re.search(r"^#define\s+BOARD_SELECT_ADDR\s+(0x[0-9A-Fa-f]+)",
                      open(os.path.join(common, "board_uart.h")).read(), re.M)
        self.sel_fixed = int(m.group(1), 16) if m else None


def build(board, jobs, out):
    """jobs: [{adapter, kind, place, base, slot_bytes, ...}]. Builds the
    images, checks them, and fills in bytes, checksums and paths."""
    make = board.make
    # what every image is linked from, once, before the images are built side by side
    sh(make + ["ONE=x", "build/one/objs.a", "build/startup.o"])
    if any(j["kind"] == "rust" for j in jobs):
        sh(make + ["ONE=x", "ONE_RUST=1", board.rust_lib])
    if any(j["kind"] == "nordic" for j in jobs):
        sh(make + ["ONE=x", "ONE_NORDIC=1", "build/one/nordic.a"])

    def one(j):
        extra = {"rust": ["ONE_RUST=1"], "nordic": ["ONE_NORDIC=1"]}.get(j["kind"], [])
        sh(make + ["one", f"ONE={j['adapter']}", f"PLACE={j['place']}", f"SLOT_BASE={j['base']:#x}",
                   f"SLOT_LEN={j['slot_bytes']}"] + extra)

    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
        list(pool.map(one, jobs))

    fixed, sel = None, board.sel_fixed
    for j in jobs:
        src = f"build/one/{j['adapter']}-p{j['place']}-{j['base']:#x}"
        d = f"{out}/img/{j['adapter']}-p{j['place']}"
        os.makedirs(d, exist_ok=True)
        elf = f"{d}/fw.elf"
        shutil.copyfile(f"{src}/fw.elf", elf)
        img = image(elf, j["base"])
        if len(img) > j["slot_bytes"]:
            sys.exit(f"{elf}: {len(img)} bytes, its slot has {j['slot_bytes']}")
        syms = symbols(elf)
        end = [a for a, _, _, n in syms if n == "_bench_fixed_end"]
        if len(end) != 1:
            sys.exit(f"{elf}: no end of the fixed part")
        part = [(a - j["base"], s, n) for a, s, t, n in syms
                if j["base"] <= a < end[0] and s is not None and t in "tTrRdD"]
        part.append((end[0] - j["base"], 0, "_bench_fixed_end"))
        # the memory functions and the baseline's code must be in it (they were not on Cortex-M0+
        # at first: memcpy came from another object than the linker script named, and nothing said so)
        where = {n: a for a, s, n in part}
        for n in FIXED_NAMES:
            if n not in where:
                sys.exit(f"{elf}: {n} is not in the fixed part")
        if where["memcpy"] % 32:
            sys.exit(f"{elf}: memcpy at offset {where['memcpy']:#x}, not on a 32-byte boundary")
        if fixed is None:
            fixed = part
            with open(f"{out}/fixed.txt", "w") as fh:
                fh.write("".join(f"{a:#07x} {s:5d} {n}\n" for a, s, n in part))
        elif part != fixed:
            sys.exit(f"{elf}: its fixed part differs from that of {jobs[0]['adapter']} p{jobs[0]['place']} "
                     f"({out}/fixed.txt): " + ", ".join(f"{a:#x} {n}" for a, s, n in sorted(set(part) ^ set(fixed))[:6]))
        here = [a for a, _, _, n in syms if n == "vl_select"]
        if board.sel_fixed is not None:
            if here:
                sys.exit(f"{elf}: selection words in RAM, the board keeps them at {board.sel_fixed:#x}")
        elif len(here) != 1 or sel not in (None, here[0]):
            sys.exit(f"{elf}: selection words at {here}, other images {sel}")
        else:
            sel = here[0]
        near_check(elf, syms, j, board.far)
        sh(["sh", "-c", f"arm-none-eabi-nm -S --size-sort -C {elf} > {d}/nm.txt"])
        j.update(bytes=len(img), elf=elf, sha256=sha256(open(elf, "rb").read()), image_sha256=sha256(img))
    return {"select_addr": sel, "fixed_bytes": fixed[-1][0],
            "fixed_sha256": sha256(open(f"{out}/fixed.txt", "rb").read())}


def near_check(elf, syms, j, far):
    """The functions the harness calls (the adapter's table) lie before the
    gap, and the code behind it at least far + placement bytes further on."""
    near = [a for a, _, _, n in syms if n == "_bench_near_end"]
    table = [(a, s) for a, s, t, n in syms if n == j["adapter"] and s]
    if len(near) != 1 or len(table) != 1:
        sys.exit(f"{elf}: no end of the adapter's code, or no table {j['adapter']}")
    data = open(elf, "rb").read()
    phoff, = struct.unpack_from("<I", data, 28)
    phentsize, phnum = struct.unpack_from("<HH", data, 42)
    words = None
    for k in range(phnum):
        ptype, off, vaddr, _paddr, filesz = struct.unpack_from("<5I", data, phoff + k * phentsize)
        if ptype == 1 and vaddr <= table[0][0] and table[0][0] + table[0][1] <= vaddr + filesz:
            at = off + table[0][0] - vaddr
            words = struct.unpack_from(f"<{table[0][1] // 4}I", data, at)
    if words is None:
        sys.exit(f"{elf}: the table {j['adapter']} is not in a loaded segment")
    end = j["base"] + j["slot_bytes"]
    funcs = [w & ~1 for w in words if w & 1 and j["base"] <= w < end]
    if 0 < len(funcs) < 3:   # none: a configuration that does not exist on this core (its table is empty)
        sys.exit(f"{elf}: the table {j['adapter']} names {len(funcs)} functions")
    name = {a: n for a, _, t, n in syms if t in "tT"}
    late = [name.get(f, hex(f)) for f in funcs if f >= near[0]]
    if late:
        sys.exit(f"{elf}: functions of the adapter behind the gap: {', '.join(late)}")
    behind = [a for a, s, t, n in syms if t in "tTwW" and s and a >= near[0] and n != "bench_shift"]
    if behind and min(behind) - near[0] < far + j["place"]:
        sys.exit(f"{elf}: code {min(behind) - near[0]} bytes behind the adapter, less than {far + j['place']}")
    j["far_code_bytes"] = (max(a + (s or 0) for a, s, t, n in syms if t in "tTwW" and a >= min(behind)) - min(behind)) if behind else 0


def stub(board, sel, out):
    """The boot stub: (path of its ELF, its flash bytes)."""
    fbase, flen, rbase, rlen = board.fbase, board.flen, board.rbase, board.rlen
    stub_ld = f"{out}/boot.ld"
    with open(stub_ld, "w") as fh:
        fh.write(f"MEMORY {{ FLASH (rx) : ORIGIN = {fbase:#x}, LENGTH = {BOOT_LEN}\n"
                 f"         RAM (rwx) : ORIGIN = {rbase:#x}, LENGTH = {rlen} }}\n"
                 "_estack = ORIGIN(RAM) + LENGTH(RAM);\nENTRY(Reset_Handler)\n"
                 "SECTIONS { .isr_vector : { KEEP(*(.isr_vector)) KEEP(*(.embedded_block)) } > FLASH\n"
                 "  .text : { *(.text*) *(.rodata*) } > FLASH\n"
                 "  .data : { *(.data*) *(.bss*) *(COMMON) } > RAM\n"
                 "  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) } }\n")
    boot = f"{out}/boot.elf"
    sh(["arm-none-eabi-gcc"] + board.arch.split() + ["-O2", "-g", "-Wall", "-Wextra", "-ffreestanding", "-nostdlib",
        "-ffunction-sections", "-Wl,--gc-sections", f"-DBENCHBOOT_SEL_ADDR={sel:#x}u",
        f"-DBENCHBOOT_FIRST={fbase + BOOT_LEN:#x}u", f"-DBENCHBOOT_END={fbase + flen:#x}u", f"-DBENCHBOOT_UNIT={UNIT}u",
        f"-DBENCHBOOT_RAM={rbase:#x}u", f"-DBENCHBOOT_RAM_END={rbase + rlen:#x}u"]
       + (["-DBENCHBOOT_RP2350"] if board.name == "rp2350" else [])
       + (["-DBENCHBOOT_NRF5340"] if board.name == "nrf5340" else []) +
       ["-T", stub_ld, os.path.join(HERE, "../common/benchboot.c"), "-o", boot])
    for ln in sh(["arm-none-eabi-size", "-A", boot]).splitlines():
        f = ln.split()
        if f and f[0] == ".data" and int(f[1]):
            sys.exit(f"{boot}: the stub must not use RAM (.data {f[1]} bytes)")
    data = image(boot, fbase)
    if len(data) > BOOT_LEN:
        sys.exit(f"{boot}: {len(data)} bytes, more than {BOOT_LEN}")
    return boot, data


def bundle(board, jobs, info, out, name, extra):
    """One ELF with a loadable segment per part, each filled with 0xff to
    the end of its last 4 KB: only pages that hold an image are written, and
    no byte between the images is left to the linker. And its manifest."""
    boot, boot_img = stub(board, info["select_addr"], out)
    parts = [("boot", board.fbase, boot[:-4] + ".bin")] + \
            [(f"i{k}", j["base"], j["elf"][:-4] + ".bin") for k, j in enumerate(jobs)]
    parts.sort(key=lambda p: p[1])
    work = f"{out}/{name}.parts"
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    objs, phdrs, lines, pages = [], [], [], 0
    for pname, base, binf in parts:
        data = open(binf, "rb").read()
        data += b"\xff" * (-len(data) % UNIT)
        pages += len(data) // UNIT
        with open(f"{work}/{pname}.bin", "wb") as fh:
            fh.write(data)
        o = f"{work}/{pname}.o"
        sh(["arm-none-eabi-objcopy", "-I", "binary", "-O", "elf32-littlearm", "-B", "arm",
            "--rename-section", f".data=.part_{pname},alloc,load,readonly,data,contents", f"{work}/{pname}.bin", o])
        objs.append(o)
        phdrs.append(f"  p_{pname} PT_LOAD;")
        lines.append(f"  .part_{pname} {base:#x} : {{ {o}(.part_{pname}) }} :p_{pname}")
    with open(f"{work}/bundle.ld", "w") as fh:
        fh.write("PHDRS {\n" + "\n".join(phdrs) + "\n}\nSECTIONS {\n" + "\n".join(lines) + "\n}\n")
    with open(f"{work}/objs.txt", "w") as fh:
        fh.write("\n".join(objs) + "\n")
    elf = f"{out}/{name}.elf"
    sh(["arm-none-eabi-ld", "-n", "-T", f"{work}/bundle.ld", f"@{work}/objs.txt", "-o", elf])
    shutil.rmtree(work)
    images = [dict(j, base=f"{j['base']:#010x}") for j in jobs]
    manifest = {"board": board.name, "flash": [f"{board.fbase:#010x}", board.flen], "boot_len": BOOT_LEN, "unit": UNIT,
                **extra, "select_addr": f"{info['select_addr']:#010x}", "select_magic": "0x564c4253",
                "fixed_bytes": info["fixed_bytes"], "fixed_sha256": info["fixed_sha256"],
                "bundle_elf": elf, "bundle_sha256": sha256(open(elf, "rb").read()),
                "boot_sha256": sha256(open(boot, "rb").read()), "boot_image_sha256": sha256(boot_img),
                "boot_bytes": len(boot_img), "flash_pages_written": pages, "images": images}
    with open(f"{out}/{name}.json", "w") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")
    print(f"{name}: {len(images)} images, {sum(i['bytes'] for i in images) + len(boot_img)} bytes, "
          f"{pages} pages of {UNIT} written, {elf}", flush=True)


def main():
    args = sys.argv[1:]
    if "--" not in args or not args or args[0] not in ("table", "sizes", "layout"):
        sys.exit(__doc__)
    cut = args.index("--")
    mode, opts, makeargs = args[0], args[1:cut], args[cut + 1:]
    layout = opts.pop(0) if mode == "layout" and opts else None
    out, only = None, None
    while opts:
        o = opts.pop(0)
        if o == "--out" and opts:
            out = opts.pop(0)
        elif o == "--bundle" and opts and mode == "table":
            only = [int(n) for n in opts.pop(0).split(",")]
        else:
            sys.exit(__doc__)
    if mode == "layout" and layout is None:
        sys.exit(__doc__)
    if mode == "layout":
        makeargs.append("FAR=0")
    board = Board(makeargs)
    out = out or f"build/v2/{board.name}"
    os.makedirs(out, exist_ok=True)
    fbase, flen = board.fbase, board.flen
    configs = read_configs()
    kinds = {a: k for a, k, _ in configs}
    names = {a: n for a, _, n in configs}

    if mode == "sizes":
        jobs = [{"adapter": a, "kind": k, "place": SIZES_PLACE, "base": fbase + BOOT_LEN,
                 "slot_bytes": min(flen, SEG) - BOOT_LEN} for a, k, _ in configs if on_board(k, board.name)]
        info = build(board, jobs, f"{out}/sizes")
        with open(f"{out}/sizes.json", "w") as fh:
            json.dump({"board": board.name, "flash_bytes": flen, "place": SIZES_PLACE, "far_bytes": board.far,
                       "fixed_bytes": info["fixed_bytes"],
                       "bytes": {j["adapter"]: j["bytes"] for j in jobs}}, fh, indent=1)
            fh.write("\n")
        shutil.rmtree(f"{out}/sizes")
        big = max(jobs, key=lambda j: j["bytes"])
        print(f"{board.name}: {len(jobs)} configurations, fixed part {info['fixed_bytes']} bytes, images "
              f"{min(j['bytes'] for j in jobs)} to {big['bytes']} bytes ({big['adapter']}), {out}/sizes.json")
        return

    if mode == "layout":
        jobs = []
        for n, ln in enumerate(open(layout), 1):
            f = ln.split("#")[0].split()
            if not f:
                continue
            if len(f) != 4:
                sys.exit(f"{layout}:{n}: four fields expected")
            jobs.append({"adapter": f[0], "kind": kinds.get(f[0], "c"), "name": names.get(f[0], f[0]),
                         "place": int(f[1]), "base": int(f[2], 0), "slot_bytes": int(f[3], 0)})
        groups = {"bundle": jobs}
    else:
        if board.per_bundle < 1:
            sys.exit(f"{board.name}: less than one segment of flash")
        numbered = {}
        for a, place, seg, off, length in read_slots():
            if a not in kinds:
                sys.exit(f"slots.txt: {a} is not in configs.txt")
            if off % UNIT or length % UNIT or off < BOOT_LEN or off + length > SEG:
                sys.exit(f"slots.txt: {a} p{place}: not a slot on {UNIT}-byte boundaries behind the first "
                         f"{BOOT_LEN} bytes of a segment")
            if not on_board(kinds[a], board.name):
                continue
            b = seg // board.per_bundle
            if only is None or b in only:
                numbered.setdefault(b, []).append(
                    {"adapter": a, "kind": kinds[a], "name": names[a], "place": place, "segment": seg, "offset": off,
                     "base": fbase + (seg % board.per_bundle) * SEG + off, "slot_bytes": length})
        if only and set(only) - set(numbered):
            sys.exit(f"no images in bundle {sorted(set(only) - set(numbered))}")
        groups = {f"bundle{b}": numbered[b] for b in sorted(numbered)}

    alljobs = [j for g in groups.values() for j in g]
    if not alljobs:
        sys.exit("no images to build")
    if len({(j["adapter"], j["place"]) for j in alljobs}) != len(alljobs):
        sys.exit("an image (adapter and placement) is listed twice")
    for g in groups.values():   # the images of one bundle share the flash
        end = fbase + BOOT_LEN
        for j in sorted(g, key=lambda j: j["base"]):
            if j["base"] % UNIT or j["slot_bytes"] % UNIT or j["base"] < end or j["base"] + j["slot_bytes"] > fbase + flen:
                sys.exit(f"{j['adapter']} p{j['place']} at {j['base']:#x}: not a free slot on a {UNIT}-byte boundary in flash")
            end = j["base"] + j["slot_bytes"]

    # nothing of an earlier table stays behind: a bundle or an image that is no longer in it
    for f in os.listdir(out):
        if re.fullmatch(r"bundle\d*\.(elf|json)", f) and (only is None or f.split(".")[0] in groups):
            os.remove(f"{out}/{f}")
    if only is None and os.path.isdir(f"{out}/img"):
        keep = {f"{j['adapter']}-p{j['place']}" for j in alljobs}
        for d in os.listdir(f"{out}/img"):
            if d not in keep:
                shutil.rmtree(f"{out}/img/{d}")

    info = build(board, alljobs, out)
    for name, jobs in groups.items():
        extra = {"far_bytes": board.far}
        if mode != "layout":
            extra.update(bundle=int(name[6:]), segment_bytes=SEG, segments_per_bundle=board.per_bundle)
        bundle(board, jobs, info, out, name, extra)


if __name__ == "__main__":
    main()
