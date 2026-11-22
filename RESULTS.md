# Results: embedded ring buffers (all in one place)

> **Status: harness development, not published results.** Numbers are facts
> about the pinned versions, configuration and board below, not general
> rankings. ⚠ marks the project owner's own library; under principle 6 it
> is tested with the same suite as every other library and more (every
> documented mode and topology), and like every result its numbers can be
> repeated outside the project. Defects are reported to
> maintainers first (principle 5) and stay unpublished for 90 days from
> sending.

Updated 2026-11-22. Six boards: nRF5340 DK (application core), Raspberry Pi
Pico 2 (RP2350), NUCLEO-G474RE, NUCLEO-H723ZG, NUCLEO-G0B1RE and SAM D20
Xplained Pro ([method](site/content/method.md)). Compiler:
arm-none-eabi-gcc 14.2.1, `-O2 -DNDEBUG`, newlib-nano; the Rust libraries
with rustc 1.99.1 at the same optimisation level; pinned
[toolchain image](toolchain/README.md). All libraries are fetched at the
commits in [`libs.lock`](firmware/nrf5340-rb-bench/libs.lock), never copied
into this repo. Every number below comes from a result record in
[`records/`](records/README.md); how to check one, with or without a board:
[Reproduce our results](site/content/reproduce.md). The interactive
[comparison](site/content/compare.html) shows the same records with filters,
code size and placement ranges.

## How each column was measured
| Column | Test | Details |
|---|---|---|
| Speed | cycle benchmark with the core's cycle counter, timing in assembly, 1024 calls per scenario, code in flash with the cache or flash accelerator on | [benchmark](firmware/nrf5340-rb-bench/README.md) |
| ISR stress | timer interrupt ↔ main loop on one core (and core 0 ↔ core 1 on the Pico 2), both directions, single bytes, blocks and zero-copy, random seeds and interrupt rates, and the interrupt sweep (one interrupt at every delay in a call); cache on/off, flash/SRAM; gcc -O2 in the runs shown (earlier campaigns also rotated five compiler flag sets); a run counts only if a deliberately broken control buffer is caught | [stress test](firmware/nrf5340-rb-stress/README.md), night reports below |
| GenMC | model check of all thread interleavings under the C11 memory model (RC11), single-byte push/pop between two threads; number of executions explored in brackets. "+ block" means the library's block and zero-copy APIs pass too. Every pass has negative controls (release and acquire made relaxed) that must fail, and do | [GenMC](verify/genmc/README.md) |

## Speed on six boards
Cells: mean cycles per call, 1-byte push / pop · 64-byte block, cycles per
byte (mean of write and read); code in flash, cache or flash accelerator on,
gcc -O2 (night 2026-11-21/22, commit `a7a206190337`). Clocks: nRF5340 64 MHz,
Pico 2 150 MHz, G474 170 MHz, H723 64 MHz, G0B1 64 MHz, SAM D20 48 MHz.
Cycles, not time, so the clocks do not matter; wait states and the memory
system do. Sorted by name;
there is no ranking of ours. ⚠ marks the project owner's own library.

<!-- table:speed -->
| Library | nRF5340 M33 | Pico 2 M33 | G474 M4 | H723 M7 | G0B1 M0+ | SAM D20 M0+ |
|---|---|---|---|---|---|---|
| AndersKaloer Ring-Buffer (C) | 58 / 40 · 16.7 | 44 / 31 · 16.5 | 57 / 41 · 20.1 | 33 / 27 · 9.3 | 73 / 50 · 27.3 | 72 / 48 · 24.4 |
| *Arduino RingBufferN as shipped (C++)* ¹ | 37 / 46 · 48.1 | 33 / 36 · 40.8 | 42 / 39 · 48.4 | 36 / 34 · 26.9 | 81 / 91 · 100.9 | 78 / 87 · 93.5 |
| Arduino SafeRingBufferN (C++) | 53 / 54 · 59.6 | 44 / 44 · 50.3 | 56 / 48 · 60.4 | 58 / 59 · 50.4 | 99 / 113 · 120.9 | 97 / 111 · 114.5 |
| bbqueue (Rust) | 175 / 157 · 5.9 | 121 / 105 · 4.4 | 161 / 139 · 7.1 | 150 / 112 · 5.8 | 270 / 229 · 15.2 | 284 / 240 · 15.4 |
| Contiki-NG ringbuf (C) | 40 / 40 · 46.6 | 33 / 32 · 38.8 | 45 / 42 · 51.9 | 39 / 35 · 28.6 | 61 / 53 · 71.9 | 60 / 52 · 63.0 |
| diffstorm cb (C) | 79 / 72 · 82.1 | 56 / 56 · 62.3 | 72 / 69 · 77.9 | 59 / 73 · 58.0 | 122 / 131 · 141.4 | 114 / 127 · 131.0 |
| DNedic lockfree spsc::RingBuf (C++) | 126 / 126 · 3.5 | 83 / 83 · 2.8 | 98 / 88 · 3.8 | 72 / 70 · 3.4 | 163 / 155 · 12.4 | 167 / 159 · 12.4 |
| ece-mohammad RingBuffer (C) | 93 / 92 · 3.8 | 66 / 64 · 2.9 | 81 / 80 · 4.1 | 57 / 53 · 3.1 | 110 / 109 · 12.4 | 111 / 111 · 12.4 |
| embassy-sync Pipe (Rust) | 222 / 213 · 6.1 | 196 / 189 · 5.4 | 229 / 217 · 6.4 | 114 / 105 · 4.3 | 271 / 252 · 13.6 | 289 / 267 · 13.9 |
| EmbeddedArtistry cbuf basic, single-context (C) | 38 / 37 · 44.1 | 35 / 32 · 39.8 | 40 / 36 · 43.9 | 33 / 29 · 24.9 | 87 / 80 · 98.4 | 84 / 76 · 91.4 |
| EmbeddedArtistry cbuf threadsafe (C) | 53 / 44 · 54.6 | 41 / 34 · 43.8 | 56 / 46 · 58.4 | 38 / 31 · 31.8 | 74 / 60 · 81.9 | 75 / 58 · 73.5 |
| ETL etl::queue, single-context (C++) | 25 / 29 · 33.6 | 26 / 28 · 33.3 | 32 / 34 · 38.9 | 25 / 26 · 19.4 | 46 / 47 · 61.4 | 47 / 48 · 54.5 |
| ETL queue_spsc_atomic (C++) | 24 / 31 · 22.6 | 25 / 26 · 22.3 | 30 / 27 · 23.9 | 33 / 32 · 26.0 | 54 / 51 · 40.0 | 57 / 53 · 37.6 |
| ETL queue_spsc_isr (C++) | 33 / 38 · 27.6 | 34 / 32 · 27.2 | 40 / 45 · 31.9 | 39 / 40 · 28.4 | 73 / 68 · 53.6 | 73 / 68 · 53.2 |
| ETL queue_spsc_locked (C++) | 80 / 80 · 51.7 | 63 / 61 · 50.9 | 79 / 80 · 61.5 | 79 / 77 · 60.5 | 115 / 110 · 92.5 | 108 / 104 · 87.6 |
| FreeRTOS stream buffer (C) | 302 / 252 · 5.3 | 208 / 170 · 4.0 | 347 / 279 · 6.5 | 206 / 150 · 4.5 | 373 / 325 · 13.2 | 359 / 322 · 13.0 |
| heapless spsc::Queue (Rust) | 31 / 37 · 39.7 | 23 / 27 · 31.4 | 35 / 37 · 43.0 | 40 / 35 · 28.0 | 61 / 63 · 73.0 | 66 / 68 · 76.0 |
| jnk0le Ringbuffer (C++) | 17 / 19 · 9.5 | 17 / 17 · 9.4 | 23 / 26 · 9.5 | 30 / 30 · 6.5 | 36 / 42 · 11.8 | 36 / 42 · 11.8 |
| kostyk348 lf_spsc (C) | 82 / 76 · 84.6 | 58 / 55 · 65.3 | 72 / 67 · 79.4 | 58 / 53 · 56.1 | 160 / 156 · 214.6 | 164 / 162 · 227.6 |
| lwrb (C) | 55 / 58 · 4.5 | 40 / 42 · 3.6 | 54 / 57 · 5.2 | 49 / 44 · 3.9 | 65 / 67 · 13.6 | 65 / 69 · 13.7 |
| Mbed CE CircularBuffer (C++) | 69 / 58 · 8.5 | 66 / 53 · 7.5 | 79 / 69 · 9.0 | 66 / 63 · 4.9 | 120 / 103 · 12.2 | 121 / 108 · 12.3 |
| micoring default, single-context (C) | 97 / 98 · 75.4 | 60 / 59 · 50.7 | 78 / 75 · 66.5 | 52 / 55 · 29.0 | 103 / 99 · 91.9 | 102 / 99 · 92.0 |
| micoring SPSC mode (C) | 119 / 123 · 116.4 | 74 / 77 · 75.7 | 98 / 97 · 96.8 | 79 / 71 · 60.0 | 127 / 133 · 131.2 | 127 / 132 · 131.9 |
| moodycamel ReaderWriterQueue (C++) | 51 / 66 · 61.2 | 39 / 47 · 45.9 | 53 / 64 · 62.5 | 54 / 54 · 44.0 | 77 / 81 · 88.6 | 77 / 82 · 83.2 |
| NuttX circbuf (C) | 144 / 123 · 2.9 | 108 / 96 · 2.5 | 123 / 110 · 2.8 | 93 / 83 · 2.7 | 234 / 218 · 11.8 | 233 / 220 · 11.9 |
| polycratia spscring (C++) | 19 / 24 · 8.6 | 19 / 22 · 8.4 | 24 / 28 · 9.5 | 37 / 32 · 5.2 | 39 / 46 · 11.8 | 39 / 49 · 11.9 |
| pxq RingBuffer_PackedState (C++) ⚠ | 17 / 20 · 3.4 | 17 / 18 · 8.3 | 20 / 21 · 3.5 | 17 / 16 · 2.9 | 35 / 38 · 9.3 | 37 / 39 · 9.3 |
| pxq Topology::None, single-context (C++) ⚠ | 25 / 21 · 3.1 | 20 / 19 · 2.5 | 19 / 20 · 3.4 | 23 / 21 · 2.9 | 35 / 38 · 9.3 | 37 / 39 · 9.3 |
| QuantumLeaps LFRB (C) | 50 / 44 · 53.6 | 39 / 36 · 43.8 | 46 / 46 · 53.4 | 47 / 42 · 42.3 | 69 / 61 · 79.9 | 70 / 63 · 74.5 |
| rigtorp SPSCQueue (C++) | 35 / 43 · 41.2 | 27 / 37 · 33.9 | 35 / 49 · 45.5 | 36 / 42 · 29.1 | 52 / 83 · 73.2 | 55 / 82 · 69.7 |
| RIOT tsrb (C) | 49 / 48 · 17.7 | 38 / 37 · 17.4 | 52 / 51 · 19.6 | 55 / 50 · 11.4 | 65 / 64 · 30.1 | 65 / 65 · 25.1 |
| rt-spsc (C++) | 20 / 19 · 26.1 | 21 / 17 · 25.8 | 26 / 24 · 31.9 | 35 / 36 · 28.9 | 45 / 44 · 59.4 | 47 / 46 · 54.5 |
| RT-Thread rt_ringbuffer + interrupt lock (C) | 73 / 52 · 3.4 | 57 / 42 · 2.9 | 73 / 54 · 3.8 | 62 / 54 · 3.4 | 98 / 78 · 12.2 | 96 / 82 · 12.1 |
| *RT-Thread rt_ringbuffer, no lock (C)* ¹ | 56 / 35 · 3.2 | 48 / 33 · 2.7 | 57 / 39 · 3.6 | 39 / 34 · 3.1 | 92 / 70 · 12.1 | 88 / 73 · 12.0 |
| TinyUSB tu_fifo (C) | 141 / 131 · 4.0 | 82 / 85 · 3.1 | 101 / 100 · 4.2 | 66 / 69 · 3.3 | 138 / 131 · 12.4 | 138 / 134 · 12.5 |
| wizard97 + PRIMASK macros (C++) | 37 / 27 · 38.6 | 30 / 26 · 34.3 | 40 / 32 · 43.9 | 51 / 49 · 43.9 | 57 / 61 · 73.9 | 61 / 65 · 71.0 |
| *wizard97 as shipped (C++)* ¹ | 22 / 22 · 28.6 | 18 / 20 · 26.3 | 29 / 25 · 33.4 | 24 / 21 · 16.5 | 41 / 41 · 55.9 | 43 / 41 · 50.5 |
| Zephyr ring_buf (C) | 79 / 74 · 3.1 | 64 / 62 · 2.7 | 79 / 74 · 3.7 | 54 / 50 · 3.1 | 115 / 105 · 10.5 | 115 / 107 · 10.5 |
| Zephyr ring_buf, CONFIG_SMP (C) | 91 / 94 · 3.5 | 72 / 73 · 2.9 | 86 / 83 · 3.9 | 72 / 67 · 3.3 | 129 / 117 · 11.1 | 132 / 123 · 11.2 |

¹ Not interrupt-safe by its own documentation or maintainers; measured for comparison only.

Records (in [`records/bench/`](records/README.md)): `nrf5340-rb-bench-flash-20261121T234544Z.json`, `nrf5340-rb-bench-rust-flash-20261122T001920Z.json`, `rp2350-rb-bench-flash-20261121T234741Z.json`, `rp2350-rb-bench-rust-flash-20261122T005713Z.json`, `stm32g474-rb-bench-flash-20261121T234437Z.json`, `stm32g474-rb-bench-rust-flash-20261122T001919Z.json`, `stm32h723-rb-bench-flash-20261121T234543Z.json`, `stm32h723-rb-bench-rust-flash-20261122T001919Z.json`, `stm32g0b1-rb-bench-flash-20261121T234437Z.json`, `stm32g0b1-rb-bench-rust-flash-20261122T001919Z.json`, `samd20-rb-bench-flash-20261121T234441Z.json`, `samd20-rb-bench-rust-flash-20261122T000532Z.json`.
<!-- /table:speed -->

Notes:
- Where a library's code lies in flash can change a mean by up to 25 % on
  some boards (pxq's ⚠ 64-byte block on the Pico 2: 7.8 to 9.8 cycles per
  byte); 710 of the 1,002 numbers move by 0.05 % or less.
  The comparison page shows the range over eight placements under each
  number, and
  [the 2026-11-14 report](reports/2026-11-14-night-flags-placement.md) and
  `firmware/nrf5340-rb-bench/placement.py` explain how it is measured. Two
  numbers within each other's range are not measurably different. A range
  is a lower bound: another build can land outside it. When lwrb's code
  changed (v3.4.0), 29 of the 666 means of the other C and C++
  configurations landed outside the range shown before, 26 of them on the
  nRF5340 (by up to 5 %), and pxq's ⚠ block number on the Pico 2 went from
  3.5-5.4 to 7.8-9.8 cycles per byte
  ([2026-11-22 report](reports/2026-11-22-lwrb-v3.4.0-rerun.md),
  [2026-11-20 report](reports/2026-11-20-publication-rerun.md)).
- The H723 runs at its reset clock (64 MHz) with reset-default flash wait
  states; the Pico 2 fetches code through its XIP cache from QSPI flash.
- The Cortex-M33 and M7 issue some instruction pairs together, so they can
  need fewer cycles than instructions (`firmware/counter-check`).
- The Rust libraries are linked into the same C firmware and use the C
  library's `memcpy`; with Rust's own memory functions bbqueue and
  embassy-sync Pipe are slower
  ([report](reports/2026-11-13-memcpy-rust.md)).
- The FreeRTOS stream buffer is measured without the scheduler; its cycles
  include the FromISR / task API choice the adapter makes (IPSR).
- "single-context" variants are the libraries' modes for use without an
  interrupt on the other side, measured for comparison; they are not
  interrupt-safe and not counted in the stress results.
- Code-in-SRAM and cache-off numbers for every library are in the records.

## Model checking (GenMC, C11 memory model)
2026-11-08, single-byte push/pop between two threads; "+ block": the block
and zero-copy APIs pass too.

| Library | Result |
|---|---|
| diffstorm cb (`11e05d60`, v1.3) | **pass (636)** [N3] |
| ETL queue_spsc_atomic | **pass (6132) + block** |
| jnk0le Ringbuffer | **pass (6132) + block** |
| kostyk348 lf_spsc | **pass (6132)** |
| lwrb | **pass (7118) + block** |
| micoring (SPSC mode) | **pass (6132) + block** |
| polycratia spscring | **pass (6132) + block** |
| QuantumLeaps LFRB | **pass (7118)** |
| rigtorp SPSCQueue | **pass (5096)** |
| rt-spsc | **pass (6132)** |
| pxq RingBuffer_PackedState ⚠ | not applicable [N1]; see the contract check below |

Libraries without atomics (they rely on a single-core contract, such as
masking interrupts) cannot be judged by the plain C11 check; they are
covered by the one-core contract check.

## One-core contract check
2026-11-16 (commit `7ed89e4`): each library's own code, compiled for the
host, with the interrupt's call made at every instruction of the main
loop's call from every start state of a small buffer, and at every pair
of instructions (two interrupts in one call) from the start states at the
wrap; interrupt masking is modelled. The result of each trial is compared
with an ideal FIFO.
Method: [contract check](verify/contract/README.md).

38 configurations, 7,039,483 trials: **35 pass, 3 fail.** The three that
fail are the variants their own projects do not call interrupt-safe
(wizard97 as shipped, Arduino `RingBufferN` as shipped, RT-Thread
`rt_ringbuffer` without a lock). The 35 include pxq ⚠ in all four
topologies and with reserve/commit, and the Rust libraries. Per
configuration: the contract-check column of the
[comparison](site/content/compare.html).

### Notes per library
- **[N1]** pxq uses `volatile` for its documented contract (ISR ↔ main loop on one
  core). Under the C11 model that is a data race by definition, so it is
  checked against its contract (the one-core contract check), not with the
  plain C11 check.
- **[N2]** AndersKaloer uses plain variables; this build happens to keep a safe store
  order, which the language does not guarantee. Its queue function overwrites
  when full; the adapter checks for space first.
- **[N3]** diffstorm up to `547d0812` had two defects, found by GenMC and a host
  reproducer: the 1-byte overwrite flag was accessed with 32-bit loads/stores,
  so uninitialised padding could turn overwrite mode on (silent data loss),
  and the consumer lacked acquire ordering (matters across cores). The stress
  test passed only because the test object is in zeroed memory. Reported on
  2026-11-08; the maintainer fixed both the same day (`91ae20b`). The row is
  `11e05d60`: GenMC passes, the reproducer gives the correct result, and the
  board stress (single, block, flash and SRAM, 2026-11-09) has 0 errors.
  The maintainer agreed on 2026-11-09 to publication before the 90 days were
  over.
  See [the finding](verify/findings/diffstorm-cb-overwrite-padding/README.md).
- **[N4]** Without user-supplied `RB_ATOMIC_START/END` macros wizard97 is not
  ISR-safe, as its own header warns. With them: 0 errors (wizard97 + PRIMASK
  macros).
- **[N5]** pxq 1.4.0 copies blocks with an element loop instead of `memcpy`. That
  makes the single-byte pop faster (31 → 20 cycles) but 64-byte blocks about
  2.2× slower (3.1 → 6.8 cycles/byte with code in flash, about 3× slower from
  SRAM). The unreleased 1.4.1 (`fix/word-copy`, `01f54417`) uses the loop up
  to 8 bytes and `memcpy` above. It measured 17 / 20 for one byte and 3.0
  cycles/byte at 64 bytes. Which version is faster depends on the C library's
  `memcpy`: with ST's toolchain it is a byte loop. Linked against newlib's
  byte-loop `memcpy` stub (as ST ships it), 1.4.0 is the fastest of the three
  from 16 bytes up (64 bytes, flash -O2: 1.3.2 575 / 575, 1.4.0 465 / 402,
  1.4.1 566 / 564 cycles). See
  [the 2026-11-08 report](reports/2026-11-08-pxq-1.4-night-run.md).
- **[N6]** TinyUSB: 55 valid overnight runs (2026-11-08/09), 25.6 million bytes
  under 114 million interrupts; not in the first two campaigns.
- **[N7]** pxq ⚠: its MPSC, SPMC and MPMC modes mask interrupts, so they are
  for one core; with the producers or consumers on the Pico 2's two cores
  they give errors, and reserve/commit starves (not counted: not a
  documented use; see
  [the validation report](reports/2026-11-17-mp-per-library-validation.md)).
  On the NUCLEO-H723ZG its indices share a cache line with its data; a DMA
  can only use it in non-cacheable memory
  ([DMA report](reports/2026-11-17-dma-producer.md)).

## ISR stress campaigns
Every campaign so far: **no errors in any real library in any valid run**.
The errors are where they are expected: the variants their own projects do
not call interrupt-safe, and on the Pico 2 in two-core mode the single-core
designs whose interrupt lock does nothing against the other core.

Since 2026-11-15 the test runs each library from its own image after its
own reset, with the run's parameters set at run time. The comparison page
and the records show the re-run with lwrb v3.4.0, the first campaign
below. The publication re-run after it is the same method with lwrb
v3.3.0; the campaigns after that used the method before, at earlier
commits.

### Re-run with lwrb v3.4.0 (2026-11-21/22)
lwrb moved to v3.4.0, which adds functions for one byte, and every test
ran again at one commit (`a7a206190337`), as in the publication re-run:
five hours of the ISR stress test per board, gcc -O2, 108 runs on the six
boards, all valid, **no errors in any real library**. The runs per board
are the same as below (9, 9, 27, 13, 8 and 42), and so is what the five
hours did not reach (the zero-copy entries on the nRF5340, the G0B1 and
the SAM D20). The sweep caught every mutant in every sweep run. Three runs
at the fastest interrupt rate starved a slow library on the SAM D20 or
the G0B1, the same libraries as below. lwrb itself: 0 errors in its 108
runs (13 of them with the two sides on the Pico 2's two cores). Details,
the speed numbers against the earlier ones and the flash writes:
[reports/2026-11-22-lwrb-v3.4.0-rerun.md](reports/2026-11-22-lwrb-v3.4.0-rerun.md).

### Publication re-run (night 2026-11-19/20)
Every test again at one commit (`8d8880f4bf78`), five hours of the ISR
stress test per board, gcc -O2: 108 runs on the six boards, all valid,
**no errors in any real library**. 9 runs on the nRF5340 and the G0B1, 27
on the G474, 13 on the H723, 8 on the SAM D20 and 42 on the Pico 2 (13 of
them with the two sides on its two cores; this line said 15 until
2026-11-22, a counting error). The sweep caught every mutant
in every sweep run. Three runs at the fastest interrupt rate starved a
slow library on the SAM D20 or the G0B1 (FreeRTOS stream buffer,
embassy-sync Pipe, NuttX circbuf); such a run is reported and not counted
for that library. The five hours did not reach the zero-copy entries of
the rotation on the nRF5340, the G0B1 and the SAM D20, so the zero-copy
API has stress runs at this commit on the G474, the H723 and the Pico 2
only. Details, the speed numbers against the earlier ones and the flash
writes: [reports/2026-11-20-publication-rerun.md](reports/2026-11-20-publication-rerun.md).

### Five flag sets, Rust libraries, new layout (night 2026-11-13/14)
209 valid runs of 211 on the six boards: **no errors in any real library**,
with five compiler flag sets (`-Os`, `-O3`, `-O2` + LTO, `-O2` + clang and,
new, `-Os` + LTO) and the three Rust libraries (heapless spsc::Queue,
bbqueue, embassy-sync Pipe; 165 to 209 valid runs each, 0 errors). The one
run too slow for the time limit and the one probe failure (retried, passed)
are explained in
[reports/2026-11-14-night-flags-placement.md](reports/2026-11-14-night-flags-placement.md),
with the placement experiment for the Rust and multi-producer sets.

### Interrupt sweep, mutants and wave 4 (night 2026-11-12/13)
The second night on all six boards added three things to the stress test.

- **Interrupt sweep** (modes `sweep`, `sweep-block`, `sweep-dma`): instead of
  interrupts at random times, one interrupt per call at every delay from the
  start of the call, from five fill levels and 256 start positions, so every
  instruction boundary of a call is hit on purpose. After each sweep the
  buffer is drained and the byte count checked (bytes lost, bytes too many).
- **Mutants**: four ring buffers with one deliberate defect each, next to the
  negative control, to show which mode can find which kind of defect. The
  sweep caught every mutant in every run in the directions where its defect
  can show (55 of 55 and 70 of 70 runs). The random modes sometimes miss: one
  mutant was caught in 39 of 89 random single-byte runs, another in 67 of 84
  random block runs in one direction. Two mutants cannot fail in the
  main→interrupt direction on one core; on the Pico 2's two cores they are
  caught in both.
- **Wave 4**: NuttX circbuf, Arduino RingBufferN as shipped (its maintainers
  call it not interrupt-safe; reported, not counted) and Arduino
  SafeRingBufferN: 28 libraries and variants in all.

422 valid runs of 427: **no errors in any real library on any board**. The
errors are where they are expected: the two variants their own projects call
unsafe (wizard97 and Arduino RingBufferN as shipped), in every mode on every
board, and on the Pico 2 in two-core mode the single-core designs whose
interrupt lock does nothing against the other core. Four runs on the nRF5340
were too slow for the time limit (not hung) and one SAM D20 run was invalid
because its control was caught in one direction only. Details, the per-mode
tables and the choice of 256 start positions:
[reports/2026-11-13-night-sweep-mutants-wave4.md](reports/2026-11-13-night-sweep-mutants-wave4.md).

### Stress, first night on all six boards (2026-11-11/12)
502 valid stress runs across the six boards (59 of them SMP on the Pico 2),
4.0 G bytes and 12.6 G interrupts through the 20 pre-wave-3 libraries: **no
errors in any real library**. Only the expected failures showed: wizard97 as
shipped (not ISR-safe by its docs) everywhere, and the single-core designs in
SMP mode. Details, including the clang build failure on the M0+ boards (fixed)
and the configurations where the control is rarely caught on fast cores:
[reports/2026-11-12-night-six-boards.md](reports/2026-11-12-night-six-boards.md).

Earlier campaigns on the nRF5340 alone (2026-11-07 to 09: 101 valid runs,
0 errors in every real library):
[2026-11-07](reports/2026-11-07-overnight-campaign.md),
[2026-11-08](reports/2026-11-08-pxq-1.4-night-run.md).

### Compilers on the STM32 boards (2026-11-12)
The libraries built with Arm GCC 14.2, clang 21.1, and ST's two compilers
from STM32CubeCLT 1.22.0 (local image only, STM32 boards only). ST Arm Clang
generates byte-identical code to upstream clang for these libraries; GNU
Tools for STM32 14.3 measures the same as Arm GCC in all but two cells. ISR
stress with both ST compilers and the Omax preset (27 runs): 0 errors,
control caught. gcc and clang are
within ±4 % on the M4 and M7; on the M0+ clang is 24 % slower because it
turns every atomic load and store on ARMv6-M into a library call. ST's Omax
preset gains 2-6 % over clang `-O3`, still behind gcc `-O3`:
[reports/2026-11-12-compilers-stm32.md](reports/2026-11-12-compilers-stm32.md).
On all six boards (2026-11-16, adding Arm Toolchain for Embedded 23.1 and
the Zephyr SDK's GCC 14.3): Zephyr's GCC measures like Arm GCC, ATfE like
upstream clang, and clang-family code is 2-5 % slower for single bytes on
the M33/M4/M7 and 20-24 % slower on both M0+ boards (atomics as library
calls on ARMv6-M); 0 errors in every run:
[reports/2026-11-16-compilers-six-boards.md](reports/2026-11-16-compilers-six-boards.md).
Five C libraries' `memcpy`/`memmove`/`memset`/`memcmp` (2026-11-17): newlib,
newlib-nano and Zephyr's picolibc copy equally fast on the M33/M4/M7;
on the M0+ Zephyr's picolibc is up to 59 % slower for 64 bytes, LLVM libc
slightly faster, and ATfE's size-built picolibc 3-5 times slower; up to 17
library configurations' block numbers move by more than 5 %:
[reports/2026-11-17-c-libraries.md](reports/2026-11-17-c-libraries.md).

## What the numbers say
- **Single bytes:** on every board pxq, jnk0le, polycratia and rt-spsc are
  among the fastest (17–24 cycles on the nRF5340); the general stream APIs
  (FreeRTOS stream buffer, embassy-sync Pipe, bbqueue) are the
  slowest (about 155–300 there), because one byte goes through several
  calls and `memcpy`. lwrb was among them up to v3.3.0 (218 / 215 there);
  v3.4.0 has functions for one byte (55 / 58).
- **Blocks:** the libraries that copy with `memcpy` (NuttX circbuf, Zephyr
  ring_buf, RT-Thread, DNedic lockfree, ece-mohammad, TinyUSB, lwrb, the
  FreeRTOS stream buffer, Mbed CE, the Rust stream buffers) need 2.5–6
  cycles per byte at 64 bytes on the M4, M7 and M33, about 10–15 on the
  M0+; the ones that copy element by element 6–130.
- **Zero-copy (DMA):** pxq, lwrb, ece-mohammad, TinyUSB, Zephyr ring_buf,
  NuttX circbuf and bbqueue have such an API. Its cost is fixed per transfer,
  independent of the number of bytes.
- **Correctness:** every library that is interrupt-safe in the configuration
  its documentation asks for showed 0 errors in the ISR stress test. The ten
  atomics-based libraries checked with GenMC pass under the C11 memory model
  (diffstorm after its fix), so they are also correct between two cores
  within the test's bounds.
  The diffstorm defects were found by GenMC and a targeted reproducer, not
  by SPSC stress testing, and reported to the maintainer on 2026-11-08.

## Concurrency modes (what each library promises)
All results above are for one producer and one consumer (SPSC). From the
libraries' own documentation (2026-11-07):

| Library | SPSC | More than one producer or consumer |
|---|---|---|
| pxq ⚠ | yes | `Topology::MPSC`, `SPMC`, `MPMC` (interrupts masked around push and/or pop; one core) |
| RIOT tsrb | yes | every operation disables interrupts, so several producers/consumers on one core |
| wizard97 + PRIMASK macros | yes | all public methods atomic (interrupts masked), one core |
| ETL | `queue_spsc_atomic`, `queue_spsc_isr`, `queue_spsc_locked` | `queue_mpmc_mutex`, for threads (a spin lock, so not for interrupts). GenMC with 2 producers + 1 consumer and 1 producer + 2 consumers: **pass**, and a no-lock control fails ([GenMC](verify/genmc/README.md)) |
| lwrb, jnk0le, QP LFRB, ece-mohammad, micoring, diffstorm, rigtorp, polycratia, rt-spsc | yes | no; several say explicitly that two producers corrupt them |
| AndersKaloer, Contiki-NG, Embedded Artistry | no explicit statement | – |

Stress with several producers or consumers on one core
([`rb-mp-stress`](firmware/rb-mp-stress/)): two interrupts at different
priorities, where B preempts A, are the two producers (MPSC) or the two
consumers (SPMC), and the main loop is the other side. On 2026-11-22
on all six boards (the re-run with lwrb v3.4.0, five hours per board), up
to 1 million values per library and run, four interrupt rates; at the two
slowest every run aims the interrupts at the push and pop and records
where they landed. A run is valid when the control was caught in it: 322
of 324 runs ([report](reports/2026-11-22-lwrb-v3.4.0-rerun.md), with the
coverage per board). The publication re-run of 2026-11-19/20 gave the
same counts with the same images
([report](reports/2026-11-20-publication-rerun.md)). The campaign before
it, 13 hours per board with half the slow-rate runs aimed, had 750 valid
runs of 850 and no errors either
([report](reports/2026-11-18-mp-campaign-coverage.md)).

| Library, mode | MPSC | SPMC |
|---|---|---|
| pxq ⚠ `Topology::MPSC` / `SPMC` / `MPMC` (1.5.0) [N7] | **0** errors | **0** errors |
| pxq ⚠ `Topology::MPSC`, reserve/commit (1.5.0) | **0** errors | – |
| RIOT tsrb | **0** errors | **0** errors |
| wizard97 RingBufCPP + PRIMASK macros | **0** errors | **0** errors |
| DNedic lockfree `mpmc::Queue` (not on the Cortex-M0+ boards: it cannot be built there) | **0** errors | **0** errors |
| heapless `mpmc::Queue` (Rust) | **0** errors | **0** errors |
| control: jnk0le (SPSC) used with two producers / consumers | caught in 322 of 324 runs | |

The control was caught in every run with aimed interrupts (156 of 156) and
in 166 of 168 with random ones at the two faster rates; the two where it
was not caught (nRF5340, MPSC, the slower of those two rates, code in
flash) are not counted. The same two entries of the rotation missed it on
2026-11-19/20, with other seeds. In the campaign of 2026-11-17/18 it was caught in 210 of 210
aimed runs and 540 of 640 random ones; the 100 where it was not caught
all had random interrupts at the slower rates, which is why those rates
are aimed now.

Each library is tested only in the modes it documents. ETL
`queue_mpmc_mutex` is not in this test: it locks with a spin lock
(`etl::mutex`, GCC `__sync` builtins), so an interrupt that tries to take
the lock while the code it preempted holds it waits forever on one core.
It is made for threads under an OS, not for interrupts.

## Building bare-metal (first-try usability)
8 of the first 19 configurations needed extra work to build for a
bare-metal Cortex-M33: missing includes in headers, a CubeMX `main.h`, POSIX
`nanosleep`, exceptions required, heap via `operator new`, ISR safety only
via CMake or user macros. Details per library:
[benchmark README](firmware/nrf5340-rb-bench/README.md#building-each-library-bare-metal-first-try-usability).

## First results outside the tables
Run once or on some of the boards; each report says what it covers.

- **Across the two cores of the nRF5340** (application ↔ network core):
  [report](reports/2026-11-17-nrf5340-cross-core.md).
- **DMA as the producer** through the zero-copy API, on the NUCLEO-G474RE
  and NUCLEO-H723ZG (with and without the data cache):
  [report](reports/2026-11-17-dma-producer.md).
- **Other C libraries** (`memcpy` from newlib, picolibc and LLVM libc) on
  all six boards: [report](reports/2026-11-17-c-libraries.md).
- **Four compilers** on all six boards:
  [report](reports/2026-11-16-compilers-six-boards.md).
- **Nordic `nrf_ringbuf`** (nRF5 SDK 17.1.1; its licence allows Nordic
  chips only, so nRF5340 only): on the comparison page.

## Not covered yet
- At the published commit: ISR stress runs of the zero-copy API on the
  nRF5340, the G0B1 and the SAM D20, and runs with the code in SRAM on the
  nRF5340 and the G0B1 (the five hours of the re-run did not reach them;
  earlier campaigns had them).
- DMA as the producer on the other four boards; vendor toolchains other
  than ST's.
- Model checking of the lock-free multi-producer queues (DNedic and
  heapless `mpmc`) between threads or cores.
- More candidates from the [candidate list](candidates/ringbuffers-embedded.md),
  in the order given there.
- Repetitions outside the project, of every library (the owner's pxq, ⚠,
  included).
