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
import series_info   # noqa: E402

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


SPAN = {}   # filled by table(): every 1-byte push and pop, and every block number, of the table


def summary():
    """The fold-out's summary line of the speed table: what is inside and the span of its numbers (no order)."""
    n = len(TABLE_ROWS)
    return (f"<strong>Speed on six boards</strong>: {n} configurations, one byte {min(SPAN['push']):.0f} to "
            f"{max(SPAN['push']):.0f} cycles per push or pop, 64-byte blocks {min(SPAN['block']):.1f} to "
            f"{max(SPAN['block']):.1f} cycles per byte (code in flash, cache on)")


TABLE_ROWS = []


def table():
    SPAN.clear()
    TABLE_ROWS.clear()
    data = json.load(open(os.path.join(HERE, "data/libs.json")))
    ver = versions()
    own = {l["record_name"] for l in data["libs"] if l.get("own")}
    rows, commits, method = {}, set(), {}
    for bid in ORDER:
        d = os.path.join(ROOT, "records/bench-v2", gen_libdata.FW[bid])
        for name in sorted(os.listdir(d)):
            r = json.load(open(os.path.join(d, name)))
            m = method.setdefault(bid, {"v": set(), "clock": set(), "commits": set(), "name": r["board"]})
            m["v"].add(series_info.method_version(r["schema"])); m["clock"].add(r["clock_hz"]); m["commits"].add(r["bench_commit"])
            if MODES.search(r["adapter"]) or SKIP.search(r["name"]):
                continue
            commits.add(r["bench_commit"])
            sp = gen_libdata.speed_v2(r)
            rows.setdefault(r["name"], {})[bid] = cell(sp)
            if sp and sp.get("push") is not None:
                SPAN.setdefault("push", []).extend([sp["push"], sp["pop"]])
                if sp.get("block") is not None:
                    SPAN.setdefault("block", []).append(sp["block"])
    core = {"nrf5340dk": "M33", "pico2": "M33", "nucleo-g474re": "M4", "nucleo-h723zg": "M7",
            "nucleo-g0b1re": "M0+", "sam-d20-xpro": "M0+"}
    head = "| Library | Version · commit | " + " | ".join(f"{SHORT[b]} {core[b]}" for b in ORDER) + " |"
    out = [head, "|---|---|" + "---|" * len(ORDER)]
    TABLE_ROWS.extend(rows)
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
    out.append("")
    out.append("The method version and the clock of each board's records (DECISIONS.md, 2026-11-26):")
    out.append("")
    for bid in ORDER:
        m = method[bid]
        if len(m["v"]) != 1 or len(m["clock"]) != 1:
            sys.exit(f"records/bench-v2/{gen_libdata.FW[bid]}: records of more than one method version or clock")
        prefix = f"bench-v2/{gen_libdata.FW[bid]}/"
        out.append(f"- {m['name']}: " + series_info.method_text(
            min(m["v"]), min(m["clock"]), series_info.archived_for(prefix, sorted(m["commits"])),
            series_info.unchanged_under_3(prefix), link=True))
    return "\n".join(out)


def main():
    p = os.path.join(ROOT, "RESULTS.md")
    s = open(p).read()
    m = re.search(r"(<!-- table:speed -->\n)(.*?)(\n<!-- /table:speed -->)", s, re.S)
    if not m:
        sys.exit("RESULTS.md has no <!-- table:speed --> ... <!-- /table:speed --> block")
    new = s[:m.start(2)] + table() + s[m.end(2):]
    # the summary line of the speed table's fold-out (the line after its <details>), from the same records
    new, k = re.subn(r'(<details id="speed-on-six-boards" markdown="1">\n)<summary>.*?</summary>',
                     lambda x: x.group(1) + "<summary>" + summary() + "</summary>", new)
    if k != 1:
        sys.exit('RESULTS.md has no <details id="speed-on-six-boards" markdown="1"> with a <summary> line after it')
    if "--check" in sys.argv[1:]:
        sys.exit(0 if new == s else 1)
    open(p, "w").write(new)
    print("RESULTS.md: speed table written")


if __name__ == "__main__":
    main()
