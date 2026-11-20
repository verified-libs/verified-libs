#!/usr/bin/env python3
"""Summarise rb-size results.tsv into a markdown report on stdout.

Flash = text + data (code, constants, initial values); RAM = data + bss.
All numbers are differences from the baseline image (same startup, main and
heap objects, no ring buffer) built with the same optimisation flag.
"""
import csv
import sys


def main():
    rows = list(csv.DictReader(open(sys.argv[1]), delimiter="\t"))
    base = {r["opt"]: r for r in rows if r["lib"] == "baseline"}
    data = {}
    for r in rows:
        if r["lib"] == "baseline":
            continue
        b = base[r["opt"]]
        flash = int(r["text"]) + int(r["data"]) - int(b["text"]) - int(b["data"])
        ram = int(r["data"]) + int(r["bss"]) - int(b["data"]) - int(b["bss"])
        data.setdefault(r["lib"], {})[(r["opt"], r["variant"])] = (flash, ram)

    print("# Flash and RAM per ring buffer\n")
    print("Bytes added to the baseline image. Each buffer is its own module (the")
    print("library's benchmark adapter: reset, push, pop, push_n, pop_n, and the")
    print("zero-copy calls where the library has them); library .c files are")
    print("linked once. RAM includes the buffer storage (capacity bytes).\n")
    for opt in ("-Os", "-O2"):
        print(f"## {opt}\n")
        print("| Library | 1 buffer (128): flash / RAM | 3 identical (3 × 128): flash / RAM | each extra identical: flash | 3 different (64, 128, 256): flash / RAM |")
        print("|---|---|---|---|---|")
        for lib, v in data.items():
            one = v.get((opt, "K=1 cap=128"))
            same = v.get((opt, "K=3 cap=128/128/128"))
            var = v.get((opt, "K=3 cap=64/128/256"))
            if not (one and same and var):
                print(f"| {lib} | – | – | – | – |")
                continue
            extra = (same[0] - one[0]) / 2
            print(f"| {lib} | {one[0]} / {one[1]} | {same[0]} / {same[1]} | {extra:.0f} | {var[0]} / {var[1]} |")
        print()


if __name__ == "__main__":
    main()
