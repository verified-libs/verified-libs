# Method: how fixed-block memory pools are measured and checked

The method of one of the three kinds of library so far ([all kinds](kinds.md));
the other kinds': [embedded ring buffers](method.md) and
[CRC calculation](method-crc.md).

The numbers are on the [results page](results-pools.md) and the
[comparison page](compare-pools.html). The details, the host checks' output
and the sizes from the cross builds are in
[`kinds/pools/README.md`](../../kinds/pools/README.md); the plan and its
decisions in [`lab/plans/2026-11-26-pools-kind.md`](../../lab/plans/2026-11-26-pools-kind.md)
and [`DECISIONS.md`](../../DECISIONS.md) (2026-11-26). This page says what
they add up to.

## What a pool is here

A library that hands out blocks of one size from storage fixed at start,
with `alloc` (a block, or none left) and `free`. Each configuration is one
pool of one block size behind one small interface
([`kinds/pools/pool.h`](../../kinds/pools/pool.h)): `init`, `alloc`, `free`,
the region the blocks lie in and the alignment the library promises (taken
from its code). One shape is measured: **32 blocks of 32 bytes**. A
library whose pool is not of one block size, or that cannot be built
without its kernel, is left out, with the reason in the kind's README
("Left out").

## Use from interrupts

**The numbers of these pages are of one context:** no interrupt calls a pool
while it is timed. Whether a pool stays correct when an interrupt calls it
is tested by a series of its own, the concurrency series
([plan](../../lab/plans/2026-11-27-pools-concurrency.md); records under
[`records/pools-isr`](../../records/README.md)). What it observed is in
each board's fold-out "Use from interrupts" on the
[results page](results-pools.md) and in a column of the
[comparison page](compare-pools.html); it is part of no score.

- **What it asks.** An interrupt calls `alloc` or `free` on the same pool
  while the main context is inside its own `alloc` or `free`. Is a block
  then handed out twice, or lost? Is the pool's state corrupted, or an
  answer given that no order of the calls gives? And, where a
  configuration takes interrupts off, how long does an interrupt wait?
- **How, on the boards.** SysTick is a one-shot interrupt, armed d cycles
  before main's call, for d = 1, 2, 3 … until the interrupt has come after
  the call 16 times in a row: so the interrupt comes at every cycle of the
  call. This is done for:
  - seven start states (0 to 32 blocks held);
  - main's alloc or free;
  - five patterns of the interrupt's calls;
  - four arrangements of the free list;
  - the cache off and on.

  Every trial is judged by the same code as the host check
  (`kinds/pools-isr/verdict.h`). The record also says which instructions
  of the configuration's code an interrupt came at.
- **On the host,** the same trials with an interrupt at every instruction
  (x86 single-step). CMSIS-RTX's LDREX/STREX variant, which the
  Cortex-M4, M7 and M33 boards run, is checked there on a model of the
  exclusive monitor.
- **Each library as it documents itself** (`kinds/pools/claims.tsv`), in
  three classes:
  - *within its documentation:* passed, or a finding;
  - *outside its documentation:* the library documents no use from
    interrupts, or only with a lock it is not built with. It is run all
    the same and only what was observed is reported; it is never called
    failing;
  - *ours:* our reference with interrupts off.
- **Controls.** On every board, three builds of ours must be caught:
  - our reference without a lock;
  - two builds with interrupts on again too early, in `alloc` and in `free`.

  A board whose controls were not all caught has no records.
- **The interrupts-off time.** It is read in the same sweep: when the
  interrupt runs, it reads how many cycles ago SysTick ran out. The
  largest such latency of a configuration, less the smallest of the
  reference without a lock in the same image, is the longest an interrupt
  waited because the configuration had interrupts off. It is for this
  pool shape and these calls, cache off and on; it is not a bound for
  every use.
- **What it cannot show:**
  - more than one core;
  - a thread waiting for a block (the pools run without their kernels);
  - two interrupts in one call, or nested interrupts;
  - another compiler or optimisation level.
  - on some cores, the one instruction right after a library turns
    interrupts on again. Whether the sweep reaches it depends on the core
    family, as the coverage of our controls showed:
    - Cortex-M0+ (NUCLEO-G0B1RE, SAM D20 Xplained Pro) and Cortex-M7
      (NUCLEO-H723ZG): yes, an interrupt landed on it;
    - Cortex-M4 (NUCLEO-G474RE) and Cortex-M33 (nRF5340 DK): no, an
      interrupt pending there was taken only after it.

    The architecture allows both (Armv7-M B5.2.3, Armv8-M B3.18). The host
    check, which takes the interrupt at the unmask itself, covers that
    instruction. Every record lists, per function of the configuration, the
    instructions that no interrupt landed on (`coverage`, `per_function`,
    `unreached`), so for each row a reader can see what the sweep did not
    reach.
  - on the Raspberry Pi Pico 2 with the cache off, the later part of a long
    call. The sweep moves the interrupt up to 4,096 cycles after it is armed,
    and there about 1,200 of those come before the call. So a call longer
    than about 2,900 cycles is interrupted only in its first part. Of the
    first series' calls, Contiki-NG's longest (a mean of up to 7,436 cycles)
    and perhaps C_Allocator's (up to 2,539) are that long. On every other
    board the longest call with the cache off is 1,132 cycles. The record's
    coverage per function (`unreached`) names the instructions no interrupt
    landed on.

  It is not a proof: a trial covers the states it tried.

What the timed series shows about locking: the **lock as built**, the
library's own code around a call in the build measured (interrupts off,
LDREX/STREX, an atomic bitmap, or none), and its cost in cycles, which is
part of every number. Our own row "reference free list, interrupts off"
gives the price of the simplest lock on each core.

## What is measured

One image per configuration and placement, under method version 3
(DECISIONS 2026-11-26: each board at the clock of the vendor's start-up
code or template, with the fewest flash wait states its manual allows at
that clock, and the board's option registers recorded with every record). In each image the board's `time_call()`
counts the cycles of every call, less the board's counter-read overhead.
After one timed `init`, six scenarios, with the cache off, then on:

| Scenario | What is timed |
|---|---|
| `pair` | 256 times alloc, then free of the same block, the pool almost empty |
| `pair_full` | the same with 31 of the 32 blocks held |
| `fill_drain_lifo` | 8 times: 32 allocs, then 32 frees in reverse order |
| `fill_drain_fifo` | 8 times: 32 allocs, then 32 frees in the order of the allocs |
| `mixed` | 512 calls from a fixed seed, the pool between 25 % and 75 % full |
| `empty` | 256 allocs on an exhausted pool (each must fail); no free |

A number on the pages is the mean of a scenario's calls (the first call
included) as the range over **eight placements** of the code (the same
configuration built eight times with its code moved by 0, 4 ... 28
bytes), first pass. Each image runs in two passes. Two rows differ only
where their ranges do not overlap: where the code lies can move a number
more than repetition does ([CRC method](method-crc.md), "What the
placements show").

**Bytes**, measured in the board images themselves: each image's link map
is compared with that of a null image (the same harness and reference with a
pool that does nothing), so the harness, the reference and the start-up code
count for no configuration ([README](../../kinds/pools/README.md), "Sizes").
Flash: the library's and the adapter's code and constant data at `-O2`.
RAM: what the pool needs beyond the 32 blocks of 32 bytes and the canaries
around them (1056 bytes, the same for every library): its control data and
any overhead per block.

## What is checked on every call

Every call is checked on the board, outside the timed window, as in the
host test:
- `alloc` gives a block exactly when fewer than 32 are held, and none when
  all 32 are;
- the block lies in the pool's region, at the promised alignment, and is
  not one already held;
- each holder writes a pattern of its own into its block and finds it
  intact at the free, which catches overlapping blocks;
- canary words before and after the pool's memory are intact after every
  call;
- all blocks come back at the end.

A fault stops the run's result from counting: a run with a fault gives no
run file, and a configuration without every run gives no record.

## The reference, and our row

**The reference free list** ([`adapter_ref.c`](../../kinds/pools/adapter_ref.c)):
a singly linked list threaded through the free blocks, no lock, one load
and one store per operation. It is ours, not a library, and has three
parts:
- *the baseline* of every image, timed in the same image as the
  configuration, and shown as the last row of every table;
- *the reference* of the host test: the same random sequence must give the
  same answers (a block or none, and the count held);
- *the control*: four broken builds of it (a block handed out twice, a
  block lost, a write outside the pool, a misaligned block) must fail the
  host test, and do.

**Our row with interrupts off**: the same list with interrupts off
(PRIMASK) around each call, a configuration of its own, labelled "not a
library" in every row. It is scored like any row on the comparison page,
and the filter "Kind of row" takes it out.

## The libraries and their versions

The set, the pins and the licences are in the kind's README ("The set");
the libraries are fetched at the commits in
[`kinds/pools/libs.lock`](../../kinds/pools/libs.lock), never copied into
this repository.

**MemoryPool is measured at a commit that is not a release.**
- The project's only release, v0.1.0, spaces the blocks of
  `MemoryPool::Fixed` by the size of a pointer, whatever the block size, so
  blocks of 32 bytes overlap; our host check of v0.1.0 shows filling block
  0 changing 24 of block 1's 32 bytes
  ([`checks/memorypool_v010.cpp`](../../kinds/pools/checks/memorypool_v010.cpp)).
  v0.1.0 also does not build for arm-none-eabi.
- The author fixed the spacing in pull request
  [#4](https://github.com/bertmelis/MemoryPool/pull/4), merged
  2024-05-14, and made the mutex optional where threads are not available
  (2024-05-15). There has been no release since.
- So the kind measures the main branch at `5073178`, and says so wherever
  the pin is shown. On the boards its mutex is compiled out, so the pool
  has no lock there.

## Checked on the host

Before any board, on the host ([README](../../kinds/pools/README.md),
"The host test, and that it can fail"):
- **The host test**: for every configuration, 64 random sequences of
  20 000 calls and the board's scenario patterns, with the checks above
  after every call. The four broken builds of the reference must fail it.
- **ASan and UBSan** over the same test, for the C and C++ code.
- **CBMC on the reference**: for 4 blocks and every sequence of 8 calls,
  the free list is exactly the blocks not held, without repeats; the two
  broken builds of the list are refuted.
- **Miri** on the Rust adapters: atomic-pool's test passes; heapless's
  board path is Arm assembly, which Miri cannot run.

**Where the host differs from the boards.** Some code runs only on the
boards, and there the per-call checks of the bench image are its only
test: CMSIS-RTX's LDREX/STREX variant (Cortex-M4, M7 and M33), heapless's
LL/SC stack, and atomic-pool's single-core path on the Cortex-M0+. The
README lists every such difference per row.

## What the placements show

The figures in this section are those of the first series
([report](../../reports/2026-11-26-pools-first-series.md)), from the
records under [`records/pools`](../../records/README.md).

**The measurement repeats, but for one board.** On five of the six boards
every mean of the series is the same in both passes, and the baseline
measures the same in every image of a board. On the Raspberry Pi Pico 2 H,
116 of 4224 means differ between the passes, all of them a
configuration's and with the cache on, by at most 6.3 % (heapless,
`init`, one call); the shortest call is the same in both passes in 115 of
the 116. The tables show the first pass.

**A mean includes the first call.** Each scenario's mean is over all its
calls, the first included. Per image the baseline runs first, then the
configuration; each with the cache off, then on; each time `init`, then
the six scenarios in the order of the table under "What is
measured" (`kinds/pools/bench/main.c`, `run_all`). The first call adds at most
12.6 % to a mean on the Raspberry Pi Pico 2 H (C_Allocator, `pair` alloc
with the cache on: a first call of 1760 cycles in a mean of 60), at most
2.0 % on the NUCLEO-H723ZG, and less than 1 % on the other four boards.

**Where the code lies moves the numbers more than repetition does.** The
same configuration, built eight times with its code moved by 0, 4 ... 28
bytes, gives different means. With the cache off the largest spread over
the eight placements, `init` aside, is 61 % on the nRF5340 DK, 37 % on
the NUCLEO-G474RE, 15 % on the NUCLEO-G0B1RE, 7 % on the Raspberry Pi
Pico 2 H and 352 % on the NUCLEO-H723ZG (Contiki-NG, `pair_full` free:
250–1132); on the SAM D20 Xplained Pro it is 0, every figure the same at
all eight placements. With the cache on it is at most 5 % on the nRF5340
DK, 6 % on the Raspberry Pi Pico 2 H, 9 % on the SAM D20 Xplained Pro,
12 % on the NUCLEO-G0B1RE, 35 % on the NUCLEO-H723ZG and 44 % on the
NUCLEO-G474RE. The CRC kind's numbers move with the placement in the
same way ([CRC method](method-crc.md), "What the placements show").

**What this means for the tables.** A difference between two
configurations is a difference only where their ranges over the eight
placements do not overlap. Every table therefore shows the range, and
a single placement says little on the NUCLEO-H723ZG with the cache off.
What the tables show, row by row, is on the
[results page](results-pools.md#what-the-tables-show).

## What is not measured

- Use from interrupts or from several threads (above), and the time a
  pool keeps interrupts off.
- Other pool shapes than 32 blocks of 32 bytes.
- Pools that live inside an RTOS and cannot be built alone, and memory
  allocators of several block sizes.
- heapless on the Cortex-M0+: its documentation says its pool needs
  LDREX/STREX, which the Cortex-M0+ does not have.
- Code run from RAM: every configuration runs from flash.
