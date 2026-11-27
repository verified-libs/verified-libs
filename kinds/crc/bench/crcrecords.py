#!/usr/bin/env python3
"""Make the CRC kind's records from the run files of run-crc.py: one record
per board and configuration, holding its eight images (one per placement)
and every run of each. As version 2's record writer
(firmware/nrf5340-rb-bench/onerecords.py), for this kind's run files
(schema "crc-bench-run/1") and with a schema of its own ("crc-bench/1").

Usage: python3 -I crcrecords.py [--check] [--out DIR] RUNDIR...

  RUNDIR   output directories of run-crc.py (build.json, bundle<N>.json and
           the run files), of one board or of several
  --out    where the records go (default: records/crc of this tree), as
           <board>/<adapter>.json; a record that is there is replaced
  --check  write nothing, only check and print the summary

A record is made only if the configuration is whole: all eight placements
were run, each in exactly the passes of a series (PASSES: 1 and 2) with a
run file each, and every run agrees on what it ran (image checksums, the
fixed part, the boot stub, the build, the layout of the image, clock,
lengths, offsets and number of repetitions); every one of those fields must
be in the run file. A run file is taken only if it is of the build next to
it (build.json: the same commit, toolchain image and board), its two result
sets are the baseline and the configuration it names, and both agreed with
the reference on every call (errors 0). A run of a tree with uncommitted
changes ("+dirty") is never taken: its image cannot be rebuilt. Anything
else is named and the configuration left out.

The summary also says, per board and CRC, whether the baseline (the
reference of that CRC, the same code at the same place in every image of a
board) measured the same in every run.
Exit: 0 every configuration found gave a record, 1 not.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "../../.."))
SCHEMA = "crc-bench/1"
SCHEMA_V3 = "crc-bench/2"   # the same, with the board's option_registers (method version 3)
RUN_SCHEMA = "crc-bench-run/1"

# Method version 3 (DECISIONS 2026-11-26): the option registers of the board, read zero-write before a
# series by lab/tools/read-options.py into the run directory (options.json, schema board-options/1). A
# record of runs whose directories hold that file is of the new version and carries them as
# "option_registers"; a record of runs without it is of the version before, unchanged.
OPTIONS_SCHEMA = "board-options/1"


def options_of(d, board):
    """(the options.json of run directory d, or None; a problem, or None)."""
    p = os.path.join(d, "options.json")
    if not os.path.exists(p):
        return None, None
    o = json.load(open(p))
    if (o.get("schema") != OPTIONS_SCHEMA or o.get("board") != board or not o.get("regions")
            or any("error" in x or "words" not in x for x in o["regions"])):
        return None, f"{p}: not every option register of {board} read (schema {OPTIONS_SCHEMA})"
    return o, None


def with_options(rec, runs, schema_new):
    """rec with the new schema and its option_registers if every run has them; (rec, None) or (None, why)."""
    opts = [r.get("_options") for r in runs]
    if all(o is None for o in opts):
        return rec, None
    if any(o is None for o in opts):
        return None, "runs with and without option registers"
    seen, out = set(), []
    for o in sorted(opts, key=lambda o: o["time"]):
        key = json.dumps(o, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(o)
    rec = dict(rec, schema=schema_new)
    rec["option_registers"] = out
    return rec, None
PLACES = (0, 4, 8, 12, 16, 20, 24, 28)   # as version 2 (oneslots.py PLACES)
PASSES = [1, 2]                          # a series: two passes (decided 2026-11-23, as version 2)
# the same in every run of a record
COMMON = ("board", "core", "board_id", "board_decoded", "code_location", "kind", "crc", "adapter", "lang", "name",
          "bench_commit", "toolchain_image", "result_version", "clock_hz", "runs", "lens", "offsets",
          "overhead_subtracted", "empty_call_raw_min", "fixed_sha256", "boot_image_sha256", "far_bytes", "layout")
# the same in every run of an image
IMAGE = ("place", "slot", "image_base", "image_bytes", "fw_sha256", "image_sha256")
# of one run
RUN = ("time", "host", "probe_rs", "pass", "attempt", "wait_s", "seconds", "run_number", "bundle", "bundle_sha256")
BOARD_DIR = {1: "nrf5340", 2: "stm32g0b1", 3: "stm32g474", 4: "stm32h723", 5: "samd20", 6: "rp2350"}


def collect(dirs, problems):
    """(board, adapter) -> [run], and (board, adapter) -> the build.json of its runs."""
    groups, builds = {}, {}
    for d in dirs:
        try:
            built = json.load(open(os.path.join(d, "build.json")))
        except OSError:
            sys.exit(f"{d}: no build.json (not an output directory of run-crc.py)")
        if built.get("kind") != "crc":
            sys.exit(f"{d}: build.json is not of the CRC kind")
        opts, why = options_of(d, built.get("board"))
        if why:
            problems.append(why)
            continue
        for f in sorted(glob.glob(os.path.join(d, "adapter_*-p*-pass*.json"))):
            r = json.load(open(f))
            if r.get("schema") != RUN_SCHEMA or r.get("invalid"):
                problems.append(f"{f}: not a valid run file" + (f" ({r['invalid']})" if r.get("invalid") else ""))
                continue
            if (r.get("bench_commit") != built.get("bench_commit") or r.get("toolchain_image") != built.get("toolchain_image")
                    or BOARD_DIR.get(r.get("board_id")) != built.get("board")):
                problems.append(f"{f}: not of the build in {d}/build.json (commit, toolchain image or board)")
                continue
            libs = r.get("libs") or []
            if (len(libs) != 2 or libs[0].get("name") != "baseline" or libs[1].get("name") != r.get("name")
                    or any(lib.get("errors") != 0 for lib in libs)):
                problems.append(f"{f}: its results are not the baseline and {r.get('name')!r}, both without errors")
                continue
            key = (r["board"], r["adapter"])
            if key in builds and builds[key]["bench_commit"] != built["bench_commit"]:
                problems.append(f"{f}: runs of {r['adapter']} on {r['board']} from two builds")
                continue
            r["_file"] = f
            r["_options"] = opts
            groups.setdefault(key, []).append(r)
            builds[key] = built
    return groups, builds


def make(runs, built):
    """(record, None) or (None, why it is not whole)."""
    if runs[0]["bench_commit"].endswith("+dirty") or runs[0]["bench_commit"] in ("", "unknown"):
        return None, f"commit {runs[0]['bench_commit']!r} cannot be rebuilt (uncommitted changes, or unknown)"
    for k in COMMON + IMAGE + RUN:
        if any(r.get(k) is None for r in runs):
            return None, f"a run without {k}"
    for k in COMMON:
        if any(r.get(k) != runs[0].get(k) for r in runs):
            return None, f"the runs differ in {k}"
    if any(r["place"] not in PLACES for r in runs):
        return None, "a placement that is not in the table"
    passes = sorted({r["pass"] for r in runs})
    if passes != PASSES:
        return None, f"passes {passes}, a series has {PASSES}"
    images = []
    for place in PLACES:
        mine = sorted((r for r in runs if r["place"] == place), key=lambda r: (r["pass"], r["time"]))
        if sorted(r["pass"] for r in mine) != passes:
            return None, f"placement {place}: passes {[r['pass'] for r in mine]} of {passes}"
        for k in IMAGE:
            if any(r.get(k) != mine[0].get(k) for r in mine):
                return None, f"placement {place}: the runs differ in {k}"
        im = {k: mine[0].get(k) for k in IMAGE}
        im["runs"] = [dict({k: r.get(k) for k in RUN}, errors=r["libs"][1]["errors"],
                           baseline_errors=r["libs"][0]["errors"], results=r["libs"][1]["results"],
                           baseline=r["libs"][0]["results"]) for r in mine]
        images.append(im)
    rec = dict({"schema": SCHEMA}, **{k: runs[0].get(k) for k in COMMON})
    rec["toolchain"], rec["libs_pinned"] = built["toolchain"], built["libs_pinned"]
    rec["crcany_generated_lock_sha256"] = built.get("crcany_generated_lock_sha256")
    rec["passes"] = len(passes)
    rec, why = with_options(rec, runs, SCHEMA_V3)
    if why:
        return None, why
    rec["images"] = images
    return rec, None


def main():
    args = sys.argv[1:]
    check = "--check" in args
    args = [a for a in args if a != "--check"]
    out = os.path.join(ROOT, "records/crc")
    if args[:1] == ["--out"] and len(args) >= 2:
        out, args = args[1], args[2:]
    if not args or any(a.startswith("-") for a in args):
        sys.exit(__doc__)
    problems = []
    groups, builds = collect(args, problems)
    written, left, base_note = 0, 0, {}
    for (board, adapter), runs in sorted(groups.items()):
        rec, why = make(runs, builds[(board, adapter)])
        if why:
            left += 1
            problems.append(f"{board} {adapter}: left out: {why}")
            continue
        # the baseline over all runs of the board, per CRC (each CRC has its own reference)
        note = base_note.setdefault((board, rec["crc"]), {"runs": 0, "values": {}})
        for im in rec["images"]:
            for r in im["runs"]:
                note["runs"] += 1
                for scen, v in r["baseline"].items():
                    if v:
                        note["values"].setdefault(scen, set()).add(v["mean"])
        written += 1
        if not check:
            name = os.path.join(out, BOARD_DIR[rec["board_id"]], adapter + ".json")
            os.makedirs(os.path.dirname(name), exist_ok=True)
            with open(name, "w") as fh:
                fh.write(dump(rec))
    for p in problems:
        print(p)
    for (board, crc), note in sorted(base_note.items()):
        moved = {k: sorted(v) for k, v in note["values"].items() if len(v) > 1}
        print(f"{board} {crc}: baseline in {note['runs']} runs: {len(note['values']) - len(moved)} of {len(note['values'])} "
              f"numbers the same in every run" + ("" if not moved else "; not the same: " + "; ".join(
                  f"{k} {v[0]} to {v[-1]} ({len(v)} values)" for k, v in sorted(moved.items()))))
    print(f"{written} records{'' if not check else ' (not written: --check)'}, {left} configurations left out, "
          f"{len(problems) - left} other problems")
    return 1 if problems else 0


def dump(rec):
    """JSON with one line per measured number set, so that a record stays readable and small (as onerecords.py)"""
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
