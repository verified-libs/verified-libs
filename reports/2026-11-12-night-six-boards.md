# Night campaign on six boards (2026-11-11/12)

The first stress campaign on all six boards at once (`lab/tools/night-all.sh`,
each board with its own copy of the repo at commit `37592d5`). The campaign
ran from 23:13 to about 07:15 UTC. Each run rotates the mode (single bytes,
blocks, DMA, and on the Pico 2 the SMP modes with the other side on core 1),
the timer prescaler, cache, code location and build flags (`-O2`, `-Os`,
`-O3`, `-O2` + LTO, `-O2` + clang). The libraries are the 20 from before wave 3;
the wave-3 libraries (Zephyr ring_buf, lockfree, ETL locked, FreeRTOS stream
buffer) came after this commit. Records are in
`~/lab-runs/overnight-20261111T2313*-<board>/` on lib-lab1.

**No errors in any real library in any valid run, on any board.** The only
errors are where they are expected: wizard97 as shipped (not ISR-safe by its
own documentation) on every board, and on the Pico 2 in SMP mode the
single-core designs (ETL queue_spsc_isr, wizard97 with and without PRIMASK
macros), whose interrupt locks do nothing against the other core. Every
multicore-documented library had 0 errors in its 59 valid SMP runs.

| Board | Runs | Valid | Did not finish | Invalid (control not caught) | Bytes moved, real libraries | Interrupts |
|---|---|---|---|---|---|---|
| nRF5340 DK (M33, 64 MHz) | 53 | 52 | 1 | 0 | 407 M | 1.90 G |
| NUCLEO-G0B1RE (M0+, 64 MHz) | 97 | 68 | 24 | 5 | 538 M | 1.79 G |
| NUCLEO-G474RE (M4, 170 MHz) | 144 | 134 | 0 | 10 | 1 070 M | 2.99 G |
| NUCLEO-H723ZG (M7, 64 MHz) | 94 | 78 | 1 | 15 | 638 M | 1.32 G |
| SAM D20 Xplained Pro (M0+, 48 MHz) | 61 | 42 | 15 | 4 | 341 M | 1.71 G |
| Pico 2 (RP2350 M33, 150 MHz; incl. 59 SMP runs) | 146 | 128 | 0 | 18 | 1 022 M | 2.84 G |

## Runs that did not finish
- **G0B1 (24) and SAM D20 (15): every `-O2` + clang run failed to build.**
  clang treats atomics on ARMv6-M as not lock-free and turns each atomic load
  and store into a call to `__atomic_load_4` / `__atomic_store_4`, which the
  toolchain does not ship for Cortex-M (gcc inlines the same operations).
  Fixed in `98e307b`: `firmware/common/armv6m_atomic.c`, built with gcc,
  implements those calls with gcc's own inline atomics of the same order
  (LDR/STR plus DMB), linked only for clang on Cortex-M0+. Read-modify-write
  calls stay undefined, so a library that needs one still fails to link (there
  is no LDREX/STREX on ARMv6-M). The smoke test before the campaign had no
  clang run on an M0+ board, which is why this showed up only now.
- The SAM D20 records of this campaign describe the clock as "DFLL48M open
  loop"; that text in `run.sh` was stale. The firmware ran closed loop on
  XOSC32K (48.005 MHz), as it has since the 48 MHz switch. Text fixed.
- nRF5340 and H723: one run each did not finish; the retry after a power cycle
  was valid.

## Runs where the control was not caught
A run counts only if the negative control (a ring with a deliberate ordering
bug) shows errors. The invalid runs cluster in two configurations:

| Configuration | nRF5340 | G0B1 | G474 | H723 | SAM D20 | Pico 2 |
|---|---|---|---|---|---|---|
| single bytes, prescaler 4 | 0/7 | 5/13 | 10/19 | 10/12 | 3/8 | 10/10 |
| blocks, prescaler 2 | 0/7 | 0/13 | 0/20 | 5/12 | 0/8 | 8/10 |

At prescaler 4 the interrupt period is 2 560-10 688 cycles. Each interrupt
moves one byte, and the main loop keeps up easily (interrupts = transfers in
these runs), so the control's window, a few cycles long, is rarely hit in
100 000 transfers. On the slower cores (nRF5340 with its flash path, the
M0+ boards) it is hit more often. The libraries are not at fault, and the
runs are correctly excluded. But these configurations add almost no valid
data on the Pico 2 and the H723. Options, for a decision:
1. more transfers for these configurations on fast cores (the run gets
   longer: at prescaler 4 on the Pico 2, about 4x for 400 000);
2. drop them from the rotation on boards where they are mostly invalid;
3. keep them as they are, as a record that slow interrupt rates stress less.

## Model checking done the same night
- GenMC: DNedic lockfree 3.0.1 `mpmc::Queue` (2 producers + 1 consumer, and
  1 + 2, at capacity 4) passes; release and acquire mutants fail; full and
  empty reached. The full suite has 130 checks, all as expected (`496aa36`).
- Zephyr ring_buf (CONFIG_SMP code) and lockfree spsc::RingBuf, including their
  block and zero-copy APIs, pass with mutants failing (`8892384`).

## Next
- Board runs of the wave-3 libraries (bench, stress, MP), and RP2350 SMP MP.
- A clang check on the M0+ boards with the fix (a few runs, before the next
  campaign).
