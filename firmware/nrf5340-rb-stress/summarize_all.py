#!/usr/bin/env python3
"""One report over the stress campaigns of several boards (one night).

Usage: summarize_all.py [CAMPAIGN_DIR ...]     (markdown on stdout)
Without arguments: the newest ~/lab-runs/overnight-<stamp>-<board> per
board. Safe to run while the campaigns are still going.

Same rules as summarize.py (per board): a run is valid only if it finished
and its negative control was caught. Sections: per board, valid runs per
configuration, errors in real libraries, the interrupt sweep.
"""
import glob
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from summarize import CONTROL, DIRS, MUTANTS, UNSAFE_BY_OWN_DOCS, analyse, mutant_table, real_errors   # noqa: E402

BOARD_ORDER = ["nrf5340dk", "nucleo-g0b1re", "nucleo-g474re", "nucleo-h723zg", "sam-d20-xpro", "pico2"]


def board_of(d):
    m = re.search(r"overnight-\d{8}T\d{6}Z-(.+)$", os.path.basename(os.path.normpath(d)))
    return m.group(1) if m else os.path.basename(os.path.normpath(d))


def latest_dirs():
    newest = {}
    for d in sorted(glob.glob(os.path.expanduser("~/lab-runs/overnight-*Z-*"))):
        if os.path.exists(os.path.join(d, "runs.tsv")):
            newest[board_of(d)] = d          # sorted: the last one per board is the newest
    return list(newest.values())


def config_of(r):
    """Rotation setting of a runs.tsv row, e.g. 'block p2 cache on flash'."""
    p = "" if r["mode"].startswith("sweep") else f" p{r['prescaler']}"
    return f"{r['mode']}{p} cache {'on' if r['cache'] == '1' else 'off'} {r['code']}"


def main():
    dirs = sys.argv[1:] or latest_dirs()
    order = {b: i for i, b in enumerate(BOARD_ORDER)}
    dirs.sort(key=lambda d: (order.get(board_of(d), 99), board_of(d)))
    res = {board_of(d): (d, *analyse(d)) for d in dirs}
    boards = list(res)

    print("# Stress campaigns, all boards\n")
    for b in boards:
        print(f"- {b}: `{res[b][0]}`")
    print()

    print("## Per board\n")
    print("| Board | Runs | Valid | Invalid (control) | Did not finish | Too slow (time limit) | Build failed "
          "| Retries | Power cycles | Errors in real libraries |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for b in boards:
        d, runs, records, valid, invalid, unfinished, agg = res[b]
        errs = real_errors(agg)
        e = "**" + ", ".join(f"{n}: {a['errors']}" for n, a in errs.items()) + "**" if errs else "0"
        built = sum(1 for r in unfinished if r["exit"] == "3")
        slow = sum(1 for r in unfinished if r["exit"] == "4")   # still running at run.sh's time limit
        print(f"| {b} | {len(runs)} | {len(valid)} | {len(invalid)} | {len(unfinished) - built - slow} | {slow} | {built} | "
              f"{sum(1 for r in runs if r['run'].endswith('r'))} | "
              f"{sum(1 for r in runs if r.get('power_cycled') == 'yes')} | {e} |")

    print("\n## Valid runs per configuration (valid / started)\n")
    cell = defaultdict(lambda: [0, 0])
    configs = []
    for b in boards:
        _, runs, _, valid, _, _, _ = res[b]
        for r in runs:
            c = config_of(r)
            if c not in configs:
                configs.append(c)
            cell[c, b][1] += 1
            cell[c, b][0] += r in valid
    print("| Configuration | " + " | ".join(boards) + " |")
    print("|---|" + "---|" * len(boards))
    for c in configs:
        cells = []
        for b in boards:
            v, n = cell[c, b]
            cells.append("-" if n == 0 else f"**{v}/{n}**" if v < n else f"{v}/{n}")
        print(f"| {c} | " + " | ".join(cells) + " |")
    print("\nBold: at least one run of that configuration was invalid or did not finish.")

    print("\n## Errors per library (valid runs)\n")
    rows = defaultdict(dict)
    for b in boards:
        for name, a in res[b][6].items():
            if a["errors"]:
                rows[name][b] = a["errors"]
    if not rows:
        print("No errors in any library in any valid run.")
    else:
        print("| Library | " + " | ".join(boards) + " |")
        print("|---|" + "---|" * len(boards))
        for name, per in sorted(rows.items()):
            tag = " *(not claimed ISR-safe)*" if name.split(" [")[0] in UNSAFE_BY_OWN_DOCS else ""
            print(f"| {name}{tag} | " + " | ".join(f"{per.get(b, 0):,}" for b in boards) + " |")
        print("\nRows without a tag count as errors in real libraries, except "
              "'single-core design' rows (SMP runs of interrupt-only designs).")

    print("\n## Interrupt sweep (valid sweep runs)\n")
    print("| Board | Runs | Trials | Interrupt inside the call | Library functions with instructions not interrupted |")
    print("|---|---|---|---|---|")
    for b in boards:
        _, runs, records, valid, _, _, _ = res[b]
        n = trials = inside = 0
        gaps = set()
        for r in valid:
            rec = records[r["record"]]
            if rec.get("sweep") is None:
                continue
            n += 1
            for lib in rec["libs"]:
                if lib["name"] == CONTROL or lib.get("n/a") or lib["name"] in MUTANTS:
                    continue
                for x in DIRS:
                    trials += lib[x].get("trials", 0)
                    inside += lib[x].get("interrupted_during_call", 0)
            for f in rec["sweep"].get("functions", []):
                if f["not_interrupted"] and f["object"] not in ("main.o", "startup.o"):
                    gaps.add(f["function"])
        if n:
            print(f"| {b} | {n} | {trials:,} | {inside / trials:.1%} | {len(gaps)} |")
        else:
            print(f"| {b} | 0 | - | - | - |")
    print("\n'Not interrupted' includes paths the sweep never executes (see README, "
          "Interrupt sweep); the per-run lists are in each record under sweep.functions.")
    print("\n## Mutants (mutants.c): valid runs where each was caught, isr→main / main→isr, all boards\n")
    mt = {}
    for b in boards:
        _, runs, records, valid, _, _, _ = res[b]
        mutant_table(mt, records, valid)
    if not mt:
        print("No mutant results (runs before mutants.c).")
    else:
        modes = sorted({m for _, m in mt})
        print("| Mutant | " + " | ".join(modes) + " |")
        print("|---|" + "---|" * len(modes))
        for name in sorted({n for n, _ in mt}):
            cells = []
            for m in modes:
                c = mt.get((name, m))
                cells.append(f"{c[1]} / {c[2]} of {c[0]}" if c else "-")
            print(f"| {name[8:]} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
