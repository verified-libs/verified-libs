# Candidates: logging and tracing from interrupts (survey)

Survey of 2026-11-24 for the choice of the next kind of library
([plan](../lab/plans/2026-11-24-next-library-kinds.md), kind E; a kind
the owner allowed the night to add after A to D). Nothing here is tested
yet. What a project says about itself is given as "it documents".

How the facts were taken: as in the [pool survey](pools-embedded.md)
(shallow clones of 2026-11-24, licence from the licence file, no GitHub
API). ⚠ marks the project owner's own libraries; the owner has none of
this kind in public.

## Why this kind

A log or trace call is the most common thing firmware does from an
interrupt, and the library behind it is a ring buffer with more than one
producer: every interrupt priority and the main loop write into it, and a
debug probe, a UART or a task reads it. So it is the ring-buffer problem
of this project in the form most firmware meets it, with two questions a
reader cannot answer by reading: how many cycles does one call take in an
interrupt, and does every message arrive whole when interrupts nest?

## The problem, and who has it

- **Messages from nested interrupts.** If a higher-priority interrupt
  logs while a lower one is half-way through writing its message, the
  two can be interleaved or one lost, unless the library locks. SEGGER
  RTT's text says: "If using RTT from within interrupts, multiple tasks or
  multi processors, define the SEGGER_RTT_LOCK() and SEGGER_RTT_UNLOCK()
  function here". Its defaults file then defines a lock for GCC, Clang,
  SEGGER Embedded Studio and CrossWorks (PRIMASK on Armv6-M and Armv8-M
  Baseline, BASEPRI up to `SEGGER_RTT_MAX_INTERRUPT_PRIORITY` on Armv7-M
  and Armv8-M Mainline), and for other compilers the lock stays empty unless the
  application defines it (`RTT/SEGGER_RTT_ConfDefaults.h`,
  `RTT/SEGGER_RTT.c`). Which interrupts are masked is the application's
  choice: "Make sure to mask all interrupts which can send RTT data".
- **The cost inside the interrupt.** Formatting text in an interrupt
  takes time; deferred and tokenized logging moves that work out: Zephyr
  "Deferred logging reduces the time needed to log a message by shifting
  time consuming operations to a known context", and "since the logging
  API can be called in an interrupt, the frontend is optimized to log the
  message as fast as possible", with messages in an MPSC packet buffer
  ([Zephyr logging documentation](https://docs.zephyrproject.org/latest/services/logging/index.html));
  Trice claims "3 or 7 Assembler instructions (< ~16 clocks) per call",
  "even from interrupt handlers" (its `README.md`). Claims like these are
  measurable.
- **Lost messages under load**: a full buffer either blocks, skips the
  message or overwrites old ones (RTT's default mode is
  `SEGGER_RTT_MODE_NO_BLOCK_SKIP`); defmt-rtt can drop a frame on
  contention (`drop-on-contention`, `defmt-rtt/src/lib.rs`). Which
  happens, and whether it is counted, is part of what a user chooses.

## Candidates

| Library | Lang. | Licence | Newest commit | Version to pin | What it documents about interrupts | Where used |
|---|---|---|---|---|---|---|
| **SEGGER RTT** | C | SEGGER's BSD-style licence with one condition (`LICENSE.md`) | 2026-11-03 | V8.58.0 | A lock for interrupts and tasks: defined by default for GCC and Clang (PRIMASK on Armv6-M, BASEPRI on Armv7-M and Armv8-M Mainline), empty for other compilers unless configured (above) | J-Link users; Nordic's nRF5 SDK ships it (`external/segger_rtt`) |
| **defmt** with **defmt-rtt** (knurling-rs) | Rust | MIT OR Apache-2.0 | 2026-11-23 | defmt 1.2.0, defmt-rtt 1.3.1 | A critical section through the `critical-section` crate, or with `drop-on-contention` no interrupt masking: a frame that meets another one in progress is dropped; targets with compare-and-swap need no critical section (`defmt-rtt/src/lib.rs`) | Embedded Rust |
| **rtt-target** (probe-rs) | Rust | MIT | 2026-07-17 | v0.5.0 | RTT for Rust with formatting on the target; a critical section | Embedded Rust |
| **Trice** (rokath) | C (host tool in Go) | MIT | 2026-11-19 | newest release to be chosen (v2.0.0-beta-4 is the newest tag) | "Trice calls can be used directly inside interrupt handlers"; "< ~16 clocks" per call in its fastest configuration (`README.md`) | – |
| **Zephyr logging** (`subsys/logging`) | C | Apache-2.0 | 2026-11-23 | v4.5.0 | Deferred mode; the frontend "optimized to log the message as fast as possible" since it "can be called in an interrupt"; messages in `mpsc_pbuf` (documentation, above) | Zephyr |
| **Pigweed `pw_log_tokenized`** (Google) | C, C++ | Apache-2.0 | 2026-11-23 | head (no release tags; Pigweed is pinned by commit) | Tokenized log messages: the format string is replaced by a hash at build time | Pigweed users |
| **Percepio TraceRecorder** | C | Apache-2.0 | 2026-11-02 | head `2f9edcbb0c92` (no tags) | RTOS event tracing with a streaming ring buffer (`streamports/RingBuffer`); per-RTOS kernel ports | Percepio Tracealyzer users; kernel ports for bare metal, FreeRTOS, ESP-IDF, ThreadX and Zephyr (`kernelports/`) |
| **RT-Thread `ulog`** (`components/utilities/ulog`) | C | Apache-2.0 | 2026-11-23 | v5.3.0 | An ISR line buffer of its own (`ULOG_USING_ISR_LOG`) and an asynchronous output mode (`ULOG_USING_ASYNC_OUTPUT`) (`ulog.c`) | RT-Thread |
| **EasyLogger** (armink) | C | MIT | 2026-11-05 | 2.2.0 | Runs on several RTOSes and bare metal; asynchronous output mode (`README.md`, in Chinese) | RT-Thread ecosystem |
| rdpoor `ulog` | C | MIT | 2025-02-10 | head `fc3b8c26dc29` | A very small logging front end; nothing about interrupts | – |

Hardware for comparison, not a library: the Cortex-M ITM stimulus ports
over SWO (Cortex-M3 and up; not on the Cortex-M0+ boards).

## What could be proven, and with which tool

- **The contract check on the host model**: the ring buffers' verdict
  (linearisable, every byte once) becomes "every message whole, once, in
  its producer's order", with two producers at two priorities, which the
  check already models for MPSC. The lock macros of RTT and the critical
  section of defmt-rtt map to its interrupt flag.
- **GenMC**: little; the candidates mask interrupts or, for defmt-rtt on
  cores with compare-and-swap, use an atomic flag that a GenMC model
  could check.
- **The decoders** (defmt, Trice, Pigweed) run on the host; they would be
  pinned and run in the toolchain image, never outside it.

## What could be measured on the six boards

- **Operation**: one log call with a fixed format and one 32-bit
  argument, through `time_call` (`a` = the value, `b` = the message
  number), from the main loop and from an interrupt; cycles per call, as
  for a ring-buffer push.
- **Baseline**: a store of the two words into a ring of our own (no
  format, no lock): the cheapest possible record.
- **Stress**: the two-interrupt test as it is, with a new judge: each
  producer logs its own numbered sequence; the reader (on the chip, so
  that the test does not depend on the probe's polling) decodes the
  buffer and checks every message whole, in order per producer, and that
  drops are counted where the library says it counts them. Controls: the
  same library with its lock removed must fail.
- **What the probe reads**: in real use a debug probe drains RTT while
  the firmware runs. The lab's rule of staying off the chip while it
  measures excludes that from the timing; it could be a separate test.
- **Placement**: the method of version 2 applies.
- **First guess of a first series**: about 10 configurations (each
  library with its lock as documented, plus defmt with and without
  `drop-on-contention`) × 8 placements; **about 15 to 25 flash writes**.

## What a filter and a column would be

- Filters: safe from nested interrupts as configured by default, with a
  documented setting, or not; drops counted; works on Cortex-M0+;
  needs a host decoder; licence.
- Columns: cycles per call from an interrupt; longest time with
  interrupts masked per call; bytes on the wire per message; code bytes.

## Effort, in the terms of the step-1 report

- Reused: almost all of the ring-buffer machinery: the two-interrupt
  stress test, the sweep with two interrupts, the contract check's MPSC
  mode, the benchmark, the page's ideas.
- New: the adapter (one call), the judge that decodes each library's
  format (the largest part: a decoder per format, some of which are
  tokenized and need the build's string table), the host decoders in the
  toolchain image.
- The catch: a library's format and its decoder are part of the result;
  a test of RTT's ring alone would be a ring-buffer test again.
