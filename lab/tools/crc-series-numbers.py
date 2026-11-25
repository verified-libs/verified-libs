#!/usr/bin/env python3
"""Step 3 of lab/plans/2026-11-24-crc-from-series-to-publication.md: the
numbers of a CRC series, checked before a sentence is written about them.
Reads run files; writes nothing.

Usage: python3 -I lab/tools/crc-series-numbers.py BOARD_DIR [--pass N]

BOARD_DIR holds one board's run files (<adapter>-p<place>-pass<N>.json, from
kinds/crc/bench/run-crc.py). Pass 1 is read unless --pass says otherwise.
A "mean" is the mean of the 256 calls of one scenario in one run, in cycles,
with the overhead of the timing subtracted (the run file's own numbers).
Tables, plain text:

(a) Noise floor. The baseline (the reference of the configuration's CRC,
    the same code in every image of that CRC) per CRC and scenario: its
    means across all images of that CRC on the board (min, max, spread in
    cycles and %), and the largest spread across the eight placements of
    one configuration.
(b) Cost per byte per configuration, offset 0, cache off and on, placement
    0: (mean at 1024 bytes - mean at 256 bytes) / 768, and what is left at
    length 0 on the same line (mean at 256 - 256 x the cost per byte); the
    range of the cost per byte over the eight placements beside it.
(c) Aligned against one byte after: per configuration, length and cache,
    placement 0, where offset 1 and offset 0 differ by more than the
    baseline's spread across the images of its CRC for that scenario (a),
    and by more than 1 % (a floor of 0 would list every difference).
--all prints (a) per scenario; without it, one line per CRC: the
scenario with the largest spread.
(d) Cache off against cache on: per configuration, placement 0, the means
    at 1024 bytes, offset 0, and their ratio.
(e) The configuration's own spread over the eight placements: per
    configuration the scenario with the largest spread in %, and its
    placements.
"""
import glob
import json
import os
import re
import sys

LENS = (1, 4, 16, 64, 256, 1024)


def load(d, p):
    runs = {}   # (adapter, place) -> run
    for f in glob.glob(os.path.join(d, f"*-pass{p}.json")):
        m = re.match(r"(.+)-p(\d+)-pass\d+\.json$", os.path.basename(f))
        if m:
            runs[(m.group(1), int(m.group(2)))] = json.load(open(f))
    return runs


def mean(run, side, sc):
    v = run["libs"][0 if side == "baseline" else 1]["results"].get(sc)
    return v["mean"] if isinstance(v, dict) and v.get("mean") is not None else None


def spread(vals):
    lo, hi = min(vals), max(vals)
    return lo, hi, hi - lo, (hi - lo) / lo * 100 if lo else 0.0


def main():
    a = sys.argv[1:]
    every = "--all" in a
    a = [x for x in a if x != "--all"]
    p = 1
    if "--pass" in a:
        i = a.index("--pass"); p = int(a[i + 1]); del a[i:i + 2]
    if len(a) != 1:
        sys.exit(__doc__)
    runs = load(a[0], p)
    if not runs:
        sys.exit(f"{a[0]}: no run files of pass {p}")
    adapters = sorted({k[0] for k in runs})
    places = sorted({k[1] for k in runs})
    scen = list(next(iter(runs.values()))["libs"][0]["results"])
    print(f"{os.path.basename(os.path.normpath(a[0]))}: {len(runs)} run files of pass {p}, "
          f"{len(adapters)} configurations, placements {places}")

    crc_of = {ad: next(r["crc"] for k, r in runs.items() if k[0] == ad) for ad in adapters}
    print("\n(a) noise floor: the baseline per CRC and scenario")
    print(f"{'CRC / scenario':44} {'images':>6} {'min':>10} {'max':>10} {'spread':>9} {'%':>6}   largest over 8 placements")
    floor = {}
    for crc in sorted(set(crc_of.values())):
        ads = [ad for ad in adapters if crc_of[ad] == crc]
        rows = []
        for sc in scen:
            vals = [mean(runs[(ad, pl)], "baseline", sc) for ad in ads for pl in places if (ad, pl) in runs]
            vals = [v for v in vals if v is not None]
            if not vals:
                continue
            lo, hi, sp, pc = spread(vals)
            floor[(crc, sc)] = sp
            worst = (-1.0, "")
            for ad in ads:
                pv = [mean(runs[(ad, pl)], "baseline", sc) for pl in places if (ad, pl) in runs]
                pv = [v for v in pv if v is not None]
                if pv:
                    s2 = spread(pv)
                    if s2[3] > worst[0]:
                        worst = (s2[3], f"{s2[2]:g} ({s2[3]:.2f} %) {ad}")
            rows.append((pc, worst[0], f"{crc + ' ' + sc:44} {len(vals):6} {lo:10g} {hi:10g} {sp:9g} {pc:6.2f}   {worst[1]}"))
        for r in (rows if every else [max(rows)] if rows else []):
            print(r[2])

    print("\n(b) cost per byte, offset 0, placement 0 (range over the placements)")
    print(f"{'configuration':34} {'cache':5} {'cycles/byte':>12} {'range':>20} {'at length 0':>12}")
    for ad in adapters:
        for cache in ("off", "on"):
            def line(r):
                m256, m1024 = mean(r, "cfg", f"len256/offset0/cache_{cache}"), mean(r, "cfg", f"len1024/offset0/cache_{cache}")
                if m256 is None or m1024 is None:
                    return None
                cpb = (m1024 - m256) / 768
                return cpb, m256 - 256 * cpb
            l0 = line(runs[(ad, places[0])]) if (ad, places[0]) in runs else None
            ls = [line(runs[(ad, pl)]) for pl in places if (ad, pl) in runs]
            ls = [x for x in ls if x]
            if not l0:
                print(f"{ad:34} {cache:5} {'none':>12}")
                continue
            rng = f"{min(x[0] for x in ls):.3f} - {max(x[0] for x in ls):.3f}"
            print(f"{ad:34} {cache:5} {l0[0]:12.3f} {rng:>20} {l0[1]:12.1f}")

    print("\n(c) offset 1 against offset 0, placement 0, where the difference exceeds the baseline's spread (a) and 1 %")
    print(f"{'configuration':34} {'scenario':18} {'offset 0':>12} {'offset 1':>12} {'diff':>10} {'floor':>8}")
    n = 0
    for ad in adapters:
        r = runs.get((ad, places[0]))
        if not r:
            continue
        for ln in LENS:
            for cache in ("off", "on"):
                m0, m1 = mean(r, "cfg", f"len{ln}/offset0/cache_{cache}"), mean(r, "cfg", f"len{ln}/offset1/cache_{cache}")
                fl = max(floor.get((crc_of[ad], f"len{ln}/offset0/cache_{cache}"), 0),
                         floor.get((crc_of[ad], f"len{ln}/offset1/cache_{cache}"), 0))
                if m0 is not None and m1 is not None and abs(m1 - m0) > fl and abs(m1 - m0) > 0.01 * m0:
                    n += 1
                    print(f"{ad:34} {f'len{ln}/cache_{cache}':18} {m0:12g} {m1:12g} {m1 - m0:10g} {fl:8g}")
    if not n:
        print("none")

    print("\n(d) cache off against cache on, 1024 bytes, offset 0, placement 0")
    print(f"{'configuration':34} {'cache off':>12} {'cache on':>12} {'off/on':>8}")
    for ad in adapters:
        r = runs.get((ad, places[0]))
        if not r:
            continue
        off, on = mean(r, "cfg", "len1024/offset0/cache_off"), mean(r, "cfg", "len1024/offset0/cache_on")
        if off is None or on is None:
            print(f"{ad:34} {'none':>12}")
        else:
            print(f"{ad:34} {off:12g} {on:12g} {off / on:8.2f}")

    print("\n(e) the configuration's spread over the placements: its largest, per configuration")
    print(f"{'configuration':34} {'scenario':28} {'min':>10} {'max':>10} {'%':>7}  placements of min / max")
    for ad in adapters:
        worst = None
        for sc in scen:
            pv = [(mean(runs[(ad, pl)], "cfg", sc), pl) for pl in places if (ad, pl) in runs]
            pv = [x for x in pv if x[0] is not None]
            if len(pv) < 2:
                continue
            lo, hi = min(pv), max(pv)
            pc = (hi[0] - lo[0]) / lo[0] * 100 if lo[0] else 0.0
            if worst is None or pc > worst[0]:
                worst = (pc, sc, lo, hi)
        if worst:
            pc, sc, lo, hi = worst
            print(f"{ad:34} {sc:28} {lo[0]:10g} {hi[0]:10g} {pc:7.2f}  p{lo[1]} / p{hi[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
