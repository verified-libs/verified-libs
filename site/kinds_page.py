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
    "crc", boards = the distinct "board"; the board's CRC unit (the class of
    step 11 of kinds/crc/README.md, site/crc_tables.py) is not a library and
    is counted apart, by the boards that have one;
  - fixed-block memory pools: the records under records/pools (schema
    pools-bench/1, read by site/pools_tables.py): configurations = the
    distinct adapters of the libraries, libraries = the distinct libraries
    of those (the table "The set" of kinds/pools/README.md), boards = the
    distinct "board"; our row with interrupts off is not a library and is
    not counted. With no records the block says the first series is not
    published yet.

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
    import sys
    sys.path.insert(0, os.path.join(ROOT, "site"))
    import crc_tables
    _, cls, _ = crc_tables.kind_tables()
    ads, crcs, boards, hw_boards = set(), set(), set(), set()
    for f in glob.glob(os.path.join(ROOT, "records/crc/*/*.json")):
        r = json.load(open(f))
        if r.get("schema") in ("crc-bench/1", "crc-bench/2"):
            if crc_tables.is_hw(cls, r["adapter"]):
                hw_boards.add(r["board"])
                continue
            ads.add(r["adapter"]); crcs.add(r["crc"]); boards.add(r["board"])
    return {"libraries": len({lib_of.get(a, a) for a in ads}), "configurations": len(ads),
            "crcs": len(crcs), "boards": len(boards), "hw_boards": len(hw_boards)}


def pools_counts():
    import sys
    sys.path.insert(0, os.path.join(ROOT, "site"))
    import pools_tables
    recs, _ = pools_tables.load()
    _, cfg, sets = pools_tables.kind_meta()
    libs = [r for _, r in recs if pools_tables.role(r["adapter"]) == "library"]
    return {"records": len(recs), "configurations": len({r["adapter"] for r in libs}),
            "libraries": len({(sets.get(r["name"]) or {}).get("library") or r["adapter"] for r in libs}),
            "boards": len({r["board"] for _, r in recs})}


def pools_block(p):
    if not p["records"]:
        counts = ("- **Status:** the first board series is not published yet; the pages below fill from its\n"
                  "  records when it is.\n")
    else:
        counts = (f"- **Libraries:** {p['libraries']}, in {p['configurations']} configurations, and a row of ours "
                  f"(not a library).\n- **Boards:** {p['boards']}.\n")
    return f"""## Fixed-block memory pools

- **What is measured:** cycles of alloc and free of one block size (32
  blocks of 32 bytes) in six scenarios and of creating the pool, with the
  cache off and on, and the bytes of flash and RAM it takes; every call is
  checked on the board. Measured in one context. Use from interrupts is
  tested in a series of its own, the concurrency series: an interrupt at
  every cycle of a call, with controls that must be caught.
{counts}- **Results:** [results page](results-pools.md)
- **Method:** [method page](method-pools.md)
- **Comparison page:** [Compare](compare-pools.html)
- **Records:** [`records/pools`](../../records/README.md)
- **How to repeat:** [Reproduce, "The pools records"](reproduce.md#the-pools-records)
"""


def markdown():
    rb, crc, pools = ring_counts(), crc_counts(), pools_counts()
    return f"""# Results

Three kinds of library are tested so far. Each has its own results, method
and records; the numbers of one kind are not compared with another's.
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

## CRC calculation

- **What is measured:** cycles of one call that computes a CRC, for messages
  of 1 to 1024 bytes, with the cache off and on, and the bytes of flash and
  RAM it takes; by libraries that compute the CRC in software and, on the
  boards that have one, by the board's CRC unit as a row beside them. Every
  call's result is checked against a reference.
- **Libraries:** {crc['libraries']}, in {crc['configurations']} configurations, for {crc['crcs']} CRCs.
- **The board's CRC unit:** on {crc['hw_boards']} boards, driven by our code (not a library), a row beside the libraries.
- **Boards:** {crc['boards']}.
- **Results:** [results page](results-crc.md)
- **Method:** [method page](method-crc.md)
- **Comparison page:** [Compare](compare-crc.html)
- **Records:** [`records/crc`](../../records/README.md)
- **How to repeat:** [Reproduce, "The CRC records"](reproduce.md#the-crc-records)

{pools_block(pools)}
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
