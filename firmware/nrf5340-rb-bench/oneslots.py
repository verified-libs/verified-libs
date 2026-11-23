#!/usr/bin/env python3
"""Give the benchmark images of version 2 their slots in flash: slots.txt
(lab/plans/2026-11-22-bench-image-per-library.md). An image is linked for
its slot, so its bytes stay the same for as long as its line here does.
The rule of this file: a line is added, or the lines of the one
configuration that changed are replaced; no other line is touched.

Usage: python3 -I oneslots.py assign SIZES.json...
       python3 -I oneslots.py free ADAPTER
       python3 -I oneslots.py show

assign  every image of configs.txt that has no slot yet gets one: the
        first free place that is large enough, in the order of configs.txt
        and of the placements. SIZES.json: one file per board, from
        "onebundle.py sizes" (onebuild.sh sizes); all six are needed, so that
        a slot has room for the image on every board.
free    take a configuration's lines out (its image has outgrown its slots,
        or it is no longer measured); "assign" then gives it slots again.
show    the table: slots, free space, flash writes per board for all of it.

A slot: a segment of 256 KB, an offset in it and a length, in units of
4 KB (the nRF5340's cache-on numbers follow the position within 4 KB, so
every image starts at the same one). The first 4 KB of a segment stay
free (the boot stub lies there in the first segment of a bundle), and no
slot crosses a segment. A slot has room for the image at its largest
placement on the board where it is largest, and a quarter of its code more
(the bytes that keep the library far from its adapter, FAR in the Makefile,
do not grow).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT, SEG = 4096, 256 * 1024
PLACES = (0, 4, 8, 12, 16, 20, 24, 28)   # bytes between the fixed part and the library (PLACE), as version 1's SHIFT
BOARDS = ("nrf5340", "stm32g0b1", "stm32g474", "stm32h723", "samd20", "rp2350")
TABLE = os.path.join(HERE, "slots.txt")
HEAD = """# The slots of the benchmark images of version 2 (oneslots.py writes this
# file, onebundle.py builds from it). One image per line; segments of
# 256 KB, the same table for every board. A line is added, or the lines of
# the one configuration that changed are replaced: no other line is touched,
# because an image's bytes depend on its line.
#
# adapter                 placement segment offset  bytes
"""


def configs():
    out = []
    for ln in open(os.path.join(HERE, "configs.txt")):
        f = ln.split("#")[0].split(None, 2)
        if f:
            out.append((f[0], f[1]))
    return out


def read():
    lines = []   # (adapter, place, segment, offset, bytes)
    if os.path.exists(TABLE):
        for n, ln in enumerate(open(TABLE), 1):
            f = ln.split("#")[0].split()
            if f:
                if len(f) != 5:
                    sys.exit(f"slots.txt:{n}: five fields expected")
                lines.append((f[0], int(f[1]), int(f[2]), int(f[3], 0), int(f[4], 0)))
    return lines


def write(lines):
    with open(TABLE, "w") as fh:
        fh.write(HEAD)
        for a, p, s, o, b in lines:
            fh.write(f"{a:25} {p:<9} {s:<7} {o:#07x} {b}\n")


def used(lines):
    """segment -> set of units in use; unit 0 always."""
    u = {}
    for a, p, s, o, b in lines:
        if o % UNIT or b % UNIT or o < UNIT or o + b > SEG:
            sys.exit(f"slots.txt: {a} p{p}: not a slot of whole units behind the first one of a segment")
        units = set(range(o // UNIT, (o + b) // UNIT))
        if units & u.setdefault(s, {0}):
            sys.exit(f"slots.txt: {a} p{p}: its slot overlaps another")
        u[s] |= units
    return u


def show(lines, flash=None):
    u = used(lines)
    nseg = max(u) + 1 if u else 0
    free = sum(SEG // UNIT - len(u.get(s, {0})) for s in range(nseg))
    print(f"{len(lines)} images of {len({a for a, *_ in lines})} configurations in {nseg} segments of {SEG // 1024} KB, "
          f"{free} units of {UNIT // 1024} KB free in them")
    kinds = dict(configs())
    for board, flen in (flash or {}).items():
        per = flen // SEG
        bundles = {s // per for a, p, s, o, b in lines if kinds.get(a) != "nordic" or board == "nrf5340"}
        print(f"  {board}: {per} segments per bundle, {len(bundles)} flash writes for all images")


def main():
    args = sys.argv[1:]
    lines = read()
    if args == ["show"]:
        show(lines)
    elif len(args) == 2 and args[0] == "free":
        keep = [ln for ln in lines if ln[0] != args[1]]
        if len(keep) == len(lines):
            sys.exit(f"{args[1]} has no slots")
        write(keep)
        print(f"{args[1]}: {len(lines) - len(keep)} slots freed")
    elif len(args) >= 2 and args[0] == "assign":
        sizes, flash, fars = {}, {}, set()
        for f in args[1:]:
            d = json.load(open(f))
            if d["place"] != PLACES[-1]:
                sys.exit(f"{f}: sizes at placement {d['place']}, not the largest ({PLACES[-1]})")
            sizes[d["board"]], flash[d["board"]] = d["bytes"], d["flash_bytes"]
            fars.add(d["far_bytes"])
        if len(fars) != 1:
            sys.exit("the sizes are not of one distance between adapter and library (far_bytes)")
        far = fars.pop()
        if set(sizes) != set(BOARDS):
            sys.exit("sizes of all boards are needed: " + ", ".join(sorted(set(BOARDS) ^ set(sizes))) + " missing or unknown")
        u = used(lines)
        have = {(a, p) for a, p, *_ in lines}
        new = 0
        for a, kind in configs():
            boards = ("nrf5340",) if kind == "nordic" else BOARDS
            missing = [b for b in boards if a not in sizes[b]]
            if missing:
                sys.exit(f"{a}: no size for {', '.join(missing)}")
            need = max(sizes[b][a] for b in boards)
            n = -(-(need + (need - far) // 4) // UNIT)   # units, with a quarter of the code to grow in
            for p in PLACES:
                if (a, p) in have:
                    continue
                s = 0
                while True:
                    taken = u.setdefault(s, {0})
                    first = next((k for k in range(1, SEG // UNIT - n + 1)
                                  if not any(k + i in taken for i in range(n))), None)
                    if first is not None:
                        break
                    s += 1
                taken |= set(range(first, first + n))
                lines.append((a, p, s, first * UNIT, n * UNIT))
                new += 1
        write(lines)
        print(f"{new} new slots")
        show(lines, flash)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
