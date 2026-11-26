# Running the boards in parallel: a queue per board (plan, 2026-11-25)

Plan only: no tool is written and nothing is tried on a board until the
owner has decided (section 6). File references are to `main` at f3ee191
unless a branch is named.

## Summary
The benchmark runs of version 2 and of the CRC kind go one board at a time
today. The tools mostly don't require that: every runner already takes the
board's lock and picks the board's own probe by serial number. The ISR
stress campaigns (`lab/tools/night-all.sh`), the checks
(`lab/tools/check.sh:84-85`) and the version 1 publication re-run
(`lab/tools/publication-rerun.sh:1-20`, benchmarks from flash included)
already ran all six boards at once. What is serial is a working rule ("one
board at a time"), the shared build tree, and a few places where one board's
event can reach another (the shared hubs). The proposal: one queue and one
worker per board, builds made before a job, the existing runners wrapped
unchanged, and a zero-write proof before the first real use. For this
series the counted time would drop from about 8 h serial to about 3 h 10 min
(the Pico 2 alone).

## 1. What is serial today, and why

| Item | Where | In parallel today? |
|---|---|---|
| Board lock | `kinds/crc/bench/run-crc.py:162-169`, `firmware/nrf5340-rb-bench/run-one.py:145-148` (`~/vl-dev/<board>.lock`, `flock` LOCK_NB); `lab/tools/check.sh:57-58`; `publication-rerun.sh:124` | Safe: one lock per board, so two jobs on one board are refused and different boards don't meet. The lock is taken non-blocking, so a second job fails at once; a queue must hold it and pass `VL_BOARD_LOCKED=1` (`run-one.py:39`). |
| Probe selection | `run-one.py:98-104` (`lab_board`: vid:pid:serial from `lab/boards.conf`), `run-crc.py:160-170` | Safe for the five probe-rs boards: each command names its probe by serial. |
| SAM D20 through OpenOCD | `firmware/common/samd20/bin/probe-rs:10-18` | Selected by VID:PID `03eb:2111` only (`adapter serial` crashes OpenOCD 0.12.0 with this EDBG, line 11), so a second SAM D20 (donations, `DECISIONS.md` 2026-11-17) would be ambiguous. OpenOCD also opens its default gdb/telnet/tcl ports (3333/4444/6666) on every call. With one SAM D20 and one call at a time per board (the lock), nothing collides today. Two SAM D20s would need a per-board port set (`gdb_port disabled` etc.) and a way to pick the EDBG other than `adapter serial`. |
| Port power (`boardpower.sh`) | `lab/tools/boardpower.sh:25` (SAFE_PORTS), `switch()` with `uhubctl -l <hub> -p <port>` | No lock of its own: two calls on the same hub run `uhubctl` on that hub at once. Each switches only its own port, but whether a neighbour port's board sees a dip when a port is switched has never been measured (section 2). Today the CRC and version 2 runners never call it (no `boardpower` in `run-crc.py`); the checks and campaigns do, on errors. |
| Hub layout | `lab/boards.conf` | Hub 4B0708619185: nRF5340 (1), G0B1 (2), G474 (3), port 4 = the cascade to hub 9E0C0069B5FA: SAM D20 (1), H723 (2), Pico 2 (3). The Pico 2's Debug Probe is on the data-only hub EE0C0869B5FA. All six share the upstream hub. |
| Pico 2 flash writes | `run-crc.py:285-345` (`PART_UNITS = 250`, `PART_SPACING = 70`) | The board's own USB port goes unanswered while the probe writes, and about 65 s into a write the host's hub power-cycles that port. Parts of 25-30 s avoid it. Other boards' writes at the same time load the same USB tree; whether a part then takes longer has not been measured. |
| Builds | `kinds/crc/bench/onebuild.sh:30-34` (writes `build/v2/<board>`, and every call runs `make build/gen/ok` in the shared `kinds/crc/build/gen`); `kinds/crc/bench/onecrc.py:361-362` (`build/one/<board>` work dir) | Per-board outputs are separate, but `build/gen` is shared and `make` in two containers at once could race on it. Version 2's `run.sh` builds in one shared `build/` (`night-all.sh:2-4` copies the tree per board for that reason). Rule for the plan: builds before jobs, not during. |
| Container mounts | `onebuild.sh:31` and `crcverify.sh` (`-v ...:Z`) | `:Z` relabels for SELinux; this host has no SELinux (`/sys/fs/selinux` absent), so concurrent containers on one tree are not blocked by it. Safe here; it would not be on an SELinux host. |
| Output directories | `run-crc.py` OUTDIR per call (`run.log`, run files) | Safe if each job has its own OUTDIR (one per board and job). |
| The worktree a run reads | `--from` default `../build/v2/<board>`; runs read only bundles, never write the tree | Safe if the worktree is detached at the job's commit and nothing builds in it while jobs run. |
| Records and checks | `crcrecords.py`, `crcverify.sh` (`TMPDIR`), `oneverify.sh` | Host-only; in parallel they compete for CPUs only (the lab rule: at most half the CPUs, nice 10, while boards run; this host has 12). |
| Our working rule | the reviewer's OK "one board at a time" for the CRC series and version 2 | A rule, not a tool limit; it is what the plan replaces. |

## 2. What could change a number

The measurement is cycles counted on the board (DWT `CYCCNT` or SysTick)
while the probe is off it (`run-crc.py:26-27`: "an attach stops the cycle
counter"). Each board's core runs from its own oscillator (HSI, HSE,
crystal) at a clock set by our firmware.

Argued (no effect on a counted cycle):
- **Host load and USB traffic:** they don't reach the board's core clock,
  its flash wait states or its caches. They only change how long the host
  takes to attach, poll and read, which changes waits and retries, not the
  counted cycles.
- **Probe polling of another board:** a probe only touches its own board.
  The board under test is off the probe while it measures.

Must be measured, because it could make a run fail or, at worst, change a
board's state:
- **A neighbour's port power cycle on a shared hub** (`boardpower.sh`
  switching hub 9E0C0069B5FA port 3 while the H723 on port 2 measures). A
  VBUS dip could brown out or reset the neighbour. That would show as a run
  without a file, not as a different number, but it is to be seen, not
  assumed.
- **The Pico 2's ~65 s limit:** its parts take 25-30 s alone. With other
  boards writing at the same time the USB tree is busier; if a part takes
  more than about 60 s the board loses power mid-write (`run-crc.py:285-289`).
  Measure part times with another board writing; until then, no other
  board writes while the Pico 2 writes (section 3).
- **USB load during a flash write** on another board: the write is verified
  (`--preverify`, then `verify`), so a bad write is caught. Whether writes
  slow down enough to hit a probe timeout (`limit=900`/`600`) is to be seen.
- **Retries and "not finished" runs:** these depend on host timing and are
  expected to rise a little. They are logged and repeated with a longer
  wait, so they don't change a kept number. Count them in the proof.

## 3. The design, smallest that works

- **One queue per board:** `~/vl-queue/<board>/` with `todo/`, `running/`,
  `done/`, `failed/`. A job is one file (JSON): the commit, the worktree
  path (detached at that commit, built before), the command (a `run-crc.py`
  or version 2 `run-one.py`/`run.sh` call, exactly as today), a hard timeout
  in seconds, and a flash write budget.
- **One worker per board:** a small script started with `nohup setsid`,
  writing its PID file, taking `~/vl-dev/<board>.lock` for as long as it
  runs, and starting each job with `VL_BOARD_LOCKED=1` and `timeout`. Jobs
  run in order. At the first failure (non-zero exit, more writes than the
  budget, a run without a file, a disagreeing call, a DIFFERS from
  crcverify) the worker moves the job to `failed/`, stops its own board's
  queue and leaves the other workers running.
- **Builds:** made before a job is queued, per commit, in that commit's
  detached worktree; never in a worktree a job is reading; never shared and
  changed. The job records the build's `bench_commit` and the bundle
  checksums, and the worker checks them at start (refuse if the tree is
  dirty or the build is of another commit).
- **Flash writes counted in one place:** `~/vl-queue/writes.tsv`, one line
  per write (UTC, board, bundle, units, job), appended by the worker from
  the runner's "FLASH WRITE" lines. Per-board and total counts come from
  that file; the budget check reads it.
- **Pico 2 writes:** the worker takes a second lock,
  `~/vl-dev/usb-write.lock`, around a Pico 2 write. Other workers take it
  only for their own writes, so no other board writes while the Pico 2 does
  (lifted only if the proof shows part times stay under ~45 s with
  concurrent writes).
- **Power switching:** a worker never calls `boardpower.sh` while another
  board on the same hub is running a job. A port switch takes a per-hub
  lock `~/vl-dev/hub-<serial>.lock` that running jobs on that hub hold
  shared (`flock -s`).
- **Status:** `queue.sh status` prints per board: worker PID and state,
  the job running (since, timeout), jobs waiting, failed, and the board's
  writes from `writes.tsv`.
- **Unchanged:** the frozen files (version 2: `firmware/`,
  `lab/boards.conf`, `lab/tools/source-commit.sh`, `boardpower.sh`,
  `verify-build.sh`, `repeat.sh`; the CRC kind at `crc-method-freeze`) and
  the CRC test sources. The queue wraps `run-crc.py` and version 2's
  runner as they are.
- **What cannot be wrapped as is:**
  - a second SAM D20 (OpenOCD picks the EDBG by VID:PID only, and its
    default ports), which needs a change in the frozen
    `firmware/common/samd20/bin/probe-rs`;
  - version 2's `run.sh`, which builds in a shared `build/`. A per-board
    tree copy works around it, as `night-all.sh` does.
- **Where the OK is given:** enqueuing a job is the OK for that board's
  run. Only the person or session that holds the OK enqueues; a job file
  names who gave it.

## 4. The proof before it is used (zero flash writes)

On the bundles already on the boards (`run-crc.py` without `--flash`,
which refuses to write: `run-crc.py:198-199`):

1. **Alone:** one quick-level repeat per board (a few configurations, 2
   passes), one board at a time, as reference.
2. **Together:** the same jobs on three or more boards at once. This
   includes the pair H723 and SAM D20 on hub 9E0C0069B5FA, and the pair G474
   and G0B1 on 4B0708619185.
3. **A neighbour's power cycle:** during (2), `boardpower.sh cycle` of a
   board that is not measuring (the nRF5340 or the Pico 2, whose port is
   switched) on the same hub as a running board.
4. **Compare (2) with (1):** means equal within 1 % / 0.05 cycles, per
   scenario, with the largest difference named. Image checksums must be the
   same. Count runs without a file and retries.
5. **Pico 2 part times:** only if a Pico 2 bundle has to be written anyway,
   time a part with another board writing. Otherwise measure later, at the
   first write that is needed, before lifting the write lock in section 3.

Pass: (2) and (3) give the same means as (1) on every board, no run is
lost to the neighbour's power cycle, and retries rise only slightly.

**As run (2026-11-25/26):**
- The account is in
  [`reports/2026-11-26-parallel-runs-proof.md`](../../reports/2026-11-26-parallel-runs-proof.md):
  part 1 as above, then 3 flash writes, at most 2 a board as the owner
  allowed.
- The proof's job list counted 5 writes, taking the Pico 2's bundle 7 to
  have replaced bundle 6. On the Pico 2 the two coexist
  (`lab/drafts/2026-11-26-pico2-bundles-coexist.md`), so its two writes
  were not needed and were not made, and the Pico 2's write times were not
  measured.

## 5. What it saves

This series, counted (`lab/plans/2026-11-25-crc-hw-and-ram-series.md` on
the branch `crc-hw-ram`, "Counted (step 3)"):

| Board | Time |
|---|---:|
| NUCLEO-G474RE | 30 min |
| NUCLEO-G0B1RE | 56 min |
| nRF5340 DK | 66 min |
| NUCLEO-H723ZG | 58 min |
| SAM D20 Xplained Pro | 88 min |
| Pico 2 | 3 h 7 min |
| **Serial** | **8 h 5 min** |
| **Parallel** (the longest) | **3 h 7 min** |

What does not get faster:
- **Builds:** about 20-25 s per board for a table build when the libraries
  are cached, made before the jobs.
- **crcrecords and crcverify:** host CPU, about 20 s per record. In
  parallel they share at most half of the 12 CPUs while boards run.
- **The Pico 2:** it alone sets the length, at about 41 s a run (its wait
  settles at 40 s: `wait 40 s` in its run.log; `run-crc.py:237`), plus its flash parts.
- **Writes:** more boards writing at once still means one write per bundle
  each, and the Pico 2 writes alone (section 3).

## 6. For the owner (one line each)

1. Allow benchmark runs (version 2, CRC kind) on several boards at once,
   after the proof in section 4 passes? (Today: one board at a time, as a
   working rule.)
2. The queue as designed (a queue and a worker per board, a write ledger,
   enqueuing = the OK): yes or changes?
3. Keep Pico 2 writes alone (no other board writes at the same time) until
   part times are measured: yes?
4. A second SAM D20 (donations) needs a change in a frozen file
   (`firmware/common/samd20/bin/probe-rs`: port set, probe selection): for
   the next method version?
5. **Method texts:** the published pages say nothing about runs being one
   board at a time. A search of `site/content/*.md`, `*.html`,
   `records/README.md` and `RESULTS.md` finds no such sentence.
   - The only nearby mention is `site/content/index.md:85-87`: "A second
     board of a kind we already have is welcome too where it lets campaigns
     run in parallel".
   - `compare.html:50` says "The calls are timed one at a time", which is
     about calls, not boards.
   - So parallel runs need no change in the published method texts. Say in
     the next method version's notes that runs may overlap across boards,
     with the proof?
