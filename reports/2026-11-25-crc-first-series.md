# CRC: the first board series (proposal, run and checks)

This report has two parts, in the order they were written. The sections up
to "Decisions for the owner" are the proposal for the series, written
before any board was used. The sections from "The first series, run" on
are the series itself (2026-11-24 to 2026-11-25, six boards), the checks
of its numbers and the repetition from an exported tree; the numbers of
the [results page](../site/content/results-crc.md) rest on those.

## The proposal (2026-11-24, before the series)

Step 6 of the [plan for CRC as the second kind](../lab/plans/2026-11-24-crc-kind.md),
written from the host work of the night of 2026-11-24 ([`kinds/crc`](../kinds/crc/README.md)).
**A proposal for the owner's decision, not a result.** No board was used
for this part and no flash was written; every count in it is computed from
cross builds and is marked as an estimate where it is one.

## What was done this night

| Step | State |
|---|---|
| 1. Interface and reference | Done. The reference passes the catalogue's check value and residue for all three CRCs and agrees with Python's `zlib.crc32` and `binascii.crc_hqx` on 2000 messages each; four builds with one parameter wrong are each caught. |
| 2. First configurations | Done: 20 configurations from 8 libraries, the reference as the baseline ([table](../kinds/crc/README.md#step-2-the-first-configurations)). |
| 3. Host test | Done. Every configuration passes check, every length 0–300 at every alignment 0–7, every split into two calls, and every (state, byte) of a step for CRC-8 and CRC-16; plain and with the address and undefined-behaviour sanitizers; the Rust adapter also under Miri. Five deliberately broken adapters are each caught by the check made for them. |
| 3b. CBMC for CRC-32 | Done ([README](../kinds/crc/README.md#step-3b-crc-32-for-every-input-cbmc)): proven for crcany's table of 256, Zephyr's table of 16 and crcany's bitwise code; of zlib's braided code the proof (24 bytes) covers the last block, where the braids are combined, and the bytes before and after it, not the loop over the earlier blocks and its tables, which the host test runs with the boards' 4-byte words (tested, not proven). crcany's slicing by 4 did not finish within 60 minutes as one proof; its 4-byte step is proven in two parts instead (CBMC: the result depends only on CRC XOR word; then all 2^32 values computed). Every control fails, as it must. |
| 4. Cross builds, sizes, loops | Done for M0+, M4, M7, M33 at -Os and -O2. |
| 5. One image | Built for the NUCLEO-G474RE (crcany `crc32iso_hdlc_word`), not flashed, against the unchanged board support. |
| 6. This proposal | Below. |
| 7. The runner | Built for all six boards, not run ([README](../kinds/crc/README.md#step-7-the-runner-built-and-not-run)). |

## The answer to the open question: per library or per algorithm?

Neither alone (the comparison is in the [README](../kinds/crc/README.md#is-the-result-one-per-library-or-one-per-algorithm)):

- On the Armv7-M and Armv8-M cores (M4, M7, M33), the C and C++ code of
  the same class often compiles to the same instructions per byte: CRC-32
  with a table of 256 from ETL, crcany and libcrc; CRC-8 with a table of
  256 from ETL, crcany and AceCRC; CRC-16 from crcany and libcrc.
- It does not for the Rust crate (a down-counter, and an unrolled loop at
  -O2), for CRC++, for the tables of 16 of CRC-8, and for most pairs on the
  Cortex-M0+.
- Where the instructions are the same, the data may not be: libcrc's table
  is in RAM, crcany's CRC-32 table is 4 KB against ETL's 1 KB. On a board
  whose cache holds only part of a table (below), that alone can change the
  cycles.

How sure: the instruction comparison is a fact of these builds (and of the
loop chosen as the work loop; `loops.py` says how it chooses). That equal
instructions give equal cycles is a hypothesis; the first series tests it.

**What it means for the page**: one line per configuration, grouped by
CRC and class, with the libraries that compile to the same loop marked as
such. If the first series shows equal cycles for equal loops, the page can
fold them into one line per (algorithm, table location) and name the
libraries; if not, the lines stay apart and the difference is itself the
finding.

## The first series, counted

Proposal: the 20 configurations of step 2, each with the reference of its
CRC as the baseline in the same image, table where the library puts it,
eight placements, the cache off and on inside every image (no extra
images for the cache).

Image size, from the cross builds at -O2 (the largest over the four
cores) plus the harness, start-up and reference as built for the
NUCLEO-G474RE (2008 bytes), 1 KB for the other boards' start-up and the
slot boot (an estimate), the far call (6144 bytes) and the largest
placement (28 bytes); a slot is that plus a quarter of the configuration's
bytes, in units of 4 KB, the rule of `oneslots.py`:

| Slot | Configurations |
|---|---|
| 12 KB | 17 configurations (all but the three below) |
| 16 KB | crcany `crc32iso_hdlc_byte`, crcany `crc32iso_hdlc_word` (4 KB tables) |
| 20 KB | zlib `crc32` (5 KB of tables, about 1 KB of code) |

That is **160 images in 9 segments of 256 KB** (a slot table of the kind's
own, in its own range of segment numbers, 100 to 199, the ring buffers'
being 0 to 99; the ring-buffer bundles stay as they are). Flash writes per board, one per bundle, a bundle holding as many
segments as the board's flash:

| Board | Flash | Segments per bundle | Flash writes |
|---|---|---|---|
| nRF5340 DK | 1 MB | 4 | 3 |
| NUCLEO-G0B1RE | 512 KB | 2 | 5 |
| NUCLEO-G474RE | 512 KB | 2 | 5 |
| NUCLEO-H723ZG | 1 MB | 4 | 3 |
| SAM D20 Xplained Pro | 256 KB | 1 | 9 |
| Raspberry Pi Pico 2 | 4 MB | 16 | 1 |
| **All six** | | | **26** |

The SAM D20 on its own: one segment per bundle, so 9 writes, the most of
any board, for 160 images of 12 to 20 KB in 252 KB per bundle (the first
4 KB of a segment stay free for the boot stub).

Ways to fewer writes, if wanted: one placement of eight for the first run
(below) gives 20 images in 2 segments: 1 write on every board but the SAM
D20 (2), 7 in all; leaving zlib out saves one 20 KB slot per placement.

## The table in flash, and copied to RAM

- **In flash** is how ETL, crcany, AceCRC, Zephyr, zlib and the crc crate
  ship their tables (`const`); libcrc and CRC++ build theirs in RAM at run
  time, so they are measured with the table in RAM as shipped.
- **Copied to RAM** for a flash-table configuration would be a second image
  of the same configuration: the table's section placed in `.data` by the
  linker script (a script of the kind's own, by the table's symbol name
  from `sizes.tsv`), so the library's code is unchanged and only the
  table's address moves. For the 15 configurations with a table in flash
  that is 120 more images in 7 more segments: 20 more flash writes on the
  six boards (nRF5340 2, G0B1 4, G474 4, H723 2, SAM D20 7, Pico 2 1;
  counted the same way as above, an estimate).
  Proposal: not in the first series; decide after it, per board, where
  "cache on" does not cover table reads (below).

## What "cache on" covers for a table read from flash

| Board | What `board_cache(1)` turns on | Table reads from flash | Source |
|---|---|---|---|
| NUCLEO-G474RE | ART: instruction cache, data cache, prefetch | Through the D-cache on DCode, which holds 256 bytes ("8 cache lines of 4 x 64 bits or 2 x 128 on DCode (256B RAM)"). A table of 16 fits; a table of 256 for CRC-32 (1 KB) or crcany's 4 KB does not, so most table reads pay the 4 wait states. | RM0440, the embedded flash memory's feature list and its section "Data cache memory (D-Cache)" |
| NUCLEO-H723ZG | The Cortex-M7 L1 instruction and data caches | Cached: "32 Kbytes of I-cache and 32 Kbytes of D-cache", and the flash lies in the Code region, which the Armv7-M default memory map makes cacheable; every table here fits. With the cache off, 7 wait states at 64 MHz (the board's `board.h`, RM0468 4.3.8). | STM32H723 data sheet; Armv7-M Architecture Reference Manual (default memory map) |
| nRF5340 DK | The application core's CACHE | Cached: "Both instruction and data accesses towards flash memory or XIP code regions are cached"; 8192 bytes of cache data. | [nRF5340 Product Specification, CACHE](https://docs.nordicsemi.com/bundle/ps_nrf5340/page/cache.html) |
| Raspberry Pi Pico 2 | The XIP cache | Cached: "A 16 kB on-chip cache retains the values of recent reads and writes" on the XIP interface, so data reads from flash too. With it off, every read goes to the QSPI flash. | [RP2350 datasheet](https://pip-assets.raspberrypi.com/categories/1214-rp2350/documents/RP-008373-DS-2-rp2350-datasheet.pdf), 4.4 and 4.4.1 |
| NUCLEO-G0B1RE | Instruction cache and prefetch (the board's `board.h` sets `ICEN`, `PRFTEN`; the G0 has no data-cache bit there) | **Unknown this night** whether data reads are buffered: RM0444 is not on lib-lab1 and could not be fetched (timeout). The survey's reading was "a table read from flash pays the wait states". | to be checked in RM0444 |
| SAM D20 Xplained Pro | The NVM controller's cache (`CTRLB.CACHEDIS` cleared) | **Unknown this night** whether it serves data reads as well as instruction fetches: the data sheet could not be fetched (HTTP 403). | to be checked in the SAM D20 data sheet |

So the G474 is where table size should show most: a table of 16 against a
table of 256 there is a comparison of cache hits against wait states,
which the other Cortex-M4/M7/M33 boards do not have.

## Placement

- **Code**: the method of version 2 applies (eight placements, the far
  call), with one difference in the image: the placement bytes lie before
  the adapter, not behind it, so the adapter and the library move together
  (`kinds/crc/README.md`, step 7). In version 2 the adapter stays; here
  that would leave the loop of a library of headers (ETL, CRC++), which is
  compiled into the adapter, at one address in all eight placements.
  Whether eight are needed at 1024 bytes: at that length the
  call is dominated by the loop, so placement may matter less than for a
  ring-buffer push; but the loop is short (5 to 18 instructions per iteration, up to 32 where the Rust crate unrolls it) and its
  alignment against the flash line and the cache line is exactly what
  placement varies. Not known before measuring.
- **The table**: a new axis. With the table in flash it moves with the
  code in every placement, so the eight placements also move the table by
  0 to 28 bytes; its alignment against a 32-byte cache line changes with
  it. A table in RAM does not move.
- **How a small first run settles both**: one board (the NUCLEO-G474RE,
  where flash wait states and a small D-cache make placement and table
  alignment matter most), four configurations (ETL `crc32_t256`, ETL
  `crc32_t16`, crcany `crc32iso_hdlc_word`, zlib `crc32`), all eight
  placements, plus the same four with the table aligned to 32 bytes
  (`aligned` on a copy of the table is not possible without changing the
  library, so by the linker script of the kind: `ALIGN(32)` before the
  table's input section). That is 64 images in about 4 segments: 2 flash
  writes on that board. The spread over the eight placements and between
  the two table alignments tells whether eight placements and a table axis
  are needed for the full series.

## The export check for a second kind (a proposal only)

Today `lab/tools/public-export.py` holds all of `firmware/` (and three lab
files) as the test sources of every record. Nothing changes for this
night's work: `kinds/crc/` is outside `firmware/` and has no records. When
CRC has records, the proposal:

- CRC records in a directory of their own (for example `records/crc/`),
  with their own ledger entries (`records/rebuilt.json` keyed by the
  record's file, as today).
- Their test sources: `kinds/crc`, `firmware/common` (the board support
  the image links) and the three lab files (`lab/boards.conf`,
  `lab/tools/source-commit.sh`, `lab/tools/boardpower.sh`).
- The ring-buffer rule unchanged: its test sources stay `firmware` and the
  three lab files.
- A test of the change must show three cases: a file changed in
  `kinds/crc` leaves the ring-buffer records exportable; a file changed
  under `firmware/` (outside `firmware/common`) still stops them; a change
  under `firmware/common` counts for both kinds.

## What the runner and the record tools need

Built since (README, [step 7](../kinds/crc/README.md#step-7-the-runner-built-and-not-run)),
with version 2's own programs used unchanged by import (`oneslots.py`,
`onebundle.py`, `run-one.py`): the kind's configurations and slot table,
the images and bundles for all six boards, and the runner with the
decoding of the result block. The counts above are now those of the built
table: 160 images, 9 segments, 26 flash writes, the slot sizes as
estimated. Still to do:

- the smoke test on a board before any launch (made once, on the
  NUCLEO-G474RE on 2026-11-24, README step 7; the reference was changed
  after it, so every bundle is another file than the one written then);
- a record writer (as `onerecords.py`) with a schema of its own (for
  example `crc-bench/1`), and the export of CRC records (above): made on
  2026-11-24, `crc-bench/1`, the export rule as proposed with the four
  programs of version 2 the kind imports added to its test sources
  (README, step 8);
- `repeat.sh` and `verify-build.sh` are frozen; the kind would need its
  own copies, reading `EXPORTED_FROM`/`SAME_SOURCES` with the kind's test
  sources: the check of a record made (`bench/crcverify.sh`, reading
  `SAME_SOURCES_CRC`); the copy of `repeat.sh` waits for the first
  records.

## Decisions for the owner

1. Whether a first series goes to the boards, and which: the 20
   configurations (26 flash writes, estimated), or first the small run on
   the NUCLEO-G474RE (2 writes) to settle placement and table alignment.
2. Whether the export check is changed as proposed above (a change of
   method for the export; made and tested in the daytime).
3. Whether `kind-crc` goes into `main`.

## The first series, run (2026-11-24 14:28 to 2026-11-25 00:13 UTC)

Run as proposed above: commit `6301058`, six boards, 20 configurations,
eight placements, two passes (`series.sh`, outside the repository; every
exit other than 0 would have stopped it before the next board). Read by
[`lab/tools/crc-series-read.py`](../lab/tools/crc-series-read.py)
(step 1 of [the plan from the series to publication](../lab/plans/2026-11-24-crc-from-series-to-publication.md)),
which reads only the run files and logs.

| Board | Exit | Runs | Without a file | Flash writes | Invalid | Disagreeing calls (configuration / baseline) | Attempts | Wait (s): runs | Empty call (cycles): runs | Pass 1 = pass 2 |
|---|---|---:|---:|---:|---:|---|---|---|---|---|
| NUCLEO-G474RE | 0 | 320 | 0 | 5 | 0 | 0 / 0 | 1: 319, 2: 1 | 5: 304, 10: 16 | 8: 320 | 7680 of 7680 means identical |
| NUCLEO-G0B1RE | 0 | 320 | 0 | 5 | 0 | 0 / 0 | 1: 318, 2: 2 | 10: 304, 20: 16 | 11: 320 | 7680 of 7680 identical |
| nRF5340 DK | 0 | 320 | 0 | 3 | 0 | 0 / 0 | 1: 310, 2: 10 | 10: 176, 20: 144 | 26: 320 | 7680 of 7680 identical |
| NUCLEO-H723ZG | 0 | 320 | 0 | 3 | 0 | 0 / 0 | 1: 308, 2: 6, 3: 6 | 5: 128, 10: 96, 20: 96 | 6: 320 | 7680 of 7680 identical |
| SAM D20 Xplained Pro | 0 | 320 | 0 | 9 | 0 | 0 / 0 | 1: 319, 3: 1 | 20: 320 | 9: 320 | 7680 of 7680 identical |
| Raspberry Pi Pico 2 | 0 | 320 | 0 | 0 | 0 | 0 / 0 | 1: 319, 4: 1 | 40: 320 | 5: 320 | 7590 of 7680 identical; 7676 within 1 % or 0.05 cycles |

Flash writes: 25 in the series (the Pico 2's one bundle was on the board
from before it), 115 in all for the lab's boards. The runner's own
records check after each board: 20 of 20.

**The waits.** The runner reads an image's results after a wait; if the
image has not finished, it repeats the run with twice the wait
(`kinds/crc/bench/run-crc.py`, lines 237-272). The longer wait is kept for
that configuration for the rest of the board's runs (both passes, all
placements), and after a run has finished the board's default becomes the
shortest wait that has finished (`state["wait"] = min(finished)`). So the
first run of a board sets the default, and a configuration that is slow at
its first look keeps a longer wait: on the G474 crcany `crc32iso_hdlc_bit`
(10 s in all 16 of its runs, one second attempt); on the G0B1 the first run
(5 to 10 s, the board's default after) and crcany's bitwise code (20 s);
on the nRF5340 nine configurations at 20 s; on the H723 eight
configurations at 10 s and six at 20 s; on the SAM D20 and the Pico 2 the
first run alone (5 to 20 s, and 5 to 40 s), after which every run used
that wait. 27 runs needed more than one attempt; every one finished.

**The empty call** (`empty_call_raw_min`, the shortest timed call of an
empty function) is the same in every run of a board.

**The Pico 2's two passes differ; this is not explained.** 90 of its 7680
means differ between pass 1 and pass 2. All 90 are of the configuration,
none of the baseline, all with the cache on, and all of CRC-32
configurations (crcany `crc32iso_hdlc_word` 39, zlib 23, Rust `Table<1>`
11, ETL `crc32_t256` 9, crcany `crc32iso_hdlc_byte` 8). Four differ by
more than 1 %; the largest is crcany `crc32iso_hdlc_word` at placement 8,
4 bytes, offset 0: 136.047 and 134.328 cycles (1.26 %). A look at the 90
(host only, from the run files):

- every placement has some (8 to 16 each), and every length (1 byte: 6,
  4: 22, 16: 23, 64: 15, 256: 19, 1024: 5); offset 0: 68, offset 1: 22;
- pass 2 is lower in 46 and higher in 44;
- the minimum of the 256 calls is the same in both passes in all 90; the
  maximum differs in 44 of them. The difference lies in a few slower
  calls, not in a shifted level.

On the other five boards all 7680 means are identical between the passes,
to the cycle.

**The records** (step 2 of the plan): `kinds/crc/bench/crcrecords.py` made
120 records (`records/crc/<board>/<adapter>.json`, 20 per board, none left
out); for every board and CRC the baseline measured the same in every run
(24 of 24 numbers). `kinds/crc/bench/crcverify.sh` rebuilt all 120 from a
fresh worktree of the records' commit (`kinds/crc/build` is not in git;
the first board's build tree, kept, held 160 images created by the run),
with the libraries copied from a local copy at their pins and checked out
again, on 6 of the host's 12 CPUs:

| Board | Records | MATCH | Wall time |
|---|---:|---:|---:|
| NUCLEO-G474RE | 20 | 20 | 16 s |
| NUCLEO-G0B1RE | 20 | 20 | 16 s |
| nRF5340 DK | 20 | 20 | 16 s |
| NUCLEO-H723ZG | 20 | 20 | 16 s |
| SAM D20 Xplained Pro | 20 | 20 | 16 s |
| Raspberry Pi Pico 2 | 20 | 20 | 15 s |

The control, a copy of the G474's ETL `crc32_t256` record with one digit
of placement 12's `image_sha256` changed, gave `DIFFERS` ("placement 12:
flash bytes differ (record 30bdcbde4b022878, rebuilt 30bdcbde4b722878)",
exit 1). `lab/tools/public-export.py --check` on the commit with the
records: no record that cannot be rebuilt from the tree, 120 CRC records.

## The numbers, checked (step 3)

Every number here is printed by a program from the 120 records:
[`lab/tools/crc-series-checks.py`](../lab/tools/crc-series-checks.py)
(`noise`, `perbyte`, `sameclass`, `offset`, `cache`, `ram`, `period`),
[`crc-loops.py`](../lab/tools/crc-loops.py) and
[`crc-placement.py`](../lab/tools/crc-placement.py) (the built images of
commit 6301058). The flash facts are quoted in
[`lab/plans/2026-11-24-crc-flash-read-sources.md`](../lab/plans/2026-11-24-crc-flash-read-sources.md).
"Per byte" is (mean at 1024 bytes − mean at 256 bytes) / 768 at offset 0;
"rest" is what that line leaves at length 0; a range is min–max over the
eight placements, first pass.

**1. Noise floor.** On five boards all 7680 means of a board are the same
in both passes, to the cycle; the baseline (the reference of each CRC)
measures the same in every image of a board, at every placement and in
both passes (for example the G474's CRC-32 baseline at 1024 bytes: 156708
cycles cache off, 56338 cache on, in all 144 runs). On the Pico 2, 90 of
7680 means differ, all of the configuration, all cache on (the largest
1.26 %); in all 90 the minimum of the 256 calls is the same in both
passes, the maximum differs in 44, and the slowest call of the scenario is
its first call in at least one pass in 71 of the 90 (in both in 51).
Which way of the two-way XIP cache is replaced on a miss is not stated in
the RP2350 datasheet (RP-008373, 4.4.1 "XIP cache" says "two-way
set-associative"; no replacement policy found). *Closing line: at one
position the repeat error is 0 on five boards and up to 1.26 % (cache on)
on the Pico 2; what limits a comparison between two configurations is the
spread over the placements (check 7), not the repetition.*

*Correction, 2026-11-27:* the RP2350 datasheet does state the replacement
policy: "Cache eviction policy is random" (RP-008373, 4.4.1.2 "Cache line
states"). It explains the Pico 2's difference between the passes; see
[What the CRC reports left unexplained](2026-11-27-crc-unexplained.md),
item 2.

*The first call in the page's figures* (`first`, every configuration and
placement, first pass). A scenario's mean includes its first call. In the
figures a page would show (16 bytes, and the cost per byte from 256 and
1024 bytes; offset 0), the first call's excess over the minimum is at
most 2.45 % of the mean (Pico 2, 16 bytes, cache on, zlib at placement 0:
first 1211, minimum 159, mean 168.0) and at most 0.25 % on the other five
boards; leaving the first call out would change a cost per byte by at
most 0.24 % (Pico 2, zlib at placement 16: 6.688 with, 6.704 without).
The mean lies further above the minimum than the first call accounts for
in some scenarios: up to 46 % on the Pico 2 (16 bytes, cache on, crcany's
slicing by 4 at placement 28: mean 269.1, minimum 146) and 35 % on the
G474 (16 bytes, cache on, AceCRC at placement 12: mean 244.2, minimum
159); there the calls themselves vary.

**2. Cost per byte, by class.** Cache on, the classes order as their
loops do on every board: bitwise 41 (H723) to 87–90 (G0B1, SAM D20)
cycles/byte; tables of 16 13–33; tables of 256 5–20; crcany's slicing by
4 2.75 (H723) to 13.5 (G0B1); zlib's braided words 4.93 (H723) to 17.7
(SAM D20). Two values were looked at because they do not fit their class:
libcrc's table of 256 in RAM is slower per byte than the tables in flash
on the two Cortex-M0+ boards (G0B1 16–20 against 15, SAM D20 16 against
14.3–15.6, cache on): its loop there is 13 instructions against 10 for
ETL and crcany (`crc-loops.py`); and the H723's bitwise code cache off
spans 41 to 225 cycles/byte over the placements, its lowest equal to its
cache-on value (41–42): see check 7. The rest at length 0 is largest for
zlib (118 to 422 cycles on the Cortex-M boards, cache off and on) and
crcany's slicing by 4 (52 to 211). Whether the classes' ranges (all configurations and placements of a
class) overlap is printed by `classes`. *Closing line: with the cache on,
the classes lie in separate bands of cost per byte in 14 of the 18 board
and CRC tables; they overlap in four: zlib's braided words with the tables
of 256 for CRC-32 on the G474, the G0B1 and the nRF5340 (on the G474 12.1
against 10.0–14.7), and Zephyr's shifts and XORs with the tables of 256
for CRC-16 on the G0B1. With the cache off they overlap in 9 of 18.*

**3. The same class from several libraries.** The loops (`crc-loops.py`,
placement 0): ETL and libcrc's CRC-32 table of 256 are the same
instructions on the M4, M7 and M33 cores (7); crcany's differs only in the
pointer increment; the Rust crate's loop is unrolled four times (25
instructions, 4 table loads); ETL and AceCRC's CRC-8 table of 256 are the
same instructions on the M4, M7 and M33, and all three CRC-8 tables of 256
on the G0B1; ETL and Zephyr's CRC-32 table of 16 are the same
instructions on the G0B1. The means (`sameclass`): with the cache on, the
per-byte ranges of one class overlap only where the loops are the same or
near it: CRC-8 table of 256 on G474, G0B1, H723 and SAM D20; CRC-32 table
of 16 on G474, G0B1, nRF5340 and H723. With the cache off they overlap
more often (on the H723 every class), because the placement ranges are
wider. The mean at 16 bytes differs between libraries of one class even
where the per-byte cost is the same (for example ETL against crcany,
CRC-32 table of 256, G474 cache on: 257–258 against 280–281 cycles, both
14.70–14.72 per byte). Pairs with the same loop instructions but not the same cost per byte:
ETL and libcrc's CRC-32 tables of 256 on the M4 and M33 cores. With the
cache on the G474 gives 14.70–14.72 against 10.0, the nRF5340 10 against
9, the Pico 2 10 against 9; on the H723 (M7) the two are the same, 8
against 8. The report
reads this as the place of the table (flash for ETL, RAM for libcrc;
check 6), because the instructions are the same. *Closing line: the same
instructions with the table in the same kind of memory give the same
cost per byte within the placement range; the same instructions with the
table in flash against RAM do not (check 6); libraries of one class
differ in the fixed part of a call, and per byte where their loops or
their table's memory differ.*

**4. Offset 0 against offset 1** (`offset`, first pass, every
placement). Above the repeat error and above 1 %: crcany's slicing by 4,
offset 1 slower with the cache off on every board (at 4 bytes +17 % to
+24 %; it steps to a word boundary first), and on the H723 with the cache
on too (+43 % at 4 bytes); on the Pico 2 with the cache on, offset 1 is
the faster one at 4 and 16 bytes (97.9 against 134.8 cycles at 4 bytes,
placement 0); zlib at 64 bytes (+1.8 % to +3.4 %) on G474, G0B1, SAM
D20; on the G474 the CRC-8 tables of 256 at 256 bytes cache on (+4.7 % to
+8.5 %). The largest differences on the nRF5340, the H723 and the Pico 2
are at 1 byte, cache on, with offset 0 the slower (Pico 2: up to 76 %,
ETL CRC-32 at placement 0, 75.0 against 18 cycles): offset 0 at 1 byte is
the first scenario after the cache is switched on (`kinds/crc/bench/main.c`,
`run_all`: length outer, offset inner), and its first call is its slowest
(for that scenario: first 644, minimum 18). *Closing line: the offset
matters for the slicing and braided code as expected; at 1 byte with the
cache on, offset 0 measures the first calls after the cache was switched
on, not the offset.*

**5. Cache off against on** (`cache`, 1024 bytes, offset 0, every
configuration and placement), with the flash facts of the source note:

| Board | Off / on | Flash read | Cache line | Wait states at our clock |
|---|---|---|---|---|
| NUCLEO-G474RE, 170 MHz | 1.47–2.98 | 64 bits (dual bank) | 32 B, I and D | 4 |
| NUCLEO-G0B1RE, 64 MHz | 1.18–1.74 | 64 bits | 8 B, instructions only | 2 |
| nRF5340 DK, 64 MHz | 2.20–4.49 | not stated | 16 B, I and D | no setting; the specification gives, for CoreMark run from flash at 64 MHz, typically 5 CPU wait states with the cache off and 6 with it on (5.2.2.1), a benchmark figure, not a flash setting |
| NUCLEO-H723ZG, 64 MHz | 1.00–7.12 | 256-bit flash word | 32 B, L1 I and D | **7: the power-on default, which our 64 MHz build keeps; RM0468's Table 16 allows 0 or 1 at 64 MHz** |
| SAM D20, 48 MHz | 1.12–1.57 | 32-bit AHB | not stated | 1 |
| Pico 2, 150 MHz | 22.4–51.5 | QSPI, 64-bit line fills | 8 B, I and D | not a wait-state setting (QSPI at 50 MHz) |

*Closing line: the cache is worth 1.2 to 7 times on the five Cortex-M
flash boards and 22 to 51 times on the Pico 2, whose flash is external;
the H723's numbers with the cache off carry 7 wait states that the
manual does not require at 64 MHz.*

**6. A table in RAM against a table in flash** (`ram`, per byte, ranges
over the placements). Cache on, libcrc's RAM table is the cheapest table
of 256 per byte on the G474 (CRC-32 10 against 13.2–14.7; CRC-16 11
against 14.2–15.3), level with the flash tables on the nRF5340, H723 and
Pico 2 (CRC-32 9, 8, 9 against 8–10, 6.75–8, 7.4–10), and dearer on the
G0B1 and the SAM D20 (CRC-32 16–20 and 16 against 13.75–15 and
12.7–15.6). CRC++'s RAM table (CRC-16) is cheaper than the flash tables
only on the G474, by a fraction (14 against 14.2–15.3), and dearer on the
other five (for example nRF5340 14 against 10–11). Cache off, libcrc's
CRC-16 table is the cheapest of its class on the G474, G0B1, nRF5340,
SAM D20 and Pico 2 and at its best placements on the H723; its CRC-32
table is not cheaper than the Rust crate's flash table on the G474, G0B1
and SAM D20 (G474 22–23 against 19.5–22.2), and the cheapest on the
Pico 2 (259 against 318–425). CRC++'s loop is longer than the others' (10
to 12 instructions against 8 for CRC-16, `crc-loops.py`). *Closing line:
where a table lies matters most with the cache off and on the boards with
the slowest flash; with the cache on the loop decides as much as the
memory.*

**7. Placements** (`period`; `crc-placement.py` for the loop and table
addresses). The step after which a configuration's mean at 1024 bytes
repeats, and the spread over the placements:

| Board | Cache off | Cache on | Fits |
|---|---|---|---|
| NUCLEO-G474RE | period 8 B in all 20; spread up to 23 % | 8 the same at every placement, 12 vary (up to 22.8 %, AceCRC) | the 64-bit flash read (RM0440 3.2, 3.3.4); in 3 of 4 configurations looked at, the slow placements are those where a 32-bit instruction of the loop crosses an 8-byte boundary |
| NUCLEO-G0B1RE | period 8 B in all 20; up to 19 % | period 8 B in 18; up to 24.9 % | the 64-bit flash read and the 8-byte cache lines (RM0444 3.2, 3.3.5); fast or slow by the loop's start modulo 8 (no 32-bit instructions in these loops) |
| nRF5340 DK | period 16 B in all 20; up to 40.7 % | the same at every placement in 18; at most 0.12 % | the 128-bit cache line (PS v1.6, 5.4.1) |
| NUCLEO-H723ZG | no period below 32 B in all 20; up to 447 % | at most 2.4 % | the 256-bit flash word and its read buffer (RM0468 4.3.8): in the three configurations looked at, slow exactly where the loop crosses a 32-byte boundary; at its fast placements the bitwise code costs what it costs with the cache on |
| SAM D20 | the same at every placement in all 20 | period 8 B; up to 4.5 % | (nothing above 4.5 %) |
| Pico 2 | 8 B in 12, the same in 3, longer in 5; up to 13.3 % | the same in 11; at most 0.23 % | cache on: the 8-byte XIP cache lines and 64-bit line fills (RP-008373 4.4, 4.4.2). Cache off: not explained; with the cache disabled, accesses "ignore the cache contents, and always access the QSPI interface" (4.4.5, XIP_CTRL CTRL.EN_SECURE / EN_NONSECURE), and the QMI makes "8/16/32-bit accesses for uncached accesses" (4.4.2) |

Not explained:

- the order of the seven placements of AceCRC's CRC-8 on the G474 with the
  cache on whose table is not 32-byte aligned (9420 to 10272 cycles at
  1024 bytes); the aligned one (placement 0, 8362) is the only one whose
  256-byte table spans 8 lines of 32 bytes, the D-cache's 8 lines (RM0440
  3.2), the others span 9;
- on the G0B1, which loop start modulo 8 is the slow one differs between
  configurations (crcany bitwise slow at 0, crcany CRC-16 at 6, libcrc at
  4);
- the Pico 2's pass difference (check 1);
- the Pico 2's period of 8 bytes with the cache off (check 7's table);
- on the Pico 2 with the cache on, crcany's slicing by 4 faster at offset 1
  than at offset 0 at 4 and 16 bytes (check 4).

*Closing line: the spread over the placements is the largest effect in
the series after the class itself; on four boards it repeats with the
step of the flash read or the cache line, and on the H723 with the cache
off it is larger than the difference between classes.*

## Repetition from outside (step 7)

2026-11-25, from a tree exported by `lab/tools/public-export.py` into an
empty directory, by the instructions of
[Reproduce](../site/content/reproduce.md) alone:

- **`kinds/crc/bench/crcverify.sh` on all 120 records**, without a local
  copy of the libraries: 120 `MATCH`, 0 `DIFFERS`, 28 s per board (the
  libraries are fetched for each board; 16 s with them at hand).
- **`kinds/crc/repeat.sh --level quick` on the Raspberry Pi Pico 2**, with
  no flash write: the tree built bundle 6 with the checksum of every run in
  our records, and a read-only compare of the board's flash with it
  matched before the run. probe-rs was called through a wrapper that
  refused a write. Three configurations (AceCRC `crc8_byte`, crcany
  `crc16_byte`, crcany `crc32iso_hdlc_bit`), eight placements, two passes,
  48 runs.
  - First run (export of `e250f78`): 48 runs, 0 flash writes, but no
    record: in a tree without git history the build recorded the commit
    as `unknown`, which the record writer refuses, so `repeat.sh` said
    `FAILED`. Compared by hand (outside the instructions), the 48 run
    files had the images of our records and all 2304 means (configuration
    and baseline) were within 1 % of one of our two passes.
  - The correction, in `kinds/crc/repeat.sh` (not a test source): in an
    exported tree it builds and runs in a copy of the sources under its
    result directory, with the exported commit in a `COMMIT` file, as the
    top-level `repeat.sh` does for version 2. `--build-only BOARD` runs the
    build step alone, and
    [`lab/tools/test-crc-repeat-export.sh`](../lab/tools/test-crc-repeat-export.sh)
    checks without a board that the build in an export records a commit
    the record writer takes (and, as a control, the same tree without the
    `COMMIT` file gave `unknown`, which it refuses).
  - Second run (export of `8d80bac`): 48 runs, 0 flash writes, 3 records,
    "same as ours": 24 of 24 images the same (bytes in flash and address),
    1152 of 1152 means within 1 %; 34 minutes with fetching and building.
    Its archive, the one a reader is asked to send, held the copy of the
    sources: 24 MB, 2914 of 2979 entries under `src/` (the fetched
    libraries, 977 files, and 322 ELF files). `repeat.sh` now removes the
    copy before it packs the archive, as the top-level `repeat.sh` does.
  - Third run (export of `8efd3b7`, the `repeat.sh` that is published):
    48 runs, 0 flash writes, 3 records, "same as ours" (24 of 24 images,
    1152 of 1152 means within 1 %); 34 minutes; the archive 49872 bytes,
    65 entries, none under `src/`.
    The three configurations are not among those whose means differed
    between our passes on the Pico 2 (check 1), so this run does not
    speak to that difference.
