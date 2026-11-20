#!/usr/bin/env python3
"""Copy the result records the comparison page shows into records/, so that
a reader can check them (site/content/reproduce.md).

Usage (on the lab host): site/collect_records.py [--runs DIR] [--stress DIR ...] [--mp-stress DIR ...]

records/bench/: the benchmark, Rust, multi-producer and size record of each
  board that site/data/libs.json names, and the placement records that
  site/data/placement*.json name. Taken from --runs (default ~/lab-runs).
records/stress/: one short stress run per board and mode as a reference for
  a run on your own board: the ISR stress records (*-rb-stress-*) of the
  --stress directories and the two-interrupt stress records
  (*-rb-mp-stress-*) of the --mp-stress directories, except the -extra ones
  (libraries held back from the public tree); none given: records/stress is
  left as it is. Of a campaign directory (one with runs.tsv) not every
  record is taken but the first run that passed (exit 0) of each mode, for
  the two-interrupt test of each mode with random and with aimed interrupts.
records/campaign/: per board a summary of the night campaigns the page's
  stress counts come from (libs.json boards[].stress.campaigns, in --runs):
  per mode and library the valid runs and the runs with errors
  (firmware/nrf5340-rb-stress/reference.py make); repeat.sh compares a run
  on your own board with it.

Files in records/bench that are no longer named are removed. A record with
a word from site/embargo.txt is refused.
"""
import glob
import json
import os
import shutil
import subprocess
import sys

SITE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SITE)


def embargo_words():
    p = os.path.join(SITE, "embargo.txt")
    if not os.path.exists(p):
        return []
    return [w.strip().lower() for w in open(p) if w.strip() and not w.startswith("#")]


def copy(src, dst_dir, words):
    text = open(src).read()
    low = text.lower()
    for w in words:
        if w in low:
            sys.exit(f"{src}: contains an embargoed word, not copied")
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copyfile(src, os.path.join(dst_dir, os.path.basename(src)))


def stress_records(d, pat):
    """The records to take from directory d: all that match pat, or, of a
    campaign directory, the first run with exit 0 per mode (and aim)."""
    tsv = os.path.join(d, "runs.tsv")
    if not os.path.exists(tsv):
        return sorted(glob.glob(os.path.join(d, pat)))
    rows = [l.rstrip("\n").split("\t") for l in open(tsv)]
    head, first = rows[0], {}
    for row in rows[1:]:
        r = dict(zip(head, row))
        rec = r.get("record", "-")
        if r.get("exit") != "0" or rec == "-":
            continue
        rec = os.path.join(d, os.path.basename(rec))
        if os.path.exists(rec):
            first.setdefault((r["mode"], r.get("aim", "")), rec)
    return [first[k] for k in sorted(first)]


def main():
    args = sys.argv[1:]
    runs = os.path.expanduser("~/lab-runs")
    stress, mpstress = [], []
    while args:
        a = args.pop(0)
        if a == "--runs":
            runs = args.pop(0)
        elif a in ("--stress", "--mp-stress"):
            while args and not args[0].startswith("--"):
                (stress if a == "--stress" else mpstress).append(args.pop(0))
        else:
            sys.exit(__doc__)
    words = embargo_words()
    libs = json.load(open(os.path.join(SITE, "data/libs.json")))
    names = set()
    for b in libs["boards"]:
        for k in ("bench", "rust_bench", "mp_bench", "nordic_bench", "size"):
            if b.get(k):
                names.add(b[k]["record"])
    for f in ("placement.json", "placement-rust.json", "placement-mp.json"):
        pl = os.path.join(SITE, "data", f)
        if os.path.exists(pl):
            for b in json.load(open(pl)).values():
                names.update(b["records"].values())
    bench = os.path.join(ROOT, "records/bench")
    os.makedirs(bench, exist_ok=True)
    for old in os.listdir(bench):
        if old not in names:
            os.remove(os.path.join(bench, old))
    for n in sorted(names):
        src = os.path.join(runs, n)
        if not os.path.exists(src):
            sys.exit(f"{src}: named by the page data but not found")
        copy(src, bench, words)
    print(f"records/bench: {len(names)} records")
    cdir = os.path.join(ROOT, "records/campaign")
    os.makedirs(cdir, exist_ok=True)
    want = set()
    for b in libs["boards"]:
        camps = (b.get("stress") or {}).get("campaigns") or []
        if not camps:
            continue
        dirs = [os.path.join(runs, c) for c in camps]
        for d in dirs:
            if not os.path.isdir(d):
                sys.exit(f"{d}: named by the page data but not found")
        out = os.path.join(cdir, b["id"] + ".json")
        subprocess.run([sys.executable, os.path.join(ROOT, "firmware/nrf5340-rb-stress/reference.py"), "make",
                        *dirs, "--out", out], check=True, stdout=subprocess.DEVNULL)
        low = open(out).read().lower()
        for w in words:
            if w in low:
                os.remove(out)
                sys.exit(f"{out}: contains an embargoed word, removed")
        want.add(b["id"] + ".json")
    for old in os.listdir(cdir):
        if old not in want:
            os.remove(os.path.join(cdir, old))
    print(f"records/campaign: {len(want)} boards")
    if stress or mpstress:
        sdir = os.path.join(ROOT, "records/stress")
        shutil.rmtree(sdir, ignore_errors=True)
        n = 0
        for d, pat in [(d, "*-rb-stress-*.json") for d in stress] + [(d, "*-rb-mp-stress-*.json") for d in mpstress]:
            for f in stress_records(d, pat):
                r = json.load(open(f))
                if "-extra-" in os.path.basename(f) or r.get("with_extra") or r.get("partial"):
                    continue
                copy(f, sdir, words)
                n += 1
        print(f"records/stress: {n} records")


if __name__ == "__main__":
    main()
