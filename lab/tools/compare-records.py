#!/usr/bin/env python3
"""Compare a result record made on your own board with one of ours.

Usage: lab/tools/compare-records.py OURS.json YOURS.json [--tol PERCENT]

Both records must be of the same kind: benchmark (*-rb-bench-*) or stress
test (*-rb-stress-*, *-rb-mp-stress-*).

Benchmark: every mean (cycles per call) of every configuration and scenario
is compared. The counts are cycles of the core, so the board's clock does not
enter. With the same firmware (fw_sha256 equal) on the same board model we
see the same means run after run, so the default tolerance is 1 % (--tol);
a mean of a few cycles may differ by one count of rounding, which is allowed
(0.05 cycles). If the firmware differs (other commit, compiler or flags) the
numbers are compared all the same, and the difference in the build is
reported first: then a difference in speed says nothing about the lab.

Stress test: a run is random in its timing, so counts are not compared. What
must agree is the verdict per configuration: errors or no errors (the
negative control and the mutants must show errors, the libraries that showed
none must show none). A configuration with errors in one record and none in
the other is listed; with few transfers a real defect can stay unseen, so
compare runs of similar length ("transfers").

Benchmark version 2 (records/bench-v2/<board>/<configuration>.json, one
record per configuration with an image per placement): give two records,
or two directories of them, and the records of the same file name are
compared:
  lab/tools/compare-records.py records/bench-v2/stm32g474 MY_RECORDS/stm32g474
First the images: a placement counts as the same firmware if the bytes in
flash (image_sha256) and the image's address are equal. Then every mean
of every placement of yours against the same placement of ours; where we
have several passes, yours must lie within the tolerance of one of them.
Configurations and placements that only one side has are counted, not
compared: a short run of yours need not hold them all.

Exit: 0 agreement, 1 differences, 2 the records cannot be compared.
"""
import glob
import json
import os
import sys

SETTINGS_BENCH = ["board", "core", "set", "code_location", "opt", "lto", "compiler_libs", "memcpy", "shift",
                  "runs", "toolchain_image", "toolchain", "libs_pinned"]
SETTINGS_STRESS = ["board", "core", "mode", "code_location", "opt", "lto", "compiler_libs", "build_flags",
                   "toolchain_image", "toolchain", "libs_pinned"]


def kind(r):
    return "bench" if "bench_commit" in r or "scenarios" in r else "stress"


def commit(r):
    return r.get("source_commit") or r.get("bench_commit") or "not recorded"


def build_diff(a, b, keys):
    out = []
    if commit(a) != commit(b):
        out.append(f"commit: ours {commit(a)}, yours {commit(b)}")
    for k in keys:
        if a.get(k) != b.get(k):
            x, y = json.dumps(a.get(k)), json.dumps(b.get(k))
            out.append(f"{k}: ours {x[:70]}, yours {y[:70]}")
    return out


def errors_of(lib):
    """Total errors of a stress record's configuration, or None if it did not run."""
    if lib.get("n/a"):
        return None
    n, seen = 0, False
    for v in lib.values():
        if isinstance(v, dict) and "errors" in v:
            n += v["errors"]
            seen = True
    return n if seen else None


def bench2(ours, yours, tol):
    """Version 2: {file name: record} of each side. Returns the exit code."""
    both = sorted(set(ours) & set(yours))
    if not both:
        print("no record of the same configuration on both sides")
        return 2
    print(f"{len(both)} configurations compared ({len(ours)} of ours, {len(yours)} of yours)")
    n_img = same_img = n = 0
    worst, builds = [], set()
    for f in both:
        a, b = ours[f], yours[f]
        for k in ("board", "core", "toolchain_image", "toolchain", "libs_pinned", "runs", "far_bytes", "result_version"):
            if a.get(k) != b.get(k):
                builds.add(f"{k}: ours {json.dumps(a.get(k))[:60]}, yours {json.dumps(b.get(k))[:60]}")
        mine = {im["place"]: im for im in a["images"]}
        for im in b["images"]:
            o = mine.get(im["place"])
            if o is None:
                continue
            n_img += 1
            same_img += o["image_sha256"] == im["image_sha256"] and int(o["image_base"], 16) == int(im["image_base"], 16)
            for scen in o["runs"][0]["results"]:
                for side in ("push", "pop"):
                    xs = [r["results"][scen][side]["mean"] for r in o["runs"] if (r["results"].get(scen) or {}).get(side)]
                    ys = [r["results"][scen][side]["mean"] for r in im["runs"] if (r["results"].get(scen) or {}).get(side)]
                    if not xs and not ys:
                        continue
                    n += 1
                    if not xs or not ys:
                        worst.append((float("inf"), a["name"], im["place"], scen, side, xs, ys))
                        continue
                    far = max(min(abs(x - y) for x in xs) for y in ys)
                    rel = max(min(100 * abs(x - y) / x if x else 0.0 for x in xs) for y in ys)
                    if far > 0.05 and rel > tol:
                        worst.append((rel, a["name"], im["place"], scen, side, xs, ys))
    print(f"firmware: {same_img} of {n_img} images the same (bytes in flash and address)"
          + ("" if same_img == n_img else "; where it differs, a difference in speed says nothing about the lab"))
    for d in sorted(builds):
        print("  build differs, " + d)
    worst.sort(key=lambda w: (-w[0], w[1:5]))
    print(f"{n} means compared, {n - len(worst)} within {tol:g} %, {len(worst)} outside")
    for rel, name, place, scen, side, xs, ys in worst[:40]:
        print(f"  {name[:40]:40} placement {place:2} {scen:8} {side:4} ours {', '.join(map(str, sorted(set(xs)))) or 'none'}, "
              f"yours {', '.join(map(str, sorted(set(ys)))) or 'none'}"
              + (f" ({rel:.1f} %)" if rel != float("inf") else " (measured on one side only)"))
    if len(worst) > 40:
        print(f"  ... and {len(worst) - 40} more")
    return 1 if worst or same_img != n_img else 0


def load2(path):
    """{file name: record} of a version 2 record or a directory of them; None if it is neither."""
    files = sorted(glob.glob(os.path.join(path, "*.json"))) if os.path.isdir(path) else [path]
    recs = {os.path.basename(f): json.load(open(f)) for f in files}
    return recs if recs and all(r.get("schema") in ("rb-bench/2", "rb-bench/3") for r in recs.values()) else None


def main():
    args = sys.argv[1:]
    tol = 1.0
    if "--tol" in args:
        i = args.index("--tol")
        tol = float(args[i + 1])
        del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    two = [load2(f) for f in args]
    if all(two):
        sys.exit(bench2(two[0], two[1], tol))
    if any(two) or any(os.path.isdir(f) for f in args):
        print("one side is of benchmark version 2 and the other is not (or a directory without its records)")
        sys.exit(2)
    a, b = (json.load(open(f)) for f in args)
    if kind(a) != kind(b):
        print("one record is a benchmark and the other a stress test")
        sys.exit(2)
    same_fw = bool(a.get("fw_sha256")) and a.get("fw_sha256") == b.get("fw_sha256")
    print("firmware: " + ("the same (fw_sha256 equal)" if same_fw else
                          f"different (ours {str(a.get('fw_sha256'))[:16]}, yours {str(b.get('fw_sha256'))[:16]})"))
    diffs = build_diff(a, b, SETTINGS_BENCH if kind(a) == "bench" else SETTINGS_STRESS)
    for d in diffs:
        print("  build differs, " + d)
    la, lb = ({l["name"]: l for l in r["libs"]} for r in (a, b))
    only = sorted(set(la) ^ set(lb))
    if only:
        print("configurations in one record only: " + ", ".join(only))
    bad = 0
    if kind(a) == "bench":
        n, worst = 0, []
        for name in la:
            if name not in lb:
                continue
            for scen, res in (la[name].get("results") or {}).items():
                for side in ("push", "pop"):
                    x = (res or {}).get(side) or {}
                    y = ((lb[name].get("results") or {}).get(scen) or {}).get(side) or {}
                    if not x.get("count") and not y.get("count"):
                        continue
                    n += 1
                    if not x.get("count") or not y.get("count"):
                        worst.append((float("inf"), name, scen, side, x.get("mean"), y.get("mean")))
                        continue
                    d = abs(x["mean"] - y["mean"])
                    rel = 100 * d / x["mean"] if x["mean"] else 0.0
                    if d > 0.05 and rel > tol:
                        worst.append((rel, name, scen, side, x["mean"], y["mean"]))
        worst.sort(reverse=True)
        print(f"{n} means compared, {n - len(worst)} within {tol:g} %, {len(worst)} outside")
        for rel, name, scen, side, x, y in worst[:40]:
            print(f"  {name[:44]:44} {scen:18} {side:4} ours {x}, yours {y}"
                  + (f" ({rel:.1f} %)" if rel != float("inf") else " (measured in one record only)"))
        if len(worst) > 40:
            print(f"  ... and {len(worst) - 40} more")
        bad = len(worst)
    else:
        print(f"transfers per configuration and direction: ours {a.get('transfers')}, yours {b.get('transfers')}")
        n = 0
        for name in la:
            if name not in lb:
                continue
            x, y = errors_of(la[name]), errors_of(lb[name])
            if x is None or y is None:
                if x != y:
                    print(f"  {name}: ran in one record only")
                    bad += 1
                continue
            n += 1
            if bool(x) != bool(y):
                print(f"  {name}: ours {x} errors, yours {y} errors")
                bad += 1
        print(f"{n} configurations compared, {n - bad} with the same verdict (errors or no errors), {bad} not")
    if only:
        sys.exit(2)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
