# Pilot: fixed-block pools (host only)

Step 4 of the [plan for the next kind](../../lab/plans/2026-11-24-next-library-kinds.md),
for the kind the [comparison](../../reports/2026-11-24-next-kind.md)
recommends: fixed-block pools used from interrupts
([survey](../../candidates/pools-embedded.md)).

**This pilot gives no result about any library.** It shows that a common
interface for pools is workable: three libraries fit it, the same
adapters build for the host and for a Cortex-M4, and a first host test
can fail. A "pass" below means only that an adapter and the test work
together in one context, with eight blocks; it says nothing about how a
library behaves under interrupts, which is what the trial would test.
Nothing was run on a board.

## What is here

| File | What it is |
|---|---|
| [`pool.h`](pool.h) | Draft of the adapter interface: `init`, `alloc`, `free`, optional interrupt variants, the region the blocks may lie in, the alignment promised. Its comment gives the reasons. |
| [`libs.lock`](libs.lock) | The three libraries, pinned by commit: ETL 20.49.0 and RIOT at the commits the ring-buffer trial pins, Eclipse ThreadX v6.5.2.202603_rel. |
| [`fetch.sh`](fetch.sh) | Fetches them, sparse, outside the repository (default `~/vl-next/pilot-pools`). Only git runs on the host. |
| [`adapter_ref.c`](adapter_ref.c) | Our own free list: the reference, the baseline of a board benchmark, and, built with `POOL_BROKEN=1` or `2`, two deliberately broken pools. |
| [`adapter_etl_pool.cpp`](adapter_etl_pool.cpp), [`adapter_riot_memarray.c`](adapter_riot_memarray.c), [`adapter_threadx_block.c`](adapter_threadx_block.c) | The three adapters. |
| [`shims/riot`](shims/riot), [`ports/host/tx_port.h`](ports/host/tx_port.h), [`tx_kernel_stubs.c`](tx_kernel_stubs.c) | What two of the libraries need from their surroundings (below). |
| [`test_pool.c`](test_pool.c) | The host test. |
| [`cross_main.c`](cross_main.c) | Calls each adapter once, so that the Cortex-M4 link keeps them; not run. |
| [`Makefile`](Makefile), [`run.sh`](run.sh) | `bash run.sh` fetches, then builds and runs the test and the cross build in the toolchain image of benchmark version 2 (`verified-libs/toolchain:2026-11-13`). |

## Why the interface looks like this

- **The signature of the ring-buffer operations.** On the 32-bit boards
  `alloc` and `free` are `uint32_t op(uintptr_t, uintptr_t)`, the type
  the boards' `time_call` takes, so the timed window of
  `firmware/common/<board>/board.h` times them as it is. (On the 64-bit
  host `alloc` returns a `uintptr_t`.)
- **One block size, chosen at build time**: every candidate of the survey
  is a pool of one block size. The pilot uses 8 blocks of 32 bytes.
- **The adapter owns the storage.** The libraries need different amounts
  of it for the same blocks: ThreadX keeps a pointer in front of every
  block, ETL and RIOT keep their list inside free blocks. So the adapter
  creates the pool and tells the test where blocks may lie.
- **No "free count" call**: not every library has one; the test counts
  the blocks it holds.
- **Interrupt variants are optional fields**: ThreadX and CMSIS-RTOS2 use
  the same call with a no-wait argument, Zephyr too; ChibiOS has separate
  `...I` calls.

## Scenarios (draft, for the board benchmark)

With the reasons; none is built yet.

| Scenario | What | Why |
|---|---|---|
| `pair` | 1024 × (alloc, free) with the pool almost empty | The cost of one block in and out, the common driver pattern |
| `pair_full` | the same with all but one block held | Some pools search; the full case shows it |
| `burst16_lifo` / `burst16_fifo` | 16 allocs, then 16 frees in the reverse or in the same order | Order matters for list-based pools (cache lines, search) |
| `empty` | alloc on an empty pool | The failure path, which an interrupt takes under load |
| `irq_off` | an interrupt requested at every cycle of a call, the delay to its handler recorded | The longest time the pool keeps interrupts off: the column no documentation gives |

Each with the cache off and on, one image per configuration, eight
placements and the far call, as in version 2 of the ring-buffer
benchmark.

## The test, and that it can fail

[`test_pool.c`](test_pool.c): 64 sequences of 20 000 random calls per
adapter. It holds its own record of the blocks it has and checks after
every call that a pool of N blocks gives the N-th and refuses the
(N+1)-th, that a block lies in the region at the promised alignment and
is not one already held, that every held block keeps the pattern its
owner wrote, and after the run that all N blocks come back.

Run on 2026-11-24 (`bash run.sh test`, toolchain image 2026-11-13):

```
pool pilot test: 8 blocks of 32 bytes, 64 sequences of 20000 steps
reference free list (ours)         pass   (expected pass)  interrupt-off sections: 0
broken: block handed out twice     FAIL   (expected FAIL)  sequence 0, step 5: no block twice: a block handed out that the test holds
broken: block lost                 FAIL   (expected FAIL)  sequence 0, step 33: capacity: no block although fewer than POOL_BLOCKS are held
ETL etl::pool (C++)                pass   (expected pass)  interrupt-off sections: 0
RIOT memarray (C)                  pass   (expected pass)  interrupt-off sections: 0
ThreadX block pool (C)             pass   (expected pass)  interrupt-off sections: 1281057
exit 0: every verdict as expected
```

The two broken pools are caught at once, each by the check made for its
fault. "Interrupt-off sections" counts how often a pool turned
"interrupts" off through the port header: ThreadX does it in every call,
ETL and RIOT have no lock of their own (their headers document none).

The cross build (`bash run.sh cross`) links the four adapters and the
libraries' files for a Cortex-M4 at `-Os` into one ELF (14 336 bytes of
text with newlib's start-up); ThreadX is built there with the release's
own `ports/cortex_m4/gnu/inc/tx_port.h`, whose `TX_DISABLE` is
`mrs PRIMASK; cpsid i`.

## ThreadX without its kernel

The block pool is five files of ThreadX's `common/src`. Run alone they
need a port header and the scheduler calls they make when a thread waits
for a block. With `TX_NO_WAIT`, the only option ThreadX documents for an
ISR, no thread ever waits, so the stubs in
[`tx_kernel_stubs.c`](tx_kernel_stubs.c) stop the program if they are
reached, and none was. The host port header is ours
([`ports/host/tx_port.h`](ports/host/tx_port.h)); "interrupts off" is a
flag there, as in the contract check's `host_irq.h`. This is the same
approach as the FreeRTOS stream buffer's in the ring-buffer trial, and
the same question stays open: is a pool without its kernel the pool
users run? For the no-wait path the code is the same; the waiting paths
are not tested this way.

## What a board benchmark and a stress test would look like

- **Benchmark**: a firmware directory of its own (its own `bench.h`
  defining the operation type `rb_op` that the boards' `board.h`
  includes, so no file under `firmware/common` changes), the scenarios
  above, the reference pool as the baseline, `configs.txt` and a slot
  table of its own in segments after the ring-buffer ones, and the
  version 2 tools copied with the result block's shape as a parameter.
- **Stress test**: the ISR stress test's timer and sweep with a new
  judge, as the host test above but with the main loop and the
  interrupt (and in the two-interrupt test, two interrupts) each holding
  blocks: no block twice, no block changed by another holder, all back
  at the end. Controls: the reference pool without a lock, and the two
  broken pools. Pools without a lock of their own (ETL, RIOT) would be
  run with a lock of ours around each call, as wizard97's ring buffer was,
  and reported as such.
- **Contract check**: the same properties as the verdict, with an
  interrupt at every instruction of `alloc` and `free` on the host model;
  for LDREX/STREX pools a model of the exclusive monitor.

## Still open

- **Where it lives.** A second kind under `firmware/` stops the export of
  every ring-buffer record until the export check holds test sources per
  kind ([step 1](../../reports/2026-11-24-what-carries-over.md)); the
  owner decides. Until then the pilot is outside `firmware/`.
- **CMSIS-RTX's pool** (the lock-free one on Armv7-M) needs the CMSIS 6
  headers and a device header to build alone; not tried this night.
- **Rust** (heapless `pool`, `atomic-pool`): not tried; they would come in
  as one crate each, as planned for the ring buffers.
- **The interrupt-off measurement** on the boards: the SysTick sweep of
  the stress test records where an interrupt lands, not how late it is;
  measuring the delay to the handler is new firmware.
- **The `align` field**: what each library promises is taken from its
  code, not from documentation: pointer alignment for RIOT and ThreadX,
  the element type's alignment for ETL (1 for a block of bytes).
