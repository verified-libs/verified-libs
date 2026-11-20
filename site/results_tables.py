#!/usr/bin/env python3
"""Write the speed table of RESULTS.md from the records the comparison page
uses, so the two cannot drift apart.

Usage: python3 site/results_tables.py [--check]

Reads site/data/libs.json for the boards and the names of their benchmark
records (SPSC set and Rust set), and the records themselves from
records/bench/ (site/collect_records.py copies them there). Unlike the
comparison page it lists every configuration of those records, also the ones
held off the page (site/data/hold.txt): the Results page keeps them.
Replaces the text between <!-- table:speed --> and <!-- /table:speed --> in
RESULTS.md. --check: exit 1 if RESULTS.md is not up to date.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "firmware/nrf5340-rb-stress"))
from decode import UNSAFE_BY_OWN_DOCS   # noqa: E402

SHORT = {"nrf5340dk": "nRF5340", "pico2": "Pico 2", "nucleo-g474re": "G474", "nucleo-h723zg": "H723",
         "nucleo-g0b1re": "G0B1", "sam-d20-xpro": "SAM D20"}
ORDER = ["nrf5340dk", "pico2", "nucleo-g474re", "nucleo-h723zg", "nucleo-g0b1re", "sam-d20-xpro"]
SKIP = re.compile(r"^(baseline|mutant|control|broken)|\(broken\)|negative control", re.I)


def mean(res, scen, side):
    v = ((res or {}).get(scen) or {}).get(side) or {}
    return v.get("mean") if v.get("count") else None


def cell(res):
    p, q = mean(res, "single/cache_on", "push"), mean(res, "single/cache_on", "pop")
    b1, b2 = mean(res, "block64/cache_on", "push"), mean(res, "block64/cache_on", "pop")
    if p is None or q is None:
        return "–"
    s = f"{p:.0f} / {q:.0f}"
    if b1 is not None and b2 is not None:
        s += f" · {(b1 + b2) / 128:.1f}"
    return s


def table():
    data = json.load(open(os.path.join(HERE, "data/libs.json")))
    boards = {b["id"]: b for b in data["boards"]}
    own = {l["record_name"] for l in data["libs"] if l.get("own")}
    rows, recs = {}, []
    for bid in ORDER:
        b = boards[bid]
        for key in ("bench", "rust_bench"):
            if not b.get(key):
                continue
            name = b[key]["record"]
            recs.append(name)
            r = json.load(open(os.path.join(ROOT, "records/bench", name)))
            for lib in r["libs"]:
                n = lib["name"]
                if SKIP.search(n) or (key == "rust_bench" and not n.endswith("(Rust)")):
                    continue
                rows.setdefault(n, {})[bid] = cell(lib.get("results"))
    core = {"nrf5340dk": "M33", "pico2": "M33", "nucleo-g474re": "M4", "nucleo-h723zg": "M7",
            "nucleo-g0b1re": "M0+", "sam-d20-xpro": "M0+"}
    head = "| Library | " + " | ".join(f"{SHORT[b]} {core[b]}" for b in ORDER) + " |"
    out = [head, "|---|" + "---|" * len(ORDER)]
    for n in sorted(rows, key=str.lower):
        label = n + (" ⚠" if n in own else "")
        if n in UNSAFE_BY_OWN_DOCS:
            label = f"*{label}* ¹"
        out.append(f"| {label} | " + " | ".join(rows[n].get(b, "–") for b in ORDER) + " |")
    out.append("")
    out.append("¹ Not interrupt-safe by its own documentation or maintainers; measured for comparison only.")
    out.append("")
    out.append("Records (in [`records/bench/`](records/README.md)): " + ", ".join(f"`{x}`" for x in recs) + ".")
    return "\n".join(out)


def main():
    p = os.path.join(ROOT, "RESULTS.md")
    s = open(p).read()
    m = re.search(r"(<!-- table:speed -->\n)(.*?)(\n<!-- /table:speed -->)", s, re.S)
    if not m:
        sys.exit("RESULTS.md has no <!-- table:speed --> ... <!-- /table:speed --> block")
    new = s[:m.start(2)] + table() + s[m.end(2):]
    if "--check" in sys.argv[1:]:
        sys.exit(0 if new == s else 1)
    open(p, "w").write(new)
    print("RESULTS.md: speed table written")


if __name__ == "__main__":
    main()
