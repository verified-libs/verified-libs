# The pools concurrency series: the job list (2026-11-27)

Proposed by the builder for the reviewer's OK per job, as the first pools
series' list (`lab/plans/2026-11-26-pools-series-jobs.md`); the plan is
`lab/plans/2026-11-27-pools-concurrency.md`. Under method version 3. Nothing
here has run on a board. **Six flash writes in all, one per board.**

## The series commit and the tree

- **Series commit:** the head of branch `pools-isr` that the reviewer
  accepts (its `kinds/pools-isr` and the pools kind's sources do not change
  after the first write). Files that are no test source of the series may
  still land: this list, `kinds/pools-isr/enqueue.sh`,
  `kinds/pools-isr/smoke-check.sh` (POOLS_ISR_NOT_SOURCES in the export
  proposal).
- **Worktree:** `~/vl-wt-pools-isr-series`, detached at the series commit,
  clean. All six boards built there: `bash kinds/pools-isr/onebuild.sh`
  (libraries from `~/vl-next/kind-pools` at the pins of
  `kinds/pools/libs.lock`). `build.json` must name the commit without
  "+dirty".
- **No-board checks at that commit, before the first job:**
  `bash kinds/pools-isr/run.sh check` (the host check: every judged verdict
  as expected) and `bash kinds/pools-isr/run.sh test-board-side` (the result
  block's layout against every image, the runner and the record writer
  against a stand-in for probe-rs).
- **Record schema:** `pools-isr/1`, records under `records/pools-isr/<board>/`.

## What the bundle is

One bundle per board, number 300: the first series' boot stub (byte for byte
the stub of the first pools series' bundles on all six boards, checked
2026-11-27 by `boot_image_sha256`) and one image per configuration in slots
of 16 KB from the start of flash + 4 KB: 13 images on the two Cortex-M0+
boards, 14 on the others; 27 to 29 units of 4 KB written.

**What the write costs besides the write:** the bundle lies where the first
series' and the CRC kind's bundles lie, so it replaces them in the units it
writes (on the NUCLEO-H723ZG the 128 KB sectors around them). The next
first-series or CRC job on that board writes its own bundle again (one more
write, then). Nothing of this series is needed after its records are made.

## Every job

Enqueued one at a time:

```sh
OK="…" C=<series commit, 40 hex> bash kinds/pools-isr/enqueue.sh JOB
```

1. **The board's option registers first:** `lab/tools/read-options.py`,
   zero write, into the job's run directory (`options.json`). Every record
   carries them; the record writer takes no run without them.
2. **Then the runner:** `kinds/pools-isr/run-isr.py BOARD DIR --wait W`,
   with `--flash` on the smoke (the bundle's one write), and on the smoke
   `--adapter` with our four rows.
3. **What the queue holds the job to** (`boardqueue.py`, as the first
   series):
   - budget `--writes` 1 (smoke) or 0 (series, with `--refuse "FLASH WRITE"`);
   - `--expect "done: RUNS runs, 0 without a file, W flash writes"`;
   - `--refuse "NOT CAUGHT"` (a control not caught) and `--refuse "STOPPED"`;
   - a timeout.
4. **A library within its documentation that fails** is not a failed job:
   the run says `FAIL … <-- NOT AS EXPECTED` in run.log, the job goes on,
   and the reviewer is told at once. It is a possible library defect: it
   goes into `lab/drafts` and to the reviewer only, never into a public file,
   until it is decided. A library outside its documentation is never a
   failure; run.log says what was observed.
5. **After a smoke:** `bash kinds/pools-isr/smoke-check.sh RUNDIR` (records
   made outside the repository: four, without a problem, each with option
   registers and some coverage). The series job on that board waits for it.
6. **Stop rules.** A board stops at the first job that is not as expected
   (a run without a file, a write over budget, a control not caught, a
   failed smoke check). The other boards go on.

## The smoke

Each smoke writes the board's bundle (its one write) and runs our four rows:
the reference without a lock, the two broken interrupts-off builds (the
three controls, each must be caught) and the reference with interrupts off
(must pass). That is every step of the series (the write, the selection,
the sweep with the cache off and on, the latency, the read of the block, the
run files, the records), shrunk to four of the 13 or 14 images.

The smoke's wait gives the first measured seconds per run. If a run of the
smoke needed a second attempt, the series job's `--wait` is set from the
smoke's finishing wait before it is enqueued.

## The jobs

Waits: 60 s on five boards (the estimate is 2 to 20 s per run); 480 s on
the Pico 2 (with the cache off its calls run from the QSPI flash: about 6
minutes per run, estimated). A run not finished is repeated with twice the
wait, up to 1800 s. Timeouts: 600 s plus, per run, twice the wait and 30 s;
the smoke adds the write.

*2026-11-27, later:* the doubling of the wait is replaced by a watch of
the trial counters (`run-isr.py --poll/--stall/--grace`, a host fix
recorded in `records/host-fixes.json` for f344730). At f344730 ETL's image
took a fault in the check after trial 4962 on the G474, so it never set
done and the ladder gave no file after about 30 minutes per board. Now a run
is judged when done is set, however long it takes while the counters move.
A run whose counters stand still is read without a write, started once more
and judged (decode.py `stop()`). `--wait` is only the time to the first look.
The job timeouts above still bound a job and must cover the Pico 2's cache-off
time once its rate is known.

| Job | Board (lab name) | Runs | Writes | Wait s | Timeout s |
|---|---|---|---|---|---|
| GS | NUCLEO-G474RE (`nucleo-g474re`) | 4 | 1 | 60 | 1500 |
| G1 | | 14 | 0 | 60 | 3000 |
| BS | NUCLEO-G0B1RE (`nucleo-g0b1re`) | 4 | 1 | 60 | 1500 |
| B1 | | 13 | 0 | 60 | 3000 |
| DS | SAM D20 Xplained Pro (`sam-d20-xpro`) | 4 | 1 | 60 | 1500 |
| D1 | | 13 | 0 | 60 | 3000 |
| HS | NUCLEO-H723ZG (`nucleo-h723zg`) | 4 | 1 | 60 | 1500 |
| H1 | | 14 | 0 | 60 | 3000 |
| NS | nRF5340 DK (`nrf5340dk`) | 4 | 1 | 60 | 1500 |
| N1 | | 14 | 0 | 60 | 3000 |
| PS | Pico 2 (`pico2`) | 4 | 1 | 480 | 5000 |
| P1 | | 14 | 0 | 480 | 15000 |

Writes: six, one per board. The Pico 2's bundle (29 units) is below the 250
units of a part, so it is written in one piece; its writing job holds the
write lock exclusively for its length, as in the first series.

## After the jobs

- `python3 -I kinds/pools-isr/isrrecords.py RUNDIR...` (in the toolchain
  image, for the coverage) makes the records; a board whose controls were not
  all caught gets none.
- The coverage per configuration (`covmap.py`) says which instructions of
  its code no interrupt reached; the report names them.
- The interrupts-off time per board and cache state is in each record
  (`result.c[].irq_wait_cycles`: the largest latency during main's call less
  the reference's smallest, in the same image).
- The export holds the records only with the export rule for this series in
  place (the proposal on branch `pools-isr`, for the owner of
  `lab/tools/public-export.py`).
