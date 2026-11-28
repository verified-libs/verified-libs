#!/usr/bin/env python3
"""Write site/data/pools.json, the data of the pools kind for the comparison
page and the MCP server, from the records under records/pools, so that it
cannot drift from them: site/build.py refuses to build if the file is not
what this program writes. As site/crc_data.py for the CRC kind.

Usage: python3 -I site/pools_data.py [--write | --check]
         (no argument: print the file; --write: write it; --check: exit 1 if
         it is not up to date)
       python3 -I site/pools_data.py --records DIR --out FILE [--claims FILE] [--isr DIR]
         (another records directory, such as synthetic records from
         site/pools_synthetic.py, into a file outside site/data; never
         site/data/pools.json; --isr: the concurrency series' records from
         another directory, such as synthetic ones from
         site/pools_isr_synthetic.py)

With no records the file says so ("published": false) and holds no boards,
configurations or rows: the pages then say the series is not published yet.
Where each field comes from is in ABOUT below, which the file carries.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import crc_data      # noqa: E402  (the board ids of the site)
import pools_isr     # noqa: E402
import pools_tables as t   # noqa: E402

OUT = os.path.join(ROOT, "site/data/pools.json")
CLAIMS = t.CLAIMS   # the kind's own file: who, documented, source
LANG = {"c": "C", "cpp": "C++", "rust": "Rust"}
ABOUT = {
    "published": "false while there are no records under records/pools: the first board series is not published yet",
    "boards": "per board directory of records/pools (records_dir): id (the board's id on the site's other kinds), the "
              "record's board, board_decoded, core and clock_hz; note_cache_off: the sentence the CRC results page puts "
              "above the board's cache-off numbers (site/crc_tables.py, before_off), or null",
    "scenarios": "the scenarios of kinds/pools/README.md (\"The image\"), with what is timed, in one line each; "
                 "'init' is one call",
    "configurations": "per adapter, in the order of kinds/pools/configs.txt: its name (the record's), language (column 2), "
                      "and from the table \"The set\" of kinds/pools/README.md its library, pin, licence and the lock as "
                      "built; role: 'library', or 'ours' for our reference free list with interrupts off (not a library, "
                      "labelled in its name cell every time; scored like any row; a filter on the kind of row leaves it "
                      "out); documented_interrupts: what the library documents about use from interrupts, with its "
                      "source (kinds/pools/claims.tsv): shown as documented, NOT tested (the series is one context), and "
                      "used in no filter and no score",
    "baseline_documented": "the claims file's row of the baseline (adapter_ref), shown in the baseline's row",
    "rows": "per board and configuration: flash_bytes (the record's sizes.flash_bytes: code and constant data) and "
            "ram_bytes (the record's sizes.ram_overhead_bytes: RAM beyond the 1056 bytes of blocks and canaries; "
            "kinds/pools/README.md, \"Sizes\"), the record's path, and cycles",
    "cycles": "cycles[cache][key]: [min, max] over the eight placements, first pass, of the mean of the scenario's calls "
              "(the first call included), in cycles, the counter-read overhead subtracted; key 'init' (one call) or "
              "'<scenario>/<alloc|free>'; null where the scenario has no such call (empty/free)",
    "baseline": "per board: the reference free list (ours, not a library), timed in the same images (the records' "
                "baseline), cycles over all images of the board's library configurations",
    "ranges": "a difference between two rows is a difference only where their ranges do not overlap "
              "(method-crc.html#log-2026-11-25-ranges); the rows are in the order of kinds/pools/configs.txt, not ranked",
    "not_here": "the second pass and the minimum, maximum and first call of each scenario: in the records",
}


def claims(path):
    """The kind's claims file, as site/pools_tables.py reads it for the results pages."""
    return t.claims(path)


ISR_ABOUT = {
    "configurations": ABOUT["configurations"].replace(
        "shown as documented, NOT tested (the series is one context), and used in no filter and no score",
        "shown as documented (the timing series is one context; whether it holds is tested by the concurrency series, "
        "each row's 'isr'), and used in no score"),
    "isr": "per row: the concurrency series (records/pools-isr, method-pools.html#log-2026-11-27-isr): class "
           "('within' its documentation, 'ours', 'outside' its documentation, 'control'); result: for 'within' and "
           "'ours' passed or what was observed, for 'outside' only what was observed (never a verdict: the library was "
           "used in a way it does not document), for a control caught or not; trials; observed (kinds); "
           "irq_wait_cycles {off, on}, where the configuration takes interrupts off as built: the longest time an "
           "interrupt waited; coverage [instructions reached, instructions]; record. Used in no score; the comparison "
           "page offers a filter on it. null where the series has no record of the row",
    "isr_variants": "per row, where the series has one: another build of the same library, a configuration of its "
                    "own in the concurrency series and not the build the row's numbers come from (C_Allocator with its "
                    "lock option ALLOC_LOCK_CMSIS_RTOS2): adapter, name, documented_interrupts (kinds/pools/claims.tsv), "
                    "and its result in the form of 'isr'",
    "baseline_isr": "per board: the reference free list without a lock, which the concurrency series runs as a "
                    "control (it must be caught), in the form of 'isr'",
    "isr_controls": "per board: our two broken interrupts-off builds of the reference, the series' other controls",
}


def build(rdir=None, claims_path=None, isr_dir=None):
    recs, syn = t.load(rdir)
    isr, isr_syn = pools_isr.load(isr_dir)
    ads, cfg, sets = t.kind_meta()
    cl = claims(claims_path or CLAIMS)
    by_dir = {}
    for f, r in recs:
        by_dir[(os.path.basename(os.path.dirname(f)), r["adapter"])] = (f, r)
    dirs = sorted({d for d, _ in by_dir}, key=lambda d: next(
        (t.PAGE_ORDER.index(r["board"]) if r["board"] in t.PAGE_ORDER else 99 for (b, _), (_, r) in by_dir.items() if b == d)))
    boards = []
    for d in dirs:
        r = next(r for (b, _), (_, r) in by_dir.items() if b == d)
        boards.append({"id": crc_data.SITE_ID.get(d, d), "records_dir": d, "name": r["board"],
                       "board_decoded": r["board_decoded"], "core": r["core"], "clock_hz": r["clock_hz"],
                       "note_cache_off": t.crc_tables.before_off(r["board"], r["clock_hz"])})
    configs = []
    for ad in ads:
        if not any(a == ad for _, a in by_dir):
            continue
        s = sets.get(cfg[ad]["name"], {})
        c = {"adapter": ad, "name": cfg[ad]["name"], "lang": LANG[cfg[ad]["lang"]], "library": s.get("library"),
             "pin": s.get("pin"), "licence": s.get("licence"), "lock": s.get("lock"), "role": t.role(ad),
             "documented_interrupts": {k: v for k, v in cl[ad].items() if k != "who"} if ad in cl else None}
        if ad in cl and cl[ad]["who"] != t.role(ad):
            sys.exit(f"{CLAIMS}: {ad} is '{cl[ad]['who']}' there, '{t.role(ad)}' here")
        if c["role"] == "ours":
            c["note"] = t.OURS_LABEL
        configs.append(c)
    rows, baseline = [], []
    for b in boards:
        base = {}
        for c in configs:
            if (b["records_dir"], c["adapter"]) not in by_dir:
                continue
            f, r = by_dir[(b["records_dir"], c["adapter"])]
            pp = t.per_place(r)
            fl, ram = t.sizes_of(r)
            rows.append({"board": b["id"], "adapter": c["adapter"], "flash_bytes": fl, "ram_bytes": ram,
                         "record": os.path.relpath(f, ROOT) if not syn else "records/pools/" + os.path.relpath(f, rdir),
                         "cycles": t.ranges({p: x["results"] for p, x in pp.items()})})
            if isr:
                k = (b["records_dir"], c["adapter"])
                rows[-1]["isr"] = pools_isr.summary(k[0], *isr[k], rdir=isr_dir) if k in isr else None
                var = [dict({"adapter": va, "name": vname,
                             "documented_interrupts": {x: y for x, y in cl[va].items() if x != "who"} if va in cl else None},
                            **pools_isr.summary(k[0], *isr[(k[0], va)], rdir=isr_dir))
                       for va, vname in pools_isr.VARIANTS.get(c["adapter"], []) if (k[0], va) in isr]
                if var:
                    rows[-1]["isr_variants"] = var
            if c["role"] == "library":
                base.update({(c["adapter"], p): x["baseline"] for p, x in pp.items()})
        if base:
            baseline.append({"board": b["id"], "cycles": t.ranges(base)})
    out = {"schema": "pools-data/1"}
    if syn:
        out["SYNTHETIC"] = "every number in this file is made up (site/pools_synthetic.py); none is a measurement"
    if isr_syn:
        out["SYNTHETIC_ISR"] = ("every result of the concurrency series in this file is made up "
                                "(site/pools_isr_synthetic.py); none is a measurement")
    out.update({"about": ABOUT, "published": bool(recs),
                "source": {"records": "records/pools", "commits": sorted({r["bench_commit"] for _, r in recs}),
                           "toolchain_image": sorted({r["toolchain_image"] for _, r in recs})},
                "blocks": 32, "block_size": 32,
                "scenarios": [{"key": "init", "text": t.INIT_TEXT}] + [{"key": k, "text": x} for k, x in t.SCENARIOS],
                "boards": boards, "configurations": configs, "rows": rows, "baseline": baseline,
                "baseline_documented": ({k: v for k, v in cl["adapter_ref"].items() if k != "who"}
                                        if recs and "adapter_ref" in cl else None)})
    if isr:   # only with records of the concurrency series: without them the file is as before
        out["about"] = dict(ABOUT, **{k: v for k, v in ISR_ABOUT.items()
                                      if k != "isr_variants" or any(r.get("isr_variants") for r in rows)})
        out["isr_source"] = {"records": "records/pools-isr", "commits": sorted({r["bench_commit"] for _, r in isr.values()}),
                             "board_notes": {b["id"]: pools_isr.BOARD_NOTE[b["records_dir"]] for b in boards
                                             if b["records_dir"] in pools_isr.BOARD_NOTE
                                             and any(k[0] == b["records_dir"] for k in isr)}}
        out["baseline_isr"] = [{"board": b["id"], **pools_isr.summary(b["records_dir"], *isr[(b["records_dir"], "adapter_ref")], rdir=isr_dir)}
                               for b in boards if (b["records_dir"], "adapter_ref") in isr]
        out["isr_controls"] = [{"board": b["id"], "adapter": a, "name": pools_isr.CONTROL_TEXT[a],
                                **pools_isr.summary(b["records_dir"], *isr[(b["records_dir"], a)], rdir=isr_dir)}
                               for b in boards for a in pools_isr.CONTROLS[1:] if (b["records_dir"], a) in isr]
    return out


def text(rdir=None, claims_path=None, isr_dir=None):
    return json.dumps(build(rdir, claims_path, isr_dir), indent=1, ensure_ascii=False) + "\n"


def main():
    a = sys.argv[1:]
    if a == ["--write"]:
        open(OUT, "w").write(text())
    elif a == ["--check"]:
        ok = os.path.exists(OUT) and open(OUT).read() == text()
        print(f"site/data/pools.json: {'up to date' if ok else 'not up to date (python3 -I site/pools_data.py --write)'}")
        return 0 if ok else 1
    elif not a:
        print(text(), end="")
    elif "--records" in a and "--out" in a:
        opt = dict(zip(a[::2], a[1::2]))
        if set(opt) - {"--records", "--out", "--claims", "--isr"} or len(a) % 2:
            sys.exit(__doc__)
        out = os.path.abspath(opt["--out"])
        if os.path.commonpath([out, os.path.join(ROOT, "site")]) == os.path.join(ROOT, "site") or \
                os.path.commonpath([out, os.path.join(ROOT, "records")]) == os.path.join(ROOT, "records"):
            sys.exit("refused: --out is for a file outside site/ and records/")
        open(out, "w").write(text(opt["--records"], opt.get("--claims"), opt.get("--isr")))
    else:
        sys.exit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
