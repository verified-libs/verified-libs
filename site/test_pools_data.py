#!/usr/bin/env python3
"""A test that site/data/pools.json gives, for every table of the two pools
results pages, what site/pools_tables.py prints: per board the results
page's one table (bytes, init, the pattern pair, the claims), and on the
page of every pattern the bytes-and-init table and each pattern's table, every configuration's cells in the same
order (the label of our row in its name cell), and the reference free list,
the baseline, as the last row. Also that the committed file is up to date
(pools_data.py), and that a synthetic record is refused under records/pools.

It runs twice: on the committed records (none until the first series is
published: then it checks the "not published yet" state) and on synthetic
records made here by site/pools_synthetic.py in a temporary directory
(made-up numbers, never written into the tree).

Usage: python3 -I site/test_pools_data.py      exit 0: every cell equal
"""
import json
import re
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pools_data      # noqa: E402
import pools_tables as t   # noqa: E402
import pools_isr       # noqa: E402


def cells(line):
    return [x.strip() for x in line.strip().strip("|").split("|")]


def sections(block):
    """board -> {"" (the board's table) / "Bytes and init" / a pattern -> [cells of each data row]}, read from the
    fold-outs: a board's fold-out has the summary "<strong>Board</strong>, ...", its nested one every pattern,
    whose tables follow the bold labels "**Bytes and init.**" and "**`<pattern>`**"."""
    out, cur, sub, depth = {}, None, "", 0
    for line in block.splitlines():
        if line.startswith("<details"):
            depth += 1
        elif line.startswith("</details>"):
            depth -= 1
            sub = ""
        elif line.startswith("<summary><strong>") and depth == 1:
            cur = re.match(r"<summary><strong>(.+?)</strong>", line).group(1)
            out[cur], sub = {"": []}, ""
        elif cur and depth == 2 and line.startswith("**Use from interrupts.**"):
            sub = "Use from interrupts"; out[cur][sub] = []
        elif cur and depth == 2 and line.startswith("**Bytes and init.**"):
            sub = "Bytes and init"; out[cur][sub] = []
        elif cur and depth == 2 and line.startswith("**`"):
            sub = re.match(r"\*\*`(\w+)`\*\*", line).group(1); out[cur][sub] = []
        elif line.startswith("| ") and cur and depth >= 1 and not line.startswith("| Configuration") and not line.startswith("|---"):
            out[cur][sub].append(cells(line))
    return out


def compare(data, summary, every):
    """(cells compared, failures) of data against the page block: per board its table (the pattern t.SUMMARY) and,
    in its nested fold-out, every pattern (summary and every are the same block: the page holds both)."""
    fails, n = [], 0
    if not data["published"]:
        for b in (summary, every):
            if data["boards"] or data["rows"] or data["configurations"] or "not published yet" not in b:
                fails.append("no records: the file or a page does not say the series is not published")
        return n, fails
    cfg = {c["adapter"]: c for c in data["configurations"]}
    claim = lambda c: t.claim_cell(c)   # noqa: E731
    sec_s, sec_a = sections(summary), sections(every)
    for b in data["boards"]:
        if b["name"] not in sec_s or b["name"] not in sec_a:
            fails.append(f"{b['id']}: no section on a page")
            continue
        rows = [r for r in data["rows"] if r["board"] == b["id"]]
        base = next(x for x in data["baseline"] if x["board"] == b["id"])
        bc = claim(data.get("baseline_documented"))
        rng = lambda cyc, keys: [t.range_text(cyc[c][k]) for c, k in keys]   # noqa: E731
        init = [("on", "init"), ("off", "init")]
        pat = lambda s: [(c, f"{s}/{o}") for c in ("on", "off") for o in t.OPS]   # noqa: E731
        # the results page: one table
        page = sec_s[b["name"]][""]
        if len(page) != len(rows) + 1:
            fails.append(f"{b['id']}: {len(page)} rows in the results page's table, {len(rows)} + 1 in the file")
        else:
            for got, r in zip(page, rows):
                c = cfg[r["adapter"]]
                want = [c["lock"], "?" if r["flash_bytes"] is None else str(r["flash_bytes"]),
                        "?" if r["ram_bytes"] is None else str(r["ram_bytes"])] + rng(r["cycles"], init + pat(t.SUMMARY)) \
                    + [claim(c["documented_interrupts"])]
                n += len(want) + 1
                if got[1:] != want:
                    fails.append(f"{b['id']} {r['adapter']} results page: page {got[1:]}, file {want}")
                if not got[0].startswith("[" + c["name"] + "]") or (c["pin"] and not got[0].endswith(" · " + c["pin"])) \
                        or (not c["pin"] and " · " in got[0]):
                    fails.append(f"{b['id']} {r['adapter']}: name or pin differs ({got[0][:70]})")
                if (t.OURS_LABEL in got[0]) != (c["role"] == "ours"):
                    fails.append(f"{b['id']} {r['adapter']}: the label of our row is wrong")
            want = [t.BASE_LABEL, "none", "–", "–"] + rng(base["cycles"], init + pat(t.SUMMARY)) + [bc]
            n += len(want)
            if page[-1] != want:
                fails.append(f"{b['id']}: the baseline row of the results page differs ({page[-1]} / {want})")
        # the page of every pattern: bytes and init, then each pattern
        page = sec_a[b["name"]].get("Bytes and init", [])
        if len(page) != len(rows) + 1:
            fails.append(f"{b['id']}: {len(page)} rows in the bytes table, {len(rows)} + 1 in the file")
            continue
        for got, r in zip(page, rows):
            c = cfg[r["adapter"]]
            want = [c["library"] or "–", c["pin"] or "–", c["lock"], "?" if r["flash_bytes"] is None else str(r["flash_bytes"]),
                    "?" if r["ram_bytes"] is None else str(r["ram_bytes"])] + rng(r["cycles"], init) + [claim(c["documented_interrupts"])]
            n += len(want)
            if got[1:] != want:
                fails.append(f"{b['id']} {r['adapter']} bytes/init: page {got[1:]}, file {want}")
            if not got[0].startswith("[" + c["name"] + "]"):
                fails.append(f"{b['id']} {r['adapter']}: row order differs ({got[0][:50]})")
            if (t.OURS_LABEL in got[0]) != (c["role"] == "ours"):
                fails.append(f"{b['id']} {r['adapter']}: the label of our row is wrong")
        if page[-1][0] != t.BASE_LABEL or page[-1][-3:] != rng(base["cycles"], init) + [bc]:
            fails.append(f"{b['id']}: the baseline row of the bytes table differs ({page[-1]})")
        for s in data["scenarios"][1:]:
            page = sec_a[b["name"]].get(s["key"], [])
            want_rows = [(cfg[r["adapter"]]["name"], r["cycles"]) for r in rows] + [(t.BASE_LABEL, base["cycles"])]
            if len(page) != len(want_rows):
                fails.append(f"{b['id']} {s['key']}: {len(page)} rows on the page, {len(want_rows)} in the file")
                continue
            for got, (name, cyc) in zip(page, want_rows):
                want = rng(cyc, pat(s["key"]))
                n += len(want)
                if got[1:] != want or not (got[0] == name or got[0].startswith("[" + name + "]")):
                    fails.append(f"{b['id']} {s['key']} {name}: page {got}, file {want}")
    return n, fails


def main():
    fails = []
    if open(pools_data.OUT).read() != pools_data.text():
        fails.append("site/data/pools.json is not up to date")
    for pg in t.PAGES.values():
        if len(set(t.page_text(os.path.join(ROOT, pg)))) != 1:
            fails.append(f"{pg} is not up to date")
    n0, f0 = compare(json.load(open(pools_data.OUT)), t.block(), t.block())
    fails += f0
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "pools_synthetic.py"), d], capture_output=True, text=True)
        if p.returncode:
            fails.append("pools_synthetic.py failed: " + p.stdout + p.stderr)
            n1 = 0
        else:
            rd = os.path.join(d, "records")
            data = pools_data.build(rd)
            n1, f1 = compare(data, t.block(rd), t.block(rd))
            fails += f1
            if "SYNTHETIC" not in data or "SYNTHETIC" not in t.block(rd):
                fails.append("synthetic data not marked SYNTHETIC")
            if {r["adapter"] for r in data["rows"] if r["board"] in ("nucleo-g0b1re", "sam-d20-xpro")} & {"adapter_heapless"}:
                fails.append("heapless on a Cortex-M0+ board")
            # a synthetic record under records/pools is refused: load() with the tree's directory pointed at it
            keep = t.RECORDS
            try:
                t.RECORDS = rd
                t.load(rd)
                fails.append("a synthetic record was taken as a record of the tree")
            except SystemExit as e:
                if "synthetic" not in str(e):
                    fails.append(f"refused for another reason: {e}")
            finally:
                t.RECORDS = keep
        # with synthetic records of the concurrency series too: the tables as before, and each board's fold-out
        # "Use from interrupts" saying what the data says
        p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "pools_isr_synthetic.py"), os.path.join(d, "isr")],
                           capture_output=True, text=True)
        if p.returncode:
            fails.append("pools_isr_synthetic.py failed: " + p.stdout + p.stderr)
        else:
            idir = os.path.join(d, "isr")
            data = pools_data.build(rd, isr_dir=idir)
            blk = t.block(rd, isr_dir=idir)
            n2, f2 = compare(data, blk, blk)
            fails += f2
            n1 += n2
            sec = sections(blk)
            names = {c["adapter"]: c["name"] for c in data["configurations"]}
            for b in data["boards"]:
                rows = sec.get(b["name"], {}).get("Use from interrupts", [])
                want = []
                for r in data["rows"]:
                    if r["board"] == b["id"]:   # the row, then another build of its library (site/pools_isr.py VARIANTS)
                        want += [(names[r["adapter"]], r["isr"]["text"])] + [(v["name"], v["text"]) for v in r.get("isr_variants", [])]
                base = next(x for x in data["baseline_isr"] if x["board"] == b["id"])
                want.append((t.BASE_LABEL, base["text"]))
                want += [(x["name"], x["text"]) for x in data["isr_controls"] if x["board"] == b["id"]]
                if len(rows) != len(want):
                    fails.append(f"{b['id']}: {len(rows)} rows in 'Use from interrupts', {len(want)} in the data")
                    continue
                for got, (name, text) in zip(rows, want):
                    n1 += 1
                    # synthetic records lie outside the tree: the cell is the text, not linked
                    if not got[0].startswith(("[" + name + "]", name)) or got[2] != text.replace("|", "\\|"):
                        fails.append(f"{b['id']} {name}: 'Use from interrupts' says {got[2][:80]!r}, the data {text[:80]!r}")
            nvar = sum(len(r.get("isr_variants", [])) for r in data["rows"])
            if nvar != len(data["boards"]) or pools_isr.VARIANT_NOTE not in blk:
                fails.append(f"C_Allocator's lock build: {nvar} rows in the data for {len(data['boards'])} boards, "
                             f"the note {'missing' if pools_isr.VARIANT_NOTE not in blk else 'there'}")
            if "SYNTHETIC: every result of the concurrency series" not in blk or "SYNTHETIC_ISR" not in data:
                fails.append("synthetic results of the concurrency series not marked SYNTHETIC")
            if "Use from interrupts was tested" not in blk or t.ONE_CONTEXT_HTML in blk:
                fails.append("with the concurrency series, the box above the tables is not reworded")
            if [x for x in data["rows"] if x.get("isr") and x["isr"]["class"] == "outside"
                    and any(w in x["isr"]["text"] for w in ("pass", "FAIL", "fail", "caught"))]:
                fails.append("a verdict word for a library outside its documentation")
    for f in fails:
        print("FAIL " + f)
    print(f"committed records: {n0} cells compared; synthetic records: {n1} cells compared; {len(fails)} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
