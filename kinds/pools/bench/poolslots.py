#!/usr/bin/env python3
"""The slots of the pools kind's benchmark images: ../slots.txt, by the rules
of version 2. The program is version 2's own, used unchanged
(firmware/nrf5340-rb-bench/oneslots.py: 256 KB segments, 4 KB units, the
first unit of a segment free, a slot is the image at its largest placement
on the board where it is largest plus a quarter of its code, eight
placements, "a line is added or the lines of the one configuration that
changed are replaced; no other line is touched"). Only its files are this
kind's: the configurations (../configs.txt) and the table (../slots.txt).

Every kind has a range of 100 segments of its own in one numbering, so the
bundle numbers of two kinds do not meet (checked, below): the ring buffers 0 to 99, the CRC
kind 100 to 199, this kind from FIRST_SEGMENT = 200 to 299. A segment lies in
flash at (segment modulo segments per bundle) * 256 KB, as in version 2, and
a board holds one bundle at a time: a pools bundle takes the place of the
other kinds' images at the same addresses (the runner compares the flash
with the bundle before every run). The boot stub is the same, byte for byte.
200 is a multiple of 1, 2 and 4 segments per bundle; on the Pico 2 (16 per
bundle) the kind's segments start at 8 of bundle 12, whose segments 192 to
199 lie in the CRC kind's range: they are unused (the CRC table holds 100 to
115). The program stops if the ring buffers' or the CRC kind's table ever
reaches FIRST_SEGMENT, or if on any board (1, 2, 4 or 16 segments per bundle)
a bundle number would hold segments of this kind and of another.

A configuration of ../boards.txt exists on the boards named there only
(onepool.py sizes leaves it out of the other boards' sizes): its slot is
sized for those boards, and the other boards leave it empty, as the slots
are one table for every board.

Usage: python3 -I poolslots.py assign SIZES.json...   (onepool.py sizes, all six boards)
       python3 -I poolslots.py free ADAPTER
       python3 -I poolslots.py show
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.dirname(HERE)
RB = os.path.join(KIND, "../../firmware/nrf5340-rb-bench")
sys.path.insert(0, RB)
import oneslots  # noqa: E402

FIRST_SEGMENT = 200
KIND_SEGMENTS = 100    # the kind's range: FIRST_SEGMENT to FIRST_SEGMENT + KIND_SEGMENTS - 1

oneslots.HERE = KIND                                   # configs.txt
oneslots.TABLE = os.path.join(KIND, "slots.txt")
oneslots.HEAD = """# The slots of the pools kind's benchmark images (bench/poolslots.py writes this
# file, bench/onepool.py builds from it), by the rules of version 2
# (firmware/nrf5340-rb-bench/oneslots.py). One image per line; segments of
# 256 KB, the same table for every board; the kind's segments are 200 to 299.
# A line is added, or the lines of the one configuration that changed are
# replaced: no other line is touched, because an image's bytes depend on
# its line.
#
# adapter                 placement segment offset  bytes
"""
_used = oneslots.used
_write = oneslots.write


def check_range(lines):
    high = [s for _, _, s, _, _ in lines if s >= FIRST_SEGMENT + KIND_SEGMENTS]
    if high:
        sys.exit(f"slots.txt: a slot in segment {max(high)}, behind the kind's last ({FIRST_SEGMENT + KIND_SEGMENTS - 1})")


def write(lines):
    """Nothing is written if a new slot would lie behind the kind's range."""
    check_range(lines)
    _write(lines)


def used(lines):
    """The ring buffers' segments count as full, so no slot goes there."""
    u = _used(lines)
    low = [s for s in u if s < FIRST_SEGMENT]
    if low:
        sys.exit(f"slots.txt: a slot in segment {low[0]}, before the kind's first ({FIRST_SEGMENT})")
    check_range(lines)
    check_bundles(lines)
    for s in range(FIRST_SEGMENT):
        u[s] = set(range(oneslots.SEG // oneslots.UNIT))
    return u


OTHER_TABLES = (os.path.join(RB, "slots.txt"), os.path.join(KIND, "../crc/slots.txt"))
PER_BUNDLE = (1, 2, 4, 16)    # the boards' segments per bundle (flash / 256 KB)


def other_segments():
    """{segment: table} of the other kinds' tables (ring buffers, CRC)."""
    out = {}
    for t in OTHER_TABLES:
        for ln in open(t):
            f = ln.split("#")[0].split()
            if len(f) == 5:
                out[int(f[2])] = os.path.relpath(t, KIND)
    return out


def check_bundles(lines):
    """No bundle number holds segments of this kind and of another, on any board."""
    other = other_segments()
    if other and max(other) >= FIRST_SEGMENT:
        sys.exit(f"{other[max(other)]} reaches segment {max(other)}, the pools kind starts at {FIRST_SEGMENT}")
    ours = {s for _, _, s, _, _ in lines} or {FIRST_SEGMENT}
    for per in PER_BUNDLE:
        meet = {s // per for s in ours} & {s // per for s in other}
        if meet:
            b = min(meet)
            sys.exit(f"at {per} segments per bundle, bundle {b} holds segments of this kind and of "
                     f"{', '.join(sorted({t for s, t in other.items() if s // per == b}))}")


def show(lines, flash=None):
    """The kind's segments only; flash writes per board as version 2 counts them."""
    u = _used(lines)
    segs = sorted(u)
    free = sum(oneslots.SEG // oneslots.UNIT - len(u[s]) for s in segs)
    print(f"{len(lines)} images of {len({a for a, *_ in lines})} configurations in {len(segs)} segments"
          + (f" ({segs[0]} to {segs[-1]})" if segs else "") + f", {free} units of {oneslots.UNIT // 1024} KB free in them")
    for board, flen in (flash or {}).items():
        per = flen // oneslots.SEG
        bundles = sorted({s // per for a, p, s, o, b in lines})
        print(f"  {board}: {per} segments per bundle, {len(bundles)} flash writes for all images (bundles {bundles})")


def read_boards():
    out = {}
    for ln in open(os.path.join(KIND, "boards.txt")):
        f = ln.split("#")[0].split()
        if f:
            out[f[0]] = set(f[1:])
    return out


class SizesOfAllBoards:
    """json for oneslots.main: a configuration of boards.txt gets, on a board without it, the largest
    size it has on its boards, so that oneslots sizes its slot for those boards."""
    def __init__(self, paths):
        self.d = {os.path.abspath(p): json.load(open(p)) for p in paths}
        for a, on in read_boards().items():
            have = [d["bytes"][a] for d in self.d.values() if d["board"] in on and a in d["bytes"]]
            if len(have) != len(on):
                sys.exit(f"{a}: sizes of {len(have)} of its {len(on)} boards (boards.txt)")
            for d in self.d.values():
                if d["board"] not in on:
                    if a in d["bytes"]:
                        sys.exit(f"{a}: a size for {d['board']}, which boards.txt does not name")
                    d["bytes"][a] = max(have)

    def load(self, fh):
        return self.d[os.path.abspath(fh.name)]


def main():
    check_bundles(oneslots.read() if os.path.exists(oneslots.TABLE) else [])
    oneslots.used = used
    oneslots.write = write
    oneslots.show = show
    if sys.argv[1:2] == ["show"]:
        show(oneslots.read())
        return
    if sys.argv[1:2] == ["assign"]:
        oneslots.json = SizesOfAllBoards(sys.argv[2:])
    oneslots.main()


if __name__ == "__main__":
    main()
