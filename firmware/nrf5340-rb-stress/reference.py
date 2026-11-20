#!/usr/bin/env python3
"""Our night campaign as a reference for a stress run on another board.

  reference.py make CAMPAIGN_DIR ... --out records/campaign/BOARD.json
  reference.py compare records/campaign/BOARD.json RECORD.json

make: per mode (runs.tsv) and library, over the valid runs of the campaigns
(summarize.py's rules: finished, negative control caught), the number of runs,
the runs with errors, the errors, and the runs the library did not finish;
per mode also how often each mutant was caught in each direction. The
configurations in site/data/hold.txt are left out.

compare: a record of run.sh (one mode) against that reference, per library.
A library with errors, or one that did not finish, where we saw none in any
of our runs of that mode is NEW and makes the exit code 1; errors where we
saw them too, or no errors where we saw some (the random modes do not find
every error in every run), are not. A run whose negative control was not
caught compares nothing (exit 1). A library missing from the reference is
not compared. Exit 2: the files do not fit (other board).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from decode import MULTICORE_DOCUMENTED, MUTANTS, UNSAFE_BY_OWN_DOCS   # noqa: E402
from summarize import CONTROL, DIRS, analyse, control_caught            # noqa: E402

MODE_RE = re.compile(r"-rb-stress-(.+)-\d{8}T\d{6}Z\.json$")


def hold():
    f = os.path.join(ROOT, "site/data/hold.txt")
    return {l.strip() for l in open(f) if l.strip() and not l.startswith("#")} if os.path.exists(f) else set()


def counted(name, smp):
    """As decode.py: whether errors of this library make a run not error-free."""
    if name in UNSAFE_BY_OWN_DOCS:
        return False
    return name in MULTICORE_DOCUMENTED if smp else True


def make(dirs, out):
    held = hold()
    ref = {"board": None, "campaigns": [], "commits": [], "modes": {}}
    commits = set()
    for d in dirs:
        runs, records, valid, _, _, _ = analyse(d)
        ref["campaigns"].append(os.path.basename(os.path.normpath(d)))
        for r in valid:
            rec = records[r["record"]]
            ref["board"] = ref["board"] or rec["board"]
            if rec["board"] != ref["board"]:
                sys.exit(f"{d}: board {rec['board']}, not {ref['board']}")
            commits.add(rec.get("source_commit", "?"))
            m = ref["modes"].setdefault(r["mode"], {"runs": 0, "transfers": set(), "libs": {}, "mutants": {}})
            m["runs"] += 1
            m["transfers"].add(int(rec.get("transfers") or 0))
            for lib in rec["libs"]:
                n = lib["name"]
                if n == CONTROL or lib.get("n/a") or lib.get("not_run") or n in held:
                    continue
                if n in MUTANTS:
                    mu = m["mutants"].setdefault(n, {"runs": 0, **{x: 0 for x in DIRS}})
                    mu["runs"] += 1
                    for x in DIRS:
                        mu[x] += lib[x]["errors"] > 0
                    continue
                e = sum(lib[x]["errors"] for x in DIRS)
                a = m["libs"].setdefault(n, {"runs": 0, "runs_with_errors": 0, "errors": 0, "did_not_finish": 0})
                a["runs"] += 1
                a["errors"] += e
                a["runs_with_errors"] += e > 0
                a["did_not_finish"] += bool(lib.get("did_not_finish"))
    for m in ref["modes"].values():
        m["transfers"] = sorted(m["transfers"])
    ref["commits"] = sorted(commits)
    with open(out, "w") as fh:
        json.dump(ref, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    for k, m in sorted(ref["modes"].items()):
        bad = [f"{n} {a['runs_with_errors']}/{a['runs']}" for n, a in m["libs"].items() if a["runs_with_errors"]]
        print(f"{k:12} {m['runs']:4} valid runs; with errors: {', '.join(bad) or 'none'}")


def compare(ref_file, rec_file):
    ref, rec = json.load(open(ref_file)), json.load(open(rec_file))
    if rec["board"] != ref["board"]:
        print(f"the record is from {rec['board']}, the reference from {ref['board']}")
        return 2
    mm = MODE_RE.search(os.path.basename(rec_file))
    mode = mm.group(1) if mm else None
    m = ref["modes"].get(mode)
    if not m:
        print(f"mode {mode}: not in our campaign ({', '.join(sorted(ref['modes']))})")
        return 2
    smp = rec.get("smp", False)
    tr = lambda t: f"{t} transfers, " if t else ""   # noqa: E731  (0 in sweep modes: trials, not a stream)
    print(f"mode {mode}: your run ({tr(rec.get('transfers'))}commit {rec.get('source_commit')}) "
          f"against {m['runs']} valid runs of ours ({tr('/'.join(str(t) for t in m['transfers'] if t))}"
          f"{' + '.join(ref['campaigns'])}, commit {', '.join(ref['commits'])})")
    if not control_caught(rec):
        print("negative control NOT caught: this run cannot show an error, nothing compared")
        return 1
    new = 0
    for lib in rec["libs"]:
        n = lib["name"]
        if n == CONTROL or n in MUTANTS or lib.get("n/a") or lib.get("not_run"):
            continue
        a = m["libs"].get(n)
        if a is None:
            continue
        e = sum(lib[x]["errors"] for x in DIRS)
        dnf = bool(lib.get("did_not_finish"))
        ours = f"ours: errors in {a['runs_with_errors']} of {a['runs']} runs"
        if a["did_not_finish"]:
            ours += f", did not finish in {a['did_not_finish']}"
        tag = "" if counted(n, smp) else " (not claimed safe in this mode)"
        if (e and not a["runs_with_errors"]) or (dnf and not a["did_not_finish"]):
            new += 1
            what = f"{e} errors" if e else ""
            what += (", " if e and dnf else "") + ("did not finish" if dnf else "")
            print(f"  NEW   {n}: {what}; {ours}{tag}")
        elif e or dnf:
            print(f"  as ours  {n}: {e} errors{', did not finish' if dnf else ''}; {ours}{tag}")
        elif a["runs_with_errors"]:
            print(f"  none here  {n}: no errors; {ours}{tag}")
    caught = rec.get("mutants_caught") or {}
    for n, c in caught.items():
        mu = m["mutants"].get(n)
        if not mu:
            continue
        line = "; ".join(f"{x}: {'yes' if c.get(x) else 'no'} (ours {mu[x]}/{mu['runs']})" for x in DIRS if x in c)
        print(f"  mutant {n[8:]}: {line}")
    rest = sum(1 for lib in rec["libs"] if lib["name"] in m["libs"]) - new
    print(f"{new} libraries NEW against ours, {rest} as ours or within what our runs showed")
    return 1 if new else 0


def main():
    a = sys.argv[1:]
    if len(a) >= 4 and a[0] == "make" and a[-2] == "--out":
        make(a[1:-2], a[-1])
    elif len(a) == 3 and a[0] == "compare":
        sys.exit(compare(a[1], a[2]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
