# MP stress test: where the interrupts land, random vs aimed (prototype)

2026-11-17, NUCLEO-G474RE (Cortex-M4F, 170 MHz), rb-mp-stress built with
`-DCOVERAGE=1` (a prototype build flag; the default image is byte-identical
to the one before the change, checked). Owner's go the same day, after the
question why the control is often not caught at the slow timer rates
(prescaler 3 and 4): making the control easier to catch would hide that
signal, so instead measure how well the test reaches each library's code,
and try aiming the interrupts at it.

## What was measured

- **Coverage.** Every interrupt records the address it interrupted (the PC
  the core stacked), per library and interrupt (main.c `vl_cov`, a hash
  table of 4096 entries; none overflowed). `cov_report.py` maps each address
  to the library's instructions with the image's line info (code inlined
  from a library header counts as the library's), and counts per
  *instruction boundary*: how often an interrupt landed exactly there.
  Boundaries where interrupts are masked (after `cpsid i` / a saved PRIMASK,
  followed along every path, nested saves included, plus the one boundary
  right after the unmasking instruction, which the core never takes: seen
  as 0 there and everything one instruction later) are not counted: no
  interrupt can land there in any test. A basic block with at least one
  interrupt in it was executed; boundaries in blocks without any are listed
  apart (possibly never executed in this test, e.g. a retry path).
- **Aimed interrupts.** Besides the timers, the main loop arms SysTick
  before each of its push/pop with a random delay of 1-160 cycles, and
  SysTick (highest priority) then pends interrupt A or B; interrupt A arms it
  the same way for B before its own push/pop (B preempting A inside an
  operation is the producer/producer resp. consumer/consumer race).
- Prescaler 3 (the rate where the control is often missed), 300 000 values
  per library, the same seeds for random and aimed; one run each.

## Results

Share of interrupts that landed in the library's code, boundaries
interrupted at least 10 times out of those in executed blocks, and the
median count per boundary:

MPSC (two interrupts produce, main consumes)

| Library | In library code | Boundaries >= 10x | Median per boundary |
|---|---|---|---|
| pxq MPSC | 4.1 % -> 7.4 % | 15/18 -> 14/16 | 308 -> 2988 |
| pxq MPMC | 2.0 % -> 4.1 % | 4/5 -> 5/5 | 172 -> 11020 |
| RIOT tsrb | 8.9 % -> 23.3 % | 23/23 -> 23/23 | 1688 -> 11157 |
| wizard97 + PRIMASK | 3.3 % -> 16.2 % | 10/12 -> 11/12 | 859 -> 9769 |
| DNedic lockfree mpmc | 6.9 % -> 17.0 % | 32/33 -> 34/35 | 228 -> 3941 |
| heapless mpmc (Rust) | 10.0 % -> 26.2 % | 65/94 -> 90/121 | 126 -> 2712 |
| pxq MPSC reserve/commit | 6.4 % -> 26.3 % | 51/55 -> 50/53 | 166 -> 2634 |
| control (jnk0le SPSC) | 2.0 % -> 3.7 % | 15/22 -> 17/20 | 184 -> 2799 |

SPMC (main produces, two interrupts consume)

| Library | In library code | Boundaries >= 10x | Median per boundary |
|---|---|---|---|
| pxq SPMC | 4.7 % -> 6.8 % | 15/16 -> 13/14 | 2146 -> 3270 |
| pxq MPMC | 2.2 % -> 3.7 % | 5/5 -> 5/5 | 2154 -> 10463 |
| RIOT tsrb | 9.8 % -> 21.4 % | 20/23 -> 23/23 | 1435 -> 10573 |
| wizard97 + PRIMASK | 7.5 % -> 13.4 % | 10/12 -> 9/10 | 1426 -> 9981 |
| DNedic lockfree mpmc | 6.6 % -> 15.8 % | 26/35 -> 33/33 | 139 -> 3823 |
| heapless mpmc (Rust) | 10.2 % -> 24.3 % | 56/94 -> 90/119 | 25 -> 2610 |
| control (jnk0le SPSC) | 2.1 % -> 3.7 % | 12/20 -> 17/20 | 112 -> 2983 |

Control (errors / lost+duplicated): MPSC 1413/1418 random -> 10196/10709
aimed; SPMC 0/885 -> 119/11737. Every library in its documented mode was
error-free in all four runs.

## Reading

- With random timer interrupts only 2-10 % of the interrupts land in the
  code under test; the rest land in the test's own loop. Aimed, the share
  is 2-4 times higher and the median count per boundary 2-20 times higher
  (more where the operation is short compared to the timer period), in
  the same run time.
- The libraries that mask interrupts (pxq, RIOT tsrb, wizard97 +
  PRIMASK) have few boundaries where an interrupt can land at all; that is
  their design, and the table counts only those. The lock-free ones
  (DNedic, heapless) have many more, and there aiming matters most:
  heapless had 56 of 94 boundaries hit 10 times or more at random, 90 of
  119 aimed, and fewer blocks never interrupted (102 -> 75-77 boundaries;
  the rest are likely retry paths that need a real collision).
- The number per library is a measure the page could show: "every
  interruptible boundary of push/pop interrupted at least N times", per
  board, independent of the control.

## Limits of the prototype

- One board, one rate, one run per setting; the window (160 cycles) is
  fixed, not fitted to each library's operation length.
- Recording costs a few dozen cycles per interrupt, so the timing differs
  slightly from the campaign image.
- Aimed runs shift the balance (interrupt B pushes or pops about two
  thirds of the values).
- The prototype builds for the STM32 boards (TIM2/TIM3 IRQ numbers) and
  ran on the G474 only. The nRF5340 and RP2350 need their timers' IRQ
  numbers; on the M0+ boards (G0B1, SAM D20) SysTick also serves as the
  cycle counter, so aiming there must be checked or done another way.
- The table is read over the debug port (one image of all libraries per
  start, `PER_LIB=0`); for the campaigns it would go into the UART dump.

Records, tables and images: `~/lab-runs/cov-proto-20261117/` on lib-lab1
(`*.cov.txt`, `*.elf`, `*.cov.json`, `report1.txt`).

## Port to all boards and one library per reset (same day, later)

The owner approved putting aimed runs into the campaigns (half of the
prescaler 3/4 runs, coverage in every report) once the measurement ran on
every board and with one library per reset. Changes:

- Timer IRQ numbers for the nRF5340 (TIMER0/1), RP2350 (PWM wrap 0/1) and
  SAM D20 (TC0/TC2). On the M0+ boards (G0B1, SAM D20) board_init leaves
  SysTick running as the cycle counter of time_call(), which this test
  does not use; the first try there never aimed (the "already armed"
  check: 0 aims), so aim_init now stops it.
- One library per reset (`PER_LIB=1`, the campaign way): the aim settings
  are run parameters in the "go" line (`cov_aim`, `cov_window`,
  `cov_seed`); after "dump" the host sends "dump2" for the table
  (common/vls_uart.h `VLS_DUMP2`, common/uart_host.py `VLS_DUMP2=1`).
  run.sh keeps one table per library with that library's image
  (`<record>.cov.<n>.txt`, `elf/<sha256>.elf`, `<record>.cov.list`).
  Images without COVERAGE stay byte-identical (checked on all six boards).
- cov_report.py reads the per-library tables; RP2350 addresses (8 hex
  digits, which objdump prints unindented) were not parsed before.
- campaign.sh: `COVERAGE=1` by default, recording in the prescaler 3/4 runs
  only (`cov_off` per run: at prescaler 1 the recording, some dozens of
  cycles per interrupt, starved the SAM D20's main loop in a smoke test;
  at prescaler 3 it adds about 3 % interrupts per value there), aimed runs
  as above (which ones
  alternates per pass of the rotation), cov_report.py over all records at
  the end; summarize.py lists aimed runs apart and adds a coverage table.

Check on five more boards, one library per reset from the shared bundle
(`IMAGES=combined`), prescaler 3, 50 000 values per library, the same
seeds for random and aimed, one run each; the libraries other than the
control, random -> aimed:

| Board | Mode | In library code (range over libraries) | Median per boundary (range) | Control: errors + lost/dup |
|---|---|---|---|---|
| nRF5340 | MPSC | 1.0-9.1 % -> 1.6-29.6 % | 18-416 -> 434-1288 | 0 -> 2,306 |
| nRF5340 | SPMC | 1.1-10.0 % -> 1.6-24.1 % | 15-378 -> 433-1008 | 277 -> 1,359 |
| RP2350 | MPSC | 1.8-11.5 % -> 1.7-23.4 % | 22-439 -> 430-579 | 0 -> 2,308 |
| RP2350 | SPMC | 1.7-13.1 % -> 1.9-20.2 % | 144-435 -> 442-734 | 295 -> 1,119 |
| SAM D20 | MPSC | 9.6-21.0 % -> 18.6-52.7 % | 12-476 -> 45-1204 | 537 -> 6,283 |
| SAM D20 | SPMC | 11.5-21.6 % -> 18.2-53.9 % | 8-361 -> 44-1231 | 269 -> 3,261 |
| G0B1 | MPSC | 5.9-13.5 % -> 14.9-42.7 % | 13-154 -> 141-1446 | 514 -> 5,094 |
| G0B1 | SPMC | 7.7-14.0 % -> 16.2-44.4 % | 4-261 -> 142-2071 | 316 -> 2,695 |
| H723 | MPSC | 8.2-16.6 % -> 10.7-26.3 % | 1-26 -> 15-1071 | 538 -> 5,895 |
| H723 | SPMC | 7.5-17.7 % -> 8.4-23.8 % | 1-50 -> 82-576 | 311 -> 2,830 |

The same picture as on the G474: aimed, more interrupts land in the
library code and every library's median count per boundary rises,
mostly by 2-20x (the lowest medians, at the random runs' weakest
libraries, by more). Random runs missed the MPSC control on the nRF5340 and RP2350;
aimed runs caught it on every board, 2-10 times as often. Every library in
its documented mode was error-free in all 20 runs. Per-library tables:
`~/lab-runs/cov-port-20261117/` (`report-*.txt`, `table.py`).
