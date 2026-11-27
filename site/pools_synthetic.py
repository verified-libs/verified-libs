#!/usr/bin/env python3
"""SYNTHETIC records of the pools kind, for building and testing the pools
pages before the board series exists. Every number here is made up: none is
a measurement, and none may ever be committed under records/ or site/data.

Usage: python3 -I site/pools_synthetic.py OUT_DIR [--seed N]

Writes, under OUT_DIR:
  runs/<board>/         made-up run files (pools-bench-run/1), build.json and
                        options.json, one directory per board, as
                        kinds/pools/bench/run-pools.py leaves them;
  records/<board>/<adapter>.json
                        the records, made from those run files by the kind's
                        own record writer (kinds/pools/bench/poolrecords.py),
                        so that they have its exact shape (pools-bench/1).
After poolrecords.py, each record gets "synthetic": true. The sizes are in
the run files, as the board build writes them ("sizes", kinds/pools/README.md,
"Sizes: `sizes` in the record"), with made-up code and const bytes.
Every record says it is synthetic four times over: "synthetic": true, the
commit "5yn7e71c0000", the toolchain image "synthetic:0" and a board_decoded
that starts with "SYNTHETIC". site/pools_data.py refuses such a record under
records/pools.

The made-up numbers have the record's shape and a plausible order of
magnitude: per configuration a cost per alloc and per free, a factor per
core and per cache state, a search cost where a pool scans (pair_full,
init), a smaller cost on the failure path (empty), and a spread over the
eight placements drawn with a fixed seed, so that some rows overlap and some
do not. heapless is left out on the two Cortex-M0+ boards, as
kinds/pools/boards.txt says.
"""
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COMMIT = "5yn7e71c0000"
IMAGE = "synthetic:0"
PLACES = (0, 4, 8, 12, 16, 20, 24, 28)
SCEN = ("pair", "pair_full", "fill_drain_lifo", "fill_drain_fifo", "mixed", "empty")
BLOCK_RAM = 32 * 32 + 2 * 16   # the blocks and the canaries, counted in ram_bytes (README, "Sizes")
# board dir -> (board, core, board_id, board_decoded, clock_hz, core factor, cache-off factor, M0+)
BOARDS = {
    "nrf5340": ("nRF5340 DK", "application (Cortex-M33)", 1, "nRF5340 DK, application core (Cortex-M33)", 64000000, 1.0, 1.15, False),
    "rp2350": ("Raspberry Pi Pico 2 H", "RP2350 core 0 (Cortex-M33)", 6, "Raspberry Pi Pico 2 H (RP2350A, core 0, Cortex-M33)",
               150000000, 1.0, 3.0, False),
    "stm32g474": ("NUCLEO-G474RE", "Cortex-M4F", 3, "NUCLEO-G474RE (STM32G474RET6, Cortex-M4F)", 170000000, 1.05, 1.6, False),
    "stm32h723": ("NUCLEO-H723ZG", "Cortex-M7", 4, "NUCLEO-H723ZG (STM32H723ZGT6, Cortex-M7)", 520000000, 0.85, 2.4, False),
    "stm32g0b1": ("NUCLEO-G0B1RE", "Cortex-M0+", 2, "NUCLEO-G0B1RE (STM32G0B1RET6, Cortex-M0+)", 64000000, 1.45, 1.3, True),
    "samd20": ("SAM D20 Xplained Pro", "Cortex-M0+", 5, "SAM D20 Xplained Pro (ATSAMD20J18A, Cortex-M0+)", 48005120, 1.5, 1.1, True),
}
# adapter -> (alloc, free, init per block, scans: pair_full factor, flash bytes M0+/other, RAM bytes beyond the blocks)
COST = {
    "baseline":            (9, 8, 3, 1.0, None, None),
    "adapter_etl":         (14, 12, 4, 1.0, (172, 172), 25),
    "adapter_riot":        (18, 16, 4, 1.0, (306, 434), 8),
    "adapter_threadx":     (46, 41, 6, 1.0, (1050, 714), 192),
    "adapter_cmsis_rtx":   (31, 28, 5, 1.0, (254, 286), 24),
    "adapter_contiki":     (21, 19, 3, 3.2, (222, 226), 44),
    "adapter_c_allocator": (26, 22, 4, 1.0, (354, 334), 45),
    "adapter_lwip":        (29, 26, 4, 1.0, (256, 232), 20),
    "adapter_memorypool":  (12, 11, 4, 1.0, (136, 120), 5),
    "adapter_heapless":    (30, 26, 5, 1.0, (None, 404), 136),
    "adapter_atomic_pool": (41, 35, 1, 2.6, (434, 514), 4),
    "adapter_ref_primask": (13, 12, 3, 1.0, (120, 116), 12),
}
MIXED_ALLOC = 262   # of the 512 calls of "mixed", the same split in every run


def configs():
    out = []
    for line in open(os.path.join(ROOT, "kinds/pools/configs.txt")):
        f = line.split(None, 2)
        if f and not f[0].startswith("#") and len(f) == 3 and f[0] in COST:
            out.append((f[0], f[1], f[2].strip()))
    return out


def only_on():
    out = {}
    for line in open(os.path.join(ROOT, "kinds/pools/boards.txt")):
        f = line.split()
        if f and not f[0].startswith("#"):
            out[f[0]] = set(f[1:])
    return out


def results(rnd, adapter, b, place, p):
    """One run's result set of one library: {key: {min, max, mean, first, count}}."""
    alloc, free, per_block, scan = COST[adapter][:4]
    _, _, _, _, _, core_f, off_f, m0 = BOARDS[b]
    if adapter == "adapter_cmsis_rtx" and m0:   # interrupts off on Armv6-M instead of LDREX/STREX
        alloc, free = alloc + 6, free + 6
    out = {}
    for cache in ("off", "on"):
        f = core_f * (off_f if cache == "off" else 1.0)
        # the spread over the placements: larger with the cache off; the second pass close to the first
        spread = lambda: (rnd.uniform(0, 0.04) + (rnd.uniform(0, 0.25) if cache == "off" else 0)) + (0.003 * (p - 1))  # noqa: E731
        for s in SCEN:
            for op, base in (("alloc", alloc), ("free", free)):
                if s == "empty" and op == "free":
                    out[f"{s}/{op}/cache_{cache}"] = None
                    continue
                m = base * f
                if s == "pair_full" and op == "alloc":
                    m *= scan
                elif s == "empty":
                    m *= 0.6 * (scan if scan > 1 else 1)
                elif s == "mixed":
                    m *= 1.08
                elif s.startswith("fill_drain") and scan > 1 and op == "alloc":
                    m *= (1 + scan) / 2
                m *= 1 + spread()
                count = 256 if s != "mixed" else (MIXED_ALLOC if op == "alloc" else 512 - MIXED_ALLOC)
                mn = max(1, int(m * 0.9))
                out[f"{s}/{op}/cache_{cache}"] = {"min": mn, "max": int(m * 1.4) + 3, "mean": round(m, 3),
                                                  "first": int(m * 1.3) + 2, "count": count}
        i = per_block * 32 * f * (1 + spread()) + 10
        out[f"init/cache_{cache}"] = {"min": int(i), "max": int(i), "mean": round(float(int(i)), 3), "first": int(i), "count": 1}
    return out


def sizes(adapter, b):
    flash, ram = COST[adapter][4:6]
    code = flash[0 if BOARDS[b][7] else 1]
    const = 8 if adapter in ("adapter_heapless", "adapter_atomic_pool") else 0
    return {"code_bytes": code, "const_bytes": const, "flash_bytes": code + const, "ram_bytes": ram + BLOCK_RAM,
            "ram_overhead_bytes": ram}


def write_runs(out, seed):
    rnd = random.Random(seed)
    cfgs, only = configs(), only_on()
    dirs = []
    for b, (board, core, bid, dec, clock, _, _, _) in BOARDS.items():
        d = os.path.join(out, "runs", b)
        os.makedirs(d, exist_ok=True)
        dirs.append(d)
        built = {"board": b, "kind": "pools", "bench_commit": COMMIT, "toolchain_image": IMAGE,
                 "toolchain": {"synthetic": "no compiler: synthetic records"}, "libs_pinned": ["synthetic"]}
        json.dump(built, open(os.path.join(d, "build.json"), "w"))
        json.dump({"schema": "board-options/1", "board": b, "chip": "SYNTHETIC", "time": "2026-11-26T00:00:00Z",
                   "probe_rs": "synthetic", "regions": [{"name": "SYNTHETIC", "address": "0x0", "source": "synthetic",
                                                        "words": ["0x0"]}]},
                  open(os.path.join(d, "options.json"), "w"))
        for n, (ad, lang, name) in enumerate(cfgs):
            if ad in only and b not in only[ad]:
                continue
            for place in PLACES:
                for p in (1, 2):
                    r = {"schema": "pools-bench-run/1", "result_version": 1,
                         "time": f"2026-11-26T{n:02d}:{place:02d}:0{p}Z", "host": "synthetic",
                         "board": board, "core": core, "board_id": bid, "board_decoded": "SYNTHETIC " + dec,
                         "code_location": "flash", "kind": "pools", "bench_commit": COMMIT, "toolchain_image": IMAGE,
                         "adapter": ad, "lang": lang, "name": name, "place": place,
                         "slot": {"segment": 200 + n, "offset": 4096 * (1 + place // 4), "slot_bytes": 12288},
                         "image_base": f"{0x08100000 + 0x40000 * n + 4096 * place:#010x}", "image_bytes": 9000 + 8 * n,
                         "fw_sha256": f"synthetic-elf-{ad}-{place}", "image_sha256": f"synthetic-img-{ad}-{place}",
                         "fixed_sha256": "synthetic-fixed", "boot_image_sha256": "synthetic-boot", "bundle": 900 + n,
                         "bundle_sha256": "synthetic-bundle", "far_bytes": 6144,
                         "layout": "fixed, placement, adapter, far, library", "run_number": f"{rnd.getrandbits(32):#010x}",
                         "pass": p, "attempt": 1, "wait_s": 5.0, "seconds": 6.0, "probe_rs": "synthetic",
                         "clock_hz": clock, "runs": 256, "blocks": 32, "block_size": 32, "sizes": sizes(ad, b),
                         "overhead_subtracted": 2,
                         "empty_call_raw_min": 8,
                         "libs": [{"name": "baseline", "results": results(rnd, "baseline", b, place, p), "errors": 0},
                                  {"name": name, "results": results(rnd, ad, b, place, p), "errors": 0}]}
                    json.dump(r, open(os.path.join(d, f"{ad}-p{place}-pass{p}.json"), "w"))
    return dirs


def main():
    a = sys.argv[1:]
    seed = 20261126
    if "--seed" in a:
        i = a.index("--seed")
        seed, a = int(a[i + 1]), a[:i] + a[i + 2:]
    if len(a) != 1 or a[0].startswith("-"):
        sys.exit(__doc__)
    out = os.path.abspath(a[0])
    if os.path.commonpath([out, os.path.join(ROOT, "records")]) == os.path.join(ROOT, "records") or \
            os.path.commonpath([out, os.path.join(ROOT, "site")]) == os.path.join(ROOT, "site"):
        sys.exit("refused: synthetic records are never written under records/ or site/")
    dirs = write_runs(out, seed)
    recs = os.path.join(out, "records")
    p = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "kinds/pools/bench/poolrecords.py"), "--out", recs] + dirs,
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit("poolrecords.py refused the synthetic runs:\n" + p.stdout + p.stderr)
    sys.path.insert(0, os.path.join(ROOT, "kinds/pools/bench"))
    import poolrecords   # noqa: E402  (the same compact form as poolrecords.py writes)
    for b in os.listdir(recs):
        for f in os.listdir(os.path.join(recs, b)):
            path = os.path.join(recs, b, f)
            rec = json.load(open(path))
            rec = dict({"schema": rec["schema"], "synthetic": True}, **{k: v for k, v in rec.items() if k != "schema"})
            open(path, "w").write(poolrecords.dump(rec))
    n = sum(len(fs) for _, _, fs in os.walk(recs))
    print(f"{n} SYNTHETIC records in {recs} (poolrecords.py: {p.stdout.strip().splitlines()[-1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
