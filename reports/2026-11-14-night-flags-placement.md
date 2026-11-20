# Night campaign with five compiler flag sets, Rust libraries and placement (2026-11-13/14)

Stress campaign on all six boards (`lab/tools/night-all.sh`, commit
`9db3c96`), five boards from 21:53 to about 06:00 UTC, the Pico 2 from 22:52
UTC (it finished its validation first). New since the campaign of
2026-11-12/13:

- **the new code layout** (`9898830`): the timing harness and the adapters
  come first in flash, so a change elsewhere no longer moves them;
- **the Rust libraries** in the stress test: heapless spsc::Queue, bbqueue
  and embassy-sync Pipe, linked into the same firmware as the C libraries;
- **a fifth compiler flag set, `-Os` with LTO** (the size build with
  link-time optimisation that many products ship), next to `-Os`, `-O3`,
  `-O2` with LTO and `-O2` with clang.

**No errors in any real library in any valid run, on any board**: 209 valid
runs of 211, about 20 G bytes and 10.6 G interrupts through the libraries.
The errors are where they are expected, as in the nights before: the
variants their own projects do not call interrupt-safe (wizard97 and
Arduino RingBufferN as shipped, RT-Thread rt_ringbuffer without a lock) on
every board, and on the Pico 2 in two-core mode the single-core designs
whose interrupt lock does nothing against the other core.

## Per board

| Board | Runs | Valid | Did not finish | Too slow (time limit) | Retries | Power cycles | Errors in real libraries |
|---|---|---|---|---|---|---|---|
| nRF5340 DK | 17 | 16 | 0 | 1 | 0 | 0 | 0 |
| NUCLEO-G0B1RE | 19 | 19 | 0 | 0 | 0 | 0 | 0 |
| NUCLEO-G474RE | 63 | 62 | 1 | 0 | 1 | 1 | 0 |
| NUCLEO-H723ZG | 33 | 33 | 0 | 0 | 0 | 0 | 0 |
| SAM D20 Xplained Pro | 11 | 11 | 0 | 0 | 0 | 0 | 0 |
| Raspberry Pi Pico 2 | 68 | 68 | 0 | 0 | 0 | 0 | 0 |

- nRF5340: `sweep-block` with the cache off at `-Os` was too slow for the
  time limit (exit 4), the same configuration as the night before; it is
  not hung, and the campaign neither retried nor power-cycled.
- NUCLEO-G474RE: one run could not read its results from the board ("probe
  failure"); the campaign power-cycled the board and the retry passed.
- No run was invalid: the negative control was caught in every run that
  finished.

## Compiler flag sets

Runs that finished with the real libraries error-free and the control
caught, all boards:

| Flags | Runs |
|---|---|
| `-Os` | 44 of 45 (the nRF5340 run that was too slow) |
| `-O3` | 44 of 45 (the G474 probe failure; the retry passed) |
| `-O2` + LTO | 42 of 42 |
| `-O2` + clang | 40 of 40 |
| `-Os` + LTO | 39 of 39 |

Before the campaign every flag set was built for all six boards, and
`-Os` + LTO, `-O2` + LTO and clang were run once in `single` and `sweep`
mode on every board (36 runs, all passed). With LTO the compiler sees the
library and the code that calls it at once and may inline and reorder
across what was a call; that is where a missing barrier would show. None
did.

## The Rust libraries

| Library | Valid runs (all modes) | Errors |
|---|---|---|
| heapless spsc::Queue | 165 | 0 |
| bbqueue | 209 | 0 |
| embassy-sync Pipe | 165 | 0 |

Including the interrupt sweep (51 to 62 runs each) and two-core runs on the
Pico 2 (26 each). bbqueue has more runs because it also has a zero-copy
API, so it is in the `dma` and `sweep-dma` runs too.

## Mutants

As the night before: the interrupt sweep caught every mutant in every run in
the directions where its defect can show; the random modes sometimes miss
("drain re-reads head" in 24 of 45 random single-byte runs, "full test
misses the wrap" in 32 of 43 random block runs in the main→interrupt
direction). On the Pico 2's two cores every mutant was caught in both
directions in every run.

## Placement of the Rust and multi-producer sets

The placement experiment (`SHIFT=0..28`, all library code moved by up to 28
bytes, see the comparison page) was run for the Rust and multi-producer
benchmark sets on five boards (80 runs), and for the SPSC set on the Pico 2.

- Most means do not move at all: the median spread of the one-byte means is
  0.0 % on every board in both sets.
- The exception is embassy-sync Pipe on the NUCLEO-G474RE: its one-byte
  write and read take 190 to 235 and 174 to 217 cycles depending on where
  the code lies (24 %). On the NUCLEO-H723ZG bbqueue's one-byte write moves
  by 4 %, and some block figures by up to 14 % (pxq Topology MPSC/MPMC
  64-byte blocks, RIOT tsrb on the G0B1).
- The Pico 2 is the steadiest board for the SPSC set: median 0.0 %, largest
  1.7 %, 72 of 74 one-byte means within 1 % (other boards: largest 4.9 % to
  28.9 %).

The comparison page shows placement ranges for the SPSC set on all six
boards now; the ranges of the Rust and multi-producer sets are in
`placement-rust-20261113.json` and `placement-mp-20261113.json` on the lab
host and not yet on the page.
