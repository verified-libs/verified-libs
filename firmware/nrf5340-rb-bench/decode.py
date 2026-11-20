#!/usr/bin/env python3
"""Decode the nrf5340-rb-bench result block (hex words from probe-rs read)
into a table on stdout and a JSON record.

Usage: decode.py WORDS_FILE META_JSON NM_FILE OUT_JSON
"""
import json
import re
import sys

MAGIC = 0x564C4235
LIBS = ["baseline", "pxq RingBuffer_PackedState (C++)", "lwrb (C)", "AndersKaloer Ring-Buffer (C)",
        "jnk0le Ringbuffer (C++)", "ETL queue_spsc_isr (C++)", "ETL queue_spsc_atomic (C++)",
        "QuantumLeaps LFRB (C)", "EmbeddedArtistry cbuf threadsafe (C)", "ece-mohammad RingBuffer (C)",
        "micoring SPSC mode (C)", "kostyk348 lf_spsc (C)", "diffstorm cb (C)", "RIOT tsrb (C)",
        "Contiki-NG ringbuf (C)", "rigtorp SPSCQueue (C++)", "wizard97 as shipped (C++)",
        "wizard97 + PRIMASK macros (C++)", "polycratia spscring (C++)", "rt-spsc (C++)",
        "TinyUSB tu_fifo (C)",
        "Zephyr ring_buf (C)", "Zephyr ring_buf, CONFIG_SMP (C)", "DNedic lockfree spsc::RingBuf (C++)",
        "ETL queue_spsc_locked (C++)", "FreeRTOS stream buffer (C)",
        "NuttX circbuf (C)", "Arduino RingBufferN as shipped (C++)", "Arduino SafeRingBufferN (C++)",
        "RT-Thread rt_ringbuffer, no lock (C)", "RT-Thread rt_ringbuffer + interrupt lock (C)", "Mbed CE CircularBuffer (C++)", "moodycamel ReaderWriterQueue (C++)",
        # single-context variants (not for sharing between contexts)
        "pxq Topology::None, single-context (C++)", "micoring default, single-context (C)",
        "EmbeddedArtistry cbuf basic, single-context (C)", "ETL etl::queue, single-context (C++)"]
# SET=mp firmware: each mode for more than one producer or consumer next to
# the library's SPSC configuration, timed from one context.
LIBS_MP = ["baseline", "pxq RingBuffer_PackedState (C++)", "pxq Topology::MPSC (C++)",
           "pxq Topology::SPMC (C++)", "pxq Topology::MPMC (C++)",
           "DNedic lockfree spsc::RingBuf (C++)", "DNedic lockfree mpmc::Queue (C++)",
           "RIOT tsrb (C)", "wizard97 + PRIMASK macros (C++)", "heapless mpmc::Queue (Rust)"]
# SET=rust firmware: the Rust libraries, with baseline and pxq as a reference.
LIBS_RUST = ["baseline", "pxq RingBuffer_PackedState (C++)", "heapless spsc::Queue (Rust)",
             "bbqueue (Rust)", "embassy-sync Pipe (Rust)"]
# SET=nordic firmware (nRF5340 only): Nordic's nrf_ringbuf, same reference.
LIBS_NORDIC = ["baseline", "pxq RingBuffer_PackedState (C++)", "Nordic nrf_ringbuf (C)",
               # parts of its single-byte call (not libraries; their error
               # counts mean nothing: they move no data)
               "part: nrf_atomic flag set + clear", "part: memcpy of 1 byte", "part: nrf_ringbuf cpy_put/cpy_get, length 0"]
# Not SPSC configurations: (library's SPSC configuration, mode).
MP_MODES = {"pxq Topology::MPSC (C++)": ("pxq RingBuffer_PackedState (C++)", "MPSC"),
            "pxq Topology::SPMC (C++)": ("pxq RingBuffer_PackedState (C++)", "SPMC"),
            "pxq Topology::MPMC (C++)": ("pxq RingBuffer_PackedState (C++)", "MPMC"),
            "DNedic lockfree mpmc::Queue (C++)": ("DNedic lockfree spsc::RingBuf (C++)", "MPMC"),
            "heapless mpmc::Queue (Rust)": ("heapless spsc::Queue (Rust)", "MPMC")}
SINGLE_CONTEXT = {"pxq Topology::None, single-context (C++)", "micoring default, single-context (C)",
                  "EmbeddedArtistry cbuf basic, single-context (C)", "ETL etl::queue, single-context (C++)",
                  "wizard97 as shipped (C++)", "Arduino RingBufferN as shipped (C++)",
                  "RT-Thread rt_ringbuffer, no lock (C)"}
SCENARIOS = [("single", 1), ("burst16", 1), ("block4", 4), ("block16", 16), ("block64", 64),
             ("dma16", 16), ("dma64", 64)]
CACHE = ["off", "on"]
STAT_WORDS = 5
# Result layout version 6 reports the board, the clock and the counter read
# overhead; version 5 (nRF5340 only) had HFCLKCTRL in their place.
BOARDS = {1: "nRF5340 DK, application core (Cortex-M33)",
          2: "NUCLEO-G0B1RE (STM32G0B1RET6, Cortex-M0+)",
          3: "NUCLEO-G474RE (STM32G474RET6, Cortex-M4F)",
          4: "NUCLEO-H723ZG (STM32H723ZGT6, Cortex-M7)",
          5: "SAM D20 Xplained Pro (ATSAMD20J18A, Cortex-M0+)",
          6: "Raspberry Pi Pico 2 H (RP2350A, core 0, Cortex-M33)"}
OVERHEAD = 1  # set from the record in main(); v5: CYCCNT read, measured by nrf5340-cyccnt


def code_sizes(nm_file):
    """Code bytes of the adapters, the library functions and the timing
    helper, from `nm -S -C` output."""
    sizes = {}
    for line in open(nm_file):
        parts = line.split(None, 3)
        if len(parts) != 4 or parts[2] not in "tT":
            continue
        name = parts[3].strip()
        if re.search(r"pxq_|lwrb_|baseline_|anders_|ring_buffer_|jnk_|etl_|qp_|RingBuf_|ea_|circular_buf_|ece_|RingBuffer_|mring|kostyk_|ds_|cb_|tsrb|ck_|ringbuf_|rig_|w97|poly_|rts_|pxqn_|lfm_|msc_|eap_|ea_plain_|etlq_|hlm?_|bbq_|emb_|memcpy|time_call", name):
            sizes[name] = int(parts[1], 16)
    return sizes


def stat(words, pos):
    mn, mx, total, first, count = words[pos:pos + STAT_WORDS]
    if count == 0:
        return None  # scenario not supported by this library (e.g. no zero-copy API)
    return {
        "min": mn - OVERHEAD,
        "max": mx - OVERHEAD,
        "mean": round(total / count - OVERHEAD, 3),
        "first": first - OVERHEAD,
        "count": count,
    }


def main():
    global OVERHEAD
    words_file, meta_file, nm_file, out_file = sys.argv[1:5]
    words = [int(w, 16) for w in open(words_file).read().split()]
    magic, version, done, clock_word, runs, nlibs, nscen = words[:7]
    if magic != MAGIC:
        sys.exit(f"bad magic {magic:#010x}")
    if done != 1:
        sys.exit("measurement not finished")
    names = {len(LIBS_MP): LIBS_MP, len(LIBS_RUST): LIBS_RUST, len(LIBS_NORDIC): LIBS_NORDIC}.get(nlibs, LIBS)
    if nscen != len(SCENARIOS) or nlibs != len(names):
        sys.exit(f"layout mismatch: {nlibs} libs, {nscen} scenarios")
    if version not in (5, 6):
        sys.exit(f"unknown result version {version}")
    trailer = 7 + nlibs * (2 * nscen * 2 * STAT_WORDS + 1) + 1  # after dwt_stalls
    if version >= 6:
        clock_hz = clock_word
        board_id, OVERHEAD, empty_raw = words[trailer:trailer + 3]
    else:
        clock_hz = 64_000_000 if clock_word == 1 else 128_000_000
        board_id, OVERHEAD, empty_raw = 1, 1, None
    if board_id not in BOARDS:
        sys.exit(f"unknown board id {board_id}")

    pos = 7
    libs = []
    for name in names:
        lib = {"name": name, "results": {}}
        for cache in CACHE:
            for scen, _ in SCENARIOS:
                push = stat(words, pos)
                pop = stat(words, pos + STAT_WORDS)
                pos += 2 * STAT_WORDS
                lib["results"][f"{scen}/cache_{cache}"] = {"push": push, "pop": pop}
        lib["errors"] = words[pos] if name != "baseline" and not name.startswith("part: ") else None
        pos += 1
        libs.append(lib)
    dwt_stalls = words[pos]
    if dwt_stalls:
        sys.exit(f"invalid run: cycle counter stalled ({dwt_stalls:#x}); results rejected")

    meta = json.load(open(meta_file))
    record = {
        "schema": "nrf5340-rb-bench/0.3",
        "result_version": version,
        "board_id": board_id,
        "board_decoded": BOARDS[board_id],
        "clock_hz": clock_hz,
        "runs": runs,
        "overhead_subtracted": OVERHEAD,
        "empty_call_raw_min": empty_raw,
        "set": {id(LIBS_MP): "mp", id(LIBS_RUST): "rust", id(LIBS_NORDIC): "nordic"}.get(id(names), "spsc"),
        "scenarios": [s for s, _ in SCENARIOS],
        "libs": libs,
        "code_bytes": code_sizes(nm_file),
        **meta,
    }
    json.dump(record, open(out_file, "w"), indent=2)

    print(f"{BOARDS[board_id]}: code in {meta.get('code_location', '?')}, {record['clock_hz'] // 1_000_000} MHz, "
          f"cycles per call, overhead {OVERHEAD} subtracted; mean (min) and, for blocks, cycles/byte")
    if empty_raw is not None:
        print(f"calibration: empty call (blx; movs; bx lr) raw minimum {empty_raw} cycles, "
              f"i.e. {empty_raw - OVERHEAD} after the read overhead")
    for scen, n in SCENARIOS:
        dma = scen.startswith("dma")
        print(f"\n== {scen}" + (f" ({n} bytes per transfer, zero-copy: library calls only, cycles per transfer"
                                 f" = acquire + commit, plus a second pair when split at the wrap)" if dma
                                 else f" ({n} bytes per call)" if n > 1 else ""))
        print(f"{'library':38} {'push on':>14} {'pop on':>14} {'push off':>9} {'pop off':>9}")
        for lib in libs:
            on = lib["results"][f"{scen}/cache_on"]
            off = lib["results"][f"{scen}/cache_off"]

            if on['push'] is None:
                continue  # library has no API for this scenario

            def cell(s):
                txt = f"{s['mean']:.1f} ({s['min']})"
                return txt + (f" {s['mean'] / n:.2f}/B" if n > 1 else "")

            print(f"{lib['name']:34} {cell(on['push']):>14} {cell(on['pop']):>14} "
                  f"{off['push']['mean']:9.1f} {off['pop']['mean']:9.1f}")
    print()
    for lib in libs:
        if lib["name"] == "baseline":
            print("errors baseline: not checked (one slot, not a FIFO: burst16 overwrites it)")
        elif lib["name"].startswith("part: "):
            continue   # parts of a library's call (SET=nordic): they move no data
        else:
            na = lib["results"]["single/cache_on"]["push"] is None
            print(f"errors {lib['name']}: {'not available on this core' if na else lib['errors']}")
    print("code bytes: " + ", ".join(f"{k} {v}" for k, v in record["code_bytes"].items()))


if __name__ == "__main__":
    main()
