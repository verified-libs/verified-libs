#!/usr/bin/env python3
"""The pools concurrency series' records (records/pools-isr, schema
"pools-isr/1", kinds/pools-isr/isrrecords.py) as the pools pages and their
data show them (lab/plans/2026-11-27-pools-concurrency.md, section 8,
decision 3: a draft for the owner to choose from).

What a row shows, in the three classes of the plan (section 2), never as a
score and never in the order of the rows:
  - within its documentation, and ours: "passed" with the trials, or what
    was observed (a finding);
  - outside its documentation: only what was observed, "observed in N of M
    trials: ..." or "nothing observed in M trials", never a verdict word;
  - a control of ours: caught, or not.
and, where the configuration takes interrupts off as built, the longest time
an interrupt waited (the record's irq_wait_cycles, cache off and on).

With no records under records/pools-isr nothing of this is shown and the
pages and data are as before. A synthetic record
(site/pools_isr_synthetic.py) is refused under records/pools-isr; from
another directory it is taken, and everything made from it says SYNTHETIC.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RECORDS = os.path.join(ROOT, "records/pools-isr")
SCHEMA = "pools-isr/1"
SERIES = "the concurrency series"
# Where a configuration takes interrupts off as built ("Lock as built", kinds/pools/README.md "The set"): on
# every board, or on the Cortex-M0+ boards only (CMSIS-RTX's Armv6-M variant; atomic-pool with
# portable-atomic's unsafe-assume-single-core).
M0 = ("stm32g0b1", "samd20")
MASKS = {"adapter_ref_primask": None, "adapter_threadx": None, "adapter_lwip": None,
         "adapter_cmsis_rtx": M0, "adapter_atomic_pool": M0, "adapter_broken_isr_alloc": None,
         "adapter_broken_isr_free": None, "adapter_c_allocator_lock": None}
# Builds of a library other than the one its one-context numbers come from, each a configuration of its own in the
# series, in a bundle of its own (lab/plans/2026-11-28-pools-isr-cal-lock.md): the one-context row's adapter ->
# [(adapter, name)]. Their records are in records/pools-isr/<bundle directory>/<board>/ (VARIANT_DIRS); of those
# directories only the variants are read (the bundle's controls proved its run; their records are bundle 300's
# names and are not shown twice).
VARIANTS = {"adapter_c_allocator": [("adapter_c_allocator_lock", "C_Allocator fb_allocator, ALLOC_LOCK_CMSIS_RTOS2 (C)")]}
VARIANT_DIRS = ("b301",)
VARIANT_NOTE = ("C_Allocator has two rows: the build the one-context numbers come from (no lock, the library's "
                "default on a bare-metal toolchain) and a build of its own with its lock option ALLOC_LOCK_CMSIS_RTOS2, "
                "which is not timed in one context.")
CONTROLS = ("adapter_ref", "adapter_broken_isr_alloc", "adapter_broken_isr_free")
CONTROL_TEXT = {"adapter_ref": "reference free list, no lock (our control)",
                "adapter_broken_isr_alloc": "broken: interrupts on too early in alloc (our control)",
                "adapter_broken_isr_free": "broken: interrupts on too early in free (our control)"}


# What the cells of one board need beside them (site/content/method-pools.md, "What it cannot show").
BOARD_NOTE = {"rp2350": "On this board with the cache off, a call longer than about 2,900 cycles is interrupted only "
                         "in its first part: the sweep moves the interrupt up to 4,096 cycles after it is armed, and "
                         "about 1,200 of those come before the call. The record's coverage per function names the "
                         "instructions no interrupt landed on."}


# The verdict texts of kinds/pools-isr/verdict.h (FAULT_TEXT), shortened for a table cell.
SHORT = {
    "no order of the calls gives these answers: a block handed out while it is held (a block twice)": "a block twice",
    "no order of the calls gives these answers: an alloc gave no block while fewer than 32 were held":
        "no block although blocks were free",
    "no order of the calls gives these answers: an alloc gave a block while all 32 were held": "a block although none was free",
    "afterwards fewer than 32 blocks: blocks lost": "blocks lost",
    "afterwards a block given twice": "a block twice, afterwards",
    "afterwards more than 32 blocks": "more than 32 blocks, afterwards",
    "a held block's pattern changed: a block shared": "a block shared",
    "a canary around the pool's memory changed": "a write outside the pool",
    "a canary changed while giving every block back": "a write outside the pool",
    "a block outside the region or misaligned": "a block outside the pool or misaligned",
    "interrupts off after main's call": "interrupts left off",
    "interrupts off after an interrupt's call": "interrupts left off",
    "a free did not answer 1": "a free refused",
    "a free refused when giving every block back": "a free refused",
    "the program crashed: a call followed the pool's corrupted state outside memory": "a crash",
    "a call did not return": "a call that did not return",
}


def is_synthetic(rec):
    return bool(rec.get("synthetic")) or str(rec.get("board_decoded", "")).startswith("SYNTHETIC")


def load(rdir=None):
    """({(board directory, adapter): (path, record)}, synthetic); a synthetic record under records/pools-isr is
    refused."""
    rdir = rdir or RECORDS
    out, syn = {}, False
    for f in sorted(glob.glob(os.path.join(rdir, "*", "*.json"))):
        r = json.load(open(f))
        if r.get("schema") != SCHEMA:
            continue
        if is_synthetic(r):
            if os.path.realpath(rdir).startswith(os.path.realpath(RECORDS)):
                sys.exit(f"refused: {os.path.relpath(f, ROOT)} is a synthetic record (site/pools_isr_synthetic.py)")
            syn = True
        out[(os.path.basename(os.path.dirname(f)), r["adapter"])] = (f, r)
    variants = {a for v in VARIANTS.values() for a, _ in v}
    for vd in VARIANT_DIRS:
        for f in sorted(glob.glob(os.path.join(rdir, vd, "*", "*.json"))):
            r = json.load(open(f))
            if r.get("schema") != SCHEMA or r.get("adapter") not in variants:
                continue
            if is_synthetic(r):
                if os.path.realpath(rdir).startswith(os.path.realpath(RECORDS)):
                    sys.exit(f"refused: {os.path.relpath(f, ROOT)} is a synthetic record (site/pools_isr_synthetic.py)")
                syn = True
            out[(os.path.basename(os.path.dirname(f)), r["adapter"])] = (f, r)
    return out, syn


def sub_path(f):
    """A record's path below its records directory: <board>/<file>, or <bundle directory>/<board>/<file>."""
    up = os.path.basename(os.path.dirname(os.path.dirname(f)))
    tail = os.path.join(os.path.basename(os.path.dirname(f)), os.path.basename(f))
    return os.path.join(up, tail) if up in VARIANT_DIRS else tail


def masks(board_dir, adapter):
    m = MASKS.get(adapter, ())
    return m is None or (m and board_dir in m)


def summary(board_dir, path, rec, rdir=None):
    """What the pages and the data show of one record."""
    c = rec["result"]["c"]
    trials = sum(x["trials"] for x in c)
    seen = {}
    for x in c:
        for k, n in x["faults"].items():
            seen[k] = seen.get(k, 0) + n
    n_seen = sum(seen.values())
    cls = rec["class"]
    s = {"class": cls, "trials": trials, "inside": sum(x["inside"] for x in c),
         "observed": sorted({SHORT.get(k, k) for k in seen}), "observed_trials": n_seen,
         "record": ("records/pools-isr/" + os.path.relpath(path, rdir)) if rdir else os.path.relpath(path, ROOT)}
    if cls == "outside":
        s["result"] = (f"outside its documentation; observed in {n_seen} of {trials} trials: " + "; ".join(s["observed"])
                       if n_seen else f"outside its documentation; nothing observed in {trials} trials")
    elif cls == "control":
        s["result"] = (f"caught in {n_seen} of {trials} trials" if n_seen else f"NOT CAUGHT in {trials} trials")
    else:
        s["result"] = (f"passed: nothing observed in {trials} trials" if not n_seen
                       else f"FAILED: observed in {n_seen} of {trials} trials: " + "; ".join(s["observed"]))
    st = rec["result"].get("stopped")
    if st:   # the sweep stopped (kinds/pools-isr/run-isr.py --stall): where, and what was not run
        s["stopped"] = {k: st.get(k) for k in ("trial", "cache", "where", "desc", "pc_symbol")}
        s["result"] += (f"; the sweep stopped at trial {st['trial']} with the cache {st['cache']}, in {st['where']}"
                        + ("; cache on not run" if st["cache"] == "off" else ""))
    if masks(board_dir, rec["adapter"]):
        s["irq_wait_cycles"] = {"off": c[0].get("irq_wait_cycles"), "on": c[1].get("irq_wait_cycles")}
    cov = rec.get("coverage") or {}
    s["coverage"] = [cov.get("reached"), cov.get("instructions")] if cov else None
    s["text"] = cell(s)
    s["passed"] = cls in ("within", "ours") and not n_seen
    return s


def cell(s):
    """One cell's text (the pages; the comparison page and its port show the data's "text")."""
    if not s:
        return "–"
    t = s["result"]
    w = s.get("irq_wait_cycles")
    if w and w["off"] is not None and w["on"] is not None:
        t += f"; an interrupt waited at most {w['off']} cycles with the cache off, {w['on']} with it on"
    return t
