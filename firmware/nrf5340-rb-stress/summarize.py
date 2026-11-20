#!/usr/bin/env python3
"""Summarise a stress campaign (overnight.sh) into a markdown report.

Usage: summarize.py CAMPAIGN_DIR    (report on stdout; safe to run any time)

Reads runs.tsv and every *-rb-stress-*.json in the directory. A run
counts as valid only if it finished and its negative control was caught in
every direction where its bug can show (main_to_isr for single bytes, both
directions for blocks).
"""
import csv
import glob
import json
import os
import sys
from collections import defaultdict

CONTROL = "broken (negative control)"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import MULTICORE_DOCUMENTED, MUTANTS, UNSAFE_BY_OWN_DOCS   # noqa: E402  (SMP documented mode; mutants.c; unsafe by docs)
DIRS = ["isr_to_main", "main_to_isr"]


def control_caught(rec):
    """The negative control showed errors where its bug can show: main_to_isr
    for single bytes, both directions for blocks, either direction in SMP."""
    ctrl = next(l for l in rec["libs"] if l["name"] == CONTROL)
    if rec.get("smp", False):
        return any(ctrl[x]["errors"] > 0 for x in DIRS)
    must = DIRS if rec.get("mode", "").startswith("blocks") else ["main_to_isr"]
    return all(ctrl[x]["errors"] > 0 for x in must)


def harness_fault(rec):
    """A run whose result the test harness itself spoiled, or None. RP2350
    SMP with one image per library and code in SRAM, before the startup
    code reset core 1 (2026-11-16, README "RP2350"): core 1 went on running
    the previous library's code while core 0 copied the next image over it."""
    if (rec.get("smp") and rec.get("code_location") == "sram"
            and (rec.get("images") or {}).get("kind") == "per_library"
            and rec.get("time", "") < "2026-11-16T06:00:00Z"):
        return "harness: core 1 not reset"
    return None


def analyse(d):
    """runs (runs.tsv rows), records {path: record}, valid / invalid /
    unfinished run rows, and per-library aggregates over the valid runs."""
    with open(os.path.join(d, "runs.tsv")) as fh:
        runs = list(csv.DictReader(fh, delimiter="\t"))
    records = {}
    for path in glob.glob(os.path.join(d, "*-rb-stress-*.json")):
        with open(path) as fh:
            records[path] = json.load(fh)

    agg = defaultdict(lambda: {"runs": 0, "bytes": 0, "irqs": 0, "errors": 0, "runs_with_errors": [], "starved": 0,
                               "dnf": 0, "runs_dnf": [],
                               "full": {x: 0 for x in DIRS}, "empty": {x: 0 for x in DIRS}})
    valid, invalid, unfinished = [], [], []
    for r in runs:
        rec = records.get(r["record"])
        if rec is None:
            unfinished.append(r)
            continue
        smp = rec.get("smp", False)
        if not control_caught(rec) or harness_fault(rec):
            invalid.append(r)
            continue
        valid.append(r)
        for lib in rec["libs"]:
            if lib["name"] == CONTROL or lib.get("n/a") or lib["name"] in MUTANTS:
                continue
            # SMP runs (RP2350, other side on core 1) are kept apart; there
            # only MULTICORE_DOCUMENTED libraries are in their documented mode.
            tags = []
            if rec.get("sweep") is not None:   # sweep: trials, not a byte stream
                tags.append("sweep")
            if smp:
                tags.append("SMP" if lib["name"] in MULTICORE_DOCUMENTED else "SMP, single-core design")
            key = lib["name"] + (f" [{', '.join(tags)}]" if tags else "")
            a = agg[key]
            a["runs"] += 1
            # one library per reset (run.sh PER_LIB=1): a library that did not
            # finish in its time limit; its counters are what it got to
            if lib.get("did_not_finish"):
                a["dnf"] += 1
                a["runs_dnf"].append(r["run"])
            errs = 0
            for x in DIRS:
                a["bytes"] += lib[x]["transferred"]
                a["irqs"] += lib[x]["irqs"]
                errs += lib[x]["errors"]
                a["full"][x] += lib[x]["full_events"] > 0
                a["empty"][x] += lib[x]["empty_events"] > 0
            a["errors"] += errs
            a["starved"] += sum(1 for s in rec.get("starved", []) if s.startswith(lib["name"] + " / "))
            if errs:
                a["runs_with_errors"].append(r["run"])
    return runs, records, valid, invalid, unfinished, agg


def mutant_table(rows, records, valid):
    """Per mutant and run mode (runs.tsv mode): in how many valid runs it
    was caught, per direction. {(mutant, mode): [runs, caught i2m, caught m2i]}"""
    for r in valid:
        rec = records[r["record"]]
        for lib in rec["libs"]:
            if lib["name"] in MUTANTS and not lib.get("n/a"):
                c = rows.setdefault((lib["name"], r["mode"]), [0, 0, 0])
                c[0] += 1
                c[1] += lib["isr_to_main"]["errors"] > 0
                c[2] += lib["main_to_isr"]["errors"] > 0
    return rows


def real_errors(agg):
    """Libraries with errors, leaving out configurations that are not
    ISR-safe by their own docs and single-core designs in SMP runs."""
    return {n: a for n, a in agg.items()
            if a["errors"] and n.split(" [")[0] not in UNSAFE_BY_OWN_DOCS and "single-core design" not in n}


def main():
    d = sys.argv[1]
    runs, records, valid, invalid, unfinished, agg = analyse(d)
    print(f"# Stress campaign {os.path.basename(d)}\n")
    retries = sum(1 for r in runs if r["run"].endswith("r"))
    cycles = sum(1 for r in runs if r.get("power_cycled") == "yes")
    print(f"Runs started: {len(runs)}; valid: {len(valid)}; no record (run failed on the board): {len(unfinished)}; "
          f"invalid (control not caught, or harness fault): {len(invalid)}. Retries after a failed run: {retries}; "
          f"runs preceded by a power cycle: {cycles}.\n")
    errs = real_errors(agg)
    if errs:
        print("**ERRORS in real libraries:** " + ", ".join(
            f"{n} ({a['errors']} errors in runs {', '.join(a['runs_with_errors'])})" for n, a in errs.items()) + "\n")
    else:
        print("**No errors in any real library across all valid runs.**\n")
    dnf = {n: a for n, a in agg.items() if a["dnf"]}
    if dnf:
        print("**Did not finish in their time limit (one library per reset; not error-free):** " + ", ".join(
            f"{n} (runs {', '.join(a['runs_dnf'])})" for n, a in dnf.items()) + "\n")

    print("## Per library (valid runs)\n")
    print("| Library | Runs | Bytes | Interrupts | Errors | Starved parts | Did not finish | Full reached isr→main / main→isr | Empty reached isr→main / main→isr |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, a in agg.items():
        tag = " *(not claimed ISR-safe)*" if name in UNSAFE_BY_OWN_DOCS else ""
        print(f"| {name}{tag} | {a['runs']} | {a['bytes']:,} | {a['irqs']:,} | {a['errors']:,} | {a['starved']} | {a['dnf']} | "
              f"{a['full']['isr_to_main']} / {a['full']['main_to_isr']} | "
              f"{a['empty']['isr_to_main']} / {a['empty']['main_to_isr']} |")

    mt = mutant_table({}, records, valid)
    if mt:
        print("\n## Mutants (mutants.c): valid runs where each was caught, isr→main / main→isr\n")
        modes = sorted({m for _, m in mt})
        print("| Mutant | " + " | ".join(modes) + " |")
        print("|---|" + "---|" * len(modes))
        for name in sorted({n for n, _ in mt}):
            cells = []
            for m in modes:
                c = mt.get((name, m))
                cells.append(f"{c[1]} / {c[2]} of {c[0]}" if c else "-")
            print(f"| {name[8:]} | " + " | ".join(cells) + " |")

    print("\n## Runs\n")
    print("Sweep runs (modes sweep*): 'Interrupts' are trials, one interrupt each; "
          "'Bytes/lib/dir' in the run table is the number of start positions.\n")
    print("| Run | Start (UTC) | Mode | Prescaler | Cache | Code | Flags | Bytes/lib/dir | Seeds | Status |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in runs:
        hf = harness_fault(records[r["record"]]) if r["record"] in records else None
        status = ("valid" if r in valid else f"invalid ({hf})" if hf else "invalid (control)" if r in invalid
                  else "build failed" if r["exit"] == "3"
                  else "too slow: still running at the time limit" if r["exit"] == "4"
                  else f"did not finish (exit {r['exit']})")
        if r.get("power_cycled") == "yes":
            status += ", after power cycle"
        code = r.get("code") or ("sram" if "sram" in r.get("ldscript", "") else "flash")
        print(f"| {r['run']} | {r['start_utc']} | {r['mode']} | {r['prescaler']} | {'on' if r['cache'] == '1' else 'off'} | "
              f"{code} | {r.get('opt') or '-O2'}{' LTO' if r.get('lto') == '1' else ''}{(' ' + r['compiler']) if r.get('compiler') not in (None, '', 'gcc') else ''} | {int(r['transfers']):,} | "
              f"{r['main_seed']} / {r['isr_seed']} | {status} |")


if __name__ == "__main__":
    main()
