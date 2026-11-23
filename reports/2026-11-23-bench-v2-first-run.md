# Benchmark version 2: the first full run (2026-11-23)

Version 2 of the benchmark gives every configuration a firmware image of
its own ([plan](../lab/plans/2026-11-22-bench-image-per-library.md),
DECISIONS 2026-11-22). This is its first full run: six boards, every
configuration at eight placements, two passes, from the build at
`f2348f3a0c37`. It started 2026-11-23 05:49 UTC and the last board ended
07:58. Nothing of it is published; version 1's numbers are the ones on the
site.

## Result

- **263 records** (`records/bench-v2/<board>/<adapter>.json`), each with
  eight images and two runs of each: 4208 runs, none without a run file.
- **Every record was rebuilt** from its commit in the toolchain image it
  names, with no board: the bytes in flash, the address, the fixed part and
  the boot stub of all 2104 images are the same (`oneverify.sh`, 263 of
  263).
- **The two passes agree.** Of 45 216 means measured in both passes, one
  differs: 221.400 against 221.249 cycles (one configuration, one
  placement, blocks of 4 bytes, on the Pico 2). All others are the same to
  the last digit.
- **The baseline** (the same code at the same place in every image of a
  board) gave the same 20 numbers in every run on five boards. On the
  NUCLEO-H723ZG one of the 20 has two values, 10.014 and 10.024 cycles:
  the first of its 1024 calls takes 35 cycles in the images of two
  configurations, in both passes.
- **26 flash writes**, as counted before the run.

| Board | Bundles | Flash writes | Runs | Records | Time |
|---|---|---|---|---|---|
| nRF5340 DK | 4 | 3 | 720 | 45 | 56 min |
| NUCLEO-G0B1RE | 6 | 5 | 688 | 43 | 72 min |
| NUCLEO-G474RE | 6 | 5 | 704 | 44 | 45 min |
| NUCLEO-H723ZG | 3 | 2 | 704 | 44 | 79 min |
| SAM D20 Xplained Pro | 12 | 11 | 688 | 43 | 73 min |
| Raspberry Pi Pico 2 H | 1 | 0 | 704 | 44 | 129 min |

The times of the G0B1 and the SAM D20 include about 25 min in which their
run stood still (below).

## Against version 1

Push, pop and block of the 37 or 38 configurations of the comparison page,
version 1 at placement 0 against version 2 at placement 0. "Ranges
overlap": the lowest-to-highest ranges over the eight placements of the two
versions share a value.

| Board | Numbers | The same | Ranges overlap | Median of v2 / v1 | Lowest to highest ratio |
|---|---|---|---|---|---|
| nRF5340 DK | 114 | 58 | 80 | 1.000 | 0.75 to 1.01 |
| NUCLEO-G0B1RE | 111 | 99 | 111 | 1.000 | 0.98 to 1.02 |
| NUCLEO-G474RE | 111 | 76 | 103 | 1.000 | 0.80 to 1.01 |
| NUCLEO-H723ZG | 111 | 8 | 16 | 0.865 | 0.60 to 1.15 |
| SAM D20 Xplained Pro | 111 | 70 | 109 | 1.000 | 0.95 to 1.02 |
| Raspberry Pi Pico 2 H | 111 | 61 | 94 | 1.000 | 0.30 to 1.02 |

- On the cores without a cache or branch predictor (G0B1, SAM D20, G474)
  the two versions give the same numbers, or numbers inside each other's
  placement ranges, for nearly every configuration. Where version 1 had a
  wide range (embassy-sync Pipe and the block copies on the G474), version
  2 sits at its fast end and no longer moves.
- In version 2 the ranges are narrow: a configuration's image moved by 4
  to 28 bytes mostly measures the same.
- **NUCLEO-H723ZG (Cortex-M7): version 2 is lower for 32 of 37
  configurations**, by 3 to 17 cycles per push or pop, mostly whole cycles, with
  the cache on and with it off (lwrb push: 49 to 38 with the cache on, 142
  to 100 with it off). The baseline is the same in both versions, and so
  are four configurations (pxq, jnk0le, two of ETL).
  One is higher (FreeRTOS stream buffer, 206 to 221). **The cause is the
  distance between a call and the code it calls** (next section): on this
  core a call to code about 4 KB or more away costs 6 to 10 cycles more
  than a call to code nearby. In version 1 a library lay about 14 KB from
  its adapter; in version 2 it lies right behind it.
- **Pico 2: one number moved by a factor of three**: pxq's 64-byte block,
  8.27 cycles per byte in version 1 (7.82 to 9.78 over the placements),
  2.51 in version 2 at every placement. Every other number on this board
  is within 2 %. pxq is the project owner's library, so this one is not to
  be shown before its cause is known. **The cause is very likely where the
  code lay in the one image of version 1** (next section): two other
  images of version 1, from the same commit, measured 2.51 as well.
- nRF5340: TinyUSB tu_fifo is 25 % (push) and 17 % (pop) lower in version
  2; in version 1 it had the widest placement range on this board.

## The two differences from version 1, looked into (2026-11-23, evening)

### NUCLEO-H723ZG: a far call costs 6 to 10 cycles

What was compared first, without the board: the image of version 1,
rebuilt from its record, and the images of version 2. The machine code of
the adapters and the libraries is the same instruction for instruction, the
stack starts at the same address, and both versions are stable when the
code moves by 4 to 28 bytes. What differs is the distance: in version 1
the adapters lie behind the harness and the libraries about 14 KB further
on (lwrb: the call from the adapter to `lwrb_write_byte` spans 14 812
bytes); in version 2 the library lies right behind its adapter (96 bytes).
The configurations with no difference between the versions are the ones
whose adapter lay near the harness in version 1 and calls nothing else.

Then on the board: 16 images of version 2 with the library moved away from
its adapter by a chosen number of bytes ("placement"; the layout mode of
`onebundle.py`), everything else byte for byte the same, the fixed part
the one of the records. Two passes, 32 runs, every number the same in both
passes, baseline 10.014/9.02 in every run. Cycles per call, single push /
pop:

| Configuration | Library moved by | Cache on | Cache off |
|---|---|---|---|
| lwrb | 0, 256, 384, 448, 512, 1024, 2048 bytes | 38.04 / 34.03 | 100.0 / 100.0 |
| lwrb | 4096 | 47.04 / 44.03 | 140.0 / 126.0 |
| lwrb | 8192 | 47.04 / 44.03 | 140.0 / 126.0 |
| lwrb | 14 716 (the distance of version 1) | 47.04 / 44.03 | 139.0 / 128.0 |
| AndersKaloer | 0, 448 | 26.05 / 20.04 | 90.1 / 87.0 |
| AndersKaloer | 15 396 (the distance of version 1) | 33.06 / 27.04 | 120.0 / 111.0 |
| Contiki-NG | 0 | 25.05 / 21.03 | 85.0 / 87.0 |
| Contiki-NG | 4096 | 33.05 / 27.03 | 126.0 / 112.0 |
| Contiki-NG | 14 296 (the distance of version 1) | 33.05 / 28.03 | 126.0 / 94.0 |

- The step lies between 2048 and 4096 bytes and is the same from there
  on: 6 to 10 cycles per call with the cache on, mostly 24 to 41 with it
  off.
- It is not a 4 KB page boundary: at 448 bytes the library function
  starts in the next 4 KB of flash and nothing changes.
- lwrb at the distance of version 1 gives 47.04; version 1 measured 47 to
  49 over its placements. AndersKaloer: 33.06, version 1 33. So the
  distance explains the difference where the adapter lay near the harness.
  Contiki-NG gives 33.05 where version 1 had 38.56: in version 1 its
  adapter lay 4.6 KB from the harness as well, a second far call, which
  this experiment does not make.
- Contiki-NG's 64-byte block, which is 64 calls of one byte: 1492 to 2004
  cycles, 8 per call.
- Why a far call costs more on this core was not looked into (the branch
  predictor of the Cortex-M7 is the first suspect). The other five boards
  show nothing like it.
- FreeRTOS stream buffer, the one configuration that is higher in version
  2, is the one whose numbers follow the placement in version 2 (221 and
  193 at alternate placements; version 1: 206). Not looked into further.

What it means for the numbers: on the Cortex-M7 version 2 measures a
library that lies next to its caller. In an application the library lies
where the linker puts it, and each call across more than a few KB costs
the 6 to 10 cycles more that version 1 happened to include, once or twice
per operation depending on the library. Both are true numbers of the same
code. This is one more part of "the number is the best case" (DECISIONS
2026-11-22, point 4), and whether the page should show the far number
beside the near one on this core is for the owner to decide.

Cost: one flash write on the NUCLEO-H723ZG. The board now holds the
experiment's images, not bundle 2 of the series (which is written again
with the next run there, one write). Run files: lab host,
`~/lab-runs/h7dist-20261123`. The layout:

```
adapter_lwrb 0 0x8001000 8192
adapter_lwrb 256 0x8003000 8192
adapter_lwrb 384 0x8005000 8192
adapter_lwrb 448 0x8007000 8192
adapter_lwrb 512 0x8009000 8192
adapter_lwrb 1024 0x800b000 8192
adapter_lwrb 2048 0x800d000 8192
adapter_lwrb 4096 0x800f000 12288
adapter_lwrb 8192 0x8012000 16384
adapter_lwrb 14716 0x8016000 20480
adapter_anders 0 0x801b000 8192
adapter_anders 448 0x801d000 8192
adapter_anders 15396 0x801f000 20480
adapter_contiki 0 0x8024000 8192
adapter_contiki 4096 0x8026000 12288
adapter_contiki 14296 0x8029000 20480
```

### Pico 2: pxq's 64-byte block

No board was used for this one, and no experiment was made for pxq alone.

Version 1 measured this configuration in three images on 2026-11-22, all
from the same commit: the image with the single-context and SPSC
configurations (the one the page's number comes from), the image with the
modes for more producers or consumers, and the image with the Rust
libraries. The 64-byte block, cycles per call, write / read:

| Image of version 1 | Placement 0 | Over the eight placements |
|---|---|---|
| SPSC set | 742 / 316 | 688 to 886 / 313 to 371 |
| MP set | 167 / 154 | the same at all eight |
| Rust set | 167 / 154 | the same at all eight |
| Version 2 | 167 / 154 | the same at all eight |

So version 1 itself has the number of version 2, twice, and the page's
8.27 per byte is (742 + 316) / 128 from the one image that differs. The
machine code of the block functions is the same in the three images
(rebuilt from the records); their addresses are not:

| | SPSC set | MP set |
|---|---|---|
| `timed` and `stat_add` (harness, between the timed calls) | 0x10000120 to 0x1000019f | the same |
| pxq `push_n` | 0x10004130 to 0x100041b5 | 0x10001248 to 0x100012cd |
| pxq `pop_n` | 0x100041b6 to 0x1000423f | 0x100012ce to 0x10001357 |
| `memcpy` | 0x10006108 to 0x100061f3 | 0x10001924 to 0x10001a0f |

The RP2350 runs its code from external flash through a cache that is, by
its datasheet, 16 KB and two-way: code 8 KB apart competes for the same
two places. In the SPSC image `push_n`, `memcpy` and the harness code that
runs between two timed calls lie 16 KB and 24 KB apart, at the same
offsets (0x130 to 0x19f): three users of two places, so every timed call
has to fetch some of its code from the flash again. `pop_n` shares less
of that range, and its number is less raised. In the MP image, and in
every image of version 2 (they are smaller than 8 KB behind the harness),
no three of them meet. That fits in direction and in size, but it is a
reading of the addresses, not an experiment.

What it means: the 8.27 of version 1 is a number of where the code lay in
one image, not of the library; the same holds for any code on this board
once an image is larger than the cache's 8 KB per way, and version 2
cannot show it. For the page, the number of version 2 has the same
footing as every other number there.

## What went wrong

- The runner stopped on the G0B1 and the SAM D20 at a configuration that
  has no numbers on a Cortex-M0+ (DNedic lockfree mpmc::Queue: no
  compare-and-swap): its log line could not print them. The run file was
  written first. The bundle was run again whole without that
  configuration and without a flash write. These two boards have 43
  records, and none for that configuration.
- On the Pico 2 six configurations were not finished 3 s after the reset;
  the runner then doubles the wait for all images of such a configuration,
  up to 48 s. The numbers are the same as with a 6 s wait the day before.
- The smoke test before the run tried the first two images of a bundle,
  not one image of every configuration, and so did not meet the first
  point.

## What a record of version 2 holds

`bench_commit`, the toolchain image and its contents, the pinned library
commits, the checksums of the fixed part and the boot stub, and per
placement the image's address, size and checksums and every run of it
(time, pass, wait, all scenarios with the cache on and off, and the
baseline measured in the same run). `lab/tools/verify-build.sh` rebuilds
the images of a record and compares them.
