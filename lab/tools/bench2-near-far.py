#!/usr/bin/env python3
"""Benchmark version 2: what the far call costs, per board.

Compares two sets of records of the same configurations: one measured with
the library right behind its adapter ("near", the first run of version 2)
and one with the library moved away by `far_bytes` ("far", the series the
pages show). The difference per call is what the distance costs.

Usage: bench2-near-far.py NEAR FAR BUILD [-v BOARD]
  NEAR, FAR  record directories (<board>/<adapter>.json), e.g. the output of
             `git archive f3d0682 records/bench-v2` and records/bench-v2
  BUILD      firmware/nrf5340-rb-bench/build/v2 after `onebuild.sh table`
             (its bundle*.json say how many bytes of a configuration lie
             behind the gap: the smallest number on a board is the stub
             every image has, i.e. a configuration that is inlined whole)
  -v BOARD   also print every configuration of that board

Configurations named in site/data/hold.txt (where that file exists) are
counted but not listed by -v.

Numbers: the difference (far minus near) of the median over all runs of the
mean cycles per call, single push and single pop. Prints markdown tables.
"""
import glob
import json
import os
import statistics as st
import sys


def med(rec, key, op):
    v = [r["results"][key][op]["mean"] for im in rec["images"] for r in im["runs"]
         if r["results"].get(key) and r["results"][key][op]]
    return st.median(v) if v else None


def main():
    args = sys.argv[1:]
    verbose = None
    if "-v" in args:
        i = args.index("-v")
        verbose, args = args[i + 1], args[:i] + args[i + 2:]
    if len(args) != 3:
        sys.exit(__doc__)
    near_root, far_root, build = args
    print("| Board | Scenario | Inlined whole: configurations, difference | Code behind the gap: configurations, median, lowest to highest |")
    print("|---|---|---|---|")
    detail = []
    for board in sorted(os.listdir(far_root)):
        behind = {}
        for f in glob.glob(f"{build}/{board}/bundle*.json"):
            for im in json.load(open(f))["images"]:
                behind.setdefault(im["adapter"], set()).add(im["far_code_bytes"])
        if not behind:
            sys.exit(f"{build}/{board}: no bundle*.json (run onebuild.sh table {board})")
        low = min(min(v) for v in behind.values())
        for key in ("single/cache_on", "single/cache_off"):
            rows = []
            for f in sorted(glob.glob(f"{far_root}/{board}/*.json")):
                a = os.path.basename(f)[:-5]
                nf = f"{near_root}/{board}/{a}.json"
                if not os.path.exists(nf):
                    continue
                n, fa = json.load(open(nf)), json.load(open(f))
                d = [None if med(n, key, op) is None or med(fa, key, op) is None
                     else round(med(fa, key, op) - med(n, key, op), 2) for op in ("push", "pop")]
                if None not in d:
                    rows.append((a, fa["name"], max(behind[a]), d[0], d[1], med(fa, key, "push"), med(fa, key, "pop")))

            def summ(rs, spread):
                v = [x for r in rs for x in r[3:5]]
                if not v:
                    return "none"
                if not spread:
                    return f"{len(rs)}, {min(v):+.2f} to {max(v):+.2f}"
                return f"{len(rs)}, {st.median(v):+.2f}, {min(v):+.2f} to {max(v):+.2f}"
            print(f"| {board} | {key} | {summ([r for r in rows if r[2] == low], False)} | "
                  f"{summ([r for r in rows if r[2] > low], True)} |")
            if board == verbose:
                detail.append((key, rows))
    hold = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../site/data/hold.txt")
    held = {l.strip() for l in open(hold)} if os.path.exists(hold) else set()
    for key, rows in detail:
        rows = [r for r in rows if r[1] not in held]
        print(f"\n{verbose} {key}: cycles per call, push / pop\n")
        print("| Configuration | Bytes behind the gap | Far | Far minus near |")
        print("|---|---|---|---|")
        for a, name, b, dp, dq, fp, fq in sorted(rows, key=lambda r: (r[2], r[0])):
            print(f"| {name} | {b} | {fp:g} / {fq:g} | {dp:+.2f} / {dq:+.2f} |")


if __name__ == "__main__":
    main()
