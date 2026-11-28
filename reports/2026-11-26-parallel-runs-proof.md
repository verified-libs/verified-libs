# Board runs in parallel: the proof (2026-11-25/26)

The proof of section 4 of the plan for parallel board runs (not published),
decided on 2026-11-25 ([change log](../site/content/method.md#log-2026-11-25-parallel)). The question was whether the boards give the same numbers when
they run at the same time, through the queue
(our lab's job queue, `lab/tools/boardqueue.py`, not published, commit 62ce14e).

**Setup:**
- Every job ran `kinds/crc/bench/run-crc.py` from a clean worktree at
  commit 40f1958, with one pass and two configurations of the bundle on
  the board.
- The comparison was per board, image and scenario, the means of the
  configuration and of the baseline. "Within" means within 1 % or 0.05
  cycles.
- The run files and logs are kept on the lab host under
  `~/vl-wt-crc-runs/proof-parallel/` and the queue's jobs, logs and write
  ledger under `~/vl-queue/`; they make no record.

## Part 1, no flash writes (2026-11-25 23:17 to 2026-11-26 00:02 UTC)

The runner refuses to write without `--flash`, and every job's budget was
0. The bundles on the boards were checked by the runner before each job:
NUCLEO-G474RE 57, NUCLEO-G0B1RE 54, SAM D20 115, NUCLEO-H723ZG 27, Pico 2 7,
nRF5340 DK 28.

| Phase | What ran | Time | Means within those of A | Run files / without a file | Retries |
|---|---|---|---|---|---|
| A | each board alone, one worker at a time | 23:17:06–23:43:58 (26 min 52 s) | – | 94 / 0 | G474 0, G0B1 1, SAM D20 2, H723 0, Pico 2 3, nRF5340 1 |
| B | all six at once, six workers | 23:43:58–23:55:48 (11 min 50 s) | 4512 of 4512 | 94 / 0 | the same as A, board by board |
| B2 | the H723 and the SAM D20 at once, the Pico 2 (same hub, not measuring) power-cycled twice; then the G474, the G0B1 (same hub, not measuring) power-cycled twice | 23:55:48–00:02:41 | 2208 of 2208 | 46 / 0 | the same as A |

- **B:** the largest difference from A was 0.004 cycles, one nRF5340 mean
  (17424.0 against 17424.004). Every other mean was identical.
- **B2:**
  - All 2208 means were identical to A's.
  - The four power cycles came at 23:56:18 and 23:57:10 (the Pico 2) and
    at 00:01:38 and 00:02:30 (the G0B1). Each fell inside the jobs
    running on the same hub.
  - They were done with `lab/tools/boardpower.sh` directly: the queue's
    `power` refuses a hub with a running job, which is the rule this step
    measured.
- **Images:** every image checksum is that of the second series' records
  of the same image.
- **Every phase:** no call disagreed with the reference, and no board was
  lost or reset.

## Part 2, flash writes (2026-11-26 00:03 to 00:20 UTC)

Three writes, each answering a question. The ledger
(`~/vl-queue/writes.tsv`) holds exactly these three:

| Question | What ran | Writes | Write time with the other board | The same write alone (second series) | Means |
|---|---|---|---|---|---|
| C1: two boards on one hub writing at once | the G474 wrote bundle 54 and the G0B1 bundle 55 at the same time (hub 4B0708619185), then each ran 16 runs | 2 | G474 54: 19.12 s; G0B1 55: 22.55 s | 18.10 s; 22.50 s | 1536 of 1536 identical to the records of the same images |
| C3: a run while a neighbour writes | the H723 wrote bundle 28 while the SAM D20 ran its part-1 job (hub 9E0C0069B5FA), then the H723 ran 16 runs | 1 | H723 28: 25.22 s | 25.24 s | SAM D20: 672 of 672 identical to A; H723: 768 of 768 identical to the records |

- **Through the queue:** both went through the queue. A writing job on a
  board other than the Pico 2 shares the write lock, and a job without
  writes takes none, so the queue allows both overlaps as it will be used.
- **Retries:** the SAM D20 had 2, as in A.
- **What the boards hold afterwards:** NUCLEO-G474RE 54, NUCLEO-G0B1RE 55,
  NUCLEO-H723ZG 28, Pico 2 6 and 7, SAM D20 115, nRF5340 DK 28.

**C2, the Pico 2's write times alone, was not measured.**
- *What happened:* the job was to write bundle 6. The runner found it
  already on the board, so nothing was written. The job's 8 runs (384
  means, identical to the records) passed, and the job failed on its
  expected write, as it should.
- *Why there was nothing to write:* bundles 6 and 7 do not exclude each
  other on the Pico 2. Bundle 6 spans 0x10000000–0x103ff000 in 226
  segments and leaves the range of bundle 7's images empty; both start
  with the same boot stub. So both have been on the board since the second
  series, and the count of the job list, which took bundle 7 to have
  replaced bundle 6 as on the STM32 boards, was wrong.
- *No write for timing only:* there is no other Pico 2 bundle at this
  commit, and a write only to time it was not made. The part of C3 with
  the Pico 2 writing was dropped with it.

## What the numbers support (a reading; the rules are the owner's decision)

- **Runs on several boards at once:**
  - Every number of every board was the same as when the board ran alone,
    to the third decimal but one mean off by 0.004 cycles.
  - The retries were the same.
  - This supports parallel runs.
- **Writes in parallel on one hub:**
  - Two STM32 boards wrote at once, and a board ran beside a writing
    neighbour.
  - Every write verified, each write took within 1.1 s of its time alone,
    and the runs that followed gave the records' numbers.
  - This supports writes in parallel for the STM32 boards, the SAM D20
    and, by the same probe-rs path, the nRF5340, though no nRF5340 write
    was made.
- **The Pico 2 writing alone:** not tested. Its rule rests on the hub
  cutting its port about 65 s into a write. Nothing here shows whether
  another board's write lengthens a Pico 2 part. The rule stays until a
  Pico 2 write is timed beside a neighbour's.
- **Power switching beside a running board:** four cycles of a neighbour's
  port on the same hub changed no number and lost no run. That supports
  switching a board that is not running beside one that is. The queue's
  rule, a free hub, is stricter than these four cycles need, but four
  cycles are few.

## What was not measured

- A Pico 2 write, alone or beside a neighbour's (above).
- More than four power cycles, and a power cycle during another board's
  flash write.
- A write on the nRF5340 DK beside others. Its port is never switched:
  after a power-on our boot stub leaves its debug port locked.
- Version 2's runner (`firmware/nrf5340-rb-bench/run-one.py`) through the
  queue. Only the CRC kind's runner ran, though both print the same "FLASH
  WRITE" line the queue counts.
- Runs longer than about 12 minutes at once. The longest job was the Pico
  2's.

## Addition: version 2's runner through the queue (2026-11-26, 10:20 to 10:28 UTC)

The trial the decision of 2026-11-26 asks for before ring-buffer runs go on
several boards at once
([change log](../site/content/method.md#log-2026-11-25-parallel)), with the reviewer's OK for each job.
- **Setup.** All jobs on the NUCLEO-G474RE, from a clean worktree at
  `a3174e7` (main), with `firmware/nrf5340-rb-bench/run-one.py` on bundle 0
  (built there with `onebuild.sh table`). Two configurations, lwrb and
  jnk0le, one pass, 16 runs each job.
- **Why a write first.** No board held a ring-buffer bundle: since the CRC
  series every board holds CRC bundles, and a board holds one bundle at a
  time. So the trial began with one write.

| Job | What ran | Flash writes | Time (UTC) | Means against the records (pass 1, same images) | Against each other |
|---|---|---|---|---|---|
| 1 | bundle 0 written (it replaces CRC bundle 54), then 16 runs | 1 (bundle 0, 127 units, 10:20:37) | 10:20:18–10:21:35 | 704 of 704 identical | – |
| 2 | the same 16 runs, no write | 0 | 10:21:35–10:22:34 | 704 of 704 identical | job 1: 704 of 704 identical |
| 3 | job 2 again, while the NUCLEO-G0B1RE and the SAM D20 ran zero-write CRC jobs through their own workers | 0 | 10:22:34–10:23:34 | 704 of 704 identical | jobs 1 and 2: 704 of 704 identical |

- **Identical.** The largest difference in every comparison was 0.
  "Within" (1 % or 0.05 cycles) is met trivially.
- **The runner through the queue.** The queue counted the runner's FLASH
  WRITE line (one line in `writes.tsv`), held job 1 to its budget of 1 and
  jobs 2 and 3 to 0 (`--refuse "FLASH WRITE"`). Every job printed its
  expected "done: 16 runs, 0 without a file, N flash writes".
- **The CRC jobs beside job 3**, from the worktree at `40f1958`:
  - *SAM D20*: the parallel proof's part-A command (bundle 115). 14 runs;
    672 of 672 means identical to part A; 2 retries, as in part A.
  - *NUCLEO-G0B1RE*: it holds bundle 55 since part C1, so the command was
    C1's without `--flash`. 16 runs; 768 of 768 means identical to C1.
- **Not run:** the nRF5340 DK, and no power switching.

**What the boards hold now:** NUCLEO-G474RE ring-buffer bundle 0 (no longer
CRC bundle 54); the others as after the proof (NUCLEO-G0B1RE 55,
NUCLEO-H723ZG 28, Pico 2 6 and 7, SAM D20 115, nRF5340 DK 28). Flash
writes in the queue's ledger: 4.

**What this supports (a reading):** version 2's runner runs through the
queue as the CRC runner does, with the same numbers alone and beside two
other boards. The run files, logs and the comparison scripts are on the lab
host (`~/vl-wt-crc-runs/v2-queue-trial/`, `~/vl-v2trial/`).

*2026-11-28: links to documents that are no longer published were removed or now point to the change log.*
