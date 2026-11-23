#!/usr/bin/env python3
"""Write the speed table of RESULTS.md from the records the comparison page
uses, so the two cannot drift apart.

Usage: python3 site/results_tables.py [--check]

Reads the records of benchmark version 2 (records/bench-v2/<board>/, one
record per configuration; site/gen_libdata.py reads the same files for the
comparison page and its speed_v2() gives the numbers here too): the value
with the image at placement 0, first pass. Unlike the comparison page it
lists every SPSC configuration of those records, also the ones held off the
page: the Results page keeps them. The modes for more than one producer or
consumer and Nordic's nrf_ringbuf (one board, pinned by nrf5-sdk.lock) are
on the comparison page only. The second column is the tested
version: the release from site/data/libs-meta.json, where the library has
one, and the pinned commit from firmware/nrf5340-rb-bench/libs.lock.
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
sys.path.insert(0, HERE)
import gen_libdata   # noqa: E402

SHORT = {"nrf5340dk": "nRF5340", "pico2": "Pico 2", "nucleo-g474re": "G474", "nucleo-h723zg": "H723",
         "nucleo-g0b1re": "G0B1", "sam-d20-xpro": "SAM D20"}
ORDER = ["nrf5340dk", "pico2", "nucleo-g474re", "nucleo-h723zg", "nucleo-g0b1re", "sam-d20-xpro"]
SKIP = re.compile(r"^(baseline|mutant|control|broken)|\(broken\)|negative control", re.I)


# not in the table: the adapters of the modes for more than one producer or consumer, and Nordic's nrf_ringbuf
MODES = re.compile(r"_(mpsc|spmc|mpmc)$|^adapter_nrf_ringbuf$")


def cell(sp):
    if not sp or sp.get("push") is None or sp.get("pop") is None:
        return "–"
    s = f"{sp['push']:.0f} / {sp['pop']:.0f}"
    if sp.get("block") is not None:
        s += f" · {sp['block']:.1f}"
    return s


def versions():
    """Tested version of each configuration: the release, where the library
    has one (site/data/libs-meta.json), and the first eight digits of the
    commit it is pinned to (libs.lock)."""
    lock = {}
    for line in open(os.path.join(ROOT, "firmware/nrf5340-rb-bench/libs.lock")):
        f = line.split()
        if len(f) >= 3 and not line.startswith("#"):
            lock[f[0]] = f[2]
    out = {}
    for name, m in json.load(open(os.path.join(HERE, "data/libs-meta.json"))).items():
        if not isinstance(m, dict) or m.get("lock") not in lock:
            continue
        pin = f"`{lock[m['lock']][:8]}`"
        out[name] = f"{m['version']} · {pin}" if m.get("version") else pin
    return out


def table():
    data = json.load(open(os.path.join(HERE, "data/libs.json")))
    ver = versions()
    own = {l["record_name"] for l in data["libs"] if l.get("own")}
    rows, commits = {}, set()
    for bid in ORDER:
        d = os.path.join(ROOT, "records/bench-v2", gen_libdata.FW[bid])
        for name in sorted(os.listdir(d)):
            r = json.load(open(os.path.join(d, name)))
            if MODES.search(r["adapter"]) or SKIP.search(r["name"]):
                continue
            commits.add(r["bench_commit"])
            rows.setdefault(r["name"], {})[bid] = cell(gen_libdata.speed_v2(r))
    core = {"nrf5340dk": "M33", "pico2": "M33", "nucleo-g474re": "M4", "nucleo-h723zg": "M7",
            "nucleo-g0b1re": "M0+", "sam-d20-xpro": "M0+"}
    head = "| Library | Version · commit | " + " | ".join(f"{SHORT[b]} {core[b]}" for b in ORDER) + " |"
    out = [head, "|---|---|" + "---|" * len(ORDER)]
    for n in sorted(rows, key=str.lower):
        label = n + (" ⚠" if n in own else "")
        if n in UNSAFE_BY_OWN_DOCS:
            label = f"*{label}* ¹"
        if n not in ver:
            sys.exit(f"no pinned commit found for {n!r} (site/data/libs-meta.json, libs.lock)")
        out.append(f"| {label} | {ver[n]} | " + " | ".join(rows[n].get(b, "–") for b in ORDER) + " |")
    out.append("")
    out.append("¹ Not interrupt-safe by its own documentation or maintainers; measured for comparison only.")
    out.append("")
    out.append("Records: one per board and configuration in [`records/bench-v2/`](records/README.md), made at commit "
               + ", ".join(f"`{c}`" for c in sorted(commits)) + ".")
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
