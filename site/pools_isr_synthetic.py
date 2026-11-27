#!/usr/bin/env python3
"""Synthetic records of the pools concurrency series (schema "pools-isr/1"),
for building the draft of its pages before the board series exists: every
number is made up. Every record says so ("synthetic": true, board_decoded
"SYNTHETIC ...", commit 5yn7e71c0000), and the pages made from them say
SYNTHETIC. As site/pools_synthetic.py for the first series.

Usage: python3 -I site/pools_isr_synthetic.py OUT_DIR
  OUT_DIR/<board directory>/<adapter>.json for the boards and configurations
  of records/pools, our three controls and the reference. Refused under
  records/ or site/.

What the made-up results look like, by the plan's classes: the controls are
caught; ours and the libraries within their documentation pass; the
libraries outside their documentation have something observed (as the host
check observed for them) except RIOT, which has nothing observed, to show
both wordings. The interrupts-off waits are made up too.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLASS = {"adapter_ref": "control", "adapter_broken_isr_alloc": "control", "adapter_broken_isr_free": "control",
         "adapter_ref_primask": "ours", "adapter_threadx": "within", "adapter_cmsis_rtx": "within",
         "adapter_lwip": "within", "adapter_heapless": "within", "adapter_atomic_pool": "within",
         "adapter_etl": "outside", "adapter_riot": "outside", "adapter_contiki": "outside",
         "adapter_c_allocator": "outside", "adapter_memorypool": "outside"}   # kinds/pools-isr/decode.py CLASS
TWICE = "no order of the calls gives these answers: a block handed out while it is held (a block twice)"
LOST = "afterwards fewer than 32 blocks: blocks lost"
CRASH = "the program crashed: a call followed the pool's corrupted state outside memory"


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = os.path.realpath(sys.argv[1])
    for bad in ("records", "site"):
        if out.startswith(os.path.realpath(os.path.join(ROOT, bad))):
            sys.exit(f"refused: synthetic records under {bad}/")
    n = 0
    for d in sorted(glob.glob(os.path.join(ROOT, "records/pools", "*"))):
        bdir = os.path.basename(d)
        first = json.load(open(sorted(glob.glob(os.path.join(d, "*.json")))[0]))
        ads = sorted({json.load(open(f))["adapter"] for f in glob.glob(os.path.join(d, "*.json"))})
        ads += ["adapter_ref", "adapter_broken_isr_alloc", "adapter_broken_isr_free"]
        for k, a in enumerate(ads):
            cls = CLASS[a]
            seed = (sum(map(ord, bdir + a)) * 7919) % 1000
            trials = [6000 + seed, 6100 + seed]
            faults = [{}, {}]
            if cls == "control" or (cls == "outside" and a != "adapter_riot"):
                faults = [{TWICE: 40 + seed % 50, LOST: 10 + seed % 20}, {TWICE: 35 + seed % 40}]
            masks = a in ("adapter_ref_primask", "adapter_threadx", "adapter_lwip", "adapter_broken_isr_alloc",
                          "adapter_broken_isr_free") or (a in ("adapter_cmsis_rtx", "adapter_atomic_pool") and bdir in ("stm32g0b1", "samd20"))
            wait = [40 + seed % 60, 20 + seed % 30] if masks else [seed % 3, seed % 2]
            c = [{"trials": trials[i], "inside": trials[i] * 3 // 5, "faults": faults[i], "irq_wait_cycles": wait[i]}
                 for i in range(2)]
            stopped = None
            if a == "adapter_etl" and bdir == "stm32g474":   # a sweep that stopped (kinds/pools-isr/run-isr.py --stall)
                c[0]["faults"], c[1] = {CRASH: 1}, {"trials": 0, "inside": 0, "faults": {}, "irq_wait_cycles": None}
                stopped = {"trial": c[0]["trials"], "cache": "off", "where": "the check after the trial",
                           "desc": "a bus fault at 0xc6c5c4c3", "pc_symbol": "SYNTHETIC"}
            seen = sum(sum(x["faults"].values()) for x in c)
            verdict = ("caught" if seen else "NOT CAUGHT") if cls == "control" else \
                ((f"outside its documentation; observed in {seen} of {sum(trials)} trials" if seen else
                  f"outside its documentation; nothing observed in {sum(trials)} trials") if cls == "outside" else
                 ("FAIL" if seen else "pass"))
            rec = {"schema": "pools-isr/1", "synthetic": True, "kind": "pools-isr", "board": bdir,
                   "board_decoded": "SYNTHETIC " + first["board_decoded"], "adapter": a, "class": cls,
                   "bench_commit": "5yn7e71c0000", "toolchain_image": "synthetic:0", "clock_hz": first["clock_hz"],
                   "verdict": verdict, "result": dict({"c": c, "done": 0 if stopped else 1}, **({"stopped": stopped} if stopped else {})),
                   "coverage": {"instructions": 100 + seed % 200, "reached": 90 + seed % 150}}
            p = os.path.join(out, bdir, a + ".json")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as fh:
                json.dump(rec, fh, indent=1)
                fh.write("\n")
            n += 1
    print(f"{n} synthetic pools-isr records in {out}")


if __name__ == "__main__":
    main()
