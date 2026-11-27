#!/usr/bin/env python3
"""A check that every number in the two texts about the pools tables equals
the records: the fold-out "What the tables show" on the results page
(site/content/results-pools.md) and the section "What the placements show"
on the method page (site/content/method-pools.md).

Each claim of the texts is computed here from records/pools (the ranges as
site/pools_data.py makes them for the pages, the passes and first calls
from the records themselves), written out as the text says it, and must be
found in its section word for word. A claim whose condition does not hold
on the records (e.g. a row said to overlap the baseline that does not)
fails, as does a number in a section that no claim covers.

Overlap is judged on the unrounded means, as on the comparison page; the
cycles are quoted as the tables give them (whole cycles,
pools_tables.range_text).

Usage: python3 -I site/test_pools_texts.py      exit 0: every number checked
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pools_data      # noqa: E402
import pools_tables as t   # noqa: E402

RESULTS = os.path.join(ROOT, "site/content/results-pools.md")
METHOD = os.path.join(ROOT, "site/content/method-pools.md")
R = t.range_text
M0 = ("nucleo-g0b1re", "sam-d20-xpro")   # the two Cortex-M0+ boards


def section(path, start, end):
    s = open(path).read()
    i = s.index(start)
    return s[i:s.index(end, i + len(start))]


def norm(text):
    """whitespace as one space: a fragment may wrap anywhere in the page"""
    return re.sub(r"\s+", " ", text)


def ov(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


class Facts:
    def __init__(self):
        self.want, self.fails = [], []

    def say(self, text):
        """a fragment the section must hold word for word"""
        self.want.append(text)

    def hold(self, cond, what):
        if not cond:
            self.fails.append("does not hold on the records: " + what)


def table_facts(d, f):
    B = {b["id"]: b for b in d["boards"]}
    name = lambda b: B[b]["name"]   # noqa: E731
    cyc = {(r["board"], r["adapter"]): r["cycles"] for r in d["rows"]}
    base = {x["board"]: x["cycles"] for x in d["baseline"]}
    boards = [b["id"] for b in d["boards"]]
    pair = ("pair/alloc", "pair/free")
    libs = {c["adapter"] for c in d["configurations"] if c["role"] != "ours"}

    # not told apart from the baseline, in pair
    hits = {(b, a, c, k) for (b, a), cy in cyc.items() if a in libs for c in ("on", "off") for k in pair
            if ov(cy[c][k], base[b][c][k])}
    riot = {(b, c, k) for b, a, c, k in hits if a == "adapter_riot"}
    f.hold(riot == {(b, c, "pair/alloc") for b in boards for c in ("on", "off")},
           "RIOT's pair alloc overlaps the baseline on every board in both cache states, its free nowhere")
    for b in ("nrf5340dk", "pico2", "nucleo-g474re", "nucleo-h723zg", "nucleo-g0b1re", "sam-d20-xpro"):
        f.say(f"{name(b)} {R(cyc[(b, 'adapter_riot')]['on']['pair/alloc'])} against {R(base[b]['on']['pair/alloc'])}")
    f.say(f"its free does not (nRF5340 DK, cache on: {R(cyc[('nrf5340dk', 'adapter_riot')]['on']['pair/free'])} "
          f"against {R(base['nrf5340dk']['on']['pair/free'])})")
    mp = {(b, c, k) for b, a, c, k in hits if a == "adapter_memorypool"}
    f.hold(mp == {("nucleo-g474re", c, k) for c in ("on", "off") for k in pair}
           | {("nucleo-h723zg", "on", "pair/alloc"), ("nucleo-h723zg", "off", "pair/alloc"), ("nrf5340dk", "off", "pair/alloc")},
           f"MemoryPool overlaps the baseline exactly where the text says ({sorted(mp)})")
    g, h, n = (lambda b: cyc[(b, "adapter_memorypool")]), "nucleo-h723zg", "nrf5340dk"
    G = "nucleo-g474re"
    for c in ("on", "off"):
        f.say(f"{R(g(G)[c]['pair/alloc'])} and {R(g(G)[c]['pair/free'])} against {R(base[G][c]['pair/alloc'])} and "
              f"{R(base[G][c]['pair/free'])}")
    f.say(f"with the cache on ({R(g(h)['on']['pair/alloc'])} against {R(base[h]['on']['pair/alloc'])}) and off "
          f"({R(g(h)['off']['pair/alloc'])} against\n  {R(base[h]['off']['pair/alloc'])})")
    f.say(f"cache off ({R(g(n)['off']['pair/alloc'])}\n  against {R(base[n]['off']['pair/alloc'])})")
    f.hold({a for _, a, _, _ in hits} == {"adapter_riot", "adapter_memorypool"}, "no other library overlaps in pair")

    # our row with interrupts off
    p = lambda b: cyc[(b, "adapter_ref_primask")]["on"]   # noqa: E731
    for b in ("nrf5340dk", "pico2", "nucleo-h723zg", "nucleo-g0b1re", "sam-d20-xpro"):
        f.hold(not any(ov(p(b)[k], base[b]["on"][k]) for k in pair), f"our row apart from the baseline on {b}")
        f.say(f"{R(p(b)['pair/alloc'])} and {R(p(b)['pair/free'])} against")
        f.say(f"{R(base[b]['on']['pair/alloc'])} and {R(base[b]['on']['pair/free'])} on")
    pa, pf, ba, bf = p(G)["pair/alloc"], p(G)["pair/free"], base[G]["on"]["pair/alloc"], base[G]["on"]["pair/free"]
    f.hold(pa[0] > ba[1] and ov(pf, bf), "G474: our row's alloc above the baseline's, its free overlapping")
    f.say(f"begins {pa[0] - ba[1]:.2f} cycles above the baseline's\n  ({R(pa)} against {R(ba)})")
    f.say(f"({R(pf)}\n  against {R(bf)})")

    # the cache
    rows = lambda b: [cy for (bb, _), cy in cyc.items() if bb == b] + [base[b]]   # noqa: E731
    for b in ("nrf5340dk", "pico2", "nucleo-g474re", "nucleo-h723zg"):
        f.hold(all(cy["off"][k][0] > cy["on"][k][1] for cy in rows(b) for k in pair), f"{b}: cache off above on in pair")
    rat = [x for cy in rows("pico2") for k in pair for x in (cy["off"][k][0] / cy["on"][k][1], cy["off"][k][1] / cy["on"][k][0])]
    f.say(f"each is {min(rat):.0f} to {max(rat):.0f} times its figure with the cache on")
    f.say(f"(the baseline's\n  alloc: {R(base['pico2']['off']['pair/alloc'])} against {R(base['pico2']['on']['pair/alloc'])})")
    mx = [max(cy["off"][k][1] / cy["on"][k][0] for cy in rows(b) for k in pair) for b in M0]
    f.say(f"at most {mx[0]:.2f} and {mx[1]:.2f} times its cache-on figure")
    f.hold(all(base[b]["off"]["pair/free"] == base[b]["on"]["pair/free"] for b in M0), "the M0+ baselines' free the same in both")
    f.say(f"the baseline's free is the same in both ({R(base[M0[0]]['on']['pair/free'])} and "
          f"{R(base[M0[1]]['on']['pair/free'])})")

    # the Cortex-M0+ boards and the bytes
    f.hold(not any((b, "adapter_heapless") in cyc for b in M0) and all((b, "adapter_heapless") in cyc for b in boards if b not in M0),
           "heapless on the four other boards only")
    fl = {(r["board"], r["adapter"]): r["flash_bytes"] for r in d["rows"]}
    ram = {(r["board"], r["adapter"]): r["ram_bytes"] for r in d["rows"]}
    ap = lambda bs: sorted(fl[(b, "adapter_atomic_pool")] for b in bs)   # noqa: E731
    m0, other = ap(M0), ap([b for b in boards if b not in M0])
    f.hold(m0[0] == m0[-1], "atomic-pool the same flash bytes on both M0+ boards")
    f.say(f"atomic-pool takes {m0[0]} flash\n  bytes there against {other[0]}–{other[-1]} on the other four boards")
    f.hold(all(v[0] == v[1] for cy in rows("sam-d20-xpro") for v in cy["off"].values() if v),
           "SAM D20: every cache-off figure one number")
    ads = {a for _, a in fl}
    f.hold(all(len({ram[(b, a)] for b in boards if (b, a) in ram}) == 1 for a in ads), "RAM bytes the same on every board")
    spread = {a: (min(v), max(v)) for a in ads for v in [[fl[(b, a)] for b in boards if (b, a) in fl]]}
    big = max((s[1] - s[0], a) for a, s in spread.items() if a != "adapter_atomic_pool")
    f.hold(big[1] == "adapter_threadx", "ThreadX's flash bytes differ most between the boards, atomic-pool aside")
    th, at = spread["adapter_threadx"], spread["adapter_atomic_pool"]
    f.say(f"differ between the boards by at most {big[0]} (ThreadX:\n  {th[0]}–{th[1]})")
    f.say(f"but for atomic-pool's ({at[0]}–{at[1]}, above)")


def method_facts(d, f, rdir):
    recs = {}
    for p in sorted(glob.glob(os.path.join(rdir, "*", "*.json"))):
        recs.setdefault(os.path.basename(os.path.dirname(p)), []).append(json.load(open(p)))
    # the passes
    diff, total = {}, {}
    for b, rs in recs.items():
        n, ds = 0, []
        for r in rs:
            for im in r["images"]:
                p = {x["pass"]: x for x in im["runs"]}
                for part in ("results", "baseline"):
                    for k, v in p[1][part].items():
                        if v is None:
                            continue
                        n += 1
                        w = p[2][part][k]
                        if v["mean"] != w["mean"]:
                            ds.append((abs(v["mean"] - w["mean"]) / v["mean"] * 100, r["adapter"], part, k, v["min"] == w["min"]))
        diff[b], total[b] = ds, n
    f.hold(all(not diff[b] for b in recs if b != "rp2350"), "every mean the same in both passes but on the Pico 2")
    for b, rs in recs.items():
        for pas in (1, 2):
            seen = {}
            for r in rs:
                for im in r["images"]:
                    run = next(x for x in im["runs"] if x["pass"] == pas)
                    for k, v in run["baseline"].items():
                        if v:
                            seen.setdefault(k, set()).add(v["mean"])
            f.hold(all(len(v) == 1 for v in seen.values()), f"{b}: the baseline the same in every image, pass {pas}")
    ds = diff["rp2350"]
    worst = max(ds)
    f.hold(all(x[2] == "results" and x[3].endswith("cache_on") for x in ds), "the Pico 2's differences: configurations, cache on")
    f.hold(worst[1] == "adapter_heapless" and worst[3].startswith("init/"), "the largest is heapless's init")
    f.say(f"{len(ds)} of {total['rp2350']} means differ between the passes")
    f.say(f"by at most {worst[0]:.1f} % (heapless")
    f.say(f"the shortest call is the same in both passes in {sum(x[4] for x in ds)} of\nthe {len(ds)}")
    # the first call, first pass
    best = {}
    for b, rs in recs.items():
        for r in rs:
            for im in r["images"]:
                run = next(x for x in im["runs"] if x["pass"] == 1)
                for part in ("results", "baseline"):
                    for k, v in run[part].items():
                        if not v or v["count"] < 2:
                            continue
                        wo = (v["mean"] * v["count"] - v["first"]) / (v["count"] - 1)
                        add = (v["mean"] - wo) / wo * 100
                        if add > best.get(b, (-1,))[0]:
                            best[b] = (add, r["adapter"], k, v["first"], v["mean"])
    pico, h7 = best["rp2350"], best["stm32h723"]
    f.hold(pico[1] == "adapter_c_allocator" and pico[2] == "pair/alloc/cache_on", "the Pico 2's largest: C_Allocator, pair alloc, cache on")
    f.say(f"The first call adds at most\n{pico[0]:.1f} % to a mean")
    f.say(f"a first call of {pico[3]} cycles in a mean of {pico[4]:.0f}")
    f.say(f"at most\n{h7[0]:.1f} % on the NUCLEO-H723ZG")
    f.hold(all(best[b][0] < 1 for b in best if b not in ("rp2350", "stm32h723")), "below 1 % on the other four boards")
    f.say("less than 1 % on the other four boards")
    # the spread over the placements, init aside
    B = {b["id"]: b["name"] for b in d["boards"]}
    sp = {}
    for (b, c), v in [((r["board"], c), (r["cycles"][c][k], r["adapter"], k)) for r in d["rows"] for c in ("off", "on")
                      for k in r["cycles"][c] if k != "init" and r["cycles"][c][k]]:
        s = (v[0][1] - v[0][0]) / v[0][0] * 100
        if s > sp.get((b, c), (-1,))[0]:
            sp[(b, c)] = (s, v[1], v[2], v[0])
    pct = lambda b, c: f"{sp[(b, c)][0]:.0f} %"   # noqa: E731
    f.say(f"`init` aside, is {pct('nrf5340dk', 'off')} on the nRF5340 DK, {pct('nucleo-g474re', 'off')} on\nthe NUCLEO-G474RE, "
          f"{pct('nucleo-g0b1re', 'off')} on the NUCLEO-G0B1RE, {pct('pico2', 'off')} on the Raspberry Pi\nPico 2 H and "
          f"{pct('nucleo-h723zg', 'off')} on the NUCLEO-H723ZG")
    w = sp[("nucleo-h723zg", "off")]
    f.hold(w[1] == "adapter_contiki" and w[2] == "pair_full/free", "the H723's largest: Contiki-NG, pair_full free")
    f.say(f"(Contiki-NG, `pair_full` free:\n{R(w[3])})")
    f.hold(sp[("sam-d20-xpro", "off")][0] == 0, "the SAM D20 with the cache off: 0")
    f.say(f"on the SAM D20 Xplained Pro it is {sp[('sam-d20-xpro', 'off')][0]:.0f}, every figure the same")
    f.say(f"With the cache on it is at most {pct('nrf5340dk', 'on')} on the nRF5340\nDK, {pct('pico2', 'on')} on the Raspberry Pi Pico 2 H, "
          f"{pct('sam-d20-xpro', 'on')} on the SAM D20 Xplained Pro,\n{pct('nucleo-g0b1re', 'on')} on the NUCLEO-G0B1RE, "
          f"{pct('nucleo-h723zg', 'on')} on the NUCLEO-H723ZG and {pct('nucleo-g474re', 'on')} on the\nNUCLEO-G474RE")
    del B


# Numbers in the sections that are not measurements: board names, the shape of the series, the placements' steps.
NOT_NUMBERS = [r"Raspberry Pi Pico 2 H", r"Pico 2", r"nRF5340 DK", r"NUCLEO-[GH]\w+", r"SAM D20", r"Cortex-M0\+",
               r"`[^`]*`", r"\]\([^)]*\)", r"0, 4 \.\.\. 28", r"first series", r'markdown="1"']


def uncovered(text, frags):
    """the numbers in text outside every fragment and every NOT_NUMBERS match"""
    mask = [False] * len(text)
    for pat in [re.escape(x) for x in frags] + NOT_NUMBERS:
        for m in re.finditer(pat, text):
            for i in range(m.start(), m.end()):
                mask[i] = True
    return [m.group(0) for m in re.finditer(r"\d+(?:[.,]\d+)?", text) if not all(mask[m.start():m.end()])]


def check(d, rdir):
    fails = []
    for name, path, start, end, fn in (
            ("results page, What the tables show", RESULTS, '<details id="what-the-tables-show"', "</details>", table_facts),
            ("method page, What the placements show", METHOD, "## What the placements show", "\n## ", None)):
        text = norm(section(path, start, end))
        f = Facts()
        if fn:
            fn(d, f)
        else:
            method_facts(d, f, rdir)
        f.want = [norm(w) for w in f.want]
        fails += [f"{name}: {x}" for x in f.fails]
        fails += [f"{name}: not in the text: {w!r}" for w in f.want if w not in text]
        left = uncovered(text, f.want)
        if left:
            fails.append(f"{name}: numbers no claim covers: {left}")
        print(f"{name}: {len(f.want)} fragments, {len(f.fails)} conditions failed")
    return fails


def main():
    rdir = os.path.join(ROOT, "records/pools")
    d = pools_data.build(rdir)
    if not d["published"]:
        print("no pools records: nothing to check")
        return 0
    fails = check(d, rdir)
    for x in fails:
        print("FAIL " + x)
    print(f"{len(fails)} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
