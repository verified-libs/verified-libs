#!/usr/bin/env python3
"""Make the pools concurrency series' records from the run files of
run-isr.py: one record per board and configuration,
records/pools-isr/<board>/<adapter>.json, schema "pools-isr/1"
(lab/plans/2026-11-27-pools-concurrency.md, section 4).

Usage: python3 -I isrrecords.py [--check] [--out DIR] [--images DIR] RUNDIR...

  RUNDIR    output directories of run-isr.py (build.json, bundle<N>.json,
            options.json and the run files), of one board or of several
  --out     where the records go (default: records/pools-isr of this tree)
  --images  the built images (default build/v1), for the coverage
            (covmap.py; needs arm-none-eabi-objdump); without them a record
            is not made
  --check   write nothing, only check and print the summary

A record is made only if:
  - its run file is whole, of this series' schema, of a commit that can be
    rebuilt (not "+dirty", not unknown), and of the build next to it
    (build.json: the same commit, toolchain image and board; the image's
    checksum the bundle manifest's);
  - its run directory holds the board's option registers (options.json,
    schema board-options/1, read zero-write by lab/tools/read-options.py
    before the job; method version 3), checked as the first series' record
    writer checks them (kinds/pools/bench/poolrecords.py options_of);
  - every control of the board's bundle has a run, and every one was caught:
    a sweep that does not catch its controls says nothing about the others,
    so then no record of that board is made.
The record keeps the run as it was (the result block decoded, the verdict
by the plan's classes) and adds the option registers and the coverage per
function of the configuration's code. For a library outside its
documentation the record holds what was observed and no verdict word.
Exit: 0 every run found gave a record, 1 not.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "../.."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "kinds/pools/bench"))
import poolrecords   # noqa: E402  (options_of, BOARD_DIR)
import decode        # noqa: E402

SCHEMA = "pools-isr/1"
RUN_SCHEMA = "pools-isr-run/1"
NEED = ("board", "adapter", "class", "bench_commit", "toolchain_image", "toolchain", "libs_pinned", "clock_hz",
        "image_base", "image_sha256", "bundle", "bundle_sha256", "time", "run_number", "verdict", "result")


def collect(dirs, problems):
    """{board: [(run, run dir)]}, with the run directory's options attached"""
    out = {}
    for d in dirs:
        bpath = os.path.join(d, "build.json")
        mans = glob.glob(os.path.join(d, "bundle*.json"))
        if not os.path.exists(bpath) or len(mans) != 1:
            problems.append(f"{d}: no build.json or not one bundle manifest")
            continue
        built, man = json.load(open(bpath)), json.load(open(mans[0]))
        imgs = {im["adapter"]: im for im in man["images"]}
        opts, why = poolrecords.options_of(d, built["board"])
        if why or opts is None:
            problems.append(why or f"{d}: no options.json (method version 3: read before the job)")
            continue
        for f in sorted(glob.glob(os.path.join(d, "adapter_*.json"))):
            r = json.load(open(f))
            miss = [k for k in NEED if r.get(k) is None]
            if r.get("schema") != RUN_SCHEMA or miss:
                problems.append(f"{f}: not a whole run file ({r.get('schema')}; without {miss})")
                continue
            if r["bench_commit"].endswith("+dirty") or r["bench_commit"] in ("", "unknown"):
                problems.append(f"{f}: commit {r['bench_commit']!r} cannot be rebuilt")
                continue
            if (r["bench_commit"], r["toolchain_image"], r["board"]) != (built["bench_commit"], built["toolchain_image"], built["board"]):
                problems.append(f"{f}: not of the build next to it")
                continue
            im = imgs.get(r["adapter"])
            if im is None or im["image_sha256"] != r["image_sha256"] or man["bundle_sha256"] != r["bundle_sha256"]:
                problems.append(f"{f}: its image is not the bundle's")
                continue
            r["_options"], r["_dir"] = opts, d
            out.setdefault(r["board"], []).append(r)
    return out


def make(runs, images, problems):
    """[(board, adapter, record)] of one board, or [] (with a problem) if its controls were not all caught"""
    board = runs[0]["board"]
    by = {}
    for r in sorted(runs, key=lambda r: r["time"]):
        by[r["adapter"]] = r                    # the last run of a configuration counts
    controls = [a for a, k in decode.CLASS.items() if k == "control"]
    missing = [a for a in controls if a not in by]
    not_caught = [a for a in controls if a in by and by[a]["verdict"] != "caught"]
    if missing or not_caught:
        problems.append(f"{board}: no record: controls without a run {missing}, not caught {not_caught}")
        return []
    sys.path.insert(0, HERE)
    import covmap
    out = []
    for a, r in sorted(by.items()):
        d = os.path.join(images, board, "img", a)
        if not os.path.exists(os.path.join(d, "fw.elf")):
            problems.append(f"{board} {a}: no built image in {d} for the coverage")
            continue
        per = covmap.cover(d, r["result"]["cov_bitmap"], int(r["image_base"], 16), a)
        rec = {k: v for k, v in r.items() if not k.startswith("_")}
        rec["schema"] = SCHEMA
        rec["option_registers"] = [r["_options"]]
        res = dict(rec["result"])
        res.pop("cov_bitmap")
        rec["result"] = res
        rec["coverage"] = {"instructions": sum(f["instructions"] for f in per.values()),
                           "reached": sum(f["reached"] for f in per.values()),
                           "per_function": {fn: {"reached": f["reached"], "instructions": f["instructions"],
                                                 "unreached": f["unreached"]} for fn, f in sorted(per.items())}}
        out.append((board, a, rec))
    return out


def main():
    args = sys.argv[1:]
    check = "--check" in args
    args = [a for a in args if a != "--check"]
    out, images = os.path.join(ROOT, "records/pools-isr"), os.path.join(HERE, "build/v1")
    while args[:1] in (["--out"], ["--images"]) and len(args) >= 2:
        if args[0] == "--out":
            out = args[1]
        else:
            images = args[1]
        args = args[2:]
    if not args or any(a.startswith("-") for a in args):
        sys.exit(__doc__)
    problems = []
    written = 0
    for board, runs in sorted(collect(args, problems).items()):
        for b, a, rec in make(runs, images, problems):
            written += 1
            print(f"{b} {a} ({rec['class']}): {rec['verdict']}; coverage {rec['coverage']['reached']} of "
                  f"{rec['coverage']['instructions']} instructions")
            if not check:
                p = os.path.join(out, b, a + ".json")
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w") as fh:
                    json.dump(rec, fh, indent=1)
                    fh.write("\n")
    for p in problems:
        print(p)
    print(f"{written} records{' (not written: --check)' if check else ''}, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
