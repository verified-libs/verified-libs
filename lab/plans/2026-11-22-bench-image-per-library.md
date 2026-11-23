# Design: one benchmark image per library (2026-11-22)

**Status: design, a build without boards, pilots on two boards, and the
build, run, record and rebuild tools tried on all six boards (steps 1 to 5
below; step 5 is not finished). Nothing in the published method, firmware
or records is changed by this note: the work is on the branch
`bench-per-lib`.**
The owner asked for it on 2026-11-22; it was on the list for the version
after 1 ([same-image rule](2026-11-22-same-image-rule.md), point 4). It is a
change of method: when it is taken into use, the benchmark gets a new
series and every board is measured again.

## Why

The stress tests and the code-size probe already build one image per
library. The speed benchmark does not: every library of a set (C and C++
single producer, Rust, more than one producer) is in one image. So

- a change in one library moves the others' numbers (lwrb v3.4.0: 29 of
  the 666 means of other libraries left the placement range shown before),
- a new library changes the image of every library in its set, so all of
  them are measured again,
- and under the same-image rule one updated library costs eight images
  per board, not one library's.

## The design

**One image per configuration and placement.** An image holds the timing
harness, the baseline and one configuration of one library, and nothing
about any other library: no table of libraries, no count, no index. The
configuration is chosen by the build (`-D`, as `size.sh` does it today with
`BENCH_ONLY`); the list of configurations lives in a file the images are
not built from. The baseline in every image is a control: it is the same
code at the same place in every image, so its numbers should agree between
all images of a board.

**The sets go away.** Today pxq and the baseline are repeated in the Rust
and the multi-producer image as a reference. With one image each there are
44 configurations on every board (36 single producer, 5 with more than one
producer or consumer, 3 Rust), and four more on the nRF5340 for Nordic's
library and its parts.

**The eight placements stay**: each configuration is built eight times,
with 0, 4, ... 28 bytes between the harness and the library code, as
today. What changes is their meaning. In a shared image the library's
position also depended on its neighbours; in its own image the eight
shifts are the only thing that moves it, and the range shown is the
library's own.

**Bundles with fixed slots.** The images are put side by side in flash
and one is started per reset, as the stress tests do it
(`firmware/common/bundle.py`). New here:

- *A slot table in the repository* (like `libs.lock`): configuration →
  place and size, for all boards at once. Flash is counted in segments of
  256 KB (the smallest board's flash), each with its first 4 KB kept free
  for the boot stub; a slot is a segment number and an offset in it and
  never crosses a segment. A board with 1 MB of flash carries four segments
  per bundle, the SAM D20 one. The table is only ever appended to.
- *Head room.* A slot is 8 KB (16 KB for the two largest), about twice
  what the images need today (3 to 4.2 KB; the two largest 11 KB), in
  units of 4 KB, a flash page on most boards.
- *A library that outgrows its slot* gets new slots at the end of the
  table. Its image changed anyway, so it is measured again anyway; no other
  image moves. The old slots stay empty until a method version tidies up.
- *A boot stub without a table.* The host writes the address of the image
  to start (with a check word) where the selection words are today, and
  resets the chip; the stub checks that the address is a slot boundary in
  flash and that a vector table lies there, and jumps. The stub is the same
  for every bundle of a board and does not change when a library moves.
  (The stress tests' stub holds a table of its images; it is left as it is.)

**Results** are read as today, over the probe from the start of RAM, with
the host off the chip while the image measures. A record is one board and
one image: configuration, placement, slot address, the checksum of the ELF
file and of the bytes in flash, and the baseline's numbers next to the
library's.

**Rust**: one small crate per library (and one for the critical section
they share), in place of today's one crate for all; see the test below.

**Not in this design**: the code locations other than flash (SRAM, CCM,
ITCM; not on the pages today) are left for later; the stress tests' bundles
keep their layout (images in index order); code size is measured as today.

## Step 2: the build without boards (done 2026-11-22)

Made with what the tree has: `make build/size/<configuration>.elf` without
`SIZE=1` links the benchmark with one configuration, normal alignment.
Toolchain image 2026-11-13, tree at `6f27a8b`, no board touched.

Bytes in flash of the 44 images per board (the harness alone is about
2.9 KB):

| Board | smallest | median | largest | over 4 KB |
|---|---|---|---|---|
| nRF5340 | 3176 | 3588 | 10716 | 9 |
| STM32G0B1 | 2960 | 3640 | 11036 | 9 |
| STM32G474 | 3304 | 3712 | 10928 | 10 |
| STM32H723 | 3316 | 3724 | 10960 | 11 |
| SAM D20 | 3020 | 3700 | 11072 | 9 |
| RP2350 | 3288 | 3700 | 10832 | 11 |

The largest RAM use is 5.3 KB, so the SAM D20's 32 KB are enough.

Flash writes for a full benchmark (44 configurations × 8 placements, slots
with at least 25 % head room in the given unit), against 24 per board
today (145 on the six boards):

| Slot unit | Slots | nRF5340 | G0B1 | G474 | H723 | SAM D20 | RP2350 | All |
|---|---|---|---|---|---|---|---|---|
| 4 KB (proposed) | 42 of 8 KB, 2 of 16 KB | 3 | 6 | 6 | 3 | 12 | 1 | 31 |
| 2 KB | 42 of 6 KB, 2 of 14 KB | 3 | 5 | 5 | 3 | 9 | 1 | 26 |
| 1 KB | 5, 6, 13 and 14 KB | 2 | 4 | 4 | 2 | 8 | 1 | 21 |

Four tests on the nRF5340 build (45 images with the empty one):

| Change | ELF checksums changed | Flash bytes changed |
|---|---|---|
| None (built twice) | 0 | 0 |
| lwrb's adapter grows, and one line in the bbqueue adapter | lwrb, and all 4 Rust images | lwrb and bbqueue only |
| One declaration added at the end of the list in `bench.h` | 0 | 0 |
| One entry added to the table in `main.c` | all 45 | 0 |

So:

- A C or C++ library already changes no other image. That part of the
  design needs no new firmware, only the build and run scripts.
- The table of libraries must leave `main.c`: a new library changes no
  byte in flash of the others, but shifts line numbers in the debug
  information of every ELF file.
- Rust needs a crate per library for the same reason: the code in flash of
  the other Rust libraries is unchanged, their debug information is not.
- With both done the ELF checksum is as stable as the bytes in flash. The
  records carry both. Which of the two decides under the same-image rule
  is the owner's to settle (below).

## Step 3: the pilot on the nRF5340 (done 2026-11-22)

On the branch `bench-per-lib`: `firmware/common/benchboot.c` (the boot stub
without a table, 184 bytes), `onebundle.py` (builds the images and the
bundle), `run-one.py` (runs them), `pilot-nrf5340.layout`. Toolchain image
2026-11-05, as version 1's records of this set. 66 images in one bundle:
six configurations (pxq, lwrb, jnk0le, QuantumLeaps LFRB, DNedic lockfree,
FreeRTOS stream buffer) at the eight placements in 8 KB slots, and
placement 0 of three of them at six more addresses up to the end of flash.
The records are on the lab host (`~/lab-runs/perlib-pilot-20261122`), not
in the repository: they are a test of the design, not results.

**Flash writes: 3.** One for the bundle (89 pages of 4 KB, 30 s), one for
the test of a single changed slot (2 pages, 1.4 s), one for the layout
test below (44 pages, 15 s).

| Question | Answer |
|---|---|
| Time per image | 3.9 s (select, reset, 3 s off the probe, read). 44 configurations x 8 placements would take about 23 minutes per board. |
| The same image run three times (66 images, in order, reversed, in order) | All 8448 numbers (mean, smallest, largest) identical. No errors, no run thrown away. |
| The same image at seven addresses (three configurations) | All 128 means identical. The address of a slot does not show. |
| One library changed (a line in lwrb's adapter) | The 14 images of lwrb changed, by both checksums; the other 52 and the boot stub did not. |
| Only the changed image written into its slot | The other 65 images gave the same numbers as before, to the last digit. |
| Numbers against version 1, cache off | The same: the mean of the eight placements agrees to 0.0 % for every number of the six configurations, and the placement ranges are the same (up to 21.5 %). |
| Numbers against version 1, cache on | **Not the same.** See below. |

**With the cache on, the small image is faster and the placements stop
mattering.** Version 1's numbers move by up to 12.9 % with the placement
(pxq, blocks of 16); in the pilot the largest move is under 0.05 %. And the
level is lower: by up to 15.5 % for pxq's block numbers, up to 3.6 % for
lwrb, 1 to 2 % for DNedic lockfree and the FreeRTOS stream buffer, nothing
for jnk0le and the QuantumLeaps buffer. Of the 68 cache-on means of the six
configurations, 32 lie inside version 1's placement range and 36 below it.
The baseline shows the same in its block numbers (44 against 46 to 48
cycles).

**The reason is the layout, tested the same evening** (one more flash
write: nine test images in free flash, each one configuration, with the
library code and `memcpy` moved by padding; run twice, identical).

- lwrb with its adapter, its code and `memcpy` at the offsets they have in
  version 1's shared image gives version 1's numbers: all 14 means exactly
  with the cache off, and within 0.003 cycles with the cache on, at
  placement 0 and at placement 16. So nothing but where the code lies
  separates the two designs.
- It is not the distance. pxq with `memcpy` 4, 8 and 16 KB further away
  gives the numbers of the small image, to 0.002 cycles.
- It is the position within 4 KB. `memcpy` at offset 0x1094, where it
  shares its position in a 4 KB page with the start of the harness, costs 3
  to 5.5 cycles per block call; so does 0x6094, its place in version 1.
  That fits an instruction cache indexed with a period of 4 KB, in which
  code at the same position competes for the same lines; the mechanism
  inside the chip was not looked into further.
- In version 1's image `memcpy` and the libraries lay behind 16 KB of
  other code, at positions that happened to overlap the harness, and the
  placement shifts moved that overlap. In a small image the measured code
  lies in one run of 3 to 4 KB and nothing overlaps at any of the eight
  placements.
- pxq's numbers were not reproduced in full: its block functions are code
  of their own in version 1's image, which the test did not move.

So version 1's cache-on range showed, in part, the cost of sharing cache
lines with other code, at whatever overlap the shared image happened to
have. The new design shows the case without overlap, the same for every
library.

This is the difference "beyond the placement ranges" that this note said
must be explained before anything is built on the design. It is a question
of what the cache-on number should mean, and so one for the owner (below).

**The baseline is not the same in every image.** Its single-item numbers
are (7 and 10 cycles everywhere, as in version 1), its block numbers with
the cache off are not: they take four values (128 to 140 cycles for blocks
of 4), following where `memcpy` lands, and that moves with the size of the
library before it. To make the baseline a true control, `memcpy` gets a
fixed place next to the harness (step 5); then the libraries' block numbers
no longer depend on their own size through `memcpy` either.

**Left on the board:** the pilot bundle, with the changed lwrb image in one
slot, and the nine test images (replaced in step 5 by bundle 0 of the
table). The nRF5340 does not hold a published image until it is flashed
again.

## Step 4: the same on the SAM D20 (done 2026-11-22)

The smallest board: 256 KB of flash (one segment: the boot stub and 31
slots of 8 KB), 32 KB of RAM, a Cortex-M0+ without a cache, driven with
OpenOCD. Nothing had to be made for it: the same stub source (128 bytes
here), builder and runner; `pilot-samd20.layout` has pxq, lwrb and jnk0le
at the eight placements, three more configurations at placement 0, and
lwrb at placement 0 in four more slots up to the end of flash.

**Flash writes: 1** (45 pages of 4 KB, 40 s).

| Question | Answer |
|---|---|
| Time per image | 3.5 s with 3 s off the probe; 44 x 8 images would take about 21 minutes. |
| The same image run three times (31 images) | All 1400 means identical, no errors, no run thrown away. |
| lwrb at five addresses | All 48 means identical. |
| Baseline | Takes the same values as in version 1 for all 20 numbers. |
| Numbers against version 1 | The same level and the same placement ranges (pxq 0.8 %, lwrb 2.7 % in both). Single numbers differ by one or two cycles (at most 2.9 %): of the 136 means of the six configurations 121 lie inside version 1's placement range. Without a cache there is no shift of level as on the nRF5340; what is left is the alignment of the code, which differs between any two images. |

**Left on the board:** the pilot bundle (replaced in step 5 by bundle 0 of
the table).

## Step 5: the tools (2026-11-22, in work)

All of it is in `firmware/nrf5340-rb-bench/` beside version 1's tools, which
are untouched: version 1's four builds give the same bytes as before the
work (all four sets and `size.sh`, compared by checksum).

### The table and the build

| File | What it is |
|---|---|
| `configs.txt` | The configurations: 44 on every board, 4 of Nordic's on the nRF5340 only. |
| `slots.txt` | One line per image: configuration, placement, segment, offset, bytes. 384 lines: 368 slots of 8 KB and 16 of 16 KB, in 13 segments of 256 KB. `oneslots.py` writes it from the measured sizes and only ever adds lines or replaces those of one configuration. |
| `onebuild.sh` | `bash onebuild.sh table [BOARD...]` builds every image of the table and the bundles in the toolchain image (about half a minute per board), `sizes` measures the images for a new table. |
| `onebundle.py` | Builds the images of a board, checks them, and packs them into bundles (one loadable segment per image, so that only the pages that hold an image are written). |
| `run-one.py` | Runs the images of a bundle on a board and writes one run file per image and pass. |
| `onerecords.py` | Makes the records from the run files. |
| `oneverify.sh` | Rebuilds the images of records and compares them. |

A slot is sized from the image at its largest placement plus a reserve of
25 % and rounded up to the unit of 4 KB. The reserve is that large because
many images are 3.7 to 4.4 KB, at the boundary of a unit: without it a few
bytes more in a library would move it to new slots. A new configuration
takes the first free place in the last segment.

One bundle is one flash write. A board gets as many bundles as it needs
segments at a time:

| Board | Bundles | Images | Bundle 0: images, units of 4 KB written |
|---|---|---|---|
| nRF5340 DK | 4 | 384 | 124, 157 |
| NUCLEO-G0B1RE | 6 | 352 | 62, 87 |
| NUCLEO-G474RE | 6 | 352 | 62, 95 |
| NUCLEO-H723ZG | 3 | 352 | 124, 168 |
| SAM D20 Xplained Pro | 12 | 352 | 31, 40 |
| Raspberry Pi Pico 2 | 1 | 352 | 352, 511 |

**A full run of version 2 is 32 flash writes** over the six boards.

### The fixed part

Every image of a board begins with the same code at the same offsets: the
vector table, the timing harness, the C library's memory functions (all of
them in every image, used or not; `memcpy` on a 32-byte boundary), `main`
with the baseline, and the start-up code: 3.2 to 3.3 KB. The configuration's
own code follows, after the placement bytes. `onebundle.py` compares the
symbols of the fixed part between all images of a board and stops at a
difference, and it stops if one of the memory functions, the harness, `main`
or the baseline's block functions is not in it.

What follows from it:

- The baseline is the same code at the same place in every image, so it is
  a control: it has to measure the same in every image of a board.
- `memcpy` does not move with the placement any more. **The placement range
  of version 2 is the range of the library's own code**; in version 1 it
  held `memcpy`'s alignment too. A series with `memcpy` at several places
  could be added as an axis of its own. That is for the owner to decide
  when the method of version 2 is frozen.

### Does the build hold what the design says?

Four tests on the whole table (2144 images, 32 bundles), each by checksum:

1. Built twice: every image and bundle the same.
2. A line added in lwrb's adapter: lwrb's 8 images per board and the bundles
   that hold them changed, nothing else.
3. A declaration added in `bench.h`, which every image includes: no byte in
   flash changed. The ELF file of one configuration changed on the two
   Cortex-M0+ boards, by its debug information. So the checksum of the ELF
   file can change without a changed image, and the bytes in flash decide,
   as the owner decided.
4. A new configuration: 8 lines added to `slots.txt`, no byte of an old
   image changed.

### On the boards

`run-one.py BOARD OUTDIR --bundle N [--flash] [--passes N]`: it compares the
bundle with the flash; if it is there, nothing is written; if not, it stops,
or with `--flash` writes it (counted in its log). Per image it writes the
selection words (the image's address, its complement and a run number),
clears the "done" word of the results, resets the chip, stays off the probe,
and reads the results. A run counts only if the results name this image's
address and this run number. A run that is not finished at the first look
is thrown away and repeated with twice the wait; the longer wait is kept
for that configuration. The tool takes the board's lock of the lab
(`~/vl-dev/<board>.lock`), so two users of one probe cannot meet.

Bundle 0 was written to every board and all its images run twice (the
second pass in reverse order):

| Board | Time to write | Per image | Runs | Without a file | Both passes the same |
|---|---|---|---|---|---|
| nRF5340 DK | 53 s | 4.1 s | 248 | 0 | all 2672 means |
| NUCLEO-G0B1RE | 16 s | 3.7 s | 124 | 0 | all 1368 |
| NUCLEO-G474RE | 14 s | 3.6 s | 124 | 0 | all 1368 |
| NUCLEO-H723ZG | 24 s | 6.6 s | 248 | 0 | all 2672 |
| SAM D20 Xplained Pro | 36 s | 3.6 s | 62 | 0 | all 748 |
| Raspberry Pi Pico 2 | 55 s | 3.8 s, 6.8 s after one slow image | 704 | 0 | all 7520 |

The NUCLEO-H723ZG needs more than 3 s per image, so its wait is 6 s. On
the Pico 2 the selection words lie in the watchdog's scratch registers
(its RAM does not survive the reset used) and the reset is written to the
core directly.

**The baseline found a fault.** On the two Cortex-M0+ boards its block
copies took two values, by placement (blocks of 4 on the NUCLEO-G0B1RE: 119
or 121 cycles). The cause: for Cortex-M0+ the C library has `memcpy` in
another object file than for the other cores, the linker script named only
one, and so `memcpy` lay behind the fixed part and moved by 4 bytes with
every other placement. Both objects are named now, `onebundle.py` checks
that the functions are in the fixed part, and the two boards were written
again. After that the baseline's 20 numbers are the same in every run on
all six boards. The images of the other four boards did not change by a
byte.

**`probe-rs verify` cannot be trusted by its exit code.** Version 0.32.0
exits with 0 when the flash differs from the file; only its text says so.
The first run on the nRF5340 took the pilot's images for the new ones that
way (they lie at the same addresses) and was thrown away. `run-one.py` now
takes a bundle to be on the board only when the output says "Verification
successful", and the OpenOCD stand-in for the SAM D20 says the same words.

**Flash writes in step 5: 8** (one per board, and a second on the
NUCLEO-G0B1RE and the SAM D20 after the `memcpy` fix); with the pilots 12
in this work. Every board now holds bundle 0 of the table and no published
image.

### Records and the rebuild check

`onerecords.py RUNDIR...` makes one record per board and configuration
(`records/bench-v2/<board>/<adapter>.json`, schema `rb-bench/2`): what is
common (board, build, clock, the checksums of the fixed part and the boot
stub), and per placement the image (slot, address, bytes, both checksums)
with every run of it (time, pass, run number, the configuration's numbers
and the baseline's). A configuration gets a record only if all eight
placements were run in every pass and all runs agree on what they ran;
anything else is named and left out. The summary says per board whether the
baseline measured the same in every run. A record with two passes is about
70 KB.

`oneverify.sh RECORD...` (also through `lab/tools/verify-build.sh`, which
hands it the records of version 2) takes the sources of the records' commit,
builds the board's table in the toolchain image the records name, and
compares per record its eight images: the bytes in flash decide, the
address, the fixed part and the boot stub must be the same, and a differing
ELF file is reported. With `VL_TREE=1` it builds the tree at hand instead:
does it still build the images the records were measured from? Tried on
the records of the runs above: all match at their commit; against the tree
after the `memcpy` fix the SAM D20's records differ in every image and in
the fixed part, and the NUCLEO-G474RE's match.

### Still to do in step 5

- `repeat.sh` for version 2.
- "Run only what changed" from the
  [same-image tools](2026-11-22-same-image-tools.md). On a board with large
  erase units (the NUCLEO-H723ZG: 128 KB) a changed image means writing all
  images that share its erase unit again.
- One Rust crate per library.
- How many passes a published run has: both passes gave the same numbers
  to the last digit on every board checked, so two is enough to show it.

### Made on 2026-11-23

- The export check knows version 1 as an archived series
  (`records/archived.json`, `public-export.py`, `verify-build.sh`). The
  entry covers all 215 records that name version 1's commit, the stress
  records and campaign summaries too, because the SAM D20's probe script in
  `firmware/common` is shared by all of them.
- Page data: `gen_libdata.py --bench2` adds `bench2` per board and `speed2`
  per configuration; the comparison page and the MCP server show version 2
  where the data has it and version 1 on request. Without records of
  version 2 nothing changes (the output is the same byte for byte).

### For the owner to decide (from step 5)

Decided 2026-11-23: yes to all four as proposed (version 1 checked against
its own commit; `memcpy`'s place looked at later; two passes; the full run
may start). See [DECISIONS.md](../../DECISIONS.md).

5. **Version 1's records beside version 2.** The same-image rule asks that
   the tree at hand builds a record's image and runs and judges it the same
   way. The tree of version 2 builds version 1's images byte for byte
   (tested), but two host-side files that version 1 uses had to change:
   `size.sh` reads the table of libraries from the file it moved to, and
   the SAM D20's probe stand-in got a `verify` command. By the letter of
   the rule version 1's records could then not be shown from this tree.
   Proposed: version 1 becomes an *archived series*. Its records stay as
   they are, the page labels them "version 1", and they are checked against
   the published commit of version 1, which stays in the public
   repository's history, not against the tree at hand. The export check
   gets a list of archived series with their commit. The alternative is to
   run version 1 once more from the new tree: 145 flash writes for a series
   that is being replaced.
6. **`memcpy` at several places** as an axis of its own: proposed not now;
   to be decided when the method of version 2 is frozen.
7. **Passes of a published run:** proposed two (the second in reverse
   order).
8. **When step 6 runs.** The full run is 26 flash writes more (bundle 0 is
   on every board) and about an hour and a half with two passes, the six
   boards at once. Proposed: soon, so that the page data and the MCP server
   are made against real records; nothing of it is published before all of
   it is in place.

## Step 6: the first full run (2026-11-23)

Started 05:49 UTC on the six boards at once, two passes, from the build at
`f2348f3a0c37`; the last board ended 07:58. Report:
[reports/2026-11-23-bench-v2-first-run.md](../../reports/2026-11-23-bench-v2-first-run.md).

| Board | Bundles | Flash writes | Runs | Without a file | Records | Rebuilt the same |
|---|---|---|---|---|---|---|
| nRF5340 DK | 4 | 3 | 720 | 0 | 45 | 45 |
| NUCLEO-G0B1RE | 6 | 5 | 688 | 0 | 43 | 43 |
| NUCLEO-G474RE | 6 | 5 | 704 | 0 | 44 | 44 |
| NUCLEO-H723ZG | 3 | 2 | 704 | 0 | 44 | 44 |
| SAM D20 Xplained Pro | 12 | 11 | 688 | 0 | 43 | 43 |
| Raspberry Pi Pico 2 H | 1 | 0 | 704 | 0 | 44 | 44 |

26 flash writes, as counted beforehand (38 in the whole work). The smoke
test cost none: bundle 0 was on every board, and the flash step was tried
on bundle 1, which the run needed anyway.

What went wrong, and what follows from it:

- `run-one.py` stopped on the NUCLEO-G0B1RE and the SAM D20 at
  `adapter_lockfree_mpmc`, which has no numbers on a Cortex-M0+ (no
  compare-and-swap): the run file was written, the log line after it could
  not print "none". The smoke test had run two images of bundle 1, not this
  one. The stopped bundle was run again whole without that configuration
  (`--adapter`), with no flash write; the three run files of the stopped
  attempt are kept aside and are in no record. So these two boards have 43
  records, and no record says "not available" for that configuration. The
  log line is to be mended with the next change of the runner, which makes
  a new series (see below).
- **The host side is part of the series.** The records name
  `f2348f3a0c37`; a changed file of the runner under `firmware/` makes them
  differ from the tree in the export check. Tools made after the run
  (page data, MCP server) are therefore outside `firmware/`. A change of
  the runner means running the series again (32 flash writes), or a rule
  that tells measuring files from reporting ones: for the owner.
  **Decided 2026-11-23** (DECISIONS): a fix of the runner or of the two
  record tools is recorded in `records/host-fixes.json` with a control run
  and the records stand; a change of how numbers are read or worked out
  means a new series. The log line was mended that way the same day
  (control: one image per board, no flash write, the records' numbers).
- The Raspberry Pi Pico 2 took 2 h 9 min, the others 45 to 80 min. With
  the 3 s wait six configurations were "not finished" at the first look,
  and the wait then doubled up to 48 s for each of their images. The
  numbers are the same as with a 6 s wait the day before. Next time:
  `--wait 7` for this board.
- A smoke test of a run must run one image of every configuration, not the
  first images of a bundle.

The two differences from version 1 were looked into the same evening
(report, "The two differences from version 1, looked into"): on the
NUCLEO-H723ZG a call to code 4 KB or more away costs 6 to 10 cycles more
(an experiment with 16 images, one flash write; the board now holds those
images, not bundle 2); the Pico 2 number of version 1 came from where the
code lay in one of its three images. For the owner: whether the page shows
a far-call number beside the near one on the Cortex-M7.

**Decided 2026-11-23, evening (DECISIONS, "Every library is measured with
a far call"):** every library lies at least 6144 bytes from its adapter
(`FAR` in the Makefile); the adapter stays at the harness, and code the
compiler puts into the adapter pays no call. What was changed for it:

- Makefile: `FAR`, and the functions of a Rust configuration's adapter are
  named to the linker, so that they lie before the gap like the C ones
  (they lay behind the placement bytes before, which made no difference
  while that was 0 to 28 bytes).
- `onebundle.py` checks every image: each function in the adapter's table
  lies before the gap, and the first code behind it at least `FAR` +
  placement bytes further on. The distance is in the manifests, the run
  files and the records (`far_bytes`).
- `oneslots.py`: a slot's quarter of spare room is counted from the code,
  not from the gap. The slot table is new from the first line (every image
  changed): 384 images in 20 segments, slots of 12 to 20 KB.
- The fixed part is byte for byte the one of the first series on every
  board.
- Built for all six boards without a board, all checks passed. Flash
  writes for the series: nRF5340 DK 5, NUCLEO-G0B1RE 9, NUCLEO-G474RE 9,
  NUCLEO-H723ZG 5, SAM D20 18, Pico 2 2: 48.
- What lies behind the gap differs much between configurations (Pico 2
  build, code bytes): nothing for nine of them (all of it is in the
  adapter), 16 to 300 bytes for a library of headers that keeps a function
  out of line (pxq: the two block functions, 270 bytes), up to 2.9 KB for
  a compiled library.
- The run: bundle 0 on every board first, through every step (flash, run,
  records, rebuild check), then the rest; each configuration is whole in
  one bundle, so a fault in one costs no write of another.

Still open before anything of version 2 is published: the run of the series
with the far call, "run only what changed" with a ledger per image, `repeat.sh` for version 2,
one Rust crate per library, and a dry run of the export with the page.
The steps are in [2026-11-23-ring-buffers-finish.md](2026-11-23-ring-buffers-finish.md).

## The questions the pilot was to answer

- **Does the address of a slot matter?** Every image is linked for its own
  address, so two libraries lie at different places in flash, at the same
  position within a 4 KB page. The pilot puts the same configuration into
  two or more slots and compares; the baseline in every image gives the
  same comparison across the whole run. If the address shows in the
  numbers, the design has to say so on the page or change.
- **The numbers against version 1.** They are expected to differ within
  about the placement ranges shown today. A difference beyond that must be
  explained before anything else is built on the design.
- **Time per image** (select, reset, wait, read): the estimate is a few
  seconds, so about as long per board as today's 24 runs.

## Steps

1. This note.
2. The build without boards (above).
3. Pilot on a board with much flash: a few flash writes, the questions
   above, and "one library changed, no other image changed" on the bundle.
4. The same on the SAM D20 (least flash and RAM).
5. Tools: records, page data, `verify-build.sh`, `repeat.sh`, the MCP
   server, and the open steps of the
   [same-image tools](2026-11-22-same-image-tools.md), made for this
   layout. In work: the build, the run, the records and the rebuild check
   are made and tried on the boards (above).
6. A smoke test of every step, then one full run on the six boards, its
   evaluation and a report. Only with the owner's word, as is publishing.

## For the owner to decide (answered, see the end)

1. **Which checksum decides** that an image is the same: the bytes in
   flash (what the chip runs), or the ELF file with its debug information
   (today's `fw_sha256`). Proposed: the bytes in flash decide, both are
   recorded, and the sources are arranged so that both stay the same.
2. **Slot unit**: 4 KB as proposed (31 writes for a full benchmark and
   room for every library to double), or tighter.
3. **The name of the new series** and whether version 1's numbers stay on
   the page next to it for a time.
4. **What the cache-on number should mean** (from the pilot). In its own
   small image a library runs with no other code on its cache lines: a
   clean number that no neighbour moves and that is the same kind of number
   for every library, but the best case. Options: (a) take it as it is and
   say so on the page; (b) add a second kind of placement that puts the
   library's code and `memcpy` on the harness's cache lines on purpose, and
   show both as a range. Proposed: (a) for the table, and (b) as a later
   addition if readers ask what a crowded cache costs; in an application
   that cost depends on the application's own layout, which no benchmark
   image can stand for.

## The owner's answers (2026-11-22)

1. The bytes in flash decide; both checksums are recorded.
2. 4 KB.
3. Version 1's and version 2's results stand next to each other. The new
   series is version 2.
   Changed by the owner 2026-11-23: the pages show version 2 only; version 1
   is archived and linked from a note per board on what changed and why
   (DECISIONS.md).
4. (a) now: the number as it is, with the page saying what it is. (b),
   placements with other code on the same cache lines, later.

The decision is in [DECISIONS](../../DECISIONS.md).
