# Pools: the concurrency series (interrupts)

2026-11-27. A plan for the series that the first pools series left open
([pools plan](2026-11-26-pools-kind.md), section 4; the
[method page](../../site/content/method-pools.md), "Measured in one
context"). The owner said this series may start without his reading the
plan first. **Host side only so far:** nothing here has run on a board; the
board part needs the reviewer's OK and goes to the session that runs the
boards. Built on branch `pools-isr`.

## 1. The question, per configuration

An interrupt calls `alloc` or `free` on the same pool at any instruction of
the main context's `alloc` or `free`. After that:
- **is a block ever handed out twice** (main and the interrupt, or one of
  them twice, hold the same block);
- **is a block lost** (after everything is given back, fewer than 32
  blocks can be allocated);
- **is the pool's state corrupted** (an allocation fails although fewer than
  32 blocks are held, a block outside the pool or misaligned is handed out,
  the canaries around the pool's memory change, or a later sequence of
  calls goes wrong);
- **is an answer impossible**: `alloc` gives no block although at every
  moment of the call a block was free, in every order of the calls
  (linearisability, below);
- and **for the configurations that turn interrupts off: for how long**
  (the longest time an interrupt waits because the pool has them off, in
  cycles).

## 2. Each library as it documents itself

A claim is tested only as the library documents it
([`kinds/pools/claims.tsv`](../../kinds/pools/claims.tsv)). The verdict per
configuration is one of three:
- **pass / fail, within its documentation**: the library documents use
  from interrupts, and the test calls it the way the documentation allows;
- **outside its documentation**: the library documents no use from
  interrupts (or documents it only with a lock option it is not built
  with). It is run all the same, because users do it, and reported with
  what happened, as *outside its documentation*, never as failing;
- **our rows**: the reference without a lock (the control, which must be
  caught) and the reference with interrupts off (which must pass).

| Configuration | Documented (claims.tsv) | Called in the interrupt as | Verdict class |
|---|---|---|---|
| reference free list (ours) | no lock: the baseline | alloc, free | control: must be caught |
| reference, interrupts off (ours) | PRIMASK around each call | alloc, free | ours: must pass |
| ThreadX | allocate and release from ISRs; allocate only with `TX_NO_WAIT` | `tx_block_allocate(…, TX_NO_WAIT)`, `tx_block_release` (the adapter's calls already use `TX_NO_WAIT`) | within |
| CMSIS-RTX | alloc from an ISR with timeout 0; free from an ISR | `osRtxMemoryPoolAlloc`, `osRtxMemoryPoolFree`: the functions `isrRtxMemoryPoolAlloc`/`Free` call after their object check (the prechecks report, check 1) | within |
| lwIP `memp` | protected by `SYS_ARCH_PROTECT`, as the port does it | `memp_malloc_pool`, `memp_free_pool` with our port (interrupts off) | within (the port is ours; the report says so) |
| heapless pool | lock-free, on cores with LDREX/STREX | alloc, free (not on the Cortex-M0+ boards) | within |
| atomic-pool | atomics; on cores without CAS `unsafe-assume-single-core` or `critical-section` | alloc, free | within |
| C_Allocator | from an interrupt only with an interrupt-masking lock option; built here with `ALLOC_LOCK_NONE` | alloc, free | outside (as built) |
| MemoryPool | without threads "not thread safe" | alloc, free | outside |
| ETL, RIOT, Contiki-NG | nothing | alloc, free | outside |

C_Allocator with one of its interrupt-masking options (e.g. its CMSIS-RTOS2
lock) would be a configuration of its own, within its documentation; it
needs that RTOS's headers and is left for a decision (section 8).

## 3. Three tests

### 3.1 The contract check on the host (an interrupt at every instruction)

The single-step method of the ring buffers' contract check
([`verify/contract`](../../verify/contract/README.md)) and of the pool
prechecks ([report](../../reports/2026-11-24-pool-prechecks.md)): main's
call runs with the x86 trap flag, and at host instruction k the signal
handler makes the interrupt's calls, for every k until main's call ends
first; with interrupts off (the pool's `pool_irq_disable`, ThreadX's
`TX_DISABLE`, RTX's `__disable_irq`, lwIP's port) an interrupt point is held
pending and taken at the restore, as on a Cortex-M.

- **Calls.** Main: `alloc`, or `free` of a block it holds. The interrupt:
  `alloc`; `free` of a block it holds; `alloc` then `free` of that block;
  `free` then `alloc`; two `alloc`s (one interrupt, two calls in it).
- **Start states.** The pool after `init`, with 0, 1, 2, 16, 30, 31 and 32
  blocks held (the last free block, the first, and the edge where the list
  becomes empty); with the blocks held taken out in a scattered order
  (every third block first), so the free list is not in address order.
  Who holds which block (main or the interrupt) is fixed per start state.
- **Verdict per trial:**
  - every block handed out lies in the region at the promised alignment,
    and is held by no one at that moment (no block twice);
  - the canaries are intact;
  - interrupts are on again after each call;
  - the answers are those of the calls one after the other, with main's
    call before, between or after the interrupt's calls
    (linearisability, counting blocks: an `alloc` gives a block exactly when
    fewer than 32 are held at its place in that order);
  - afterwards every block is given back and exactly 32 `alloc`s succeed,
    each block once (nothing lost, nothing twice), and the pool's state
    passes a short sequence of the host test's checks.
- **What runs on the host:** the library's own C/C++ code compiled for
  x86-64, as in the first series' host test (`kinds/pools/Makefile`), with
  two exceptions where the board code is not what the host runs:
  - *CMSIS-RTX on Armv7-M/Armv8-M* uses LDREX/STREX (`atomic_link_get`,
    `atomic_link_put`, `atomic_inc32`, `atomic_dec32`, Arm inline assembly).
    The check runs RTX's own `osRtxMemoryPoolAlloc`/`Free` (cut out
    unchanged, as `kinds/pools/extract.py` does) with
    `EXCLUSIVE_ACCESS` 1 and those four functions transliterated into C, one
    statement per instruction, on the exclusive-monitor model of the
    prechecks (`verify/exclusive/excl_model.h`, copied for 64-bit words).
    That is the step the prechecks left open. Whether the transliteration
    matches the assembly is a reading (20 lines), not a check; the board
    sweep runs the real code. The model's own control (the monitor not
    cleared at exception entry) must make it fail.
  - *heapless and atomic-pool* run their host paths (heapless a tagged CAS,
    atomic-pool x86 atomics), not the LL/SC or interrupts-off code the
    boards run. The host verdict covers their algorithm on the host's
    atomics; the board sweep is the test of the board code.
  - *MemoryPool* on the host has a `std::mutex` (glibc has threads); an
    interrupt that takes it while main holds it would block forever, which
    is the host's artefact, not the board's (no mutex there). The check
    builds it as the boards do: `kinds/pools-isr/no_gthreads.h`, included
    first, removes `_GLIBCXX_HAS_GTHREADS` before its `Fixed.h` tests it.
  - *CMSIS-RTX's interrupts-off variant*: the first series' host header
    (`shims/host/ARMCM_host.h`) keeps PRIMASK in a variable beside the test's
    flag, so an interrupt could come between the two, inside what is one
    instruction (`cpsid`) on a Cortex-M. The check uses a copy with one
    flag (`kinds/pools-isr/ARMCM_isr.h`).
- **Controls**, each must be caught: the reference without a lock (a block
  twice or lost); two broken interrupts-off builds of the reference
  (written for this check, in `kinds/pools-isr/`): interrupts restored too
  early in `alloc` (before the block's link is read and the head written)
  and in `free` (before the head is written); and
  for CMSIS-RTX's transliteration, a variant whose `atomic_link_get`
  ignores STREX's result.

### 3.2 The interrupt sweep on the boards (the real machine code)

The ring buffers' sweep (`firmware/nrf5340-rb-stress/main.c`, `sweep=1`),
copied for pools into `kinds/pools-isr/main.c`: SysTick (core registers, the
same on every Cortex-M) as a one-shot, armed d cycles before main's call,
for d = 1, 2, 3, … until the interrupt has come after the call SWEEP_TAIL
times in a row; the handler makes the interrupt's calls (as in 3.1) and
records the interrupted PC in a coverage bitmap (one bit per halfword of
code), which the host maps to the instructions of the library's functions.
The same start states and calls as 3.1, from several start positions of
the free list, cache on and off. After each trial the image runs the
checks of the first series (`kinds/pools/bench/main.c`: no block twice,
region and alignment, each holder's pattern intact, canaries) and, after
each start state, gives every block back and allocates all 32 once.

**No random stress in this series** (decided while building, 2026-11-27,
for the reviewer to confirm). The ring buffers' random timer stress came
before their sweep and found what the sweep then found deterministically.
Here the sweep already puts one interrupt at every cycle of every call shape
and start state, cache off and on, and the host check at every instruction.
What a random stress would add is long histories and two interrupts in one
call. A pool keeps no state across calls beyond its list (every trial
checks the list whole afterwards), and two interrupts in one call are better
tried as the ring buffers' two-interrupt sweep does it (`sweep=2`), which is
listed in section 7. A timer stress would need each board's timer code,
which the sweep does not.

- **Coverage** (`covmap.py`): the bitmap mapped to the instructions of the
  configuration's own code (every `.text` input section of the image's link
  map that is neither the harness nor the C library). The record gives,
  per function, the instructions reached and the addresses of those not
  reached. Not every instruction of a library is on the path of `alloc` and
  `free` (its `init`, its error branches), so the report names the
  unreached ones on those paths rather than asking for all.
- **Controls on every board:** the reference without a lock must be caught
  by the sweep; the two broken interrupts-off builds too. A run in which a
  control is not caught gives no record.

### 3.3 The interrupts-off time

Measured in the sweep itself, so no second image: the SysTick handler reads
how long ago SysTick ran out. Main arms SysTick with reload d; once the
count has started it sets the reload register to 0xFFFFFF, so after it runs
out the counter starts again from 0xFFFFFF, and the handler's first read of
the current value gives the cycles since it ran out: 0xFFFFFF − value. That
works on every Cortex-M, the M0+ included (no DWT needed). The latency of a
trial is that figure. With interrupts on it is the exception entry and the
handler's first instructions, the same in every trial but for a few cycles
(the instruction being completed, the bus); where main has interrupts off
the interrupt waits until they are on again. **The longest interrupts-off
time** of a configuration is the largest latency over its trials minus the
smallest latency of the same image's reference without a lock (which never
masks); the record keeps both, and the d at which the largest came, so
that it can be mapped to the instruction that masked.

Its limits, to be said with the number:
- it is the time an interrupt waited, as long as the sweep's steps hit the
  first masked cycle (steps of one cycle: they do);
- the cache state and the placement change it, so it is measured with the
  cache on and off and reported per board;
- it is the masked time of one call of this shape (32 blocks of 32 bytes,
  the calls above), not a bound for every use.

## 4. Records: `pools-isr/1`

New files only, in a directory of their own: `kinds/pools-isr/` (host check,
image, runner, record writer) and `records/pools-isr/<board>/<adapter>.json`.
The directory is outside `kinds/pools`, so the first series' source list
(`POOLS_TEST_SOURCES`, which counts every file under `kinds/pools`, a new one
too) does not see it: its records stand as they are.
No file of the first series changes; nothing frozen is edited (patterns
are copied). A record per board and configuration:
- `schema` `pools-isr/1`, the board fields and `bench_commit`,
  `toolchain_image`, `libs_pinned`, `option_registers` (method version 3),
  `clock_hz`;
- `documented`: the claims.tsv line, and `class` (`within`, `outside`,
  `control`, `ours`);
- `sweep`: per cache state, start state and calls: trials, trials with the
  interrupt inside the call, faults by kind (block twice, block lost,
  region, pattern, canary, impossible answer), the first fault in full;
  coverage (instructions of `alloc`/`free` reached, of all);
- `stress`: calls, interrupts, faults as above;
- `irq_off_cycles`: per cache state, the largest latency, the reference's
  smallest, their difference, and the d;
- `controls`: each control's verdict in the same image run (caught or
  not).
The public export needs a source list of its own for this series
(`POOLS_ISR_*` in `lab/tools/public-export.py`); that is a change to the
export, for its owner to make when the board part is decided.

## 5. The host side built on 2026-11-27 (branch `pools-isr`)

- `kinds/pools-isr/contract.c`, `Makefile`, `run.sh`: the contract check of
  3.1, run in the toolchain image as the kind's other host checks
  (`bash kinds/pools-isr/run.sh`: three programs, every configuration, then
  CMSIS-RTX's LDREX/STREX variant and its control); `ARMCM_isr.h` and
  `no_gthreads.h` (3.1, "What runs on the host");
- `kinds/pools-isr/excl_host.h`, `rtx_excl_prelude.h`: the exclusive-monitor
  model for 64-bit words and RTX's four atomic functions transliterated;
- `kinds/pools-isr/broken_isr.c`: the two broken interrupts-off builds of
  the reference (2026-11-27, after the first smokes: the `alloc` build's
  window widened; it wrote the head right after the unmask, which the
  NUCLEO-G474RE and the nRF5340 DK never interrupted, section 7; every other
  image of the six boards is byte for byte the same);
- the board side (2026-11-27, later the same night): one image per
  configuration (`main.c` with `POOL_ISR_ADAPTER`, the latency calibrated
  in each image with the reference without a lock), all of a board in one
  bundle behind the first series' boot stub (byte for byte its stub on all
  six boards), built by `onebuild.sh` / `build.py` from the first series'
  objects (`kinds/pools/bench/onepool.py`, imported, not changed): 13 or 14
  images of 4.1 to 5.7 KB per board;
- `run-isr.py`, the runner (the first series' probe calls, lock, selection,
  Pico 2 handling imported from `run-pools.py`); `decode.py`, the result
  block and the verdict by the classes of section 2 (for a library outside
  its documentation only what was observed); `isrrecords.py`, the record
  writer (`pools-isr/1`; option registers required; no record of a board
  whose controls were not all caught); `covmap.py`, the coverage;
- `test_decode.py` and `test_runner.py` (`make test-board-side`): the block's
  layout against the `results` symbol of every image, the verdicts, and the
  runner and the record writer against a stand-in for probe-rs, with three
  refusals (no options, a dirty tree, a control not caught);
- the job list and the smoke: `lab/plans/2026-11-27-pools-isr-jobs.md`,
  `enqueue.sh`, `smoke-check.sh`;
- the export rule for the series, a proposal in a commit of its own
  (`POOLS_ISR_*` in `lab/tools/public-export.py`, a KINDS entry).

**Artefacts of the host check found while building it** (none a library's;
each would have made a correct pool look wrong):
1. the harness could fire the interrupt twice in one trial: a trap between
   clearing "pending" and the call to the interrupt fired it again. It made
   CMSIS-RTX's LDREX/STREX variant look as if it lost a block. Fixed: the
   pending flag is cleared inside the interrupt, after it is marked running;
2. the first series' host header for CMSIS-RTX keeps PRIMASK beside the
   test's flag, so an interrupt could land between the two, inside what is
   one instruction on a Cortex-M (`ARMCM_isr.h`, one flag);
3. MemoryPool's `std::mutex` on the host, where an interrupt that takes it
   while main holds it waits forever; built as on the boards
   (`no_gthreads.h`);
4. the blocks the interrupt and main give back were chosen once per case,
   while heapless's `init` hands out the blocks in another order after each
   start: chosen after every start state now.

The results of the host check go into the report of the series, not into
this plan.

## 6. The board part: estimate

- **Images.** One image per board holding every configuration of that
  board and the controls (built: 9.3 to 9.7 KB), selected per run over the
  debug port, or one image per configuration in one bundle if the
  same-image rule (DECISIONS 2026-11-22) is taken to cover this series too.
  Either fits in one bundle per board.
- **Flash writes:** one per board, six in all (the SAM D20 possibly two if
  one image per configuration is chosen: its bundles of the first series
  held up to 16 images each).
- **Time per board**, from the image as built (`main.c`: 61 cases of start
  state and calls, 4 rotations each, d from 1 until 16 trials in a row
  after the call) and the trial's cost (a setup and a verdict of about 130
  pool calls around the one timed call):
  - a call of 20 to 300 cycles with the cache on gives about 40 to 320
    trials per case; with a trial of about 10 000 to 20 000 cycles that is
    1 to 10 s per configuration and cache state at 48 to 170 MHz (520 MHz
    on the NUCLEO-H723ZG);
  - so on five boards about 5 to 15 minutes for 14 configurations, both
    cache states, with a reset and a read of the result block (4.4 KB) per
    configuration;
  - the Pico 2 with the cache off is the exception: its calls take 500 to
    1600 cycles from the QSPI flash (first series), so up to about 1600
    delays per case and a trial of about 1 ms: about 6 minutes per
    configuration, **about 1.5 hours** for the board; fewer rotations
    there would shorten it (to be decided with the smoke);
  - under the queue as the first series. These are estimates from the
    first series' cycle counts, to be replaced by the smoke's.- **Zero-write smoke** first, as always: the image's first configuration,
  shrunk.

## 7. What this series cannot show

- More than one core (the Pico 2's second core, the nRF5340's network
  core): another series.
- A thread that waits for a block (an RTOS kernel's blocking alloc): the
  pools run without their kernels.
- Interrupts of several priorities (nested): one interrupt at a time; the
  ring buffers' two-interrupt sweep could carry over later.
- The compiler's code for another target or another optimisation level:
  the boards run `-O2` as the first series.
- On the Cortex-M4 (NUCLEO-G474RE) and the Cortex-M33 (nRF5340 DK), the one
  instruction right after a call turns interrupts on again. An interrupt
  pending at that point was taken only after the next instruction; in the
  first smokes (2026-11-27) no interrupt was ever taken at the instruction
  right after an `msr primask` there, while the Cortex-M0+ boards and the
  M7 were interrupted at it. The architecture allows both: Armv7-M B5.2.3
  (MSR) guarantees a lower execution priority only after an ISB, exception
  entry or exception return, and Armv8-M B3.18 (RKLWH) requires a pending
  exception to be taken "within finite time". So a library whose only
  unprotected instruction is the one right after its unmask shows nothing
  on those boards. The host check covers it: it takes a pending interrupt
  at the unmask itself (3.1).

## 7a. For the next method version (a note, not now)

A fault handler of the series' own in the image (2026-11-27). It would
record the fault, put the pool back to its start state, and let the sweep
go on, so that a library used outside its documentation gets its whole
sweep and not only its first corruption. Now the board layer's handler
(`b .`, firmware/common, frozen) stops the image. The runner reads where it
stopped without a write (run-isr.py `--stall`), and the cache-on half is not
run after a stop with the cache off. Adding the handler changes every image,
so it needs a new series commit and a write per board. Also: the image
could take the cache state to start with from the selection words, so that
the cache-on half can run alone after a stop.

Also: SWEEP_DMAX (4,096 cycles after arming) as a function of the board
and cache state, or of the configuration's longest call. On the Raspberry
Pi Pico 2 with the cache off, about 1,200 cycles come before main's call
(the R1 rate probe, 2026-11-27: about 1,800 trials per case for the
reference), so a call longer than about 2,900 cycles is reached only in its
first part (Contiki-NG, perhaps C_Allocator). That is a change to main.c,
so it needs a new series commit and a write per board.

## 8. Decisions for the owner (in the morning list)

1. The board part: run it (six flash writes, about an hour per board), and
   one image per board or one per configuration.
2. Whether C_Allocator is also measured with an interrupt-masking lock
   option of its own (a configuration within its documentation).
3. How the pages show it: a column "use from interrupts, tested" beside
   "documented", with the three classes of section 2, and the
   interrupts-off time per board.
