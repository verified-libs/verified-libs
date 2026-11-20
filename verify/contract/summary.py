#!/usr/bin/env python3
"""Turn the output of run.sh into the comparison page's data.

Usage: summary.py OUTPUT.txt [--single] [--commit C] [--date D] [--json site/data/contract.json]

OUTPUT.txt is what `bash run.sh` printed (one line per configuration:
name, capacity, trials, pass/FAIL; the run's exit line last). --commit is
the commit run.sh was run at (default: the last commit that changed
verify/contract), --date the day of the run (default: the file's date),
--single for a run with CONTRACT_DOUBLE=0 (one interrupt per call; the
default is the full run, up to two interrupts per call).
Only a complete run is accepted (its "exit 0" line: every verdict as
expected, controls and mutants failed). site/gen_libdata.py reads the JSON
and keys it by the configuration names of the records; the page shows only
the configurations it shows anyway. Configurations named in
site/data/hold.txt are left out of the JSON.
"""
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LINE = re.compile(r"^(?P<name>\S.*?)\s+capacity\s+(?P<cap>\d+)\s+(?P<trials>\d+) trials\s+(?P<v>pass|FAIL)\b")


def main():
    args = sys.argv[1:]
    opts = {}
    for k in ("--commit", "--date", "--json"):
        if k in args:
            i = args.index(k)
            opts[k] = args[i + 1]
            del args[i:i + 2]
    single = "--single" in args
    if single:
        args.remove("--single")
    if len(args) != 1:
        sys.exit(__doc__)
    src = args[0]
    text = open(src).read()
    if not re.search(r"^exit 0$", text, re.M):
        sys.exit(f"{src}: no 'exit 0' line (incomplete run, or a verdict not as expected)")
    commit = opts.get("--commit") or subprocess.check_output(
        ["git", "-C", ROOT, "log", "-1", "--format=%h", "--", "verify/contract"], text=True).strip()
    date = opts.get("--date") or datetime.date.fromtimestamp(os.path.getmtime(src)).isoformat()
    # configurations held back from the page (site/data/hold.txt, record names
    # with the language suffix) never enter the file
    hf = os.path.join(ROOT, "site/data/hold.txt")
    hold = {re.sub(r" \((C\+\+|C|Rust)\)$", "", l.strip()) for l in open(hf)
            if l.strip() and not l.startswith("#")} if os.path.exists(hf) else set()
    configs = {}
    for line in text.splitlines():
        m = LINE.match(line)
        if m and not m["name"].startswith(("control:", "mutant:")) and m["name"] not in hold:
            configs[m["name"]] = {"verdict": m["v"].lower(), "trials": int(m["trials"])}
    out = {"commit": commit, "date": date, "source": os.path.basename(src),
           "interrupts_per_call": 1 if single else 2, "configs": configs,
           "trials": sum(c["trials"] for c in configs.values())}
    if "--json" in opts:
        json.dump(out, open(opts["--json"], "w"), indent=1, ensure_ascii=False)
    for n, c in configs.items():
        print(f"{n:44} {c['verdict']:5} {c['trials']:>8}")
    print(f"{len(configs)} configurations, {out['trials']} trials, commit {commit}, {date}")


if __name__ == "__main__":
    main()
