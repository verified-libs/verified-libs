#!/usr/bin/env python3
"""A test of kinds/pools/bench/poolscompare.py's fastest-call rule, without a
board: from our own records, changed copies as a reader's records could be,
in a throwaway directory. Cases:
  - our Pico 2 records against themselves: the same, none judged by the
    fastest call;
  - a cache-on mean of the Pico 2 slower by a few calls that miss, the
    fastest call unchanged: the same, judged by its fastest call;
  - the same, but the fastest call slower too: differs;
  - a cache-off mean of the Pico 2 slower: differs (our passes agree to the
    cycle with the cache off);
  - a cache-on mean of the NUCLEO-G474RE slower, the fastest call unchanged:
    differs (the rule applies only where our own passes vary);
  - the Pico 2's one-call mean (CMSIS-RTX init, cache on) faster by our own
    largest one-call difference: the same; by one cycle more: differs.
  python3 -I lab/tools/test-poolscompare.py
Exit 0: as expected.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CMP = os.path.join(REPO, "kinds/pools/bench/poolscompare.py")
fails = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


def run(ours, yours):
    p = subprocess.run([sys.executable, "-I", CMP, ours, yours], capture_output=True, text=True)
    return p.returncode, p.stdout


def variant(t, board, name, change):
    """A copy of our records of BOARD with CHANGE applied to the record of NAME; its directory."""
    d = os.path.join(t, f"{board}-{len(os.listdir(t))}")
    shutil.copytree(os.path.join(REPO, "records/pools", board), d)
    f = os.path.join(d, name)
    r = json.load(open(f))
    change(r)
    json.dump(r, open(f, "w"))
    return d


def slower(scen, by_mean, by_min=0, place=0):
    def change(r):
        for run_ in next(im for im in r["images"] if im["place"] == place)["runs"]:
            v = run_["results"][scen]
            v["mean"] = round(v["mean"] + by_mean, 3)
            v["min"] += by_min
            v["max"] = max(v["max"], v["min"] + 110)
    return change


def init_faster(by):
    def change(r):
        im = next(im for im in r["images"] if im["place"] == 0)
        v = im["runs"][0]["results"]["init/cache_on"]
        v["mean"] = v["min"] = v["max"] = v["first"] = v["mean"] - by
    return change


ours = os.path.join(REPO, "records/pools/rp2350")
g474 = os.path.join(REPO, "records/pools/stm32g474")
with tempfile.TemporaryDirectory() as t:
    t2 = os.path.join(t, "v")
    os.makedirs(t2)
    rc, out = run(ours, ours)
    check(rc == 0 and " 0 by their fastest call" in out, "Pico 2 against itself: the same, none by the fastest call")
    one = float(out.split("in a mean of one call, ")[1].split(" cycles")[0]) if "in a mean of one call, " in out else None
    check(one is not None and one > 0, f"our own largest one-call difference on the Pico 2 is named ({one} cycles)")
    rc, out = run(ours, variant(t2, "rp2350", "adapter_atomic_pool.json", slower("empty/alloc/cache_on", 0.82)))
    check(rc == 0 and " 1 by their fastest call" in out, "a cache-on mean slower by misses, fastest call the same: the same")
    rc, out = run(ours, variant(t2, "rp2350", "adapter_atomic_pool.json", slower("empty/alloc/cache_on", 2.0, 2)))
    check(rc == 1 and " 1 outside" in out, "a cache-on mean whose fastest call is slower too: differs")
    rc, out = run(ours, variant(t2, "rp2350", "adapter_atomic_pool.json", slower("empty/alloc/cache_off", 16.0)))
    check(rc == 1 and " 1 outside" in out, "a cache-off mean slower, fastest call the same: differs")
    rc, out = run(g474, variant(t2, "stm32g474", "adapter_atomic_pool.json", slower("empty/alloc/cache_on", 2.0)))
    check(rc == 1 and " 1 outside" in out and "fastest call" not in out,
          "NUCLEO-G474RE: a cache-on mean slower, fastest call the same: differs, no fastest-call rule")
    if one:
        rc, out = run(ours, variant(t2, "rp2350", "adapter_cmsis_rtx.json", init_faster(one)))
        check(rc == 0 and " 1 by their fastest call" in out, f"the one-call mean faster by {one:g} cycles: the same")
        rc, out = run(ours, variant(t2, "rp2350", "adapter_cmsis_rtx.json", init_faster(one + 1)))
        check(rc == 1 and " 1 outside" in out, f"the one-call mean faster by {one + 1:g} cycles: differs")
print(f"{len(fails)} failed")
sys.exit(1 if fails else 0)
