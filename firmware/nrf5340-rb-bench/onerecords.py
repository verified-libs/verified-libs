#!/usr/bin/env python3
"""Make the records of benchmark version 2 from the run files of run-one.py:
one record per board and configuration, holding its eight images (one per
placement) and every run of each
(lab/plans/2026-11-22-bench-image-per-library.md).

Usage: onerecords.py [--check] [--out DIR] RUNDIR...

  RUNDIR   output directories of run-one.py (build.json, bundle<N>.json and
           the run files), of one board or of several
  --out    where the records go (default: records/bench-v2 of this tree),
           as <board>/<adapter>.json; a record that is there is replaced
  --check  write nothing, only check and print the summary

A record is made only if the configuration is whole: all its placements
were run, every pass of every placement gave a run file, and every run
agrees on what it ran (image checksums, the fixed part, the boot stub, the
build, clock and number of repetitions). Anything else is named and the
configuration left out.
The summary also says whether the baseline, which is the same code at the
same place in every image of a board, measured the same in every run.
Exit: 0 every configuration found gave a record, 1 not.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCHEMA = "rb-bench/2"
PLACES = (0, 4, 8, 12, 16, 20, 24, 28)
RUN_SCHEMA = "rb-bench-run/2"
# the same in every run of a record
COMMON = ("board", "core", "board_id", "board_decoded", "code_location", "adapter", "kind", "bench_commit",
          "toolchain_image", "result_version", "clock_hz", "runs", "overhead_subtracted", "empty_call_raw_min",
          "scenarios", "fixed_sha256", "boot_image_sha256", "far_bytes")
# the same in every run of an image
IMAGE = ("place", "slot", "image_base", "image_bytes", "fw_sha256", "image_sha256")
# of one run
RUN = ("time", "host", "probe_rs", "pass", "attempt", "wait_s", "seconds", "run_number", "bundle", "bundle_sha256")


def main():
    args = sys.argv[1:]
    check = "--check" in args
    args = [a for a in args if a != "--check"]
    out = os.path.join(ROOT, "records/bench-v2")
    if args[:1] == ["--out"] and len(args) >= 2:
        out, args = args[1], args[2:]
    if not args or any(a.startswith("-") for a in args):
        sys.exit(__doc__)
    groups, builds, problems = {}, {}, []   # (board, adapter) -> runs
    for d in args:
        try:
            built = json.load(open(os.path.join(d, "build.json")))
        except OSError:
            sys.exit(f"{d}: no build.json (not an output directory of run-one.py)")
        for f in sorted(glob.glob(os.path.join(d, "adapter_*-p*-pass*.json"))):
            r = json.load(open(f))
            if r.get("schema") != RUN_SCHEMA or r.get("invalid"):
                problems.append(f"{f}: not a valid run file")
                continue
            if r["bench_commit"] != built["bench_commit"]:
                problems.append(f"{f}: not of the build in {d}/build.json")
                continue
            r["_file"] = f
            groups.setdefault((r["board"], r["adapter"]), []).append(r)
            builds[(r["board"], r["adapter"])] = built
    written, left, base_note = 0, 0, {}
    for (board, adapter), runs in sorted(groups.items()):
        why = None
        for k in COMMON:
            if any(r.get(k) != runs[0].get(k) for r in runs):
                why = f"the runs differ in {k}"
        passes = sorted({r["pass"] for r in runs})
        images = []
        for place in PLACES:
            mine = sorted((r for r in runs if r["place"] == place), key=lambda r: (r["pass"], r["time"]))
            if sorted(r["pass"] for r in mine) != passes:
                why = why or f"placement {place}: passes {[r['pass'] for r in mine]} of {passes}"
                continue
            for k in IMAGE:
                if any(r.get(k) != mine[0].get(k) for r in mine):
                    why = why or f"placement {place}: the runs differ in {k}"
            im = {k: mine[0].get(k) for k in IMAGE}
            im["runs"] = [dict({k: r.get(k) for k in RUN}, errors=r["libs"][1]["errors"],
                               results=r["libs"][1]["results"], baseline=r["libs"][0]["results"]) for r in mine]
            images.append(im)
        if any(r["place"] not in PLACES for r in runs):
            why = why or "a placement that is not in the table"
        if why:
            left += 1
            problems.append(f"{board} {adapter}: left out: {why}")
            continue
        built = builds[(board, adapter)]
        rec = dict({"schema": SCHEMA}, **{k: runs[0].get(k) for k in COMMON})
        rec["name"] = runs[0]["libs"][1]["name"]
        rec["toolchain"], rec["libs_pinned"] = built["toolchain"], built["libs_pinned"]
        rec["passes"] = len(passes)
        rec["images"] = images
        # the baseline over all runs of the board
        note = base_note.setdefault(board, {"runs": 0, "values": {}})
        for im in images:
            for r in im["runs"]:
                note["runs"] += 1
                for scen, v in r["baseline"].items():
                    for op in ("push", "pop"):
                        if v[op]:
                            note["values"].setdefault(f"{scen} {op}", set()).add(v[op]["mean"])
        written += 1
        if not check:
            name = os.path.join(out, board_dir(runs[0]), adapter + ".json")
            os.makedirs(os.path.dirname(name), exist_ok=True)
            with open(name, "w") as fh:
                fh.write(dump(rec))
    for p in problems:
        print(p)
    for board, note in sorted(base_note.items()):
        moved = {k: sorted(v) for k, v in note["values"].items() if len(v) > 1}
        print(f"{board}: baseline in {note['runs']} runs: {len(note['values']) - len(moved)} of {len(note['values'])} "
              f"numbers the same in every run" + ("" if not moved else "; not the same: " + "; ".join(
                  f"{k} {v[0]} to {v[-1]} ({len(v)} values)" for k, v in sorted(moved.items()))))
    print(f"{written} records{'' if not check else ' (not written: --check)'}, {left} configurations left out, "
          f"{len(problems) - left} other problems")
    return 1 if problems else 0


def board_dir(run):
    """the directory name of a board: the firmware's name for it, from the bundle the run names"""
    return {1: "nrf5340", 2: "stm32g0b1", 3: "stm32g474", 4: "stm32h723", 5: "samd20", 6: "rp2350"}[run["board_id"]]


def dump(rec):
    """JSON with one line per measured number set, so that a record stays readable and small"""
    def stats(res):
        return "{" + ", ".join(f"{json.dumps(k)}: {json.dumps(v, separators=(',', ':'))}" for k, v in res.items()) + "}"
    head = {k: v for k, v in rec.items() if k != "images"}
    text = json.dumps(head, indent=1)[:-2] + ',\n "images": [\n'
    ims = []
    for im in rec["images"]:
        runs = []
        for r in im["runs"]:
            meta = {k: v for k, v in r.items() if k not in ("results", "baseline")}
            runs.append("    {" + json.dumps(meta)[1:-1] + ',\n     "results": ' + stats(r["results"])
                        + ',\n     "baseline": ' + stats(r["baseline"]) + "}")
        meta = {k: v for k, v in im.items() if k != "runs"}
        ims.append("  {" + json.dumps(meta)[1:-1] + ',\n   "runs": [\n' + ",\n".join(runs) + "\n   ]}")
    return text + ",\n".join(ims) + "\n ]\n}\n"


if __name__ == "__main__":
    sys.exit(main())
