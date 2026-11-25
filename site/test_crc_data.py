#!/usr/bin/env python3
"""A test that site/data/crc.json gives, for the columns of the CRC results
page, what site/crc_tables.py prints: per board, CRC, cache and
configuration the class, the table place, flash and RAM bytes, the 16-byte
figure and the per-byte figure (offset 0, ranges over the placements, as the
page formats them). Also that the file is up to date (crc_data.py).

Usage: python3 -I site/test_crc_data.py      exit 0: every cell equal
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import crc_data     # noqa: E402
import crc_tables   # noqa: E402


def fmt_range(r, f):
    if r is None:
        return "–"
    lo, hi = f(r[0]), f(r[1])
    return lo if lo == hi else f"{lo}–{hi}"


def main():
    data = json.load(open(crc_data.OUT))
    fails = 0
    if open(crc_data.OUT).read() != crc_data.text():
        print("FAIL site/data/crc.json is not up to date"); fails += 1
    cfg = {c["adapter"]: c for c in data["configurations"]}
    bname = {b["id"]: b for b in data["boards"]}
    ads, cls, sizes = crc_tables.kind_tables()
    recs = {}
    for row in data["rows"]:
        rec = json.load(open(os.path.join(ROOT, row["record"])))
        recs[(row["board"], rec["crc"], row["adapter"])] = (rec, row)
    cells = 0
    for b in data["boards"]:
        for crc in data["crcs"]:
            pairs = [recs[(b["id"], crc, ad)] for ad in ads if (b["id"], crc, ad) in recs]
            if not pairs:
                continue
            rows = [p[0] for p in pairs]
            core = crc_tables.CORE.get(rows[0]["core"].split("(")[-1].rstrip(")"), rows[0]["core"])
            for cache in ("on", "off"):
                out = []
                crc_tables.table(b["name"], crc, rows, core, cls, sizes, 0, cache, "1", out, None, False, True)
                printed = [l for l in out if l.startswith("| ") and not l.startswith("| Configuration")]
                if len(printed) != len(pairs):
                    print(f"FAIL {b['id']} {crc} cache {cache}: {len(printed)} rows printed, {len(pairs)} in the file")
                    fails += 1
                    continue
                for line, (rec, row) in zip(printed, pairs):
                    got = [x.strip() for x in line.strip("|").split("|")][1:]
                    c = cfg[row["adapter"]]
                    want = [c["class"], c["table"], str(row["flash_bytes"]), str(row["ram_bytes"]),
                            fmt_range(row["cycles"][cache]["0"]["16"], lambda v: f"{v:.0f}"),
                            fmt_range(row["per_byte"][cache]["0"], lambda v: f"{v:.1f}")]
                    cells += len(want)
                    if got != want:
                        print(f"FAIL {b['id']} {row['adapter']} cache {cache}: page {got}, file {want}")
                        fails += 1
                    if not line.startswith(f"| {rec['name']}"):
                        print(f"FAIL {b['id']} {row['adapter']}: row order differs ({line[:60]})")
                        fails += 1
    print(f"{cells} cells of {len(data['rows'])} rows compared, cache on and off; {fails} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
