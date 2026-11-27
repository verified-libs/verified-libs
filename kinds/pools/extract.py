#!/usr/bin/env python3
"""The host part of check 1: cut CMSIS-RTX's three pool functions out of
rtx_mempool.c, as they are, into a file of their own for the host build.

Usage: python3 -I extract.py RTX_MEMPOOL_C OUT_C

rtx_mempool.c cannot be compiled for x86-64 as a whole: its public API
(osMemoryPoolNew, osMemoryPoolAlloc, ...) calls the kernel through the SVC
macros of rtx_core_cm.h, which bind variables to the Arm registers r0-r3.
The pool's algorithm is in three functions that make no such call:
osRtxMemoryPoolInit, osRtxMemoryPoolAlloc and osRtxMemoryPoolFree. This
script copies the file's include line and those three functions, each from
its first line to the closing brace at the start of a line, byte for byte,
and checks that each copy occurs in the source unchanged. Nothing else is
taken, nothing is rewritten. Exit 1 if a function is not found exactly once.
"""
import re
import sys

NAMES = ("osRtxMemoryPoolInit", "osRtxMemoryPoolAlloc", "osRtxMemoryPoolFree")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src = open(sys.argv[1], encoding="utf-8").read()
    parts = ['#include "rtx_lib.h"\n']
    if src.count('#include "rtx_lib.h"\n') != 1:
        sys.exit("rtx_lib.h is not included exactly once")
    for name in NAMES:
        starts = [m.start() for m in re.finditer(r"^[a-zA-Z_][^\n;]*\b" + name + r" \([^)]*\) \{\n", src, re.M)]
        if len(starts) != 1:
            sys.exit(f"{name}: {len(starts)} definitions found, not 1")
        end = src.index("\n}\n", starts[0]) + 3
        body = src[starts[0]:end]
        if src.count(body) != 1:
            sys.exit(f"{name}: the copy is not in the source once")
        parts.append("\n" + body)
        print(f"{name}: lines {src[:starts[0]].count(chr(10)) + 1}-{src[:end].count(chr(10))} copied")
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        fh.write("/* Cut out of CMSIS-RTX's Source/rtx_mempool.c by extract.py, byte for byte. */\n" + "".join(parts))


if __name__ == "__main__":
    main()
