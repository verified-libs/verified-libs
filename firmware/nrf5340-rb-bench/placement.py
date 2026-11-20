#!/usr/bin/env python3
"""Placement experiment (run.sh SHIFT=N): how much the benchmark's numbers
depend on where the library code lies in memory.

Usage: placement.py RECORD.json ... [--json OUT.json]
  The records of one or more boards, one per shift (SHIFT=0, 4, ... 28;
  records <prefix>-flash[-shiftN]-<time>.json). Records of one board must
  share the commit and differ only in "shift".

For every board, configuration and figure (1-byte push, 1-byte pop, 64-byte
block per byte, zero-copy write/read; cache on, as the comparison page) it
prints the lowest and highest mean over the shifts and the spread
(max - min) / min. --json writes the same per board (with the records' names);
site/gen_libdata.py reads it as site/data/placement.json and the comparison
page shows the range under the shift-0 value.
"""
import json
import os
import sys
from collections import defaultdict

FIGS = [("push", "single/cache_on", "push", 1), ("pop", "single/cache_on", "pop", 1),
        ("block", "block64/cache_on", "push", 64), ("block_pop", "block64/cache_on", "pop", 64),
        ("dma_w", "dma64/cache_on", "push", 1), ("dma_r", "dma64/cache_on", "pop", 1)]


def main():
    args = sys.argv[1:]
    out = None
    if "--json" in args:
        i = args.index("--json")
        out = args[i + 1]
        del args[i:i + 2]
    by_board = defaultdict(list)
    for f in args:
        r = json.load(open(f))
        by_board[r["board"]].append((r.get("shift", 0), r, f))
    result = {}
    for board, recs in by_board.items():
        recs.sort(key=lambda t: t[0])
        commits = {r.get("bench_commit") for _, r, _ in recs}
        if len(commits) != 1:
            sys.exit(f"{board}: records from different commits {sorted(commits)}")
        shifts = [s for s, _, _ in recs]
        vals = defaultdict(dict)   # (lib, fig) -> shift -> mean
        for s, r, _ in recs:
            for lib in r["libs"]:
                res = lib.get("results") or {}
                for fig, scen, side, per in FIGS:
                    v = (res.get(scen) or {}).get(side)
                    if v and v.get("count") and v.get("mean"):
                        vals[(lib["name"], fig)][s] = v["mean"] / per
        b = {"commit": commits.pop(), "shifts": shifts, "libs": defaultdict(dict),
             "records": {str(sh): os.path.basename(f) for sh, _, f in recs}}
        print(f"\n## {board} (commit {b['commit']}, shifts {shifts})\n")
        print(f"{'configuration':48} {'figure':9} {'shift 0':>8} {'min':>8} {'max':>8} {'spread':>7}")
        for (lib, fig), d in sorted(vals.items()):
            if len(d) != len(shifts):
                continue
            lo, hi = min(d.values()), max(d.values())
            sp = (hi - lo) / lo if lo else 0.0
            b["libs"][lib][fig] = {"shift0": d.get(0), "min": lo, "max": hi, "spread": sp,
                                   "by_shift": {str(k): v for k, v in sorted(d.items())}}
            if fig in ("push", "pop", "block", "dma_w"):
                print(f"{lib[:48]:48} {fig:9} {d.get(0, float('nan')):8.2f} {lo:8.2f} {hi:8.2f} {100 * sp:6.1f}%")
        allsp = sorted(x["spread"] for l in b["libs"].values() for f, x in l.items() if f in ("push", "pop"))
        if allsp:
            print(f"\n1-byte push/pop: median spread {100 * allsp[len(allsp) // 2]:.1f} %, "
                  f"largest {100 * allsp[-1]:.1f} %, {sum(s <= 0.01 for s in allsp)} of {len(allsp)} within 1 %")
        result[board] = b
    if out:
        json.dump(result, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
