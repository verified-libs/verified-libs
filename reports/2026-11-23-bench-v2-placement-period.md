# Benchmark version 2: numbers that follow the placement (2026-11-23)

The two earlier reports of the day noted one configuration on the
NUCLEO-H723ZG (Cortex-M7) whose numbers go up and down from one placement
to the next: the FreeRTOS stream buffer. This is what the records and the
images say about it. No board was used and no flash written.

## What is seen

FreeRTOS stream buffer, NUCLEO-H723ZG, cache on, cycles per call
(`records/bench-v2/stm32h723/adapter_freertos_sb.json`; both passes give
the same number at every placement):

| Placement (bytes) | 0 | 4 | 8 | 12 | 16 | 20 | 24 | 28 |
|---|---|---|---|---|---|---|---|---|
| single push | 224.2 | 196.9 | 225.2 | 196.9 | 224.2 | 196.9 | 224.2 | 196.9 |
| single pop | 172.1 | 155.6 | 173.1 | 156.6 | 172.1 | 155.6 | 172.1 | 155.6 |
| burst of 16, push | 132.8 | 133.9 | 132.8 | 133.9 | 132.8 | 133.9 | 132.8 | 133.9 |
| block of 16, push | 225.0 | 218.4 | 225.1 | 218.2 | 225.0 | 218.2 | 225.0 | 218.2 |

The number depends on the placement modulo 8 bytes and on nothing else:
placements 8 bytes apart agree to within one cycle.

## What moves between two placements

Read from the images of placement 0 and 4 (symbol tables and
disassembly): the fixed part (timing code, `memcpy`, the baseline), the
adapter, and everything in RAM are at the same offsets and addresses in
both. Only the library's own code, behind the gap, lies 4 bytes further
on: 27 symbols, from `prvWriteBytesToBuffer` to the end of the image. So
the only thing that differs between a 224 and a 197 is whether the
library's instructions lie at an address that is 0 or 4 modulo 8.

## It is not this library

The same pattern, alike at placements 8 bytes apart and different at 4,
is in many numbers of the series. Counted over every record: numbers
where the two groups of four placements each agree within 0.5 cycles and
differ from each other by more than 1 cycle and more than 1 %.

| Board | Numbers | With the pattern | Largest |
|---|---|---|---|
| nRF5340 DK | 968 | 0 | |
| NUCLEO-G0B1RE | 932 | 177 | 256 cycles on a block of 64 (4 per byte) |
| NUCLEO-G474RE | 940 | 141 | 701 cycles on a block of 64, cache off |
| NUCLEO-H723ZG, cache on | 470 | 48 | 27.5 cycles: the single push above |
| SAM D20 Xplained Pro | 932 | 12 | 4 cycles |
| Pico 2 | 940 | 0 | |

On the Cortex-M7 it is mostly the block operations of other libraries
(16 to 23 cycles on a block of 16 in the largest cases, about one cycle
per byte for a library that copies byte by byte). The stream buffer has
the largest single-call case because one single push runs some 200
cycles of library code in several functions; a library whose push is 20
cycles has little that can move.

A likely reading, not an experiment and not checked against the
reference manuals: on the STM32G0 and G4 the flash is read in words of 8
bytes, and the Cortex-M7 takes its instructions over a 64-bit bus, so
where an instruction or a loop lies within 8 bytes can cost a cycle each
time it runs. The nRF5340 and the Pico 2, which show nothing, run their
code through a cache with longer lines. Which instructions of the stream
buffer pay was not looked into: it would explain one number of one
library, and the placements already measure what it costs.

## What it means for the pages

Nothing changes. This is the effect the eight placements are there to
show: the pages give the value at placement 0 and the range over all
placements, and for this configuration the range is wide (197 to 225 for
the single push). The number of a library on these boards is good to
within its range, not to the last cycle, whichever library it is.

A board experiment was not needed: the eight placements are the
experiment, four images at each of the two positions, and they agree.
