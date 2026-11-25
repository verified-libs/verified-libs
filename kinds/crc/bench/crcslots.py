#!/usr/bin/env python3
"""The slots of the CRC kind's benchmark images: ../slots.txt, by the rules
of version 2. The program is version 2's own, used unchanged
(firmware/nrf5340-rb-bench/oneslots.py: 256 KB segments, 4 KB units, the
first unit of a segment free, a slot is the image at its largest placement
on the board where it is largest plus a quarter of its code, eight
placements, "a line is added or the lines of the one configuration that
changed are replaced; no other line is touched"). Only its files are this
kind's: the configurations (../configs.txt) and the table (../slots.txt).

Every kind has a range of 100 segments of its own in one numbering, so the
bundle numbers of two kinds never meet: the ring buffers 0 to 99 (their
table held segments 0 to 19 when this was written, with room for one more
configuration in them), this kind from FIRST_SEGMENT = 100 to 199, a next
kind from 200. A segment lies in flash at (segment modulo segments per
bundle) * 256 KB, as in version 2, and a board holds one bundle at a time: a
CRC bundle takes the place of the ring-buffer images at the same addresses,
as one ring-buffer bundle takes another's (run-crc.py compares the flash
with the bundle before every run). The boot stub is the same, byte for byte.
On the Pico 2 (16 segments per bundle) the kind's nine segments lie at 4 to
12 of a bundle. The first segment was 20 until 2026-11-24, before any series
of the kind was run; 80 is a multiple of every board's segments per bundle
(1, 2, 4, 16), so every image has the address and the bytes it had with 20
and every bundle writes the same to flash (the bundle's file carries its
number in its symbol names, so the file's SHA-256 is another). If the ring
buffers' table ever reaches FIRST_SEGMENT, or
this kind's table the next kind's range, this program stops.

Usage: python3 -I crcslots.py assign SIZES.json...   (onecrc.py sizes, all six boards)
       python3 -I crcslots.py free ADAPTER
       python3 -I crcslots.py show
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.dirname(HERE)
RB = os.path.join(KIND, "../../firmware/nrf5340-rb-bench")
sys.path.insert(0, RB)
import oneslots  # noqa: E402

FIRST_SEGMENT = 100
KIND_SEGMENTS = 100    # the kind's range: FIRST_SEGMENT to FIRST_SEGMENT + KIND_SEGMENTS - 1

oneslots.HERE = KIND                                   # configs.txt
oneslots.TABLE = os.path.join(KIND, "slots.txt")
oneslots.HEAD = """# The slots of the CRC kind's benchmark images (bench/crcslots.py writes this
# file, bench/onecrc.py builds from it), by the rules of version 2
# (firmware/nrf5340-rb-bench/oneslots.py). One image per line; segments of
# 256 KB, the same table for every board; the kind's segments are 100 to 199.
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
    for s in range(FIRST_SEGMENT):
        u[s] = set(range(oneslots.SEG // oneslots.UNIT))
    return u


def rb_last_segment():
    last = -1
    for ln in open(os.path.join(RB, "slots.txt")):
        f = ln.split("#")[0].split()
        if len(f) == 5:
            last = max(last, int(f[2]))
    return last


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


def main():
    if rb_last_segment() >= FIRST_SEGMENT:
        sys.exit(f"the ring buffers' slots reach segment {rb_last_segment()}, the CRC kind starts at {FIRST_SEGMENT}")
    oneslots.used = used
    oneslots.write = write
    oneslots.show = show
    if sys.argv[1:2] == ["show"]:
        show(oneslots.read())
        return
    oneslots.main()


if __name__ == "__main__":
    main()
