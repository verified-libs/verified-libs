# Method version 3: the reruns of the nRF5340 DK and the NUCLEO-H723ZG, job list

For the reviewer's OK, job by job (DECISIONS 2026-11-26). Nothing here has
been enqueued.

**The series commit is `4032f80`** (`4032f809fd8d…`, `kind-pools`). Every job
runs in the worktree `~/vl-wt-v3-series`, a clean checkout of it, so the
version 3 test sources cannot change after the first write.
- *Step b of the pools plan* runs meanwhile and touches only `kinds/pools/`,
  `lab/tools/` (`public-export.py` for the pools rule) and texts. None of
  these is a test source of version 2 or of the CRC kind; any exception is
  named before it is made.
- *Built at 4032f80* (`~/vl-v3-proof/build-reruns.log`, 11:03 UTC):
  - ring buffers, `firmware/nrf5340-rb-bench/build/v2/<board>`, bundles 0–4,
    the nRF5340's with the nRF5 SDK;
  - CRC, `kinds/crc/build/v2/<board>`, bundles 25–28: both series' 38
    configurations (35 on the nRF5340, which has no CRC unit) in four
    bundles, one fewer than the two series wrote.
- *Each job:* first `lab/tools/read-options.py` into its run directory
  (zero-write; the record makers take it into `rb-bench/3` and
  `crc-bench/2`), then the runner, both in one command.
  - Output: `~/vl-wt-crc-runs/v3/<board>/<job>/`.
  - Enqueue one job: `OK=... bash lab/tools/v3-reruns-enqueue.sh JOB`.
  - Every job must print "done: N runs, 0 without a file, W flash writes".
    A job with no write also has `--refuse "FLASH WRITE"`.

## Jobs

| Job | Board | Kind, bundle | Images | Runs | Writes | Timeout | Leaves on the board |
|---|---|---|---|---|---|---|---|
| N0 smoke | nRF5340 DK | CRC 25, `--only 2 --passes 1` | 2 | 2 | 1 | 900 s | CRC 25 (v3, new stub) |
| N1 | nRF5340 DK | CRC 25 | 72 | 144 | 0 | 3600 s | CRC 25 |
| N2 | nRF5340 DK | CRC 26 | 84 | 168 | 1 | 4200 s | CRC 26 |
| N3 | nRF5340 DK | CRC 27 | 53 | 106 | 1 | 2700 s | CRC 27 |
| N4 | nRF5340 DK | CRC 28 | 71 | 142 | 1 | 3600 s | CRC 28 |
| N5–N9 | nRF5340 DK | ring buffers 0, 1, 2, 3, 4 | 84, 84, 81, 75, 60 | 168, 168, 162, 150, 120 | 1 each | 1800 s (N9 1500) | ring-buffer bundle 4 |
| H0 smoke | NUCLEO-H723ZG | CRC 25, `--only 2 --passes 1` | 2 | 2 | 1 | 900 s | CRC 25 (v3, 520 MHz) |
| H1 | NUCLEO-H723ZG | CRC 25 | 72 | 144 | 0 | 3000 s | CRC 25 |
| H2–H4 | NUCLEO-H723ZG | CRC 26, 27, 28 | 84, 77, 71 | 168, 154, 142 | 1 each | 3300, 3300, 3000 s | CRC 28 |
| H5–H9 | NUCLEO-H723ZG | ring buffers 0–4 | 84, 84, 81, 75, 28 | 168, 168, 162, 150, 56 | 1 each | 2400 s (H9 1200) | ring-buffer bundle 4 |

- **Writes:** 9 per board, 18 in all.
- **Time, estimated** from the published series' time per run:
  - nRF5340: CRC ~2 h 30 + ring buffers ~1 h;
  - H723: CRC ~2 h + ring buffers ~1 h 25 at 64 MHz (less at 520).
- **The two boards side by side** through their own workers: about 3 h 40.
  They are on different hubs (nRF5340 4B07…, H723 9E0C…).
- **No power switching.** The nRF5340 is not power-cycled; that waits for
  the watched power-on after the records are made.

## Smoke plans

**N0, nRF5340 with the new stub.**
- The board holds CRC 28 of the second series with the old stub. Its port
  is open since the erase of 2026-11-25, and it has stayed powered.
- N0 writes CRC 25 with the new stub. The runner then starts its images
  as always: selection words, then a system reset (AIRCR), which keeps the
  port open with either stub.
- *Pass:* every run decoded, errors 0, `clock_hz` 64 000 000, and both
  UICR words in `options.json` 0x50FA50FA.
- *What N0 does not show:* that the stub opens the port after a power-on.
  That is the watched power-on, after the records (DECISIONS 2026-11-26).
- *On a locked port:* the job fails, and the board's queue is STOPPED.
  The recovery is the lab note's recipe (`lab/drafts/2026-11-25-nrf5340-approtect-recovery.md`),
  with the owner's word for an erase, as on 2026-11-25.

**H0, H723 at 520 MHz.**
- *Pass:* every run decoded, errors 0, and `clock_hz` 520 000 000 in the
  run files. That is the image's own figure (`board_clock_hz`, a
  constant), not a measurement.
- *The clock checked:*
  - `h7_clock_520` waits for VOS0, FLASH_ACR = 3 WS / WRHIGHFREQ 3 and the
    switch to PLL1 before it returns (`board.h`), so an image that ran ran
    at the clock it set.
  - The cycle counts of the 2 smoke runs, set against the version 2
    records of the same configurations, must be those of a faster clock
    with fewer flash wait states: about the same with the cache on, fewer
    with it off.
  - An independent check of the frequency needs a timer outside the core's
    clock. The optional H-1 below gives one (the host's wall clock against
    the image's own CYCCNT-based time).
- *The UART* is not used by the bench images (results are read from RAM
  through the probe); its 130 MHz divisor (`board_uart.h`) matters only
  for the stress images, which version 3 does not run.
- *Temperature and a stop limit.*
  - The bench images run at 520 MHz only while an image runs (one run is
    seconds); `board_idle` returns to 64 MHz between runs.
  - The full-load measurement of 2026-11-16/17 in the closed cabinet:
    52 °C after an hour at 520 MHz
    ([report](../../reports/2026-11-17-h723-thermal.md)); VOS0 allows 105 °C.
  - So the bench series stays below that plateau, and no watch runs
    during it: a second probe user would disturb the runner.
  - *Optional H-1, before H0:* `firmware/h7-thermal`, one write. 600 s of
    full load at 520 MHz with its stop limit (LIMIT_C 85 °C). Its
    samples give the die temperature and the image's CYCCNT time against
    the host's, which checks the clock as well.
    - Its `run.sh` prints no FLASH WRITE line, so the queue would not
      count its write. It would be run as a queue job whose command first
      prints that line for the queue (budget 1), or by hand under the
      board's lock with a line in the ledger.
    - Recommended: yes, as the clock and heat check, one write more
      (10 for the H723).
- *First calls:* the run files give each scenario's first call beside its
  mean (`first`). The smoke reports them for the 2 images. A first call
  above the scenario's maximum of the other calls is expected (the cache
  is cold); a first call that is a stall (0, `dwt_stalls`) is not, and
  stops the series.

## After the jobs

1. `onerecords.py` and `crcrecords.py` on each board's run directories. The
   records carry `option_registers`.
2. `oneverify.sh` / `crcverify.sh`: MATCH at 4032f80.
3. The baseline of every record against the present (now archived)
   records, per scenario (point 4 of the nRF5340 decision).
4. Then the watched power-on of the nRF5340 (DECISIONS 2026-11-26).
