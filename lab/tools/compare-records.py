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

Exit: 0 agreement, 1 differences, 2 the records cannot be compared.
"""
import json
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


def main():
    args = sys.argv[1:]
    tol = 1.0
    if "--tol" in args:
        i = args.index("--tol")
        tol = float(args[i + 1])
        del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
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
