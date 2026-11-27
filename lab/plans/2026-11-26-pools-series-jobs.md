# The pools kind's first series: the job list (2026-11-26)

Proposed by the builder for the reviewer's OK per job (as the v3 reruns,
`lab/plans/2026-11-26-v3-reruns-jobs.md`). Measured under method version 3.

## The series commit and the tree

- **Series commit: `f12caf7`** on `kind-pools`. It replaces `2c807f9`, at
  which nothing was written: f12caf7 adds the configuration's sizes to every
  record (`sizes`, README "Sizes"). All 512 images and all 16 bundle files
  are byte for byte those of 2c807f9. Its pools test sources
  (`lab/tools/public-export.py` POOLS_TEST_SOURCES) do not change after the
  first write. Files that are no pools test source may still land: this list,
  `lab/tools/pools-series-enqueue.sh`, `lab/tools/pools-smoke-check.sh`, and
  the ledger's pools support in `image-ledger.py`.
- **Worktree:** `~/vl-wt-pools-series`, detached at `f12caf7`, clean. All six
  boards are built there (`kinds/pools/bench/onebuild.sh table`, libraries
  from `~/vl-next/kind-pools` at the pins of `kinds/pools/libs.lock`).
- **Record schema:** `pools-bench/1` (`kinds/pools/README.md`, "On the
  boards"), stable from this commit on.

## Every job

Enqueued one at a time, with `OK=… bash lab/tools/pools-series-enqueue.sh JOB`.

1. **The board's option registers first:** `lab/tools/read-options.py`,
   zero write, into the job's run directory (`options.json`). Every record
   carries them.
2. **Then the runner:** `kinds/pools/bench/run-pools.py BOARD DIR --bundle N --passes 2`.
   - With `--flash` when the job writes its bundle.
   - On a smoke, `--adapter A,B`.
3. **What the queue holds the job to:**
   - Budget: `--writes` 0 or 1. A job with 0 also has `--refuse "FLASH WRITE"`.
   - `--expect "done: RUNS runs, 0 without a file, W flash writes"`.
   - `--refuse "errors [1-9]"`.
   - A timeout.
   - The Pico 2's writing job holds the write lock exclusively for its whole
     length (boardqueue.py), so no other board writes meanwhile. Its write
     goes in parts of at most 250 units, 70 s apart (run-pools.py
     `write_parts`).
4. **The check after every job** (`~/vl-v3-proof/check_job.py`): options
   read whole; the run-file count as expected; the board's clock; errors 0;
   no stall.
5. **After a smoke** (`lab/tools/pools-smoke-check.sh`):
   - two records made from the smoke's run directory (outside the repository),
     each with its sizes;
   - both rebuilt by `poolverify.sh` at the series commit: MATCH, the sizes
     equal to the build's.
6. **Stop rules.** A board stops at the first job that is not as expected
   (a run without a file, errors, a stall, a write over budget, a failed
   smoke check). The other boards go on.

## The smoke

Each smoke runs on the board's first bundle and writes it (1 write):
- **two configurations whole:** eight placements, two passes, so 32 runs and
  a record each;
- **every call checked:** the reference free list is measured beside each
  configuration in every image, as the baseline.

The smoke's configurations, one C++ and one Rust where the bundle has one:
- atomic-pool and ETL: H723, nRF5340, Pico 2 (all in bundle 50 or 12);
- atomic-pool and MemoryPool: G474 and G0B1 (bundle 101);
- ETL and RIOT: SAM D20 (bundle 200 has no Rust configuration; Rust on a
  Cortex-M0+ is covered by the G0B1's smoke).

The series job on the smoke's bundle then runs all its images without a write.

## The jobs

Timeouts allow twice the seconds per run of the board's CRC runs, plus 600 s.

| Job | Board | Bundle | Runs | Writes | Timeout s |
|---|---|---|---|---|---|
| GS | NUCLEO-G474RE (`nucleo-g474re`) | 101, smoke | 32 | 1 | 1000 |
| G1 | | 101 | 84 | 0 | 1600 |
| G2 | | 100 | 84 | 1 | 1700 |
| G3 | | 102 | 8 | 1 | 800 |
| BS | NUCLEO-G0B1RE (`nucleo-g0b1re`) | 101, smoke | 32 | 1 | 1300 |
| B1 | | 101 | 68 | 0 | 2100 |
| B2 | | 100 | 84 | 1 | 2500 |
| B3 | | 102 | 8 | 1 | 800 |
| DS | SAM D20 Xplained Pro (`sam-d20-xpro`) | 200, smoke | 32 | 1 | 2000 |
| D1 | | 200 | 42 | 0 | 2400 |
| D2 | | 201 | 42 | 1 | 2400 |
| D3 | | 202 | 42 | 1 | 2400 |
| D4 | | 203 | 26 | 1 | 1700 |
| D5 | | 204 | 8 | 1 | 1000 |
| HS | NUCLEO-H723ZG (`nucleo-h723zg`) | 50, smoke | 32 | 1 | 1000 |
| H1 | | 50 | 168 | 0 | 2500 |
| H2 | | 51 | 8 | 1 | 800 |
| NS | nRF5340 DK (`nrf5340dk`) | 50, smoke | 32 | 1 | 1300 |
| N1 | | 50 | 168 | 0 | 4300 |
| N2 | | 51 | 8 | 1 | 800 |
| PS | Pico 2 (`pico2`) | 12, smoke | 32 | 1 | 3600 |
| P1 | | 12 | 176 | 0 | 15000 |

**Writes:** G474 3, G0B1 3, SAM D20 5, H723 2, nRF5340 2, Pico 2 1. That is
16, as counted (the smoke's write is the series' write of that bundle).

**Runs:** 1024 in the series (88 images per board, 80 on the two
Cortex-M0+ boards, two passes each), plus 192 in the smokes.

**Records:** 11 per board and 10 on the G0B1 and the SAM D20 (no heapless),
so 64.

**Configurations in more than one bundle:**
- reference, interrupts off: 4 + 4 placements, on every board but the Pico 2;
- C_Allocator: 2 + 6 on the G474, G0B1 and SAM D20;
- ThreadX: 5 + 3 on the SAM D20;
- MemoryPool: 7 + 1 on the SAM D20.

Their records are made from the run directories of both jobs
(`poolrecords.py DIR...`).

**Time, from the boards' CRC runs:**
- G474 about 20 min; H723 about 20 min;
- G0B1 about 35 min; nRF5340 about 40 min;
- SAM D20 about 70 min;
- Pico 2 about 2.5 h, 41 s per run, as in its CRC series.

## Order

1. **Now, side by side:** G474, G0B1, SAM D20, H723. Each board's smoke
   first, then its series jobs in the order above, each only after the job
   before it passed.
2. **The Pico 2:** after its smoke (its write alone, in parts), then P1.
3. **The nRF5340:** after N9 of the v3 reruns and once its records' run
   directories are safe (copied, and the records made). No power cycle. The
   watched power-on comes after pools, when the reviewer decides.

## What each board holds afterwards

The last bundle written:
- G474 and G0B1: pools bundle 102;
- SAM D20: 204;
- H723 and nRF5340: 51;
- Pico 2: 12.

The ring-buffer and CRC bundles are gone from flash; they are rebuilt from
their series commits when needed (one write each).
