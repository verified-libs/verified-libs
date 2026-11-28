#!/usr/bin/env python3
"""For the CRC pages: the numbers of the CRC series, checked, from the records (records/crc,
schema crc-bench/1). Reads only; writes nothing. The class of each
configuration comes from kinds/crc/README.md, step 2 (as site/crc_tables.py).

Usage: python3 -I lab/tools/crc-series-checks.py [--records DIR] CHECK...

CHECK, one or more of:
  noise      passes and baseline: per board how many means are identical
             between the two passes, the largest pass difference (the
             repeat error), the baseline per CRC across all images; for the
             means that differ between the passes: the same minimum or not,
             and whether the slowest call is the first call of the scenario
  perbyte    cost per byte, (mean at 1024 - mean at 256) / 768, and what is
             left at length 0 on the same line, offset 0, per board, class
             and configuration, cache on and off: min-max over the placements
  sameclass  per class that two or more libraries offer: per board and cache
             state, the configurations' ranges over the placements of the
             cost per byte and of the mean at 16 bytes, and whether the
             ranges overlap
  offset     offset 1 against offset 0 (all placements, first pass): per
             board and configuration the largest relative difference, listed
             where it exceeds the board's repeat error
  cache      cache off against cache on at 1024 bytes, offset 0: per board
             the range of off/on over the configurations and placements
  ram        a table built in RAM (libcrc, CRC++) against a table in flash of
             the same class: cost per byte ranges, per board and cache state
  classes    per board, CRC and cache state: each class's range of the cost
             per byte over its configurations and placements, and which
             class ranges overlap
  first      the first call in the figures a page shows (16 bytes, and the
             cost per byte from 256 and 1024 bytes; offset 0; cache on and
             off): per board the largest mean - min of the 256 calls, the
             part of the mean that is the first call's excess ((first -
             min) / 256), and the largest change of the cost per byte if
             the first call were left out of both means
  period     per board and configuration, cache off and on, 1024 bytes,
             offset 0: the smallest step d of 4, 8, 16, 32 bytes with
             mean(p) == mean(p + d) for every placement p (4: the same at
             every placement; 32: none shorter), and the spread over the
             placements
"""
import collections
import glob
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
spec = importlib.util.spec_from_file_location("crc_tables", os.path.join(ROOT, "site", "crc_tables.py"))
ct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ct)
BOARDS = ("stm32g474", "stm32g0b1", "nrf5340", "stm32h723", "samd20", "rp2350")
SCEN = [f"len{l}/offset{o}/cache_{c}" for c in ("off", "on") for l in (1, 4, 16, 64, 256, 1024) for o in (0, 1)]


def load(rdir):
    """board -> adapter -> record"""
    out = {}
    for b in BOARDS:
        for f in sorted(glob.glob(os.path.join(rdir, b, "*.json"))):
            r = json.load(open(f))
            if r.get("schema") in ("crc-bench/1", "crc-bench/2"):
                out.setdefault(b, {})[r["adapter"]] = r
    return out


def run(rec, place, p=1):
    im = next(i for i in rec["images"] if i["place"] == place)
    return next(r for r in im["runs"] if r["pass"] == p)


def m(rec, place, sc, side="results", p=1):
    v = run(rec, place, p)[side].get(sc)
    return v["mean"] if isinstance(v, dict) else None


def places(rec):
    return sorted(i["place"] for i in rec["images"])


def rng(vals, fmt="{:.2f}"):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "none"
    lo, hi = min(vals), max(vals)
    return fmt.format(lo) if fmt.format(lo) == fmt.format(hi) else f"{fmt.format(lo)}-{fmt.format(hi)}"


def cpb(rec, place, cache):
    a, b = m(rec, place, f"len256/offset0/cache_{cache}"), m(rec, place, f"len1024/offset0/cache_{cache}")
    if a is None or b is None:
        return None, None
    k = (b - a) / 768
    return k, a - 256 * k


def repeat_error(recs):
    worst = 0.0
    for rec in recs.values():
        for pl in places(rec):
            for side in ("results", "baseline"):
                for sc in SCEN:
                    a, b = m(rec, pl, sc, side, 1), m(rec, pl, sc, side, 2)
                    if a is not None and b is not None and a != b:
                        worst = max(worst, abs(a - b) / max(a, b) * 100)
    return worst


def check_noise(data):
    print("== noise: passes and baseline")
    for b, recs in data.items():
        n = same = 0
        diff = []
        for ad, rec in recs.items():
            for pl in places(rec):
                r1, r2 = run(rec, pl, 1), run(rec, pl, 2)
                for side in ("results", "baseline"):
                    for sc in SCEN:
                        v1, v2 = r1[side].get(sc), r2[side].get(sc)
                        if not isinstance(v1, dict):
                            continue
                        n += 1
                        if v1["mean"] == v2["mean"]:
                            same += 1
                        else:
                            diff.append((ad, pl, side, sc, v1, v2))
        print(f"{b}: {same} of {n} means identical between the passes; repeat error {repeat_error(recs):.2f} %")
        if diff:
            sm = sum(1 for d in diff if d[4]["min"] == d[5]["min"])
            first_slow = sum(1 for d in diff if (d[4]["max"] == d[4]["first"]) or (d[5]["max"] == d[5]["first"]))
            first_both = sum(1 for d in diff if d[4]["max"] == d[4]["first"] and d[5]["max"] == d[5]["first"])
            maxdiff = sum(1 for d in diff if d[4]["max"] != d[5]["max"])
            print(f"  {len(diff)} differ: sides {dict(collections.Counter(d[2] for d in diff))}, "
                  f"cache {dict(collections.Counter(d[3].split('/')[2] for d in diff))}; same minimum in {sm}; "
                  f"maximum differs in {maxdiff}; the slowest call is the first call of the scenario in at least one pass "
                  f"in {first_slow}, in both passes in {first_both}")
        for crc in sorted({r["crc"] for r in recs.values()}):
            for sc in ("len1024/offset0/cache_off", "len1024/offset0/cache_on"):
                vals = [m(r, pl, sc, "baseline", p) for r in recs.values() if r["crc"] == crc for pl in places(r) for p in (1, 2)]
                print(f"  baseline {crc} {sc}: {len(vals)} runs, {rng(vals, '{:g}')}")


def check_perbyte(data, cls):
    print("== perbyte: (mean1024 - mean256)/768 and the rest at length 0, offset 0, min-max over the placements")
    for b, recs in data.items():
        print(f"{b}")
        for ad in sorted(recs, key=lambda a: (cls.get(a, ('?',))[0], a)):
            rec = recs[ad]
            row = []
            for cache in ("off", "on"):
                v = [cpb(rec, pl, cache) for pl in places(rec)]
                row.append(f"cache {cache}: {rng([x[0] for x in v])} /B, rest {rng([x[1] for x in v], '{:.0f}')}")
            print(f"  {cls.get(ad, ('?',))[0]:24} {ad:34} " + "; ".join(row))


def classes_multi(cls, ads):
    by = collections.defaultdict(list)
    for ad in ads:
        if ad in cls:
            by[(cls[ad][0], ad.split("_")[2] if ad.split("_")[2].startswith("crc") else "")].append(ad)
    return by


def crc_of(rec):
    return rec["crc"]


def check_sameclass(data, cls):
    print("== sameclass: ranges over the placements, and whether they overlap")
    for b, recs in data.items():
        groups = collections.defaultdict(list)
        for ad, rec in recs.items():
            groups[(rec["crc"], cls.get(ad, ("?",))[0])].append(ad)
        for (crc, c), ads in sorted(groups.items()):
            libs = {a.split("_")[1] for a in ads}
            if len(libs) < 2:
                continue
            for cache in ("off", "on"):
                parts, ivals = [], []
                for ad in sorted(ads):
                    v = [cpb(recs[ad], pl, cache)[0] for pl in places(recs[ad])]
                    v16 = [m(recs[ad], pl, f"len16/offset0/cache_{cache}") for pl in places(recs[ad])]
                    ivals.append((min(v), max(v)))
                    parts.append(f"{ad.replace('adapter_', '')} {rng(v)} /B, 16 B {rng(v16, '{:.0f}')}")
                overlap = max(lo for lo, _ in ivals) <= min(hi for _, hi in ivals)
                print(f"{b} {crc} {c} cache {cache}: " + " | ".join(parts) + f" | per-byte ranges all overlap: {'yes' if overlap else 'no'}")


def check_offset(data):
    print("== offset: offset 1 against offset 0, first pass, every placement; above the board's repeat error")
    for b, recs in data.items():
        rep = repeat_error(recs)
        rows = []
        for ad, rec in recs.items():
            worst = (0.0, "")
            for pl in places(rec):
                for cache in ("off", "on"):
                    for ln in (1, 4, 16, 64, 256, 1024):
                        a, c = m(rec, pl, f"len{ln}/offset0/cache_{cache}"), m(rec, pl, f"len{ln}/offset1/cache_{cache}")
                        if a and c:
                            d = (c - a) / a * 100
                            if abs(d) > abs(worst[0]):
                                worst = (d, f"p{pl} len{ln} cache {cache}: {a:g} / {c:g}")
            if abs(worst[0]) > rep:
                rows.append((abs(worst[0]), f"  {ad:34} {worst[0]:+.2f} % ({worst[1]})"))
        print(f"{b}: repeat error {rep:.2f} %; {len(rows)} of {len(recs)} configurations above it")
        for _, line in sorted(rows, reverse=True):
            print(line)


def check_cache(data):
    print("== cache: off/on at 1024 bytes, offset 0, every configuration and placement")
    for b, recs in data.items():
        v = []
        for ad, rec in recs.items():
            for pl in places(rec):
                off, on = m(rec, pl, "len1024/offset0/cache_off"), m(rec, pl, "len1024/offset0/cache_on")
                if off and on:
                    v.append((off / on, ad, pl))
        lo, hi = min(v), max(v)
        print(f"{b}: off/on {lo[0]:.2f} ({lo[1]} p{lo[2]}) to {hi[0]:.2f} ({hi[1]} p{hi[2]})")


def check_ram(data, cls):
    print("== ram: a table built in RAM against a table in flash of the same class, cost per byte, min-max over the placements")
    pairs = {"CRC-32/ISO-HDLC": ["adapter_libcrc_crc32"], "CRC-16/IBM-3740": ["adapter_libcrc_ccitt_ffff", "adapter_crcpp_ccittfalse_table"]}
    for b, recs in data.items():
        for crc, ram in pairs.items():
            flash = [ad for ad, r in recs.items() if r["crc"] == crc and cls.get(ad, ("",))[0] == "table of 256" and ad not in ram]
            for cache in ("off", "on"):
                parts = [f"{ad.replace('adapter_', '')} (RAM) {rng([cpb(recs[ad], pl, cache)[0] for pl in places(recs[ad])])}" for ad in ram]
                parts += [f"{ad.replace('adapter_', '')} (flash) {rng([cpb(recs[ad], pl, cache)[0] for pl in places(recs[ad])])}" for ad in flash]
                print(f"{b} {crc} cache {cache}: " + " | ".join(parts))


def wofirst(v):
    """the mean of the 256 calls without the first"""
    return (v["mean"] * v["count"] - v["first"]) / (v["count"] - 1)


def check_first(data):
    print("== first: the first call of a scenario in the page's figures, every configuration and placement, first pass")
    for b, recs in data.items():
        for cache in ("on", "off"):
            out = []
            for ln in (16, 256, 1024):
                sc = f"len{ln}/offset0/cache_{cache}"
                w_mm, w_f = (0.0, ""), (0.0, "")
                for ad, rec in recs.items():
                    for pl in places(rec):
                        v = run(rec, pl)["results"].get(sc)
                        if not isinstance(v, dict):
                            continue
                        mm = (v["mean"] - v["min"]) / v["mean"] * 100
                        fx = (v["first"] - v["min"]) / v["count"] / v["mean"] * 100
                        if mm > w_mm[0]:
                            w_mm = (mm, f"{ad.replace('adapter_', '')} p{pl}: mean {v['mean']:g}, min {v['min']}")
                        if fx > w_f[0]:
                            w_f = (fx, f"{ad.replace('adapter_', '')} p{pl}: first {v['first']}, min {v['min']}, mean {v['mean']:g}")
                out.append(f"  {ln} B: mean above min up to {w_mm[0]:.2f} % ({w_mm[1]}); first call's excess up to {w_f[0]:.2f} % of the mean ({w_f[1]})")
            worst = (0.0, "")
            for ad, rec in recs.items():
                for pl in places(rec):
                    r = run(rec, pl)["results"]
                    a, c = r.get(f"len256/offset0/cache_{cache}"), r.get(f"len1024/offset0/cache_{cache}")
                    if isinstance(a, dict) and isinstance(c, dict):
                        k1 = (c["mean"] - a["mean"]) / 768
                        k2 = (wofirst(c) - wofirst(a)) / 768
                        d = abs(k1 - k2) / k1 * 100 if k1 else 0.0
                        if d > worst[0]:
                            worst = (d, f"{ad.replace('adapter_', '')} p{pl}: {k1:.3f} with, {k2:.3f} without the first call")
            print(f"{b} cache {cache}:")
            print("\n".join(out))
            print(f"  per byte: largest change without the first call {worst[0]:.2f} % ({worst[1]})")


def check_classes(data, cls):
    print("== classes: per board, CRC and cache state, each class's per-byte range (configurations and placements); overlaps")
    for b, recs in data.items():
        for crc in sorted({r["crc"] for r in recs.values()}):
            for cache in ("on", "off"):
                by = collections.defaultdict(list)
                for ad, rec in recs.items():
                    if rec["crc"] == crc:
                        by[cls.get(ad, ("?",))[0]] += [cpb(rec, pl, cache)[0] for pl in places(rec)]
                iv = {c: (min(v), max(v)) for c, v in by.items()}
                ov = [f"{a} / {c}" for i, a in enumerate(sorted(iv)) for c in sorted(iv)[i + 1:]
                      if iv[a][0] <= iv[c][1] and iv[c][0] <= iv[a][1]]
                print(f"{b} {crc} cache {cache}: " + "; ".join(f"{c} {iv[c][0]:.2f}-{iv[c][1]:.2f}" for c in sorted(iv))
                      + f" | overlapping: {', '.join(ov) if ov else 'none'}")


def check_period(data):
    print("== period: smallest step d (bytes) with mean(p) == mean(p+d) for all p, 1024 bytes offset 0; spread over the placements")
    for b, recs in data.items():
        for cache in ("off", "on"):
            per, spreads = collections.Counter(), []
            for ad, rec in recs.items():
                vals = {pl: m(rec, pl, f"len1024/offset0/cache_{cache}") for pl in places(rec)}
                d = next((d for d in (4, 8, 16) if all(vals[p] == vals[(p + d) % 32] for p in vals)), 32)
                per[d] += 1
                lo, hi = min(vals.values()), max(vals.values())
                spreads.append(((hi - lo) / lo * 100, ad))
            spreads.sort()
            lab = {4: "same at every placement", 8: "8 B", 16: "16 B", 32: "32 B or none shorter"}
            print(f"{b} cache {cache}: " + ", ".join(f"{lab[k]}: {v}" for k, v in sorted(per.items())) + f"; spread {spreads[0][0]:.2f} % ({spreads[0][1]}) to {spreads[-1][0]:.2f} % ({spreads[-1][1]})")


def main():
    a = sys.argv[1:]
    rdir = os.path.join(ROOT, "records/crc")
    if a[:1] == ["--records"]:
        rdir = a[1]; a = a[2:]
    if not a:
        sys.exit(__doc__)
    data = load(rdir)
    _, cls, _ = ct.kind_tables()
    for c in a:
        {"noise": lambda: check_noise(data), "perbyte": lambda: check_perbyte(data, cls),
         "sameclass": lambda: check_sameclass(data, cls), "offset": lambda: check_offset(data),
         "cache": lambda: check_cache(data), "ram": lambda: check_ram(data, cls),
         "period": lambda: check_period(data), "first": lambda: check_first(data),
         "classes": lambda: check_classes(data, cls)}.get(c, lambda: sys.exit(__doc__))()
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
