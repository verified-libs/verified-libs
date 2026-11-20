#!/usr/bin/env python3
"""One result block from the blocks of a PER_LIB=1 run (run.sh): one library
per reset, the whole block read after each library.

Usage: merge_words.py NLIBS OUT WORDS_0 WORDS_1 ... WORDS_{NLIBS-1}
  A WORDS_l of "-": library l was not run (run.sh LIBS); its rows stay zero.

Library l's rows are taken from WORDS_l only (read right after it ran, so a
library that wrote over memory cannot change the rows of the libraries
before it). Header and run parameters come from the first block given. Interrupt sweep:
capacity and the per-library sweep arrays likewise from WORDS_l; the
coverage bitmap is the union, the PCs outside it the sum. The layout is
main.c's struct results (as decode.py reads it).
"""
import sys

NDIRS, FIELDS = 2, 8


def main():
    nlibs, out, files = int(sys.argv[1]), sys.argv[2], sys.argv[3:]
    if len(files) != nlibs:
        sys.exit(f"{len(files)} blocks for {nlibs} libraries")
    blocks = [None if f == "-" else [int(x, 16) for x in open(f).read().split()] for f in files]
    if not any(blocks):
        sys.exit("no library was run")
    first = next(b for b in blocks if b)
    zero = [0] * len(first)
    blocks = [b if b else zero for b in blocks]
    w = list(first)
    if w[4] != nlibs or w[5] != NDIRS:
        sys.exit(f"layout mismatch: nlibs {w[4]}, ndirs {w[5]}")
    row = NDIRS * FIELDS
    for l, b in enumerate(blocks):
        w[6 + l * row:6 + (l + 1) * row] = b[6 + l * row:6 + (l + 1) * row]
    w[2] = 1   # done: every library was run (the ones that did not finish are named in the meta data)
    if w[1] & 0x200:   # interrupt sweep
        q = 6 + nlibs * row + 7
        cov_words = w[q + 2]
        w[q + 3] = sum(b[q + 3] for b in blocks)                # PCs outside the bitmap
        cap = q + 4
        for l, b in enumerate(blocks):
            w[cap + l] = b[cap + l]
        arrays = cap + nlibs
        for k in range(8):
            a = arrays + k * nlibs * NDIRS
            for l, b in enumerate(blocks):
                w[a + l * NDIRS:a + (l + 1) * NDIRS] = b[a + l * NDIRS:a + (l + 1) * NDIRS]
        cov = arrays + 8 * nlibs * NDIRS
        for i in range(cov_words):
            v = 0
            for b in blocks:
                v |= b[cov + i]
            w[cov + i] = v
    with open(out, "w") as fh:
        fh.write("\n".join(f"{x:08x}" for x in w) + "\n")


if __name__ == "__main__":
    main()
