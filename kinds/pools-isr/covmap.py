#!/usr/bin/env python3
"""Map the coverage bitmap of a pools-isr run (main.c: one bit per halfword
of the image, set where an interrupt came during main's call) to the
instructions of the configuration's own code (plan 3.2, "Coverage").

The configuration's code is every .text input section of the image's link
map (fw.map) that comes from neither the harness nor the C library: not
main.o, startup.o, the reference of the latency calibration (ref_pool.o, but
in the reference's own image, where it is the configuration) and not the C
library's members. Its instructions are objdump's, between each section's
start and end. An instruction is reached if the bit of its first halfword is
set.

Usage: python3 -I covmap.py IMAGE-DIR RUN-FILE     (IMAGE-DIR: build/v1/<board>/img/<adapter>)
       as a module: cover(image_dir, bitmap_words, base) -> per function
       {"reached", "instructions", "unreached": [addresses]}
Needs arm-none-eabi-objdump (the toolchain image).
"""
import json
import os
import re
import subprocess
import sys

HARNESS = ("main.o", "startup.o")
LIBC = re.compile(r"lib_a-|libc_nano|libgcc|libnosys|crt")


def sections(mapfile, adapter):
    """[(name, address, size, object)] of the configuration's .text input sections"""
    out, pend = [], None
    for ln in open(mapfile):
        if pend:
            m = re.match(r"^\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+(\S+)", ln)
            if m:
                out.append((pend, int(m.group(1), 16), int(m.group(2), 16), m.group(3)))
            pend = None
            continue
        m = re.match(r"^ (\.text\S*)\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+(\S+)", ln)
        if m:
            out.append((m.group(1), int(m.group(2), 16), int(m.group(3), 16), m.group(4)))
        elif re.match(r"^ (\.text\S*)$", ln.rstrip()):
            pend = ln.strip()
    own = []
    for name, addr, size, obj in out:
        base = obj.rsplit("(", 1)[-1].rstrip(")") if "(" in obj else os.path.basename(obj)
        if not size or not addr or base in HARNESS or LIBC.search(obj):
            continue
        if base == "ref_pool.o" and adapter != "adapter_ref":
            continue
        own.append((name, addr, size, base))
    return own


def instructions(elf, start, end):
    """[(address, function)] of the instructions in [start, end)"""
    out = subprocess.run(["arm-none-eabi-objdump", "-d", f"--start-address={start:#x}", f"--stop-address={end:#x}", elf],
                         capture_output=True, text=True, check=True).stdout
    return parse(out)


def parse(out):
    """[(address, function)] of the instruction lines of objdump -d's output. An address of eight hex digits
    (the Pico 2's 0x1000xxxx) is printed with no space before it, a shorter one with spaces: both are taken.
    Literal-pool words (.word, eight digits in one group) are not instructions and are not taken."""
    res, fn = [], None
    for ln in out.splitlines():
        m = re.match(r"^([0-9a-f]+) <(.+)>:$", ln)
        if m:
            fn = m.group(2)
            continue
        m = re.match(r"^\s*([0-9a-f]+):\s+[0-9a-f]{4}(?: [0-9a-f]{4})?\s+\S", ln)
        if m:
            res.append((int(m.group(1), 16), fn))
    return res


def cover(image_dir, bitmap, base, adapter):
    elf = os.path.join(image_dir, "fw.elf")
    per = {}
    for _name, addr, size, _obj in sections(os.path.join(image_dir, "fw.map"), adapter):
        for a, fn in instructions(elf, addr, addr + size):
            off = (a - base) >> 1
            hit = 0 <= off < 32 * len(bitmap) and bitmap[off >> 5] >> (off & 31) & 1
            f = per.setdefault(fn, {"reached": 0, "instructions": 0, "unreached": []})
            f["instructions"] += 1
            if hit:
                f["reached"] += 1
            else:
                f["unreached"].append(f"{a:#x}")
    return per


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    run = json.load(open(sys.argv[2]))
    per = cover(sys.argv[1], run["result"]["cov_bitmap"], int(run["image_base"], 16), run["adapter"])
    for fn, f in sorted(per.items()):
        print(f"{f['reached']:5d} of {f['instructions']:5d}  {fn}")
    print(f"{sum(f['reached'] for f in per.values())} of {sum(f['instructions'] for f in per.values())} instructions reached")


if __name__ == "__main__":
    main()
