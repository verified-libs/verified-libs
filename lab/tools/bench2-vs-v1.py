#!/usr/bin/env python3
"""Benchmark version 2 against version 1, per board, from the page data
(site/data/libs.json holds both: "speed" is version 1, "speed2" version 2).

Usage: bench2-vs-v1.py [LIBS.json] [-v BOARD]

Per board: how many of the means (push, pop and block of every configuration
and of every producer/consumer mode) are the same to a tenth of a cycle, how
many lie within each other's placement range, and the largest moves.
-v BOARD lists every mean of that board whose ranges do not meet.
Prints markdown.
"""
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def pairs(lib, bid):
    yield lib["name"], (lib.get("speed") or {}).get(bid), (lib.get("speed2") or {}).get(bid)
    mp = lib.get("mp")
    if mp:
        for mode in mp["modes"]:
            yield (lib["name"] + ", " + mode, ((mp.get("speed") or {}).get(bid) or {}).get(mode),
                   ((mp.get("speed2") or {}).get(bid) or {}).get(mode))


def span(s, k):
    r = (s.get("range") or {}).get(k) or [s[k], s[k]]
    return min(r[0], s[k]), max(r[1], s[k])


def main():
    args = sys.argv[1:]
    verbose = None
    if "-v" in args:
        i = args.index("-v")
        verbose = args[i + 1]
        del args[i:i + 2]
    data = json.load(open(args[0] if args else os.path.join(HERE, "../../site/data/libs.json")))
    print("| Board | Means | Same to 0.1 cycle | Ranges meet | Median change | Largest moves outside the ranges |")
    print("|---|---|---|---|---|---|")
    for b in data["boards"]:
        bid = b["id"]
        n = same = meet = 0
        ratios, out = [], []
        for lib in data["libs"]:
            for name, one, two in pairs(lib, bid):
                if not one or not two:
                    continue
                for k in ("push", "pop", "block"):
                    if one.get(k) is None or two.get(k) is None:
                        continue
                    n += 1
                    same += round(one[k], 1) == round(two[k], 1)
                    (lo1, hi1), (lo2, hi2) = span(one, k), span(two, k)
                    ratios.append(two[k] / one[k])
                    if lo1 <= hi2 + 0.05 and lo2 <= hi1 + 0.05:
                        meet += 1
                    else:
                        out.append((two[k] / one[k], name, k, one[k], two[k]))
        if not n:
            continue
        out.sort()
        ends = ([out[0]] if out and out[0][0] < 1 else []) + ([out[-1]] if out and out[-1][0] > 1 else [])
        text = "; ".join(f"{x[1]} {x[2]} {x[3]:.1f} to {x[4]:.1f} ({(x[0] - 1) * 100:+.0f} %)" for x in ends) or "none"
        print(f"| {b['name']} | {n} | {same} | {meet} | {(statistics.median(ratios) - 1) * 100:+.1f} % | {text} |")
        if verbose == bid:
            for x in out:
                print(f"    {x[1]} {x[2]}: {x[3]:.2f} to {x[4]:.2f} ({(x[0] - 1) * 100:+.0f} %)")


if __name__ == "__main__":
    main()
