#!/usr/bin/env python3
"""The numbers of reports/2026-11-27-crc-unexplained.md, from run files,
records and built images we have. Reads only; writes nothing; no board.

  retries  RUNDIR...        H723 CRC: the estimated length of a run against the
                            waits and the retries in run.log
  passes   RECORDS_DIR      Pico 2: means that differ between pass 1 and pass 2
  order    RUNDIR_A RUNDIR_B  Pico 2 pools: the same image after the same image,
                            in two jobs: are its cache-on means equal?
  residue  PLACEMENT_TXT    Pico 2 CRC, cache off: does the loop's first address
                            modulo 8 decide the mean? (the output of
                            lab/tools/crc-placement.py)
  spread   RECORDS_DIR      per configuration, the cache-off key with the
                            largest spread over the placements
  loop     FUNC ELF...      the shortest backward-branch loop of FUNC, its
                            addresses modulo 32 (needs arm-none-eabi-objdump)
  sixpass  RUNDIR           Pico 2 pools, one configuration in six passes (job
                            U1): per library and cache state, the means (init
                            left out) equal in all six passes, in pass pairs of
                            the same order and of reverse order, the fastest
                            call equal in all six, and the largest difference
"""
import collections
import glob
import json
import os
import re
import subprocess
import sys


def retries(dirs):
    for d in dirs:
        log = open(os.path.join(d, "run.log")).read()
        ret = collections.Counter(a for a, _p, _w in re.findall(r"(\S+) p(\d+) 0x[0-9a-f]+: not finished after (\d+) s", log))
        est = {}
        for f in glob.glob(os.path.join(d, "*-pass1.json")):
            r = json.load(open(f))
            sums = [sum(v["mean"] * v["count"] for v in lib["results"].values() if v) for lib in r["libs"]]
            # timed: baseline and configuration; untimed: the reference's ref_crc() before every call, in both
            # loops (kinds/crc/bench/main.c scenario()), which costs what the baseline's timed call costs
            est[r["adapter"]] = max(est.get(r["adapter"], 0), (sums[0] + sums[1] + 2 * sums[0]) / r["clock_hz"])
        print(d, f"(clock {r['clock_hz'] / 1e6:.0f} MHz)")
        for a, t in sorted(est.items(), key=lambda x: -x[1]):
            print(f"  {a:34} {t:6.2f} s  retries {ret.get(a, 0)}")


def passes(rdir):
    n, rows = 0, []
    for f in glob.glob(os.path.join(rdir, "*.json")):
        r = json.load(open(f))
        for im in r["images"]:
            p = {x["pass"]: x for x in im["runs"]}
            for part in ("results", "baseline"):
                for k, v in p[1][part].items():
                    if not v:
                        continue
                    n += 1
                    w = p[2][part][k]
                    if v["mean"] != w["mean"]:
                        rows.append((abs(v["mean"] - w["mean"]) / v["mean"] * 100, r["adapter"], im["place"], part, k,
                                     v["min"] == w["min"], v["max"] == w["max"]))
    print(f"{len(rows)} of {n} means differ between the passes; of the configuration {sum(x[3] == 'results' for x in rows)}; "
          f"with the cache on {sum(x[4].endswith('cache_on') for x in rows)}; minimum the same in {sum(x[5] for x in rows)}; "
          f"maximum the same in {sum(x[6] for x in rows)}; largest {max(rows)[0]:.2f} % ({max(rows)[1]}, {max(rows)[4]})")


def order(a, b):
    def runs(d):
        seq = [(m.group(1), int(m.group(2)), int(m.group(3))) for m in
               (re.search(r"(adapter_\w+) p(\d+) 0x[0-9a-f]+ pass (\d):", ln) for ln in open(os.path.join(d, "run.log"))) if m]
        out = {}
        for k, (ad, p, ps) in enumerate(seq):
            r = json.load(open(os.path.join(d, f"{ad}-p{p}-pass{ps}.json")))
            out[(ad, p, ps)] = (seq[k - 1][:2] if k else None, {key: v["mean"] for key, v in r["libs"][1]["results"].items() if v})
        return out
    A, B = runs(a), runs(b)
    tally = {True: [0, 0], False: [0, 0]}
    for (ad, p, _ps), (pred, v) in A.items():
        for (ad2, p2, _ps2), (pred2, v2) in B.items():
            if (ad, p) == (ad2, p2):
                keys = [k for k in v if k.endswith("cache_on")]
                t = tally[pred == pred2]
                t[0] += sum(v[k] == v2[k] for k in keys)
                t[1] += len(keys)
    print(f"the same image after the same image: {tally[True][0]} of {tally[True][1]} cache-on means equal; "
          f"after another image: {tally[False][0]} of {tally[False][1]}")


def residue(path):
    for block in open(path).read().split("\nrp2350 "):
        lines = block.strip().splitlines()
        rows = [dict(f8=int(f[2]), off=float(f[-2]), length=int(f[5], 16) - int(f[1], 16) + 1)
                for f in (ln.split() for ln in lines) if len(f) >= 14 and f[0].isdigit()]
        if not rows:
            continue
        g = collections.defaultdict(set)
        for x in rows:
            g[x["f8"]].add(round(x["off"]))
        spread = (max(x["off"] for x in rows) / min(x["off"] for x in rows) - 1) * 100
        print(f"{lines[0].replace('rp2350 ', ''):32} loop {rows[0]['length']:3} bytes  spread {spread:5.2f} %  "
              f"first%8 decides: {all(len(v) == 1 for v in g.values())}  {dict((k, sorted(v)) for k, v in sorted(g.items()))}")


def spread(rdir):
    for f in sorted(glob.glob(os.path.join(rdir, "*.json"))):
        r = json.load(open(f))
        per = {}
        for im in r["images"]:
            run = next(x for x in im["runs"] if x["pass"] == 1)
            for k, v in run["results"].items():
                if v and k.endswith("cache_off") and not k.startswith("init"):
                    per.setdefault(k, {})[im["place"]] = v["mean"]
        k, vals = max(per.items(), key=lambda kv: max(kv[1].values()) / min(kv[1].values()))
        lo = min(vals.values())
        print(f"{r['adapter']:22} {k:30} " + " ".join(f"{p}:{vals[p]:.0f}" for p in sorted(vals))
              + f"  slower than 1.2 x the fastest at {[p for p, v in sorted(vals.items()) if v > 1.2 * lo]}")


def loop(fn, elfs):
    for elf in elfs:
        out = subprocess.run(["arm-none-eabi-objdump", "-d", "--no-show-raw-insn", elf], capture_output=True, text=True).stdout
        ins, cur = [], None
        for ln in out.splitlines():
            m = re.match(r"^([0-9a-f]+) <(.+)>:$", ln)
            if m:
                cur = m.group(2)
                continue
            m = re.match(r"^\s+([0-9a-f]+):\s+(\S+)\s*(.*)$", ln)
            if m and cur == fn:
                ins.append((int(m.group(1), 16), m.group(2), m.group(3)))
        addrs, found = [a for a, _, _ in ins], []
        for i, (a, mn, ops) in enumerate(ins):
            m = re.match(r"([0-9a-f]+)", ops)
            if re.match(r"^b(eq|ne|cs|cc|hs|lo|mi|pl|vs|vc|hi|ls|ge|lt|gt|le)?(\.n|\.w)?$", mn) and m:
                t = int(m.group(1), 16)
                if t < a and t in addrs:
                    found.append((t, (ins[i + 1][0] if i + 1 < len(ins) else a + 2) - 1))
        p = re.search(r"-p(\d+)/", elf).group(1)
        if found:
            f, l_ = min(found, key=lambda x: x[1] - x[0])
            print(f"p{p:>2} {fn}: loop {f:#x}-{l_:#x}, first %32 {f % 32:2}, last %32 {l_ % 32:2}, crosses a 32-byte boundary: {f // 32 != l_ // 32}")
        else:
            print(f"p{p:>2} {fn}: no loop")


def sixpass(d):
    runs = {}
    for f in glob.glob(os.path.join(d, "adapter_*-p*-pass*.json")):
        m = re.search(r"-p(\d+)-pass(\d+)\.json$", f)
        runs[(int(m.group(1)), int(m.group(2)))] = json.load(open(f))
    places, passes = sorted({p for p, _ in runs}), sorted({s for _, s in runs})
    print(f"{len(places)} placements, passes {passes[0]} to {passes[-1]}")
    for li in (1, 0):
        for cache in ("cache_off", "cache_on"):
            res = lambda p, s: runs[(p, s)]["libs"][li]["results"]
            keys = [k for k, v in res(places[0], passes[0]).items() if v and k.endswith(cache) and not k.startswith("init/")]
            cells = [(p, k) for p in places for k in keys]
            eq = lambda a, b, f="mean": sum(res(p, a)[k][f] == res(p, b)[k][f] for p, k in cells)
            same = [eq(a, b) for a in passes for b in passes if a < b and (b - a) % 2 == 0]
            rev = [eq(a, b) for a in passes for b in passes if a < b and (b - a) % 2 == 1]
            all_m = sum(len({res(p, s)[k]["mean"] for s in passes}) == 1 for p, k in cells)
            all_f = sum(len({res(p, s)[k]["min"] for s in passes}) == 1 for p, k in cells)
            w = max(((max(m) - min(m)) / min(m) * 100, p, k) for p, k in cells
                    for m in [[res(p, s)[k]["mean"] for s in passes]])
            print(f"{runs[(places[0], passes[0])]['libs'][li]['name']}, {cache}: all passes equal {all_m} of {len(cells)}; "
                  f"same order {min(same)} to {max(same)}; reverse order {min(rev)} to {max(rev)}; fastest call equal in all "
                  f"{all_f} of {len(cells)}; largest {w[0]:.2f} % (placement {w[1]}, {w[2]})")


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    {"retries": lambda: retries(a[1:]), "passes": lambda: passes(a[1]), "order": lambda: order(a[1], a[2]),
     "residue": lambda: residue(a[1]), "spread": lambda: spread(a[1]), "loop": lambda: loop(a[1], a[2:]),
     "sixpass": lambda: sixpass(a[1])}[a[0]]()


if __name__ == "__main__":
    main()
