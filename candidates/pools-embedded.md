# Candidates: fixed-block pools used from interrupts (survey)

Survey of 2026-11-24 for the choice of the next kind of library
([plan](../lab/plans/2026-11-24-next-library-kinds.md), kind A). Nothing
here is tested yet. What a project says about itself is given as "it
documents"; what the code does is from reading the source at the commit
named. **Verifying the claims would be the point of the tests.**

How the facts were taken: each repository was cloned (shallow, sparse
where large) on 2026-11-24; "newest commit" is the date of the head of the
default branch that day, "release" the newest release tag, and the
licence is the one in the repository's licence file (the GitHub API was
not used this night). ⚠ marks the project owner's own libraries; the
owner has none of this kind in public (their public repositories:
RingBuffer-Cortex and math_bits).

## The problem, and who has it

A fixed-block pool hands out blocks of one size from a static array: a
UART or network driver takes a buffer in its interrupt, fills it, and
hands it to a task, which gives it back. Allocation and release happen in
different contexts, often both in interrupts, so the free list is shared
between an interrupt and the main loop, or between two interrupts. What
goes wrong in practice:

- **A free list changed by two contexts at once** loses a block or hands
  one out twice: the pool is then smaller than it should be, or two
  owners write into one buffer. A pool is usually protected by turning
  interrupts off (most RTOS pools) or by a lock-free stack on
  load-linked/store-conditional (LDREX/STREX on Cortex-M3 and up).
- **The ABA problem of lock-free stacks.** A lock-free free list
  (a Treiber stack) can be corrupted if, between reading the head and
  swapping it, other contexts take and return blocks so that the head
  looks unchanged. heapless's documentation says Cortex-M's LDREX/STREX
  prevents it because any preemption clears the exclusive monitor; an
  open issue discusses whether that holds as written
  ([rust-embedded/heapless#180](https://github.com/rust-embedded/heapless/issues/180)).
- **Which calls are allowed in an interrupt** differs per call and per
  argument: CMSIS-RTOS2 allows `osMemoryPoolAlloc` from an interrupt only
  with a timeout of 0
  ([CMSIS-RTOS2 documentation](https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html));
  ThreadX allows `tx_block_allocate` from an ISR only with `TX_NO_WAIT`
  ([ThreadX chapter 4](https://github.com/eclipse-threadx/rtos-docs/blob/main/rtos-docs/threadx/chapter4.md));
  lwIP needs `LWIP_ALLOW_MEM_FREE_FROM_OTHER_CONTEXT` to free heap
  memory from an interrupt, and its own text warns that it then turns
  interrupts on and off often
  ([lwIP `opt.h`](https://github.com/lwip-tcpip/lwip/blob/master/src/include/lwip/opt.h)).
- **Interrupt latency.** A pool that turns interrupts off for its
  operation adds that time to the latency of every other interrupt. The
  length of that section is rarely documented; it can be measured.

## Candidates

Most deployed first: the pools of RTOSes and SDKs, which bare-metal code
can use without the scheduler when it calls them without waiting (as the
ring-buffer work did with the FreeRTOS stream buffer). Then small
libraries with a licence.

### RTOS and SDK pools (C)

| Library | Licence | Newest commit | Release to pin | What it documents about interrupts and threads | What the code does | Where used |
|---|---|---|---|---|---|---|
| **Zephyr `k_mem_slab`** (`kernel/mem_slab.c`) | Apache-2.0 | 2026-11-23 | v4.5.0 | `k_mem_slab_alloc` and `k_mem_slab_free` are marked `@isr_ok`; "timeout must be set to K_NO_WAIT if called from ISR" (`include/zephyr/kernel.h`) | A free list under a spinlock (`k_spin_lock`: interrupts off on one core) | Zephyr drivers and subsystems |
| **CMSIS-RTX `osMemoryPool`** (`Source/rtx_mempool.c`) | Apache-2.0 | 2026-11-18 | v5.9.1 | Alloc may be called from an ISR with timeout 0; free may be called from an ISR (CMSIS-RTOS2 docs, above) | On Armv7-M and Armv8-M: a lock-free free list with LDREX/STREX (`atomic_link_get`/`atomic_link_put`, `rtx_core_cm.h`); on Armv6-M (Cortex-M0+): interrupts off | Keil RTX5, CMSIS-based projects, Mbed OS (archived) |
| **Eclipse ThreadX block pool** (`common/src/tx_block_*.c`) | MIT | 2026-11-01 | v6.5.2.202603_rel | `tx_block_allocate` and `tx_block_release`: allowed from "Initialization, threads, timers, and ISRs"; `TX_NO_WAIT` is the only option from an ISR (docs, above) | Interrupts off (`TX_DISABLE`) around the free-list change | ThreadX (formerly Azure RTOS) |
| **RT-Thread `rt_mp`** (`src/mempool.c`) | Apache-2.0 | 2026-11-23 | v5.3.0 | No statement about interrupts found in the file | `rt_spin_lock_irqsave` around the free list; the check "not in an interrupt" is on the waiting path only, so a call with `time = 0` from an interrupt passes through the code | RT-Thread |
| **NuttX `mempool`** (`mm/mempool/mempool.c`) | Apache-2.0 | 2026-11-24 | nuttx-13.1.0 | A pool has an "interrupt mempool" part of its own (`interruptsize`, `include/nuttx/mm/mempool.h`), used when called from an interrupt | `spin_lock_irqsave` around its queues | NuttX (network buffers among others) |
| **uC/OS-III `OSMem`** (`Source/os_mem.c`) | Apache-2.0 | 2026-07-15 | v3.08.02 | `OSMemCreate` refuses an ISR (`OS_ERR_MEM_CREATE_ISR`); `OSMemGet`/`OSMemPut` carry no such check | `CPU_CRITICAL_ENTER` (interrupts off) around the free list | Micrium uC/OS-III, now Weston Embedded |
| **lwIP `memp`** (`src/core/memp.c`) | BSD-3-Clause | 2026-11-23 | STABLE-2_2_1_RELEASE | `SYS_ARCH_PROTECT` "by disabling interrupts for an embedded system or by using a semaphore or mutex" (`src/include/lwip/sys.h`) | Pool get and put under `SYS_ARCH_PROTECT` | lwIP, in most vendor network stacks |
| **ChibiOS memory pools** (`os/oslib/src/chmempools.c`) | GPL-3.0 (the RT and OSLIB files; ChibiOS also sells licences) | 2026-05-31 | ver_20.3.1 (newest tag; the main branch is ahead) | `chPoolAllocI` and `chPoolFreeI` are marked `@iclass` (ChibiOS's class of calls made inside its system lock, from a thread or an interrupt handler) | The I-class calls assume the caller holds the lock; the plain calls take it | ChibiOS |
| **QP/C `QMPool`** (`src/qf/qf_mem.c`) | GPL-3.0-or-later, or commercial (dual) | 2026-11-17 | v8.1.6 | No statement about interrupts in `qmpool.h` or `qf_mem.c`; the pools are QP's event pools (`Q_NEW`) | `QF_CRIT_ENTRY`/`EXIT` (a critical section of the port) around the free list | QP framework (Quantum Leaps) |
| **ETL `etl::pool`** (`include/etl/ipool.h`) | MIT | 2026-11-20 | 20.49.0 | Nothing about threads or interrupts in the header | No locking; the user has to lock | Embedded C++ projects using ETL |
| **RIOT `memarray`** (`sys/include/memarray.h`) | LGPL-2.1-only | 2026-11-23 | 2026.10 | Nothing about threads or interrupts in the header | No locking | RIOT |
| **Contiki-NG `memb`** (`os/lib/memb.c`) | BSD-3-Clause | 2026-11-19 | release/v5.2 | Nothing about interrupts in the header | No locking (Contiki's processes are cooperative) | Contiki-NG |

### Rust

| Library | Licence | Newest commit | Version to pin | What it documents | What the code does | Where used |
|---|---|---|---|---|---|---|
| **heapless `pool`** (`box_pool!`, `arc_pool!`, `object_pool!`) | MIT OR Apache-2.0 | 2026-11-19 | 0.9.4 (`Cargo.toml` of the head; tag v0.9.3) | "This module/API is only available on these compilation targets: ARM architectures which instruction set include the LDREX, CLREX and STREX instructions, e.g. thumbv7m-none-eabi but not thumbv6m-none-eabi" (`src/pool.rs`); its own cycle counts on a Cortex-M4F: 23 cycles for `BoxPool::alloc` | A Treiber stack on LL/SC (`src/pool/treiber/llsc.rs`); CAS with a tag on x86 | The embedded Rust ecosystem |
| **atomic-pool** (embassy-rs) | MIT OR Apache-2.0 | 2025-06-07 | 2.0.1 | Uses `portable-atomic`; on cores without compare-and-swap with its `critical-section` or `unsafe-assume-single-core` feature (`README.md`) | A bitmap of used slots, claimed with atomic operations | Embassy projects |

### Small libraries with a licence

| Library | Licence | Newest commit | Release | What it documents | Where used |
|---|---|---|---|---|---|
| endurodave/C_Allocator | MIT | 2026-11-16 | v2.1.0 | Fixed-block allocator in C; a CI job named "RTOS Locks" (`README.md`); a lock guard (`src/LockGuard.h`) | Article on CodeProject; Arduino library manifest |
| Igwe-Starking/eccles-rtmem | MIT | 2026-10-03 | v2.0.0 | Pool allocator in C99; Cortex-M PRIMASK backend; "RTOS-mutex backends aren't ISR-safe by default. Interrupt-masking backends (AVR, MSP430, Cortex-M…) are." (`README.md`) | – |
| bertmelis/MemoryPool | MIT | 2024-05-15 | v0.1.0 | C++; a compile warning "The memory pool is not thread safe" where `std::mutex` is missing (`src/Fixed.h`) | Arduino/PlatformIO library |

### Considered, not proposed

- **japaric/lifo** (Rust, MIT/Apache-2.0): "interrupt-safe, lock-free
  memory pool for Cortex-M"; deprecated, merged into heapless (its
  `README.md`), newest commit 2019.
- **FreeRTOS kernel**: has no fixed-block pool (its `portable/MemMang`
  holds heaps 1 to 5: kind B).
- **FreeRTOS-Plus-TCP network buffers**: a pool inside a network stack,
  tied to its descriptors.
- **cherry-embedded/CherryBP**: found by search, could not be cloned on
  2026-11-24.

## What could be proven, and with which tool

- **The contract check on the host model** (`verify/contract`) fits the
  pools that turn interrupts off: an interrupt at every instruction of
  `alloc` and `free`, every pool state of a small pool (4 blocks: every
  subset allocated). The verdict is new: no block handed out twice, no
  block outside the pool, the number of free blocks right after a drain,
  and every outcome one that the calls in some order give. What the tool
  needs besides: the RTOS's critical-section macros mapped to the flag of
  `host_irq.h`, as for the FreeRTOS stream buffer.
- **LDREX/STREX code** (CMSIS-RTX on Armv7-M, heapless): the host model
  can stand for the exclusive monitor (a store-exclusive fails if an
  interrupt came since the load-exclusive, as on Cortex-M), so the same
  check reaches it; the inline assembly has to be translated by
  `hostify.py`, which today handles only the PRIMASK instructions. This
  is new work and is where the ABA question above is decided for one
  core.
- **GenMC** (C11 threads): fits a pool written with C11 atomics; none of
  the C candidates above is, so GenMC plays a small part here.
- **Miri and loom** (Rust): Miri runs heapless's x86 code path, not its
  LL/SC path (inline assembly). Loom is not in the toolchain image.
- **Differential test against a reference pool** on the host: a free
  list of our own, the same random sequence of calls, the same answers
  (allowing a different block order, since pools differ in LIFO or FIFO
  order).

## What could be measured on the six boards

- **Operations**: `alloc` and `free`, each through `time_call` (`free(a)`,
  `alloc()` returning the address).
- **Scenarios**: one alloc and one free in turn (the pool almost full and
  almost empty), a burst of 16 allocs then 16 frees in the same and in the
  reverse order, alloc on an empty pool (the failure path), each with the
  cache off and on, as today.
- **Baseline**: a free list of our own without a lock, and one with
  interrupts off around it: the cost of the protection itself.
- **A number no ring-buffer page has**: the longest time with interrupts
  off per call. Measured with the interrupt sweep's method: a SysTick
  interrupt armed at every delay, and the delay from the request to the
  handler recorded. It is a column a reader choosing a pool for a
  real-time system needs.
- **Placement**: the method of version 2 applies as it is (one image per
  configuration, eight placements, the library `FAR` from its adapter).
- **Stress**: the ISR stress test's mechanism with a new judge: the main
  loop and the interrupt (and in the two-interrupt test, two interrupts)
  allocate and free at random, every owner writes a pattern of its own
  into its block and checks it before the free; at the end every block
  must be back. Controls: a pool without a lock (must fail), and mutants
  (a lost store of the head, a free that does not link the block).
- **Two cores**: the RP2350 test (core 1 against core 0) applies only
  to pools that claim it (none of the C pools above claims more than one
  core without the RTOS's SMP build; `atomic-pool` with
  `portable-atomic`'s `critical-section` on the RP2350 would).
- **First guess of a first series**: about 12 configurations (7 RTOS
  pools, ETL and RIOT with a lock of ours, the two Rust pools, one small
  library) × 8 placements = 96 images per board, about 5 segments of
  256 KB; with the ring-buffer bundles untouched, 2 to 5 flash writes per
  board for the benchmark (more on the SAM D20, 256 KB of flash) and one
  for a stress bundle: **about 20 to 30 flash writes** on the six boards.
  heapless's pool does not build for the two Cortex-M0+ boards (its own
  documentation).

## What a filter and a column would be

- Filters: documented for use from an interrupt (with which call and
  argument); lock-free or interrupts off; builds for Cortex-M0+;
  0 stress errors; contract check passed; licence permissive.
- Columns: cycles for alloc and free; the longest time with interrupts
  off per call; bytes of overhead per block and of code; the order blocks
  come back in (LIFO or FIFO).

## Effort, in the terms of the step-1 report

- New: the adapter interface (`init`, `alloc`, `free`, small), the
  scenarios and baseline, the stress judge and controls, the contract
  verdict, the interrupt-off measurement, the RTOS stubs per pool (as for
  the FreeRTOS stream buffer), the page data and page.
- Reused as it is: boards, `time_call`, one image per configuration,
  placements, bundles, the boot stub, the stress timers, the sweep and
  coverage, the export.
- Medium: a translation of LDREX/STREX for the host model.
