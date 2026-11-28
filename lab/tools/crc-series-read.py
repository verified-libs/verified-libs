#!/usr/bin/env python3
"""Read a CRC series before a record is made from it. Reads only; writes nothing.

Usage: python3 -I lab/tools/crc-series-read.py SERIES_DIR [BOARD ...]

SERIES_DIR is the series' output directory (series.log, and one directory
of run files per board, written by kinds/crc/bench/run-crc.py through
series.sh). Per board one table row:
  exit             the runner's exit, from series.log
  runs / no file   the runs and the runs without a file, from run.log's last summary line
  writes           flash writes (FLASH WRITE lines of run.log)
  files            run files (*-pass1.json, *-pass2.json)
  invalid          run files marked invalid by the runner
  errors           calls that disagreed with the reference, in the
                   configuration and in the baseline (sum over all runs)
  attempts, wait_s the values seen, with their counts
  empty call       the values of empty_call_raw_min seen, with their counts
  pass 1 vs 2      of the means of every (configuration, placement,
                   scenario) present in both passes, for the configuration
                   and the baseline: how many agree within 1 % or within
                   0.05 cycles, and the largest difference, named
Exit 0; 2 if a board directory cannot be read.
"""
import collections
import glob
import json
import os
import re
import sys


def read_board(series, board):
    d = os.path.join(series, board)
    row = {"board": board}
    log = open(os.path.join(series, "series.log")).read() if os.path.exists(os.path.join(series, "series.log")) else ""
    m = re.findall(rf"^\S+ {re.escape(board)}: exit (\d+)", log, re.M)
    row["exit"] = m[-1] if m else "running" if f"{board}: start" in log else "?"
    runlog = open(os.path.join(d, "run.log")).read() if os.path.exists(os.path.join(d, "run.log")) else ""
    m = re.findall(r"(\d+) runs, (\d+) without a file", runlog)
    row["runs"], row["no_file"] = (m[-1] if m else ("?", "?"))
    row["writes"] = len(re.findall(r"FLASH WRITE", runlog))
    files = sorted(glob.glob(os.path.join(d, "*-pass[12].json")))
    row["files"] = len(files)
    attempts, waits, empty = collections.Counter(), collections.Counter(), collections.Counter()
    invalid, err_cfg, err_base = 0, 0, 0
    means = {}   # (adapter, place, side, scenario) -> {pass: mean}
    for f in files:
        r = json.load(open(f))
        attempts[r.get("attempt")] += 1
        waits[r.get("wait_s")] += 1
        empty[r.get("empty_call_raw_min")] += 1
        if r.get("invalid"):
            invalid += 1
        libs = r.get("libs", [])
        if len(libs) >= 2:
            err_base += libs[0].get("errors", 0) or 0
            err_cfg += libs[1].get("errors", 0) or 0
        for side, lib in zip(("baseline", "configuration"), libs[:2]):
            for sc, v in lib.get("results", {}).items():
                if isinstance(v, dict) and v.get("mean") is not None:
                    means.setdefault((r["adapter"], r["place"], side, sc), {})[r["pass"]] = v["mean"]
    row.update(invalid=invalid, err_cfg=err_cfg, err_base=err_base, attempts=dict(attempts), waits=dict(waits),
               empty=dict(empty))
    both = [(k, v[1], v[2]) for k, v in means.items() if 1 in v and 2 in v]
    agree = sum(1 for _, a, b in both if abs(a - b) <= 0.05 or abs(a - b) <= 0.01 * max(abs(a), abs(b)))
    row["pairs"], row["agree"] = len(both), agree
    row["identical"] = sum(1 for _, a, b in both if a == b)
    if both and row["identical"] < len(both):
        k, a, b = max(both, key=lambda t: abs(t[1] - t[2]))
        rel = abs(a - b) / max(abs(a), abs(b)) * 100 if max(abs(a), abs(b)) else 0.0
        row["largest"] = f"{k[0]} p{k[1]} {k[2]} {k[3]}: {a:g} / {b:g} ({abs(a - b):g} cycles, {rel:.2f} %)"
        kr, ar, br = max(both, key=lambda t: abs(t[1] - t[2]) / max(abs(t[1]), abs(t[2]), 1e-9))
        rr = abs(ar - br) / max(abs(ar), abs(br)) * 100 if max(abs(ar), abs(br)) else 0.0
        row["largest_rel"] = f"{kr[0]} p{kr[1]} {kr[2]} {kr[3]}: {ar:g} / {br:g} ({abs(ar - br):g} cycles, {rr:.2f} %)"
    return row


def fmt(c):
    return ", ".join(f"{k}: {v}" for k, v in sorted(c.items(), key=lambda kv: str(kv[0])))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    series = sys.argv[1]
    boards = sys.argv[2:] or sorted(b for b in os.listdir(series) if os.path.isdir(os.path.join(series, b)))
    rc = 0
    for b in boards:
        if not os.path.isdir(os.path.join(series, b)):
            print(f"{b}: no directory"); rc = 2; continue
        r = read_board(series, b)
        print(f"{b}: exit {r['exit']}; {r['runs']} runs, {r['no_file']} without a file, {r['writes']} flash writes, "
              f"{r['files']} run files, {r['invalid']} invalid")
        print(f"  disagreeing calls: configuration {r['err_cfg']}, baseline {r['err_base']}")
        print(f"  attempts {{{fmt(r['attempts'])}}}; wait_s {{{fmt(r['waits'])}}}; empty call {{{fmt(r['empty'])}}}")
        print(f"  pass 1 vs 2: {r['agree']} of {r['pairs']} means within 1 % or 0.05 cycles, {r['identical']} identical")
        if r.get("largest"):
            print(f"  largest difference: {r['largest']}")
            print(f"  largest relative:   {r['largest_rel']}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
