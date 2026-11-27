#!/usr/bin/env python3
"""Compare CRC records made on your own board with ours (records of
crcrecords.py, schema "crc-bench/1"): two records, or two directories of
them, and the records of the same file name are compared. As version 2's
comparison (lab/tools/compare-records.py), for this kind's records.

Usage: python3 -I crccompare.py OURS YOURS [--tol PERCENT]
  python3 -I crccompare.py records/crc/stm32g474 MY_RECORDS/stm32g474

First the images: a placement counts as the same firmware if the bytes in
flash (image_sha256) and the image's address are equal. Then every mean
(cycles per call) of every placement of yours, of the configuration and of
the baseline in the same image, against the same placement of ours; where
we have several passes, yours must lie within the tolerance of one of
them. The default tolerance is 1 %; a mean of a few cycles may differ by
one count of rounding, which is allowed (0.05 cycles). Configurations and
placements that only one side has are counted, not compared.

Exit: 0 agreement, 1 differences, 2 the records cannot be compared.
"""
import glob
import json
import os
import sys

SCHEMA = ("crc-bench/1", "crc-bench/2")   # /2: with option registers (method version 3)
BUILD = ("board", "core", "crc", "toolchain_image", "toolchain", "libs_pinned", "runs", "lens", "offsets", "far_bytes",
         "layout", "result_version", "fixed_sha256", "boot_image_sha256")


def load(path):
    """{file name: record} of a record or a directory of them; None if it is neither."""
    files = sorted(glob.glob(os.path.join(path, "*.json"))) if os.path.isdir(path) else [path]
    try:
        recs = {os.path.basename(f): json.load(open(f)) for f in files}
    except (OSError, ValueError):
        return None
    return recs if recs and all(r.get("schema") in SCHEMA for r in recs.values()) else None


def compare(ours, yours, tol):
    both = sorted(set(ours) & set(yours))
    if not both:
        print("no record of the same configuration on both sides")
        return 2
    print(f"{len(both)} configurations compared ({len(ours)} of ours, {len(yours)} of yours)")
    n_img = same_img = n = 0
    worst, builds = [], set()
    for f in both:
        a, b = ours[f], yours[f]
        for k in BUILD:
            if a.get(k) != b.get(k):
                builds.add(f"{k}: ours {json.dumps(a.get(k))[:60]}, yours {json.dumps(b.get(k))[:60]}")
        mine = {im["place"]: im for im in a["images"]}
        for im in b["images"]:
            o = mine.get(im["place"])
            if o is None:
                continue
            n_img += 1
            same_img += o["image_sha256"] == im["image_sha256"] and int(o["image_base"], 16) == int(im["image_base"], 16)
            for part in ("results", "baseline"):
                for scen in o["runs"][0][part]:
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
                        worst.append((rel, a["name"], im["place"], part, scen, xs, ys))
    print(f"firmware: {same_img} of {n_img} images the same (bytes in flash and address)"
          + ("" if same_img == n_img else "; where it differs, a difference in speed says nothing about the lab"))
    for d in sorted(builds):
        print("  build differs, " + d)
    worst.sort(key=lambda w: (-w[0], w[1:5]))
    print(f"{n} means compared, {n - len(worst)} within {tol:g} %, {len(worst)} outside")
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
        print("not records of the CRC kind (crc-bench/1) on both sides, or a directory without them")
        return 2
    return compare(two[0], two[1], tol)


if __name__ == "__main__":
    sys.exit(main())
