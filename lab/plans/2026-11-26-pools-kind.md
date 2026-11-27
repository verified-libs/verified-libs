# Plan: fixed-block memory pools as the third kind

**Decided by the owner on 2026-11-26: all seven points of "For the owner"
as recommended** ([`DECISIONS.md`](../../DECISIONS.md), 2026-11-26, "Pools
as the third kind, and method version 3").

Written 2026-11-26, when the owner said it is time for the next kind. The
order was decided on 2026-11-24: **D (CRC) first, then A (fixed-block
pools) in a narrower form**
([comparison of kinds](../../reports/2026-11-24-next-kind.md), "Review and
decision"). CRC is published, so A is next.

This is a plan, for the owner's decision. Nothing in it has run on a
board. The steps after the owner's word are host work first, as for CRC
([CRC plan](2026-11-24-crc-kind.md)). The changes of method that go with
this kind are in a plan of their own:
[`2026-11-26-method-version-3.md`](2026-11-26-method-version-3.md).

Read first: the [pool survey](../../candidates/pools-embedded.md), the
[pilot](../../pilot/pools/README.md), the
[two prechecks](../../reports/2026-11-24-pool-prechecks.md), and what the
CRC kind taught (its [plan to publication](2026-11-24-crc-from-series-to-publication.md),
the [first](../../reports/2026-11-25-crc-first-series.md) and
[second](../../reports/2026-11-25-crc-second-series.md) series).

## 1. Where we stand

**The decision and its narrowing.** The decision says "A in a narrower
form". **No file says what "narrower" means:** not the decision text
(report, line 147), the plan for the kinds
([`2026-11-24-next-library-kinds.md`](2026-11-24-next-library-kinds.md),
line 179) or the CRC plan (line 5). The review's points against A
(report, lines 124–140) are the only guide:
- twelve of the seventeen pools live inside an RTOS or a network stack,
  and a reader does not choose an RTOS for its pool;
- the hard cases (CMSIS-RTX's lock-free path, heapless, perhaps
  atomic-pool) were not in the pilot;
- the interrupts-off number would be measured on a pool without its
  kernel, and its measurement is not designed;
- a first series would bring a new judge, a new verdict, a model of
  LDREX/STREX, kernel stubs and new firmware all at once.

This plan reads "narrower" in two ways, **for the owner to confirm**:
- *Fewer libraries.* The pools a bare-metal project can pick by
  themselves, plus the RTOS pools that were shown to run alone on their
  no-wait path.
- *Fewer things measured at first.* The first series is a benchmark in
  one context: cycles, bytes and correctness on every call. The interrupt
  claims are shown as documented claims, and are tested in a later
  series (section 4).

**The two prechecks** ([report](../../reports/2026-11-24-pool-prechecks.md)),
both on the host, without a board:
1. *Can CMSIS-RTX's pool be built alone?* Yes.
   - For Cortex-M4, M33 and M0+, `rtx_mempool.c` is unchanged and nothing
     of the kernel is stubbed; it takes `OS_EVR_MEMORY=0`, a two-line
     `RTE_Components.h` and the device header.
   - On the host, the pool's three functions are cut out unchanged, Armv6-M
     variant only. They pass the pilot's test.
2. *Can LDREX/STREX be modelled on the host model?* Yes, for one core.
   - [`verify/exclusive/`](../../verify/exclusive/) models the local
     monitor, with its rules quoted from DDI 0403E.e and DDI0553B.z.
   - A made-up lock-free free list passes. A broken pop and a pop/push
     that ignore STREX's result are caught.
   - It cannot represent several cores, the compiler's actual code
     (it runs a C transliteration), progress, or two interrupts in one
     call.
   - RTX's own `atomic_link_get`/`atomic_link_put` have not been run
     through it yet (report, "Open").

The report is headed "Draft for review". Its branch (`pools-prechecks`,
`834b61f`) is merged into this plan's branch, not into `main`.

**What the pilot showed** ([README](../../pilot/pools/README.md)), host
only, with 8 blocks of 32 bytes:
- An interface (`pool.h`: `init`, `alloc`, `free`, the region and the
  alignment promised) fits ETL `etl::pool`, RIOT `memarray` and the
  ThreadX block pool. The prechecks added CMSIS-RTX.
- The host test (64 sequences of 20 000 random calls) catches a pool
  that hands a block out twice, and one that loses a block.
- ThreadX and CMSIS-RTX run without their kernel on the no-wait path.
  Their kernel stubs stop the program if reached, and none was.
- It gives no result about any library.

**The candidates.** Licences are from each repository's licence file
(survey of 2026-11-24). A pin is a commit only where the pilot or the
prechecks pinned one. The rest are to be pinned in step 1, with the
licence file read again.

| Candidate | Lang. | Licence | Pin | Lock of its own | In the narrower set? |
|---|---|---|---|---|---|
| ETL `etl::pool` | C++ | MIT | `7d604f2` (pilot, = the ring-buffer trial's) | none (header documents none) | yes |
| RIOT `memarray` | C | LGPL-2.1-only | `9c9a6ab` (pilot) | none | yes |
| Contiki-NG `memb` | C | BSD-3-Clause | release/v5.2, to pin | none (cooperative processes) | yes |
| endurodave/C_Allocator | C | MIT | v2.1.0, to pin | a lock guard (`src/LockGuard.h`) | yes |
| eccles-rtmem | C | MIT | v2.0.0, to pin | PRIMASK backend on Cortex-M | yes |
| bertmelis/MemoryPool | C++ | MIT | v0.1.0, to pin | none without `std::mutex` | yes |
| heapless `pool` | Rust | MIT OR Apache-2.0 | 0.9.4 / tag v0.9.3, to pin | lock-free (LL/SC); **not for Cortex-M0+** (its docs) | yes, four boards |
| atomic-pool | Rust | MIT OR Apache-2.0 | 2.0.1, to pin | atomic bitmap (`portable-atomic`) | yes |
| ThreadX block pool | C | MIT | `93387b0` (pilot) | interrupts off (`TX_DISABLE`) | yes (runs alone, pilot) |
| CMSIS-RTX `osRtxMemoryPool` | C | Apache-2.0 | `b566de4`, with CMSIS 6 `af1b110`, Cortex_DFP `cd38dbb` (prechecks) | LDREX/STREX on v7-M/v8-M, interrupts off on v6-M | yes (runs alone, prechecks) |
| Zephyr `k_mem_slab` | C | Apache-2.0 | v4.5.0, to pin | spinlock (interrupts off) | only if built alone within an hour (step 1) |
| lwIP `memp` | C | BSD-3-Clause | STABLE-2_2_1, to pin | `SYS_ARCH_PROTECT` | only if built alone within an hour |
| RT-Thread, NuttX, uC/OS-III, ChibiOS (GPL-3.0), QP/C (GPL-3.0 or commercial) | C | as in the survey | – | kernel locks | no (inside an RTOS; later if asked) |

That gives ten configurations, at most twelve with Zephyr and lwIP. The
CRC kind's first series had at most 20.

**Where the earlier material does not fit the decision** (said plainly,
not smoothed):
- *The kind's framing.*
  - The survey and the pilot frame the kind as "fixed-block pools used
    from interrupts". Their test plan centres on what happens under
    interrupts: the stress judge, the contract verdict and the
    interrupts-off column. The survey says "Verifying the claims would
    be the point of the tests".
  - A single-context first series measures none of that. It is the
    narrower form the review points to, but it leaves the survey's main
    reason for the kind to a later series. The owner should decide this
    knowingly (section 4).
- *The survey's first-series guess.* "About 12 configurations (7 RTOS
  pools, ETL and RIOT with a lock of ours, the two Rust pools, one small
  library)" (survey, "What could be measured"). This contradicts the
  review's point that a reader does not choose an RTOS for its pool. This
  plan takes two RTOS pools, not seven.
- *Where the code lives.*
  - The pilot proposes "a firmware directory of its own" and copies of the
    version 2 tools.
  - The CRC kind showed the better way: everything in `kinds/<kind>/`,
    version 2's programs used unchanged, by import.
  - The pilot's text is out of date on this. It does not conflict with the
    decision.
- *The prechecks are a draft.* The decision made them a condition for
  starting A. Their answers are "yes", but the report says "Draft for
  review" and was not merged into `main`.

## 2. What a pool is here, and what is measured

**A pool** is a library that hands out blocks of one size from storage
fixed at start, with `alloc` (a block or "none left") and `free`. Every
candidate is one pool of one block size (pilot, "Why the interface looks
like this").

**The interface.** The pilot's [`pool.h`](../../pilot/pools/pool.h) moves to
`kinds/pools/pool.h`:
- `init` (creates the pool in storage the adapter owns);
- `alloc` and `free`, in the shape the boards' `time_call` takes
  (`uint32_t op(uintptr_t, uintptr_t)`);
- the region blocks may lie in;
- the alignment the library promises (taken from its code and said so,
  pilot "Still open").
- Optional interrupt variants stay in the header for a later series.

**Shape of the pool.** The block size and count are fixed at build time,
so each shape is a new image.
- *Proposed:* one shape in the first series, 32 blocks of 32 bytes (1 KB
  of blocks). That is enough for the bursts below.
- *Alternative:* a second shape, 8 blocks of 256 bytes (a network buffer),
  doubles the images.
- This is for the owner (section "For the owner").

**Operations and scenarios.** Each operation is timed alone by
`time_call`, with 256 timed calls per scenario. The cache is off and on,
eight placements, two passes, with the reference timed in the same image:
the CRC kind's method.

| Scenario | What | Why |
|---|---|---|
| `init` | one call | its cost may grow with the count (a list threaded through the blocks) |
| `pair` | alloc then free, the pool almost empty | the common driver pattern |
| `pair_full` | the same with all but one block held | a pool that searches shows it here |
| `fill_drain_lifo` | 32 allocs, then 32 frees in reverse order | fill and drain; list order matters |
| `fill_drain_fifo` | 32 allocs, then 32 frees in the same order | the other order |
| `mixed` | a fixed-seed sequence of allocs and frees, the pool between 25 % and 75 % full | mixed order, as a driver under load |
| `empty` | alloc on an exhausted pool | the failure path |

A table per scenario gives cycles per alloc and per free, each as a range
over the eight placements, the first pass. Bytes:
- **flash** is the code at `-O2` for the board's core;
- **RAM** is the pool's control data plus the overhead per block (as
  `sizeof` and as the adapter's storage). The blocks themselves are left
  out, as they are the same for every library.

**What "correct" means**, checked after every call on the board, outside
the timed window, and in the host test:
- *No block handed out twice:* a bitmap of the blocks held.
- *A freed block is usable again:* a block freed and taken again must
  pass the pattern check.
- *Exhaustion is reported:* with N blocks held, `alloc` gives none. With
  fewer than N held, it gives one.
- *Alignment:* every block lies in the region, at the promised alignment.
- *No write outside the pool:*
  - canary words before and after the adapter's storage, checked after
    every call;
  - each holder writes a pattern of its own into its block and checks it
    at the free, which catches overlapping blocks.
- *All N come back at the end.*

A failed check stops the image with its code in the result block, as a
CRC mismatch does, and the record says so.

**On the host** (step 1):
- the pilot's test, made the kind's test: random sequences, the checks
  above, deliberately broken pools that must be caught;
- the whole test built with ASan and UBSan;
- CBMC on the reference pool (every operation keeps the free list a
  permutation of the free blocks, for a small N), and on the small C
  pools where it finishes in 60 minutes;
- Miri for the Rust adapters if it runs (heapless's LL/SC path is inline
  assembly: Miri runs its x86 path only, survey).

## 3. The reference and the baseline

**Our own free list** ([`adapter_ref.c`](../../pilot/pools/adapter_ref.c)
from the pilot): a LIFO singly linked list threaded through the free
blocks, no lock, as the textbooks write it. It plays three parts, as the
bitwise CRC did:
- *The reference of the host test.* The same random sequence must give
  the same answers: a block or none, and the same count held. Block
  addresses are not compared, since pools differ in LIFO or FIFO order.
- *The baseline of every image:* timed in the same image, so each row has
  what the simplest pool costs at that placement on that board.
- *The control:* built with `POOL_BROKEN=1` or `2`, it must fail the host
  test (pilot, "The test, and that it can fail").

**Why this reference.** It is the least a pool can do: one load and one
store per operation. A library's cycles above it are what its checks,
bookkeeping or locking cost, which a reader can weigh. It is ours and
short (`adapter_ref.c` is 71 lines with its two broken variants), so its correctness can be shown completely, by
the host test and by CBMC.

**Proposed, for the owner:** the same list with interrupts off around
each operation (PRIMASK), as a row of ours labelled "not a library", as
the CRC unit was. It gives the price of the simplest lock on each core,
which is what the libraries without a lock of their own would need.

## 4. Concurrency: claims, and what the first series shows

**What the candidates claim** (survey, with its sources):

| Candidate | Claim about interrupts or threads | How |
|---|---|---|
| ThreadX | allowed from ISRs with `TX_NO_WAIT` | interrupts off |
| CMSIS-RTX | alloc from an ISR with timeout 0, free from an ISR | LDREX/STREX (v7-M, v8-M), interrupts off (v6-M) |
| Zephyr `k_mem_slab` | `@isr_ok`, `K_NO_WAIT` from an ISR | spinlock |
| lwIP `memp` | protected by `SYS_ARCH_PROTECT` | port-defined |
| heapless `pool` | lock-free; only on targets with LDREX/STREX/CLREX | Treiber stack on LL/SC |
| atomic-pool | atomic; on cores without CAS via `critical-section` | atomic bitmap |
| eccles-rtmem | "Interrupt-masking backends (AVR, MSP430, Cortex-M…) are" ISR-safe | PRIMASK |
| C_Allocator | a lock guard; a CI job "RTOS Locks" | the user's lock |
| ETL, RIOT, Contiki-NG, MemoryPool | none (MemoryPool warns it is not thread safe) | – |

**The first series measures one context only**, as expected. It says so
on every page that shows it. The claims are shown, not tested:
- a column "documented use from interrupts", with the library's own
  sentence and its source;
- a note above the table: "Measured in one context. Whether a pool is
  safe when an interrupt calls it is not tested in this series; the
  column gives what each library documents."

No filter or score uses an untested claim.

**What a later series would add**, each with the owner's word:
- *The stress judge on the boards.* The ISR stress test's mechanism with
  holders in main and in the interrupt, the controls being the reference
  without a lock and the two broken pools (survey, "Stress").
- *The contract check on the host model.* An interrupt at every
  instruction of `alloc` and `free`, for the interrupts-off pools. For
  CMSIS-RTX and heapless, with the exclusive monitor model and RTX's
  `atomic_link_get`/`atomic_link_put` transliterated, the step the
  prechecks left open.
- *The interrupts-off time.* Its measurement is not designed (review),
  and it would be measured on pools without their kernels.

## 5. Steps from here to a published page

Each step ends with a commit and a push on `kind-pools`. Nothing goes
into `main` without the owner. Where a step needs the owner's word, it
says so.

| Step | What | Owner's word |
|---|---|---|
| 0 | This plan: the narrowing, the set, one context first, the shape, the baseline | **yes** |
| 1 | Host work in `kinds/pools/`, never under `firmware/`. Lock file and fetch script; interface; the reference with its proofs; adapters; host test with broken controls, sanitizers, CBMC; cross builds and sizes per core at `-Os` and `-O2`. A library that cannot be built alone in an hour is listed with the reason and left out. A value that differs from the reference is first our fault; if it stands, `lab/drafts` only, and work on that library stops. | no (within the plan) |
| 2 | The method changes that go with this kind ([method version 3](2026-11-26-method-version-3.md)) made and shown, before any pool image is built for a board | **yes** (frozen files) |
| 3 | One bench image for one board, built and not flashed. Then the counted proposal for the first series in a report: images, segments, bundles and flash writes per board, time serial and through the queue | **yes**, for the series |
| 4 | The series, through the queue, one job per board, each job with the reviewer's OK (DECISIONS 2026-11-26); the Pico 2 writes alone | per job |
| 5 | Records and export: `records/pools/<board>/<adapter>.json` (schema `pools-bench/1`; run files `pools-bench-run/1`), made by a `poolrecords.py` as `crcrecords.py`; a `poolverify.sh` rebuild that gives `MATCH`; the export with `POOLS_TEST_SOURCES` (`kinds/pools` minus its host tests, `firmware/common`, the version 2 programs used by import, the three lab files), `SAME_SOURCES_POOLS`, ledger entries `pools/<board>/<file>` in `records/rebuilt.json`; `test-public-export.sh` cases for the new kind | **yes** (a change of the export rule, as for CRC) |
| 6 | Pages from the start: results page (`results-pools.md`, tables written from the records by `site/pools_tables.py` with a `--check`), method page, the kinds overview, and the Compare page (`compare-pools.html`, weights giving a score that is a range, overlap marks, as the CRC page) with the MCP tools `list_pool_configurations` and `compare_pools`, a port of the page's script tested against it with gjs; `site/data/pools.json` written from the records; the reproduce section | **yes**, to publish |
| 7 | The method frozen at a tag `pools-method-freeze`, as `crc-method-freeze` | **yes** |
| later | The concurrency series of section 4 | **yes** |

What the CRC kind taught, built in from the start:
- *Ranges, not one number:* every cycle figure is min–max over the eight
  placements, and two rows differ only where their ranges do not overlap.
- *The page and the MCP are one script:* the MCP is a port tested against
  the page's own script, view for view.
- *The export per kind:* a file of this kind never under `firmware/`.
- *Rows that are not libraries are labelled every time:* the reference,
  and a row of ours such as the lock.
- *Board facts from the board:* option registers recorded with the series
  (method version 3).
- *A runner that refuses to write without `--flash`, and a write budget
  per job:* the queue.

## 6. Board cost, estimated

These are estimates only. Real numbers come from the image sizes of step 3.
- *Image size.* The pilot's cross build linked four adapters with
  newlib's start-up into 14 336 bytes of text. A pool image holds one
  adapter plus the harness and the reference, so it is taken as the size
  of a CRC image without a table: about 8–12 KB.
- *Images per board.* With ten configurations, eight placements and one
  shape, that is 80 images per board. On the two Cortex-M0+ boards
  heapless is left out (its docs), so they have 72.
- *Segments.* At about 12 KB a slot, 80 images fill about 4 segments of
  256 KB (the CRC kind's 160 images took 9).

| Board | Segments per bundle (CRC kind) | Bundles = flash writes | Time, scaled from the CRC first series by images (160 → 80) |
|---|---|---|---|
| nRF5340 DK | 4 | 1 | ~45 min (88 min for 160) |
| Pico 2 | 16 | 1 (in parts, alone) | ~1 h 50 (3 h 40 for 160) |
| NUCLEO-G474RE | 2 | 2 | ~17 min (33 min) |
| NUCLEO-H723ZG | 4 | 1 | ~33 min (65 min, at 64 MHz) |
| NUCLEO-G0B1RE | 2 | 2 (72 images) | ~28 min (62 min) |
| SAM D20 Xplained Pro | 1 | 4 (72 images) | ~53 min (118 min) |

- **About 11 flash writes in all**, plus one smoke bundle per board if
  the smoke needs one. With a second pool shape it is about 22.
- **Serial:** about 4 h 10.
- **Through the queue:** the longest board sets the time, about 2 h (the
  Pico 2). The Pico 2 writes alone, in parts.
- The times above are first and second pass together, as the CRC series
  ran.
- With twelve configurations, about +20 %.

## For the owner

1. **"Narrower" means:** the bare-metal pools plus the two RTOS pools
   shown to run alone (10, at most 12), measured in one context first.
   *Recommended: yes.*
2. **First series in one context only;** the interrupt claims shown as
   documented, not tested, and said so on the page. *Recommended: yes;
   the concurrency series later, with its own plan.*
3. **One pool shape** (32 blocks of 32 bytes) in the first series.
   *Recommended: yes; 8 × 256 bytes later if readers ask.*
4. **The baseline** is our lock-free free list; the same with PRIMASK as
   a labelled row of ours. *Recommended: both.*
5. **Zephyr and lwIP** only if each builds alone within an hour.
   *Recommended: yes.*
6. **The pools series runs only under method version 3.** *Recommended:
   yes (see that plan).*
7. **The prechecks report** to be reviewed and taken off "draft", with
   its branch, as part of this plan. *Recommended: yes.*
