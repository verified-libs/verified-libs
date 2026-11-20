#!/usr/bin/env python3
"""Summarize an rb-mp-stress campaign (campaign.sh) into a Markdown report.

Usage: summarize.py CAMPAIGN_DIR

A run is valid only if its JSON record exists, the control (an SPSC queue
used with two producers / consumers) was caught and no library starved.
Errors are totalled over valid runs only; invalid and failed runs are listed
with the reason, never counted as passes. Campaigns with COVERAGE=1 (since
2026-11-17): aimed runs (runs.tsv aim 1) are listed apart, and the coverage
of each record (its .cov.json, cov_report.py) is summarized per library.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra"))
try:   # optional further MPSC libraries (extra/)
    from mp_extra import KNOWN_FINDING, SUMMARY_NOTE
except ImportError:
    KNOWN_FINDING, SUMMARY_NOTE = {}, " (the control excluded)"


def main():
    any_extra = [False]   # the held-back libraries only in WITH_EXTRA=1 records: their note only then
    d = sys.argv[1]
    rows = list(csv.DictReader(open(os.path.join(d, "runs.tsv")), delimiter="\t"))
    runs, per_lib, cov = [], {}, {}
    caught = {}           # aimed or not -> [control caught, runs with a record]
    for r in rows:
        rec = r["record"]
        status, reason = "valid", ""
        data = None
        if rec == "-" or not os.path.exists(rec):
            status, reason = "failed", f"no record (exit {r['exit']})"
        else:
            data = json.load(open(rec))
            any_extra[0] |= bool(data.get("with_extra"))
            libs = data["libs"]
            control = next(l for l in libs if l["name"].startswith("control"))
            starved = [l["name"] for l in libs if l["starved"] and not l.get("n/a")]
            if starved:
                status, reason = "invalid", "starved: " + ", ".join(starved)
            elif not (control["errors"] or control["mismatch"]):
                status, reason = "invalid", "control not caught"
            c = caught.setdefault(r.get("aim") == "1", [0, 0])
            c[0] += bool(control["errors"] or control["mismatch"])
            c[1] += 1
        runs.append((r, status, reason))
        if status != "valid":
            continue
        cj = rec[:-5] + ".cov.json"
        if os.path.exists(cj):
            for l in json.load(open(cj))["libs"]:
                key = (l["library"], r["mode"], r.get("aim") == "1")
                cov.setdefault(key, []).append(l)
        for l in data["libs"]:
            if l.get("n/a"):          # cannot be built for this core
                continue
            key = (l["name"], r["mode"])
            a = per_lib.setdefault(key, {"runs": 0, "values": 0, "errors": 0, "mismatch": 0,
                                         "irqs": 0, "full_or_empty_both": 0})
            a["runs"] += 1
            a["values"] += l["transferred"]
            a["errors"] += l["errors"]
            a["mismatch"] += l["mismatch"]
            a["irqs"] += l["irqs_a"] + l["irqs_b"]
            a["full_or_empty_both"] += 1 if (l["full_or_empty_a"] and l["full_or_empty_b"]) else 0

    valid = sum(1 for _, s, _ in runs if s == "valid")
    print(f"# MPSC/SPMC campaign {os.path.basename(d)}\n")
    print(f"Runs: {len(runs)}; valid: {valid}; invalid: "
          f"{sum(1 for _, s, _ in runs if s == 'invalid')}; failed: "
          f"{sum(1 for _, s, _ in runs if s == 'failed')}.\n")
    real_bad = [(k, a) for k, a in per_lib.items()
                if not k[0].startswith("control") and k[0] not in KNOWN_FINDING
                and (a["errors"] or a["mismatch"])]
    if real_bad:
        print("**ERRORS in a library in its documented mode:** "
              + ", ".join(f"{k[0]} ({k[1]})" for k, _ in real_bad) + "\n")
    else:
        print("**No errors in any library in its documented mode across all valid runs**"
              + (SUMMARY_NOTE if any_extra[0] else " (the control excluded)") + ".\n")

    print("## Per library and mode (valid runs)\n")
    print("| Library | Mode | Runs | Values | Interrupts | Errors | Lost + duplicated | Both interrupts hit full/empty |")
    print("|---|---|---|---|---|---|---|---|")
    for (name, mode), a in sorted(per_lib.items(), key=lambda x: (x[0][1], x[0][0])):
        print(f"| {name} | {mode} | {a['runs']} | {a['values']:,} | {a['irqs']:,} | {a['errors']:,} | "
              f"{a['mismatch']:,} | {a['full_or_empty_both']} of {a['runs']} |")

    if any(k for k in caught):
        print("\nControl caught: " + "; ".join(f"{'aimed' if k else 'random'} interrupts {c[0]} of {c[1]} runs"
                                              for k, c in sorted(caught.items())) + ".")
    if cov:
        print("\n## Coverage (valid runs)\n")
        print("Where the interrupts landed (cov_report.py): the share in the library's code, and the "
              "instruction boundaries of its push/pop where an interrupt can land (not masked, in a "
              "block that ran): interrupted at least 10 times in the weakest run, the median count "
              "per boundary over the runs' medians, and the most boundaries in blocks never "
              "interrupted in a run (likely paths the test did not take, e.g. a retry).\n")
        print("| Library | Mode | Interrupts | Runs | In library code | Boundaries >= 10x (weakest run) "
              "| Median per boundary | Never-interrupted blocks (boundaries) |")
        print("|---|---|---|---|---|---|---|---|")
        for (name, mode, aimed), ls in sorted(cov.items(), key=lambda x: (x[0][1], x[0][0], x[0][2])):
            share = sum(l["in_library"] for l in ls) / max(sum(l["interrupts"] for l in ls), 1)
            weak = min(ls, key=lambda l: l["hit10"] / max(l["executed"], 1))
            med = sorted(l.get("median", 0) for l in ls)[len(ls) // 2]
            print(f"| {name} | {mode} | {'aimed' if aimed else 'random'} | {len(ls)} | {100 * share:.1f} % | "
                  f"{weak['hit10']} of {weak['executed']} | {med:,.0f} | {max(l['unseen'] for l in ls)} |")

    print("\n## Runs\n")
    print("| Run | Start (UTC) | Mode | Prescaler | Interrupts | Code | Values/lib | Seeds main / A / B | Status |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r, s, why in runs:
        print(f"| {r['run']} | {r['start_utc']} | {r['mode']} | {r['prescaler']} | "
              f"{'aimed' if r.get('aim') == '1' else 'random'} | {r['code']} | "
              f"{int(r['transfers']):,} | {r['main_seed']} / {r['seed_a']} / {r['seed_b']} | "
              f"{s}{' (' + why + ')' if why else ''} |")


if __name__ == "__main__":
    main()
