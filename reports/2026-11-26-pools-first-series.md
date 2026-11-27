# Pools, the first series on the boards (2026-11-26)

Fixed-block pools, the third kind: 32 blocks of 32 bytes. Eleven
configurations on six boards (`kinds/pools/README.md`). The job list is
`lab/plans/2026-11-26-pools-series-jobs.md`; each job approved by the review
before it was enqueued. Measured
under method version 3.

## Result

- **64 records** (`records/pools/`, `pools-bench/1`): 11 on each board but
  the two Cortex-M0+ boards, which have 10 (heapless needs LDREX/STREX).
  Committed in `kind-pools` `e81e2a0` (42) and `f00be00` (22).
- **Series commit `f12caf7`.** The pools test sources (`public-export.py`
  POOLS_TEST_SOURCES) have not changed since the first write.
  - It replaced `2c807f9`, at which nothing was written, to add the sizes to
    the records.
  - All 512 images and 16 bundle files are byte for byte those of `2c807f9`.
- **All 64 records rebuilt by `poolverify.sh` at `f12caf7`: MATCH** (flash
  bytes, addresses, fixed part, boot stub, toolchain, layout, sizes).
- **Nothing was left out.** In every run the baseline (our reference free
  list) measured the same on each board: 24 of 24 numbers.
- **No fault** in any configuration's checks: every call was checked
  outside the timed window, errors 0 in all runs. No library defect was seen.
- **The export check passes:** "64 pools records".

## The jobs

| Board | Smoke (configurations) | Series jobs | Runs | Writes | Time (UTC) |
|---|---|---|---|---|---|
| NUCLEO-G474RE | GS: atomic-pool, MemoryPool | G1–G3 | 32 + 176 | 3 | 14:14–14:35 |
| NUCLEO-G0B1RE | BS: atomic-pool, MemoryPool | B1–B3 | 32 + 160 | 3 | 14:14–14:34 |
| SAM D20 Xplained Pro | DS: ETL, RIOT | D1–D5 | 32 + 160 | 5 | 14:14–14:37 |
| NUCLEO-H723ZG | HS: atomic-pool, ETL | H1–H2 | 32 + 176 | 2 | 14:14–14:35 |
| Pico 2 | PS: atomic-pool, ETL | P1 | 32 + 176 | 1 | 14:56–15:20 |
| nRF5340 DK | NS: atomic-pool, ETL | N1–N2 | 32 + 176 | 2 | 15:01–15:26 |

- **Writes: 16 in all, as counted** (the queue's ledger). The smoke's write
  is that bundle's write for the series.
- **Every smoke passed:** the job's check, two records made with their
  sizes, both MATCH.
- **Every series job passed its check:** options read whole, the run count,
  the clock, errors 0, no stall. No board stopped.
- **A run took about 5.6 s** on every board (wait 5 s), so the series took
  20–25 minutes per board.
- **The Pico 2's write** went alone, under the exclusive write lock, in two
  parts: 250 units in 33 s, then 15 units in 2.4 s, the second started 70 s
  after the first (`run-pools.py` `write_parts`). No power loss.
- **The nRF5340** ran after its method version 3 reruns had ended and their
  records were made. It was not power-cycled.
- **The four boards on two hubs** ran side by side; no power switching.

## Option registers

Read zero-write before every job; every record carries them. On each board
every reading of the day is equal; the values are in the method version 3
report (`reports/2026-11-26-method-version-3-reruns.md`).

## Sizes (`sizes` in each record)

Flash bytes (code + constant data) and RAM beyond the 1056 bytes of blocks
and canaries. Measured in the board image against a null image
(`kinds/pools/bench/onepool.py` `sizes_of`), the same at all eight
placements:

| Configuration | G0B1, SAM D20 (M0+) | G474 (M4) | H723 (M7) | nRF5340, Pico 2 (M33) | RAM overhead |
|---|---|---|---|---|---|
| reference, interrupts off (ours) | 120 | 116 | 120 | 120 | 12 |
| ETL | 172 | 172 | 172 | 176 | 25 |
| RIOT | 140 | 128 | 128 | 128 | 8 |
| ThreadX | 780 | 724 | 720 | 732 | 192 |
| CMSIS-RTX | 256 | 288 | 292 | 288 | 24 |
| Contiki-NG | 224 | 232 | 232 | 232 | 44 |
| C_Allocator | 356 | 336 | 336 | 336 | 45 |
| lwIP | 260 | 236 | 236 | 236 | 20 |
| MemoryPool | 136 | 120 | 124 | 124 | 5 |
| heapless | – | 404 | 412 | 404 | 136 |
| atomic-pool | 948 | 604 | 608 | 560 | 4 |

The RAM overhead is the same on every board.

## Files beside the records

- **`kinds/pools/claims.tsv`:** what each library documents about use from
  interrupts and threads, with sources. The pages show it as "documented,
  not tested". It is no test source.
- **Run directories:** `~/vl-wt-pools-runs/<board>/<job>/`, with
  `options.json`, `run.log` and the run files.
  - The smokes' records are in `…/<job>-records/`. They are not in the
    repository: the series jobs ran the same images again.

## Open

- **The ledger for pools records** (`lab/tools/image-ledger.py`): not made.
  Until it is, a pools record of a commit whose pools test sources differ
  from HEAD's stops the export. None does today.
- **The concurrency series** (plan, section 4).
