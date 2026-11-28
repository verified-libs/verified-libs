# Publication re-run: every test at one commit, all six boards (night 2026-11-19/20)

Everything version 1 shows is measured again here, at one commit:
`8d8880f4bf78` (tag `v1-method-freeze-2`). The public repository has no
history, so a record must name sources the reader has (DECISIONS
2026-11-16). `lab/tools/publication-rerun.sh 5 5` ran on each board, one
step after the other: code size, the three benchmark sets (SPSC,
multi-producer, Rust) at eight code placements, five hours of the ISR
stress test and five hours of the two-interrupt stress test (MPSC/SPMC).
Start 2026-11-19 17:33 UTC; the last board finished 2026-11-20 06:44 UTC.

## Result

- **ISR stress test: no errors in any real library in any run** (108 runs
  on six boards, all valid).
- **Two-interrupt test: no errors in any library in its documented mode in
  any valid run** (324 runs on six boards, 322 valid).
- The control was caught in every run of the ISR test and in 322 of the
  324 runs of the two-interrupt test. The two where it was not caught are
  left out: both on the nRF5340, MPSC mode, random interrupts at
  prescaler 2.
- No step failed: no benchmark image needed a second try, no stress run
  was repeated, no board was power-cycled.
- The speed numbers are the earlier ones within their placement ranges.
- Not reached in the five hours: the zero-copy (DMA API) entries of the
  ISR rotation on the nRF5340, the G0B1 and the SAM D20 (see below).

## Benchmarks

24 images per board (three sets at placement shifts 0, 4, ..., 28), 25 on
the nRF5340 (Nordic's nrf_ringbuf, one placement). All 145 ran at the
first try. The records are in `records/bench/` (151 with the six code-size
records).

Against the numbers shown before (records of 2026-11-13 to 2026-11-16,
made at other commits), seven rows of the speed table changed. Five moved
by one cycle per call or by at most 0.5 cycles per byte. The other two:

- embassy-sync Pipe on the G474: 229 / 217 cycles for push / pop, before
  190 / 174. Both pairs lie in its placement range (190-235 / 174-217).
- bbqueue on the H723: push 150 cycles, before 144. Its range was 144-150
  before; in this build it is 150 at all eight placements.

In both cases the code landed at other addresses in this build, and the
speed of that library on that board depends on them. This is what the
placement ranges on the comparison page are for. The bbqueue case also
shows their limit: eight placements of one build need not show the whole
range, so a range is a lower bound on how much a number can move.

Placement, over the 1,002 numbers that have a range: 703 do not move at
all over the eight placements and 826 move by 1 % or less. The largest
ranges:

| Number | Range over eight placements | |
|---|---|---|
| pxq RingBuffer_PackedState ⚠, 64-byte block, Pico 2 | 3.53-5.44 cycles per byte | 54 % |
| embassy-sync Pipe, pop, G474 | 174-217 cycles | 25 % |
| embassy-sync Pipe, push, G474 | 190-235 cycles | 24 % |
| pxq ⚠ (both variants), 64-byte block, G474 | 2.88-3.55 cycles per byte | 23 % |
| lwrb, push, G474 | 180-211 cycles | 17 % |

The first row was 4.49-5.83 (30 %) in the records of 2026-11-13. On the
Pico 2 pxq's block write also varies from call to call within one run (147
to 762 cycles for 64 bytes at shift 0; lwrb in the same image: 208 to 249
at every placement), so its mean there is the least stable number in the
table. The cause has not been looked into; the Pico 2 fetches its code
through the XIP cache from QSPI flash. Version 1 shows the number with its
range.

## ISR stress test

`firmware/nrf5340-rb-stress/overnight.sh`, five hours per board, each
library from its own image after its own reset, gcc -O2 (one flag set, as
the reference campaign of 2026-11-15; the campaigns of 2026-11-13/14 and
before rotated five). The rotation has 17 entries and is run grouped by
code location, flash first, to save flash writes. A run is valid when the
control (a deliberately broken buffer) was caught in it.

| Board | Runs | Valid | Modes (runs) | Code | Cache or accelerator |
|---|---|---|---|---|---|
| nRF5340 DK | 9 | 9 | single 3, block 2, sweep 2, sweep-block 2 | flash 9 | on 6, off 3 |
| NUCLEO-G0B1RE | 9 | 9 | single 3, block 2, sweep 2, sweep-block 2 | flash 9 | on 6, off 3 |
| NUCLEO-G474RE | 27 | 27 | single 7, block 6, dma 4, sweep 4, sweep-block 5, sweep-dma 1 | flash 22, SRAM 5 | on 21, off 6 |
| NUCLEO-H723ZG | 13 | 13 | single 4, block 2, dma 2, sweep 2, sweep-block 2, sweep-dma 1 | flash 12, SRAM 1 | on 10, off 3 |
| SAM D20 Xplained Pro | 8 | 8 | single 3, block 2, sweep 2, sweep-block 1 | flash 8 | on 6, off 2 |
| Pico 2 | 42 | 42 | single 7, block 6, dma 6, sweep 4, sweep-block 4, sweep-dma 2; two cores: smp 4, smp-block 4, sweep-smp 2, sweep-smp-block 3 | flash 32, SRAM 10 | on 42 |
| All | 108 | 108 | | | |

Summed over the library rows of the six campaign reports: 11.6 × 10⁹ bytes
through the buffers under 6.4 × 10⁹ interrupts.

**Errors only where they are expected**, as in every campaign before:

- on every board, the three variants their own projects do not call
  interrupt-safe: wizard97 as shipped, Arduino RingBufferN as shipped and
  RT-Thread rt_ringbuffer without a lock;
- on the Pico 2 with the two sides on two cores, the nine single-core
  designs (their interrupt lock does nothing against the other core).

**Mutants** (four buffers with one deliberate defect each): the sweep
caught every mutant in every sweep run in the directions where its defect
can show, on all six boards. With random interrupts the weak spots of
the earlier campaigns are the same: "drain re-reads head" was caught in 11
of 27 single-byte runs, and "full test misses the wrap" in the direction
main to interrupt in 16 of 20 block runs.

**Starved parts.** At the fastest interrupt rate (prescaler 0) the main
loop of a slow library on a slow core can get too little time to finish
next to the interrupt load. The test reports that as starved, not as an
error and not as a pass. It happened in three runs:

| Run | Starved |
|---|---|
| SAM D20, single, `samd20-rb-stress-single-20261119T194650Z` | FreeRTOS stream buffer (interrupt to main), embassy-sync Pipe (main to interrupt), NuttX circbuf (both directions) |
| SAM D20, block, `samd20-rb-stress-block-20261119T201617Z` | NuttX circbuf (interrupt to main) |
| G0B1, single, `stm32g0b1-rb-stress-single-20261119T192422Z` | NuttX circbuf (both directions) |

The site data now leaves such a run out of that library's run count and
says so next to the number (`site/gen_libdata.py`, `"not_counted"`; on the
comparison page "1 run not counted: starved by the interrupt load").
Before this night's evaluation it was counted with the passes, which is
not what the method page says. The per-mode summary in `records/campaign/`
(what `repeat.sh` compares a repetition with) is made by the frozen
summarizer and still counts the run for the library; it has no errors
either way.

**Not reached.** The rotation's zero-copy entries (dma, sweep-dma) come
after the flash entries for single bytes and blocks. On the three slowest
boards a run of all libraries takes about 40 minutes, so five hours ended
before them: the re-run has no ISR stress run of the zero-copy API on the
nRF5340, the G0B1 and the SAM D20. It has them on the G474 (5), the H723
(3) and the Pico 2 (8). The same three boards have no run from SRAM
(the SAM D20 has no such image at all). The comparison page shows what
was run; nothing from earlier commits is mixed in.

## Two-interrupt test (MPSC / SPMC)

`firmware/rb-mp-stress/campaign.sh`, five hours per board, each library
from its own image, 1,000,000 values per library and run at prescaler 1
and 2, fewer at 3 and 4. New in this campaign:
every run at prescaler 3 and 4 uses aimed interrupts, and random
interrupts are used at prescaler 1 and 2 only. In the campaign of
2026-11-17/18 half the slow-rate runs were random, and 100 of 850 runs
were invalid because the control was not caught in them
([report](2026-11-18-mp-campaign-coverage.md)). This time two of 324 are:
runs 2 and 10 on the nRF5340, both MPSC with random interrupts at
prescaler 2 and the code in flash. With aimed interrupts the control was
caught in every run on every board. So random interrupts can miss the
control at prescaler 2 as well: on the nRF5340 in 2 of its 13 random runs
(2 of the 3 at that rate in MPSC mode, the two with the code in flash).
On the other five boards they caught it in all 155.

| Board | Runs | Valid | Control caught, random interrupts | Control caught, aimed |
|---|---|---|---|---|
| nRF5340 DK | 25 | 23 | 11 of 13 | 12 of 12 |
| NUCLEO-G0B1RE | 43 | 43 | 23 of 23 | 20 of 20 |
| NUCLEO-G474RE | 83 | 83 | 43 of 43 | 40 of 40 |
| NUCLEO-H723ZG | 57 | 57 | 29 of 29 | 28 of 28 |
| SAM D20 Xplained Pro | 27 | 27 | 15 of 15 | 12 of 12 |
| Pico 2 | 89 | 89 | 45 of 45 | 44 of 44 |
| All | 324 | 322 | 166 of 168 | 156 of 156 |

No run failed (probe, serial port or build).

Coverage of the aimed runs (the control left out), as in the report of
2026-11-18: the share of interrupts that landed in the library's code, the
median number of interrupts per instruction boundary where one can land,
and how many of those boundaries were interrupted at least 10 times in the
weakest run. Range over the libraries:

| Board | In library code | Median per boundary | Boundaries >= 10x, weakest run | Rows with every boundary >= 10x |
|---|---|---|---|---|
| nRF5340 DK | 8.5-31.9 % | 3,728-9,754 | 63-97 % | 0 of 13 |
| NUCLEO-G0B1RE | 14.3-42.7 % | 710-15,912 | 83-100 % | 8 of 11 |
| NUCLEO-G474RE | 4.2-27.8 % | 2,239-18,566 | 68-100 % | 4 of 13 |
| NUCLEO-H723ZG | 9.0-26.1 % | 58-5,620 | 55-100 % | 1 of 13 |
| SAM D20 Xplained Pro | 18.2-53.6 % | 429-12,296 | 87-100 % | 8 of 11 |
| Pico 2 | 1.9-24.5 % | 1,732-7,861 | 63-100 % | 2 of 13 |

Per library, the valid runs of all boards together:

| Library | Mode | Boards | Runs | Values | Interrupts | Errors | Lost + duplicated | Both interrupts hit full/empty |
|---|---|---|---|---|---|---|---|---|
| DNedic lockfree mpmc::Queue | mpsc | 4 | 127 | 89,808,771 | 644,699,381 | 0 | 0 | 127 of 127 |
| RIOT tsrb | mpsc | 6 | 163 | 116,211,181 | 894,191,360 | 0 | 0 | 163 of 163 |
| control: jnk0le Ringbuffer (SPSC) with two producers | mpsc | 6 | 163 | 116,210,140 | 802,117,116 | 2,094,513 | 2,183,959 | 163 of 163 |
| heapless mpmc::Queue (Rust) | mpsc | 6 | 163 | 116,212,406 | 959,814,847 | 0 | 0 | 163 of 163 |
| pxq ⚠ RingBuffer_PackedState, Topology::MPMC | mpsc | 6 | 163 | 116,210,676 | 824,830,151 | 0 | 0 | 163 of 163 |
| pxq ⚠ RingBuffer_PackedState, Topology::MPSC | mpsc | 6 | 163 | 116,209,943 | 823,145,306 | 0 | 0 | 163 of 163 |
| pxq ⚠ RingBuffer_PackedState, Topology::MPSC, reserve/commit | mpsc | 6 | 163 | 116,214,773 | 1,118,214,677 | 0 | 0 | 163 of 163 |
| wizard97 + PRIMASK macros | mpsc | 6 | 163 | 116,211,142 | 838,601,297 | 0 | 0 | 163 of 163 |
| DNedic lockfree mpmc::Queue | spmc | 4 | 125 | 87,800,102 | 589,698,111 | 0 | 0 | 125 of 125 |
| RIOT tsrb | spmc | 6 | 159 | 112,200,071 | 805,528,315 | 0 | 0 | 159 of 159 |
| control: jnk0le Ringbuffer (SPSC) with two consumers | spmc | 6 | 159 | 112,200,085 | 732,920,154 | 10,585 | 2,135,602 | 159 of 159 |
| heapless mpmc::Queue (Rust) | spmc | 6 | 159 | 112,200,127 | 865,413,527 | 0 | 0 | 159 of 159 |
| pxq ⚠ RingBuffer_PackedState, Topology::MPMC | spmc | 6 | 159 | 112,200,062 | 754,620,539 | 0 | 0 | 159 of 159 |
| pxq ⚠ RingBuffer_PackedState, Topology::SPMC | spmc | 6 | 159 | 112,200,059 | 754,026,068 | 0 | 0 | 159 of 159 |
| wizard97 + PRIMASK macros | spmc | 6 | 159 | 112,200,060 | 763,724,677 | 0 | 0 | 159 of 159 |

DNedic's queue cannot be built for the two Cortex-M0+ boards. pxq ⚠ has
five of the rows because it documents that many modes; every documented
mode is tested ([conflict of interest](../site/content/method.md)).

Reading, as on 2026-11-18: a pass here means "no error while interrupts
arrived at these points this often", and the table says how often. The
thinnest coverage is again heapless `mpmc::Queue` on the H723 (median 58
hits per boundary in MPSC mode), and on the nRF5340 no row has every
boundary interrupted 10 times in its weakest run (63 to 97 % of them); the
per-library aim window that would raise both is not part of version 1.

## What the evaluation changed in the tools

No firmware and no campaign script changed (frozen until the export).
Changed on the host side only:

- `site/collect_records.py` takes, from a campaign directory, the first
  run that passed of each mode (for the two-interrupt test: of each mode
  with random and with aimed interrupts), not every record. `records/stress/`
  then holds 58 records (11 MB; the sweep records carry every sweep
  position); the campaign reports here and `records/campaign/` cover all
  runs.
- `site/gen_libdata.py` and the comparison page: starved runs, as above.
- `lab/tools/public-export.py`, `verify-build.sh` and `repeat.sh`: a record
  names the commit it was made at, and the records can only be committed
  after it. The export now lists the commits whose test sources (firmware,
  board table, the two scripts the tests call) are byte for byte those of
  the exported tree (`SAME_SOURCES`), the two tools accept a record from
  any of them, and the export refuses a tree with a record from any other
  commit.

## Flash writes

Counted from the benchmark logs and from the bundle checksums in the
stress records (a bundle is written when its checksum changes; some of
those writes change only part of the flash).

| Board | Benchmark images | Bundles | Sum |
|---|---|---|---|
| nRF5340 DK | 25 | 3 | 28 |
| NUCLEO-G0B1RE | 24 | 3 | 27 |
| NUCLEO-G474RE | 24 | 5 | 29 |
| NUCLEO-H723ZG | 24 | 4 | 28 |
| SAM D20 Xplained Pro | 24 | 17 | 41 |
| Pico 2 | 24 | 7 | 31 |

The SAM D20's 256 KB hold the ISR test's libraries only as two bundles
written in turn, so each of its eight ISR runs wrote the flash twice.
Before this: a first start at the tag `v1-method-freeze` was stopped after
four minutes (its code-size step failed on every board; fixed in the
script, see the plan) and had written 12 benchmark images (two per board,
three on the SAM D20, one on the Pico 2), and the smoke tests of the
driver wrote the G474 about five times.

## Records

- `records/bench/`: every benchmark and code-size record of the night.
- `records/stress/`: one run per board and mode, see above.
- `records/campaign/`: the per-mode summary of each board's ISR campaign.
- The campaign directories with every run stay on the lab host
  (`~/lab-runs/overnight-20261119T*` and `mp-campaign-2026112*`).

*2026-11-28: links to documents that are no longer published were removed or now point to the change log.*
