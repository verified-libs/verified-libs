#!/usr/bin/env python3
"""The overview of the kinds of library (site/content/kinds.md, the page
kinds.html, "Results" in the menu), written from the data, so that its
counts cannot drift: site/build.py refuses to build if the file is not what
this program writes.

One block per kind, the same fields in the same order, no ranking. The counts:
  - ring buffers: site/data/libs.json, the data of the comparison page
    (site/gen_libdata.py): configurations = its rows ("libs"), libraries =
    the distinct repositories ("url") of those rows, boards = "boards";
  - CRC: the records under records/crc (schema crc-bench/1): configurations
    = the distinct adapters, libraries = the distinct libraries of those
    adapters (third column of kinds/crc/configs.txt), CRCs = the distinct
    "crc", boards = the distinct "board".

Usage: python3 -I site/kinds_page.py [--write | --check]
  (no argument: print the page; --write: write site/content/kinds.md;
  --check: exit 1 if it is not up to date)
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ring_counts():
    d = json.load(open(os.path.join(ROOT, "site/data/libs.json")))
    return {"libraries": len({l["url"] for l in d["libs"]}), "configurations": len(d["libs"]),
            "boards": len(d["boards"])}


def crc_counts():
    lib_of = {}
    for line in open(os.path.join(ROOT, "kinds/crc/configs.txt")):
        f = line.split()
        if f and not f[0].startswith("#"):
            lib_of[f[0]] = f[2]
    ads, crcs, boards = set(), set(), set()
    for f in glob.glob(os.path.join(ROOT, "records/crc/*/*.json")):
        r = json.load(open(f))
        if r.get("schema") == "crc-bench/1":
            ads.add(r["adapter"]); crcs.add(r["crc"]); boards.add(r["board"])
    return {"libraries": len({lib_of.get(a, a) for a in ads}), "configurations": len(ads),
            "crcs": len(crcs), "boards": len(boards)}


def markdown():
    rb, crc = ring_counts(), crc_counts()
    return f"""# Results

Two kinds of library are tested so far. Each has its own results, method
and records; the numbers of one kind are not compared with the other's.
The kinds are in the order they were added.

## Embedded ring buffers

- **What is measured:** cycles per push and pop and per block, code size, an
  interrupt stress test in which a deliberately broken buffer must be
  caught, and model checks where a library promises lock-free concurrency.
- **Libraries:** {rb['libraries']} (counted by repository), in {rb['configurations']} configurations.
- **Boards:** {rb['boards']}.
- **Results:** [results page](../../RESULTS.md)
- **Method:** [method page](method.md)
- **Comparison page:** [Compare](compare.html)
- **Records:** [`records/`](../../records/README.md)
- **How to repeat:** [Reproduce](reproduce.md)

## CRC calculation in software

- **What is measured:** cycles of one call that computes a CRC, for messages
  of 1 to 1024 bytes, with the cache off and on, and the bytes of flash and
  RAM a configuration takes; every call's result is checked against a
  reference.
- **Libraries:** {crc['libraries']}, in {crc['configurations']} configurations, for {crc['crcs']} CRCs.
- **Boards:** {crc['boards']}.
- **Results:** [results page](results-crc.md)
- **Method:** [method page](method-crc.md)
- **Comparison page:** not on the comparison page yet.
- **Records:** [`records/crc`](../../records/README.md)
- **How to repeat:** [Reproduce, "The CRC records"](reproduce.md#the-crc-records)

The counts are written from the data by
[`site/kinds_page.py`](../kinds_page.py); the site is not built if this
page and the data disagree.
"""


if __name__ == "__main__":
    import sys
    page = os.path.join(ROOT, "site/content/kinds.md")
    if sys.argv[1:] == ["--write"]:
        open(page, "w").write(markdown())
    elif sys.argv[1:] == ["--check"]:
        ok = os.path.exists(page) and open(page).read() == markdown()
        print(f"site/content/kinds.md: {'up to date' if ok else 'not up to date (--write)'}")
        sys.exit(0 if ok else 1)
    else:
        print(markdown(), end="")
