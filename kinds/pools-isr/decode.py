#!/usr/bin/env python3
"""Decode the result block of the pools concurrency image (main.c, struct
results) into a dict, and judge it by the plan's classes
(lab/plans/2026-11-27-pools-concurrency.md, section 2). No board: the words
come from a run (read over the debug port) or from a test.

The layout is read from the sources, not repeated here: NPF from verdict.h's
enum fault and FAULT_TEXT, COV_WORDS and the field order from main.c's
struct cache_res and struct results (every field a uint32_t). test_decode.py
checks the computed size against the `results` symbol of each board's image.

The verdict words follow the plan's classes: "pass" or "FAIL" only for the
rows within their documentation and ours; "caught" or "NOT CAUGHT" for the
controls; for a library outside its documentation only what was observed,
never a verdict word: it was used in a way it does not document.

A run that stops making progress (run-isr.py: the trial counter stands
still, done never set) is judged too, with what the runner read over the
probe without a write (stop()): a fault in the core (the board layer's
fault handler loops, so the image never writes done) counts as one trial
with the host check's own fault text (PF_CRASH, verdict.h), so the host and
the board say the same; a stall without a fault as "a call did not return".
The verdict then says where the sweep stopped, and that the cache-on half
was not run if it stopped with the cache off (the image sweeps the cache on
only after the cache off).

Usage: python3 -I decode.py WORDS-FILE ADAPTER   (a file of hex words, as a
debug-port read gives them)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The class of each configuration by what its library documents (plan, section 2; kinds/pools/claims.tsv).
CLASS = {"adapter_ref": "control", "adapter_broken_isr_alloc": "control", "adapter_broken_isr_free": "control",
         "adapter_ref_primask": "ours", "adapter_threadx": "within", "adapter_cmsis_rtx": "within",
         "adapter_lwip": "within", "adapter_heapless": "within", "adapter_atomic_pool": "within",
         "adapter_etl": "outside", "adapter_riot": "outside", "adapter_contiki": "outside",
         "adapter_c_allocator": "outside", "adapter_memorypool": "outside",
         # bundle 301 (lab/plans/2026-11-28-pools-isr-cal-lock.md): C_Allocator built with its interrupt-masking
         # lock option ALLOC_LOCK_CMSIS_RTOS2, no kernel linked
         "adapter_c_allocator_lock": "within"}


def layout():
    """(fault texts, the fields of struct cache_res, of struct results) from verdict.h and main.c."""
    v = open(os.path.join(HERE, "verdict.h")).read()
    enum = re.search(r"enum fault \{(.*?)\};", v, re.S).group(1)
    codes = [c.strip() for c in enum.replace("\n", " ").split(",") if c.strip()]
    if codes[-1] != "NPF":
        sys.exit("verdict.h: enum fault does not end with NPF")
    texts = re.findall(r'^\s*"(.*?)",?\s*$', re.search(r"FAULT_TEXT\[NPF\] = \{(.*?)\};", v, re.S).group(1), re.M)
    if len(texts) != len(codes) - 1:
        sys.exit(f"verdict.h: {len(texts)} fault texts for {len(codes) - 1} codes")
    m = open(os.path.join(HERE, "main.c")).read()
    cov = int(re.search(r"#define COV_WORDS (\d+)u", m).group(1))

    def fields(struct):
        body = re.search(r"struct " + struct + r" \{(.*?)\};", m, re.S).group(1)
        out = []
        for ln in body.splitlines():
            ln = ln.split("/*")[0].strip()
            if not ln:
                continue
            mm = re.match(r"(uint32_t|struct cache_res)\s+(.*);$", ln)
            if not mm:
                sys.exit(f"main.c struct {struct}: cannot read {ln!r}")
            for f in mm.group(2).split(","):
                f = f.strip()
                a = re.match(r"(\w+)\[(\w+)\]$", f)
                n = {"NPF": len(codes) - 1, "COV_WORDS": cov}.get(a.group(2), None) if a else 1
                if a and n is None:
                    n = int(a.group(2))
                out.append((a.group(1) if a else f, n, mm.group(1)))
        return out
    return texts, fields("cache_res"), fields("results")


def words_needed():
    _, cr, rs = layout()
    per = sum(n for _, n, _ in cr)
    return sum(n * (per if t == "struct cache_res" else 1) for _, n, t in rs)


def decode(words, adapter):
    texts, cr, rs = layout()
    per = sum(n for _, n, _ in cr)
    out, i = {}, 0
    for name, n, t in rs:
        if t == "struct cache_res":
            blocks = []
            for _ in range(n):
                c, j = {}, i
                for fn, fnn, _ in cr:
                    c[fn] = words[j] if fnn == 1 else list(words[j:j + fnn])
                    j += fnn
                c["faults"] = {texts[k]: v for k, v in enumerate(c["faults"]) if v}
                if c["first_fault"]:
                    cs = c["first_case"]
                    c["first"] = {"fault": texts[c["first_fault"]], "held": cs >> 16, "main": "alloc" if (cs >> 8 & 0xff) == 1 else "free",
                                  "interrupt": cs >> 4 & 0xf, "rotation": cs & 0xf, "d": c["first_d"]}
                blocks.append(c)
                i += per
            out[name] = blocks
        else:
            out[name] = words[i] if n == 1 else list(words[i:i + n])
            i += n
    if out["magic"] != 0x564C4931:
        raise ValueError(f"magic {out['magic']:#x}, not VLI1")
    out["adapter"] = adapter
    out["class"] = CLASS.get(adapter)
    out["cov_bitmap"] = out.pop("cov")
    out["coverage_bits"] = sum(bin(w).count("1") for w in out["cov_bitmap"])
    for k, c in enumerate(out["c"]):
        # the longest wait of an interrupt: the largest latency during main's call less the reference's smallest
        # in the same image (calibrate(), main.c)
        ok = c["lat_n"] and out["cal_lat_n"][k]
        c["irq_wait_cycles"] = max(0, c["lat_max"] - out["cal_lat_min"][k]) if ok else None
    return out


NO_RETURN = "a call did not return"


def stop(res, info):
    """Add a stopped run's last trial to its decoded block (done 0): INFO is run-isr.py's stall read
    ({"fault": bool, "where": ..., "desc": ..., "pc_symbol": ..., "phase", "fired", "fired_phase"}). The text
    of the fault is PF_CRASH's (FAULT_TEXT), or NO_RETURN for a stall without a fault."""
    texts = layout()[0]
    crash = texts[-1]
    if not crash.startswith("the program crashed"):
        raise ValueError("verdict.h: the last fault text is not PF_CRASH's")
    k = 1 if res["c"][1]["lat_min"] else 0          # sweep_one() sets lat_min first: the cache-on sweep had begun
    c = res["c"][k]
    swept = bool(c["lat_min"])
    text = crash if info["fault"] else NO_RETURN
    c["trials"] += 1
    ph = info.get("fired_phase") if info.get("fired") else info.get("phase")
    c[{0: "before", 1: "inside"}.get(ph, "after")] += 1
    c["faults"][text] = c["faults"].get(text, 0) + 1
    if not c["first_fault"] and "first" not in c:
        c["first"] = {"fault": text, "trial": c["trials"], "where": info["where"]}
    res["faults_total"] += 1
    res["stopped"] = dict(info, cache=["off", "on"][k], trial=c["trials"], in_sweep=swept, text=text)
    return res


def stop_note(rec):
    st = rec.get("stopped")
    if not st:
        return ""
    at = f" in {st['pc_symbol']}" if st.get("pc_symbol") else ""
    note = (f"; the sweep stopped at trial {st['trial']} with the cache {st['cache']}, in {st['where']} "
            f"({st['desc']}{at})")
    return note + ("; cache on not run: the image sweeps the cache on only after the cache off" if st["cache"] == "off"
                   else "; the cache-on sweep did not finish")


def judge(rec):
    """the verdict by the plan's classes: 'pass' / 'FAIL' (within its documentation, ours), 'caught' /
    'NOT CAUGHT' (a control), and for a library outside its documentation only what was observed"""
    seen = sum(sum(c["faults"].values()) for c in rec["c"])
    trials = sum(c["trials"] for c in rec["c"])
    inside = sum(c["inside"] for c in rec["c"])
    if (not rec["done"] and not rec.get("stopped")) or not (inside or rec.get("stopped")):
        return "incomplete"
    k = rec["class"]
    if k == "control":
        return "caught" if seen else "NOT CAUGHT"
    if k == "outside":
        return ((f"outside its documentation; observed in {seen} of {trials} trials: "
                 + "; ".join(sorted({t for c in rec["c"] for t in c["faults"]}))) if seen else
                f"outside its documentation; nothing observed in {trials} trials") + stop_note(rec)
    return "FAIL" if seen else "pass"


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    words = [int(w, 16) for w in open(sys.argv[1]).read().split()]
    rec = decode(words, sys.argv[2])
    rec.pop("cov_bitmap")
    print(json.dumps(dict(rec, verdict=judge(rec)), indent=1))


if __name__ == "__main__":
    main()
