#!/usr/bin/env python3
"""Merge the result blocks of one-library runs (run.sh PER_LIB=1: one
library per reset, each block from its own run) into one block, as one run
of every library would have left it, for decode.py.

Usage: merge_mp.py [--magic 0xMAGIC] [--slot WORDS] OUT_WORDS WORDS_FILE...
(--magic: another test with the same layout, 12 header words and 12 words
per library, e.g. ../rb-dma-stress, magic 0x564C4431; --slot: words per
library if not 12, e.g. ../rb-xcore-stress 16; a slot counts as absent if
its first word is NOT_IN_IMAGE)
Each block holds one library's slot (the others are NOT_IN_IMAGE, main.c);
the headers (mode, transfers, seeds, board, clock, ...) must all be the same.
A block that is not finished (done != 1: a library that did not end in
time, read over the debug port) is left out; its slots stay NOT_IN_IMAGE.
"""
import sys

MAGIC = 0x564C4D31
NHDR, NSLOT = 12, 12
ABSENT = 0xFFFFFFFE


def main():
    global MAGIC, NSLOT
    a = sys.argv[1:]
    while a and a[0] in ("--magic", "--slot"):
        if a[0] == "--magic":
            MAGIC = int(a[1], 0)
        else:
            NSLOT = int(a[1])
        a = a[2:]
    out, files = a[0], a[1:]
    blocks = []
    for f in files:
        w = [int(x, 16) for x in open(f).read().split()]
        if len(w) < NHDR or w[0] != MAGIC:
            sys.exit(f"{f}: not a block with magic {MAGIC:#010x}")
        if w[2] != 1:
            print(f"note: {f}: not finished, left out", file=sys.stderr)
            continue
        blocks.append((f, w))
    if not blocks:
        sys.exit("no finished block")
    f0, ref = blocks[0]
    nlibs = ref[4]
    n = NHDR + nlibs * NSLOT
    merged = ref[:NHDR] + [0] * (nlibs * NSLOT)
    for i in range(nlibs):
        merged[NHDR + i * NSLOT] = ABSENT
    taken = {}
    for f, w in blocks:
        if len(w) < n:
            sys.exit(f"{f}: {len(w)} words, {n} expected")
        if w[:NHDR] != ref[:NHDR]:
            diff = [k for k in range(NHDR) if w[k] != ref[k]]
            sys.exit(f"{f}: header differs from {f0} at words {diff}")
        for i in range(nlibs):
            s = w[NHDR + i * NSLOT:NHDR + (i + 1) * NSLOT]
            if s[0] == ABSENT:
                continue
            if i in taken:
                sys.exit(f"slot {i} in both {taken[i]} and {f}")
            taken[i] = f
            merged[NHDR + i * NSLOT:NHDR + (i + 1) * NSLOT] = s
    with open(out, "w") as fh:
        fh.write("".join(f"{x:08x}\n" for x in merged))


if __name__ == "__main__":
    main()
