#!/usr/bin/env python3
"""Decode the rb-dma-stress result block (main.c struct results) into a
table and a JSON record.

Usage: decode.py WORDS_FILE META_JSON OUT_JSON
Exit 0 only if every library run is error-free (no sequence error, no
lost or extra byte, not stalled) and the control, if it ran, was caught
and the DMA transfers overlapped the consumer's reads (else the window was
not exercised).
"""
import json
import sys

MAGIC = 0x564C4431
NAMES = ["pxq RingBuffer_PackedState", "lwrb", "Zephyr ring_buf", "TinyUSB tu_fifo", "ECE ring_buffer",
         "NuttX circbuf", "bbqueue (Rust)", "control: lwrb with the commit before the DMA writes"]
BOARDS = {1: "nRF5340 DK, application core (Cortex-M33)", 2: "NUCLEO-G0B1RE", 3: "NUCLEO-G474RE",
          4: "NUCLEO-H723ZG", 5: "SAM D20 Xplained Pro", 6: "Raspberry Pi Pico 2 H"}
HDR = ["magic", "version", "done", "transfers", "nlibs", "board_id", "clock_hz", "prescaler",
       "main_seed", "dma_seed", "code_in_sram", "reserved"]
FIELDS = ["transferred", "errors", "first_error_at", "first_error_got", "first_error_want", "full_events",
          "dma_transfers", "overlaps", "retries", "mismatch", "dma_irqs", "stalled"]


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
    libs, pos = [], len(HDR)
    for name in NAMES:
        lib = {"name": name, **dict(zip(FIELDS, w[pos:pos + len(FIELDS)]))}
        pos += len(FIELDS)
        if lib["transferred"] == 0xFFFFFFFE:        # not in this run
            continue
        lib["n/a"] = lib["transferred"] == 0xFFFFFFFF
        lib["starved"] = not lib["n/a"] and (lib["stalled"] != 0 or lib["transferred"] < h["transfers"])
        libs.append(lib)
    if not libs:
        sys.exit("no library in the block")
    meta = json.load(open(meta_file))
    record = {"schema": "rb-dma-stress/0.1", "transfers": h["transfers"],
              "params": {"board": BOARDS.get(h["board_id"], h["board_id"]), "clock_hz": h["clock_hz"],
                         "prescaler": h["prescaler"], "main_seed": f"{h['main_seed']:#010x}",
                         "dma_seed": f"{h['dma_seed']:#010x}", "code_in_sram": bool(h["code_in_sram"])},
              "libs": libs, **meta}
    json.dump(record, open(out_file, "w"), indent=2)

    print(f"{record['params']['board']}, {h['clock_hz'] // 1_000_000} MHz; DMA producer (one byte per timer "
          f"request), main loop consumer; {h['transfers']} bytes per library")
    print(f"{'library':52} {'bytes':>8} {'errors':>7} {'lost+x':>6} {'DMA xfers':>9} {'overlap':>8} "
          f"{'full':>7} {'retries':>7}")
    for l in libs:
        if l["n/a"]:
            print(f"{l['name']:52}      n/a (no zero-copy API)")
            continue
        print(f"{l['name']:52} {l['transferred']:8} {l['errors']:7} {l['mismatch']:6} {l['dma_transfers']:9} "
              f"{l['overlaps']:8} {l['full_events']:7} {l['retries']:7}"
              + ("  STALLED" if l["stalled"] else "") + ("  STARVED" if l["starved"] else ""))
    control = next((l for l in libs if l["name"].startswith("control")), None)
    real = [l for l in libs if not l["name"].startswith("control") and not l["n/a"]]
    real_ok = all(l["errors"] == 0 and l["mismatch"] == 0 and not l["starved"] for l in real)
    window = all(l["overlaps"] > 0 for l in libs if not l["n/a"])
    caught = control is None or control["errors"] > 0 or control["mismatch"] > 0
    print(f"\nlibraries error-free: {real_ok}; control caught: "
          + ("(not in this run)" if control is None else str(caught))
          + f"; reads during transfers in every library: {window}")
    sys.exit(0 if real_ok and caught and window else 1)


if __name__ == "__main__":
    main()
