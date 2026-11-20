#!/usr/bin/env python3
"""Decode the rb-mp-stress result block into a table and a JSON record.

Usage: decode.py WORDS_FILE META_JSON OUT_JSON
Exit code 0 only if every library in a mode it documents (except the known,
already documented finding) is error-free AND the control (an SPSC queue
used with two producers / two consumers) is caught.
"""
import json
import sys

MAGIC = 0x564C4D31
import os
# Further MPSC libraries (extra/, held back from the public tree): only in a
# WITH_EXTRA=1 firmware ("with_extra" in the meta data), in firmware order
# before the control.
EXTRA_MPSC, KNOWN_FINDING, EXTRA_MULTICORE = [], {}, set()


def load_extra():
    global EXTRA_MPSC, KNOWN_FINDING, MULTICORE_DOCUMENTED
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra"))
    from mp_extra import EXTRA_MPSC as X, KNOWN_FINDING as K, MULTICORE_DOCUMENTED as M
    EXTRA_MPSC, KNOWN_FINDING = X, K
    MULTICORE_DOCUMENTED = MULTICORE_DOCUMENTED | M
    LIBS[1][-1:-1] = X


LIBS = {1: ["pxq RingBuffer_PackedState, Topology::MPSC", "pxq RingBuffer_PackedState, Topology::MPMC",
            "RIOT tsrb", "wizard97 + PRIMASK macros", "DNedic lockfree mpmc::Queue",
            "heapless mpmc::Queue (Rust)", "pxq RingBuffer_PackedState, Topology::MPSC, reserve/commit",
            "control: jnk0le Ringbuffer (SPSC) with two producers"],
        2: ["pxq RingBuffer_PackedState, Topology::SPMC", "pxq RingBuffer_PackedState, Topology::MPMC",
            "RIOT tsrb", "wizard97 + PRIMASK macros", "DNedic lockfree mpmc::Queue",
            "heapless mpmc::Queue (Rust)", "control: jnk0le Ringbuffer (SPSC) with two consumers"]}
# SMP mode (roles on two cores, RP2350): only these are built for several
# cores (compare-and-swap); the others are single-core (interrupt-lock)
# designs, reported but not counted there.
# heapless mpmc::Queue: compare-and-swap where the core has it (RP2350); on
# Cortex-M0+ through portable-atomic's critical sections (one core only).
MULTICORE_DOCUMENTED = {"DNedic lockfree mpmc::Queue", "heapless mpmc::Queue (Rust)"}
BOARDS = {1: "nRF5340 DK, application core (Cortex-M33)", 2: "NUCLEO-G0B1RE", 3: "NUCLEO-G474RE",
          4: "NUCLEO-H723ZG",
          5: "SAM D20 Xplained Pro", 6: "Raspberry Pi Pico 2 H"}
FIELDS = ["transferred", "errors", "first_error_at", "first_error_got", "first_error_want",
          "full_or_empty_a", "full_or_empty_b", "irqs_a", "irqs_b", "moved_a", "moved_b", "mismatch"]
HDR = ["magic", "mode", "done", "transfers", "nlibs", "board_id", "clock_hz", "timer_prescaler",
       "main_seed", "seed_a", "seed_b", "code_in_sram"]


def main():
    words_file, meta_file, out_file = sys.argv[1:4]
    if json.load(open(meta_file)).get("with_extra"):
        load_extra()
    w = [int(x, 16) for x in open(words_file).read().split()]
    h = dict(zip(HDR, w[:len(HDR)]))
    if h["magic"] != MAGIC:
        sys.exit(f"bad magic {h['magic']:#010x}")
    if h["done"] != 1:
        sys.exit("not finished")
    smp = bool(h["mode"] & 0x100)
    mode = h["mode"] & 0xFF
    names = LIBS[mode]
    if h["nlibs"] != len(names):
        sys.exit(f"layout mismatch: {h['nlibs']} libs")
    pos = len(HDR)
    libs = []
    for name in names:
        lib = {"name": name, **dict(zip(FIELDS, w[pos:pos + len(FIELDS)]))}
        pos += len(FIELDS)
        lib["n/a"] = lib["transferred"] == 0xFFFFFFFF   # main.c NOT_AVAILABLE
        lib["absent"] = lib["transferred"] == 0xFFFFFFFE  # main.c NOT_IN_IMAGE (one-library image)
        lib["starved"] = not lib["n/a"] and not lib["absent"] and lib["transferred"] < h["transfers"]
        if lib["absent"]:
            continue                                     # not in this image: not in the record
        libs.append(lib)
    if not libs:
        sys.exit("no library of this mode in the image")

    mode_name = {1: "MPSC: interrupts A (low prio) and B (high prio) produce, main consumes",
                 2: "SPMC: main produces, interrupts A (low prio) and B (high prio) consume"}[mode]
    if smp:
        mode_name = {1: "MPSC on two cores: core 1 and core 0's main loop produce, core 0's main loop consumes",
                     2: "SPMC on two cores: core 0's main loop produces, core 1 and core 0's main loop consume"}[mode]
    record = {"schema": "rb-mp-stress/0.1", "mode": mode_name, "transfers": h["transfers"],
              "params": {"board": BOARDS.get(h["board_id"], h["board_id"]), "clock_hz": h["clock_hz"],
                         "timer_prescaler": h["timer_prescaler"], "main_seed": f"{h['main_seed']:#010x}",
                         "seed_a": f"{h['seed_a']:#010x}", "seed_b": f"{h['seed_b']:#010x}",
                         "code_in_sram": bool(h["code_in_sram"])},
              "smp": smp, "libs": libs, **json.load(open(meta_file))}
    json.dump(record, open(out_file, "w"), indent=2)

    side = "full" if mode == 1 else "empty"
    moved = "pushed" if mode == 1 else "popped"
    print(f"{record['params']['board']}, {h['clock_hz'] // 1_000_000} MHz; {mode_name}; {h['transfers']} values per library")
    print(f"{'library':54} {'values':>7} {'errors':>7} {'lost+dup':>8} {moved + ' A/B':>15} {side + ' A/B':>13} {'irqs A/B':>15}")
    for l in libs:
        if l["n/a"]:
            print(f"{l['name']:54}     n/a (cannot be built for this core)")
            continue
        print(f"{l['name']:54} {l['transferred']:7} {l['errors']:7} {l['mismatch']:8} "
              f"{l['moved_a']:>7}/{l['moved_b']:<7} {l['full_or_empty_a']:>6}/{l['full_or_empty_b']:<6} "
              f"{l['irqs_a']:>7}/{l['irqs_b']:<7}" + ("  STARVED" if l["starved"] else ""))
    control = next((l for l in libs if l["name"].startswith("control")), None)
    # a one-library image (ONLY=n) without the control: nothing to catch
    control_caught = control is None or control["errors"] > 0 or control["mismatch"] > 0
    real = [l for l in libs if not l["name"].startswith("control") and l["name"] not in KNOWN_FINDING
            and not l["n/a"] and (not smp or l["name"] in MULTICORE_DOCUMENTED)]
    if smp:
        for l in libs:
            if not l["name"].startswith("control") and l["name"] not in MULTICORE_DOCUMENTED and not l["n/a"]:
                print(f"note: {l['name']}: {l['errors']} errors, {l['mismatch']} lost+dup; "
                      "single-core design, not in its documented mode on two cores")
    real_ok = all(l["errors"] == 0 and l["mismatch"] == 0 for l in real)
    starved = [l["name"] for l in libs if l["starved"]]
    for l in libs:
        if l["name"] in KNOWN_FINDING and not l["n/a"]:
            print(f"note: {l['name']}: {l['errors']} errors, {l['mismatch']} lost+dup "
                  f"(known finding, see {KNOWN_FINDING[l['name']]})")
    for n in starved:
        print(f"note: {n}: starved (fewer values than requested), not counted")
    print(f"\nlibraries in their documented mode error-free: {real_ok}; control caught: "
          + ("(not in this image)" if control is None else str(control_caught)))
    sys.exit(0 if real_ok and control_caught and not starved else 1)


if __name__ == "__main__":
    main()
