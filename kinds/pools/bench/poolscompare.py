#!/usr/bin/env python3
"""Compare pools records made on your own board with ours (records of
poolrecords.py, schema "pools-bench/1"): two records, or two directories of
them, and the records of the same file name are compared. As the CRC kind's
comparison (kinds/crc/bench/crccompare.py), for this kind's records.

Usage: python3 -I poolscompare.py OURS YOURS [--tol PERCENT]
  python3 -I poolscompare.py records/pools/stm32g474 MY_RECORDS/stm32g474

First the images: a placement counts as the same firmware if the bytes in
flash (image_sha256) and the image's address are equal. Then every mean
(cycles per call) of every placement of yours, of the configuration and of
the baseline (the reference free list in the same image), against the same
placement of ours; where we have several passes, yours must lie within the
tolerance of one of them. The default tolerance is 1 %; a mean of a few
cycles may differ by one count of rounding, which is allowed (0.05 cycles).
A number that one side has and the other has not (e.g. "empty/free", which
is null on both sides when the build is the same) counts as a difference.

Where our own two passes of the board differ beyond the tolerance in some
mean of a cache state (in our records only on the Raspberry Pi Pico 2 with
the cache on: its XIP cache replaces at random, RP2350 datasheet 4.4.1.2, so
how many calls miss varies from run to run), a mean of that cache state
that lies outside the tolerance is judged by its fastest call instead: the
same within the tolerance as the fastest call of one of our passes. A mean
of one call has no faster call; it may differ from ours by no more than our
own passes differ in a mean of one call in that cache state. The count line
says how many means were judged so. On the boards whose passes agree to the
cycle, this rule never applies.
Configurations and placements that only one side has are counted, not
compared. This script measures nothing and checks no record.

Exit: 0 agreement, 1 differences, 2 the records cannot be compared.
"""
import glob
import json
import os
import sys

SCHEMA = ("pools-bench/1",)
BUILD = ("board", "core", "toolchain_image", "toolchain", "libs_pinned", "runs", "blocks", "block_size", "far_bytes",
         "layout", "result_version", "fixed_sha256", "boot_image_sha256", "sizes")


def load(path):
    """{file name: record} of a record or a directory of them; None if it is neither."""
    files = sorted(glob.glob(os.path.join(path, "*.json"))) if os.path.isdir(path) else [path]
    try:
        recs = {os.path.basename(f): json.load(open(f)) for f in files}
    except (OSError, ValueError):
        return None
    return recs if recs and all(r.get("schema") in SCHEMA for r in recs.values()) else None


def close(x, y, tol):
    return abs(x - y) <= 0.05 or (x and 100 * abs(x - y) / x <= tol)


def spread(ours, tol):
    """From our own records: {cache state: number of means whose two passes differ beyond the tolerance}, and
    {cache state: the largest difference of our passes in a mean of one call}."""
    vary, one = {}, {}
    for r in ours.values():
        for im in r["images"]:
            for part in ("results", "baseline"):
                for scen in im["runs"][0][part]:
                    xs = [q[part][scen] for q in im["runs"] if q[part].get(scen)]
                    if len(xs) < 2:
                        continue
                    cache = scen.rsplit("/", 1)[-1]
                    m = [x["mean"] for x in xs]
                    if not close(min(m), max(m), tol):
                        vary[cache] = vary.get(cache, 0) + 1
                    if all(x.get("count") == 1 for x in xs):
                        one[cache] = max(one.get(cache, 0.0), max(m) - min(m))
    return vary, one


def fastest(o, im, part, scen, tol, one_call):
    """A mean outside the tolerance in a cache state where our own passes vary: every pass of yours has the
    fastest call of one of ours (a mean of one call: within our own largest difference in a mean of one call)."""
    xs = [q[part][scen] for q in o["runs"] if q[part].get(scen)]
    ys = [q[part][scen] for q in im["runs"] if q[part].get(scen)]
    if any("min" not in v for v in xs + ys):
        return False
    if all(v.get("count") == 1 for v in xs + ys):
        return all(min(abs(x["mean"] - y["mean"]) for x in xs) <= one_call for y in ys)
    return all(any(close(x["min"], y["min"], tol) for x in xs) for y in ys)


def compare(ours, yours, tol):
    both = sorted(set(ours) & set(yours))
    if not both:
        print("no record of the same configuration on both sides")
        return 2
    print(f"{len(both)} configurations compared ({len(ours)} of ours, {len(yours)} of yours)")
    n_img = same_img = n = 0
    worst, builds, by_fast = [], set(), 0
    vary, one_call = spread(ours, tol)
    for f in both:
        a, b = ours[f], yours[f]
        for k in BUILD:
            if a.get(k) != b.get(k):
                builds.add(f"{a.get('adapter', f)} {k}: ours {json.dumps(a.get(k))[:60]}, yours {json.dumps(b.get(k))[:60]}")
        mine = {im["place"]: im for im in a["images"]}
        for im in b["images"]:
            o = mine.get(im["place"])
            if o is None:
                continue
            n_img += 1
            same_img += o["image_sha256"] == im["image_sha256"] and int(o["image_base"], 16) == int(im["image_base"], 16)
            for part in ("results", "baseline"):
                keys = sorted(set(o["runs"][0][part]) | set(im["runs"][0][part]))
                for scen in keys:
                    xs = [r[part][scen]["mean"] for r in o["runs"] if r[part].get(scen)]
                    ys = [r[part][scen]["mean"] for r in im["runs"] if r[part].get(scen)]
                    if not xs and not ys:
                        continue
                    n += 1
                    if not xs or not ys:
                        worst.append((float("inf"), a["name"], im["place"], part, scen, xs, ys))
                        continue
                    far = max(min(abs(x - y) for x in xs) for y in ys)
                    rel = max(min(100 * abs(x - y) / x if x else 0.0 for x in xs) for y in ys)
                    if far > 0.05 and rel > tol:
                        cache = scen.rsplit("/", 1)[-1]
                        if cache in vary and fastest(o, im, part, scen, tol, one_call.get(cache, 0.0)):
                            by_fast += 1
                        else:
                            worst.append((rel, a["name"], im["place"], part, scen, xs, ys))
    print(f"firmware: {same_img} of {n_img} images the same (bytes in flash and address)"
          + ("" if same_img == n_img else "; where it differs, a difference in speed says nothing about the lab"))
    for d in sorted(builds):
        print("  build differs, " + d)
    worst.sort(key=lambda w: (-w[0], w[1:5]))
    print(f"{n} means compared, {n - len(worst) - by_fast} within {tol:g} %, "
          + (f"{by_fast} by their fastest call, " if vary else "") + f"{len(worst)} outside")
    for cache, k in sorted(vary.items()):
        print(f"  with the {cache.replace('_', ' ')} our own two passes differ beyond {tol:g} % in {k} means of this board: "
              f"there a mean outside {tol:g} % is judged by its fastest call (the same within {tol:g} % as in one of our "
              f"passes; a mean of one call, by our own largest difference in a mean of one call, "
              f"{one_call.get(cache, 0.0):g} cycles)")
    for rel, name, place, part, scen, xs, ys in worst[:40]:
        print(f"  {name[:36]:36} placement {place:2} {part:8} {scen:28} ours {', '.join(map(str, sorted(set(xs)))) or 'none'}, "
              f"yours {', '.join(map(str, sorted(set(ys)))) or 'none'}"
              + (f" ({rel:.1f} %)" if rel != float("inf") else " (measured on one side only)"))
    if len(worst) > 40:
        print(f"  ... and {len(worst) - 40} more")
    return 1 if worst or same_img != n_img else 0


def main():
    args = sys.argv[1:]
    tol = 1.0
    if "--tol" in args:
        i = args.index("--tol")
        tol = float(args[i + 1])
        del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    two = [load(p) for p in args]
    if not all(two):
        print("not records of the pools kind (pools-bench/1) on both sides, or a directory without them")
        return 2
    return compare(two[0], two[1], tol)


if __name__ == "__main__":
    sys.exit(main())
