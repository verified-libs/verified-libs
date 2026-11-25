# Candidates: queues with more than one producer or consumer (survey)

Survey of 2026-11-24 for the choice of the next kind of library
([plan](../lab/plans/2026-11-24-next-library-kinds.md), kind C). This kind
is an extension of the ring buffers, not a new one: the published
comparison already has five configurations tested with more than one
producer or consumer (below). Nothing new here is tested yet; what a
project says about itself is given as "it documents".

How the facts were taken: as in the [pool survey](pools-embedded.md)
(shallow clones of 2026-11-24, licence from the licence file, no GitHub
API). ⚠ marks the project owner's own libraries.

## What is there already

The two-interrupt stress test (`firmware/rb-mp-stress`: two interrupts at
two priorities as producers or consumers, and on the RP2350 the second
core) and the benchmark of version 2 cover these, as published
(`site/data/libs-meta.json`, "mp"):

| Configuration | Modes | Cores | How |
|---|---|---|---|
| pxq RingBuffer_PackedState ⚠ | MPSC, SPMC, MPMC | 1 | interrupts masked around push and/or pop |
| RIOT tsrb | MPSC, SPMC, MPMC | 1 | every operation masks interrupts |
| wizard97 + PRIMASK macros | MPSC, SPMC, MPMC | 1 | every method masks interrupts |
| DNedic lockfree `mpmc::Queue` | MPSC, SPMC, MPMC | 2 | a class of its own, compare-and-swap |
| heapless `mpmc::Queue` | MPSC, SPMC, MPMC | 2 | a type of its own, compare-and-swap |

The test is described in [reports/2026-11-18-mp-campaign-coverage.md](../reports/2026-11-18-mp-campaign-coverage.md).
Kind C means: more libraries of this sort, the RTOS message queues, and a
measurement of what the hardware allows (below).

## The problem, and who has it

Several interrupts that report into one queue (a sensor interrupt and a
UART interrupt into the main loop's event queue), or several tasks on two
cores: the queue must take items from more than one producer at once.
What goes wrong in practice:

- **A lock-free MPSC or MPMC queue needs a read-modify-write**
  (compare-and-swap or LDREX/STREX). Cortex-M0+ has neither, so such a
  library either does not build there, uses a critical section, or uses a
  polyfill (Rust's `portable-atomic`).
- **Two cores.** On the nRF5340 the two cores' LDREX/STREX does not
  exclude the other core (our own probe,
  [firmware/nrf5340-net-probe/README.md](../firmware/nrf5340-net-probe/README.md));
  a queue built on it is then not safe across the cores, whatever the
  library does. The RP2350 has two Cortex-M33 cores with hardware
  spinlocks (its SIO block).
- **Interrupt variants.** RTOS queues have separate calls for
  interrupts: FreeRTOS's `xQueueSend` "must not be called from an
  interrupt service routine" (`include/queue.h`), `xQueueSendFromISR` is
  the one for interrupts; ThreadX allows `tx_queue_send` from ISRs with
  `TX_NO_WAIT`
  ([ThreadX chapter 4](https://github.com/eclipse-threadx/rtos-docs/blob/main/rtos-docs/threadx/chapter4.md));
  Zephyr's `k_msgq_put` is `@isr_ok` with `K_NO_WAIT`.

## Candidates

| Library | Lang. | Licence | Newest commit | Version to pin | What it documents | Where used |
|---|---|---|---|---|---|---|
| **FreeRTOS queue** (`queue.c`) | C | MIT | 2026-11-17 | V11.3.3 | `...FromISR` variants for interrupts; the plain calls "must not be called from an interrupt service routine" (`include/queue.h`) | FreeRTOS |
| **Zephyr `k_msgq`** (`kernel/msg_q.c`) | C | Apache-2.0 | 2026-11-23 | v4.5.0 | `k_msgq_put` `@isr_ok` with `K_NO_WAIT` (`include/zephyr/kernel.h`) | Zephyr |
| **Zephyr `mpsc_pbuf`** (`lib/os/mpsc_pbuf.c`) | C | Apache-2.0 | 2026-11-23 | v4.5.0 | "Multi producer, single consumer packet buffer"; variable-length packets, allocate then commit, an overwrite mode (`include/zephyr/sys/mpsc_pbuf.h`) | Zephyr |
| **CMSIS-RTX `osMessageQueue`** (`Source/rtx_msgqueue.c`) | C | Apache-2.0 | 2026-11-18 | v5.9.1 | `osMessageQueuePut` from an ISR with timeout 0 (CMSIS-RTOS2); the code uses atomic counters (`atomic_inc32`, `atomic_dec32_nz`) | Keil RTX5, CMSIS projects |
| **ThreadX queue** (`common/src/tx_queue_*.c`) | C | MIT | 2026-11-01 | v6.5.2.202603_rel | `tx_queue_send`: "Initialization, threads, timers, and ISRs" (docs, above) | ThreadX |
| **QP/C `QEQueue`** (`include/qequeue.h`) | C | GPL-3.0-or-later or commercial | 2026-11-17 | v8.1.6 | The event queue of an active object, into which any part of the application posts; to be read in detail | QP framework |
| **embassy-sync `Channel`** | Rust | MIT OR Apache-2.0 | 2026-11-23 | 0.8.0 | "A Multiple Producer Multiple Consumer (MPMC) channel. Each message is only received by a single consumer." (`README.md`); the lock is the user's choice of raw mutex (e.g. `CriticalSectionRawMutex`) | Embassy |
| **crossbeam `ArrayQueue`** | Rust | MIT OR Apache-2.0 | 2026-11-22 | crossbeam-queue 0.3.14 | "a bounded MPMC queue"; `no_std` with the `alloc` feature (`crossbeam-queue/README.md`) | Desktop and server Rust; `no_std` users |
| **Concurrency Kit `ck_ring`** | C | BSD-2-Clause | 2026-10-19 | 0.7.2 | SPSC, MPSC, SPMC and MPMC variants of one ring; ports per architecture (`include/gcc/arm/`); whether it builds for Cortex-M is unknown | Server software (its CI covers FreeBSD among others) |
| rigtorp `MPMCQueue` | C++ | MIT | 2026-11-17 | v1.0 | "A bounded multi-producer multi-consumer concurrent queue for C++20"; storage from an allocator, `std::allocator` by default (`README.md`) | Desktop and server C++ |
| moodycamel `ConcurrentQueue` | C++ | Simplified BSD (also Boost licence, `LICENSE.md`) | 2026-10-25 | v1.0.5 | Lock-free MPMC; allocates blocks from the heap | Desktop and server C++ |
| darkautism `lfqueue` | C | WTFPL (licence file) | 2026-09-26 | head `94d214d2f748` | "A small multi-producer / multi-consumer lock-free queue written in C", with hazard slots and ThreadSanitizer tests (`README.md`) | – |

Listed, not proposed for boards: rigtorp `MPMCQueue`, moodycamel
`ConcurrentQueue`, crossbeam `ArrayQueue` and `lfqueue` allocate from a
heap and are made for servers; they would answer the question "does a
server queue hold up on a microcontroller" as rigtorp's SPSC queue did in
the ring-buffer trial.

## What could be proven, and with which tool

- **GenMC** for the queues written with C11 or C++11 atomics (DNedic
  `mpmc::Queue` was started this way; ck_ring, lfqueue): two producers
  and one consumer under RC11, as in `verify/genmc/mpmc_cxx.cpp`.
- **The contract check on the host model** for the queues that mask
  interrupts (the RTOS queues): it already handles two producers or two
  consumers for MPSC, SPMC and MPMC (its README); the RTOS calls need
  their critical sections mapped, as for the FreeRTOS stream buffer.
- **loom** (Rust) for embassy-sync and crossbeam: not in the toolchain
  image; Miri is, and runs crossbeam's own tests.

## What could be measured on the six boards

- **The benchmark of version 2 as it is**: a new configuration is a new
  line in `configs.txt` and new slots; the scenarios (single, burst,
  blocks) apply. An RTOS queue holds items of a fixed size; one byte per
  item makes the numbers comparable with the ring buffers.
- **The two-interrupt stress test as it is**, plus the second core of the
  RP2350 for the libraries that claim more than one core.
- **New**: the cost of contention. Today each producer's call is timed
  alone. A scenario in which the second interrupt hits the first one's
  call at every instruction (the interrupt sweep with two interrupts
  exists) gives the extra cycles a lock-free retry or a lock costs.
- **First guess of a first series**: 6 to 8 configurations × 8
  placements; they fit in the free slots after the ring-buffer table, so
  **about 10 to 15 flash writes** for the benchmark and the stress
  bundle on the six boards.

## What a filter and a column would be

They exist: the comparison page has the topologies (SPSC, MPSC, SPMC,
MPMC) and "two cores" as filters. New would be a column for the cost
under contention and a filter "works on Cortex-M0+ without a lock".

## Effort, in the terms of the step-1 report

- Small: adapters for the new libraries, RTOS stubs (as for the FreeRTOS
  stream buffer), one more scenario.
- Reused as it is: almost everything: interface, scenarios, both stress
  tests, the contract check, GenMC, the page and the MCP server.
- The catch: adding configurations to the ring-buffer benchmark touches
  `firmware/`, so the export check asks for a rebuild of every record
  (step-1 report); it is the same for any new library in the ring-buffer
  trial, and would be paid once for the whole extension.
