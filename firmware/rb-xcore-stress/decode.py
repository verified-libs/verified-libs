#!/usr/bin/env python3
"""Decode the rb-xcore-stress result block (main.c struct results).

Usage: decode.py WORDS_FILE META_JSON OUT_JSON
Exit 0 only if the network core started, every library run that is
documented for several cores has no error in either direction, and the
control, if run, was caught. pxq (a single-core design) is reported, not
counted.
"""
import json
import sys

MAGIC = 0x564C5831
NAMES = ["lwrb (C)", "jnk0le Ringbuffer (C++)", "ETL queue_spsc_atomic (C++)", "QuantumLeaps LFRB (C)",
         "micoring SPSC mode (C)", "kostyk348 lf_spsc (C)", "diffstorm cb (C)", "rigtorp SPSCQueue (C++)",
         "polycratia spscring (C++)", "rt-spsc (C++)", "Zephyr ring_buf, CONFIG_SMP (C)",
         "DNedic lockfree spsc::RingBuf (C++)", "moodycamel ReaderWriterQueue (C++)",
         "heapless spsc::Queue (Rust)", "bbqueue (Rust)", "pxq RingBuffer_PackedState (C++)",
         "broken (negative control, SMP window)"]
NOT_COUNTED = {"pxq RingBuffer_PackedState (C++)": "single-core design (interrupt masking), not documented for two cores"}
HDR = ["magic", "version", "done", "transfers", "nlibs", "board_id", "clock_hz", "mode",
       "main_seed", "net_seed", "net_started", "reserved"]
FIELDS = ["transferred", "errors", "first_error_at", "first_error_got", "first_error_want",
          "full_events", "empty_events", "net_calls"]
DIRS = ["net_to_app", "app_to_net"]


def main():
    words_file, meta_file, out_file = sys.argv[1:4]
    w = [int(x, 16) for x in open(words_file).read().split()]
    h = dict(zip(HDR, w[:len(HDR)]))
    if h["magic"] != MAGIC:
        sys.exit(f"bad magic {h['magic']:#010x}")
    if h["done"] != 1:
        sys.exit("not finished")
    if h["nlibs"] != len(NAMES):
        sys.exit(f"layout mismatch: {h['nlibs']} libs")
    pos, libs = len(HDR), []
    for name in NAMES:
        dirs = {}
        for d in DIRS:
            dirs[d] = dict(zip(FIELDS, w[pos:pos + len(FIELDS)]))
            pos += len(FIELDS)
        if all(v["transferred"] == 0xFFFFFFFE for v in dirs.values()):
            continue
        for v in dirs.values():
            v["starved"] = v["transferred"] < h["transfers"]
        libs.append({"name": name, "dirs": dirs})
    meta = json.load(open(meta_file))
    record = {"schema": "rb-xcore-stress/0.1", "transfers": h["transfers"],
              "mode": {1: "single bytes", 2: "blocks"}.get(h["mode"], h["mode"]),
              "params": {"board": "nRF5340 DK: application core and network core", "clock_hz": h["clock_hz"],
                         "main_seed": f"{h['main_seed']:#010x}", "net_seed": f"{h['net_seed']:#010x}"},
              "net_started": bool(h["net_started"]), "libs": libs, **meta}
    json.dump(record, open(out_file, "w"), indent=2)

    print(f"nRF5340: producer and consumer on different cores; {record['mode']}; {h['transfers']} bytes "
          f"per library and direction; network core started: {bool(h['net_started'])}")
    print(f"{'library':44} {'net->app bytes/errors':>22} {'app->net bytes/errors':>22}")
    for l in libs:
        a, b = l["dirs"]["net_to_app"], l["dirs"]["app_to_net"]
        print(f"{l['name']:44} {a['transferred']:>12}/{a['errors']:<9} {b['transferred']:>12}/{b['errors']:<9}"
              + ("  STARVED" if a["starved"] or b["starved"] else ""))
    control = next((l for l in libs if l["name"].startswith("broken")), None)
    real = [l for l in libs if l is not control and l["name"] not in NOT_COUNTED]
    real_ok = all(v["errors"] == 0 and not v["starved"] for l in real for v in l["dirs"].values())
    caught = control is None or any(v["errors"] > 0 for v in control["dirs"].values())
    for l in libs:
        if l["name"] in NOT_COUNTED:
            e = sum(v["errors"] for v in l["dirs"].values())
            print(f"note: {l['name']}: {e} errors; {NOT_COUNTED[l['name']]}")
    print(f"\nlibraries documented for several cores error-free: {real_ok}; control caught: "
          + ("(not in this run)" if control is None else str(caught)))
    sys.exit(0 if h["net_started"] and real_ok and caught else 1)


if __name__ == "__main__":
    main()
