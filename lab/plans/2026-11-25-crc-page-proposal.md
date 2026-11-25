# CRC: what the page shows, a proposal for the owner

2026-11-25. Step 4 of
[`2026-11-24-crc-from-series-to-publication.md`](2026-11-24-crc-from-series-to-publication.md).
Written after step 3 ([series report](../../reports/2026-11-25-crc-first-series.md),
"The numbers, checked"). A proposal: the owner chooses; the review adds a
recommendation. Every table below is written by
[`site/crc_tables.py`](../../site/crc_tables.py) from the 120 records
(`records/crc`, branch `kind-crc-records`), here for one board and CRC:
the NUCLEO-G474RE, CRC-32/ISO-HDLC. The page would carry one such table
per board and CRC (18), in the order of `kinds/crc/configs.txt`: no
ranking, no winner.

What every variant leaves out, and why:

- **The 1-byte figures.** At offset 0 with the cache on, the 1-byte
  scenario is the first one after the cache is switched on
  (`kinds/crc/bench/main.c`, `run_all`), so its mean holds the first calls
  with the cache on (series report, check 4). The tables use 16 bytes and
  the cost per byte from 256 and 1024 bytes, in which the first call adds
  at most 2.45 % to a mean (Pico 2) and at most 0.25 % on the other boards
  (check 1).
- **A factor of the baseline.** The baseline is the bitwise reference at
  one position in the image; every table method comes out below 1 against
  it, and the factor says nothing a row does not say.

## Variant 1: the range over the eight placements, no placement picked

### CRC-32/ISO-HDLC on the NUCLEO-G474RE (Cortex-M4F, 170 MHz), cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| etl crc32_t256 (C++) | table of 256 | flash | 1072 | 0 | 257–258 | 14.7 |
| crcany crc32iso_hdlc_byte (C)[1] | table of 256 | flash | 4168 | 0 | 280–281 | 14.7 |
| libcrc crc_32 (C)[2] | table of 256 | RAM, built at the first call | 140 | 1025 | 196 | 10.0 |
| crc (Rust) Table<1> | table of 256 | flash, computed at compile time | 1250 | 0 | 263 | 13.2 |
| etl crc32_t16 (C++) | table of 16 | flash | 132 | 0 | 293 | 17.0 |
| zephyr crc32_ieee (C) | table of 16 | flash | 150 | 0 | 306 | 17.0 |
| crcany crc32iso_hdlc_word (C) | slicing by 4 | flash (4 KB) | 4296 | 0 | 238 | 9.9 |
| zlib crc32 (C) | other: "braided" words | flash | 5818 | 0 | 247–248 | 12.1–12.2 |
| crcany crc32iso_hdlc_bit (C) | bitwise | none | 96 | 0 | 1025 | 61.0 |

[1] crcany's generated crc32iso_hdlc.c defines `table_byte` as `table_word[0]` (`#define table_byte table_word[0]`, build/gen/src/crc32iso_hdlc.c line 29): the byte code reads the first row of the word table, so the whole word table (4 x 256 x 4 = 4096 bytes, one symbol `table_word` in the image) is linked in. The flash bytes count it.
[2] libcrc builds its table in RAM at its first call. The adapter's init() makes that call (kinds/crc/adapter_libcrc.c, lc32_init) and bench/main.c calls init() before the timed calls (line 156), so the 256 calls of a scenario find the table built; the building is not measured.

### CRC-32/ISO-HDLC on the NUCLEO-G474RE (Cortex-M4F, 170 MHz), cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| etl crc32_t256 (C++) | table of 256 | flash | 1072 | 0 | 463–489 | 27.0–29.0 |
| crcany crc32iso_hdlc_byte (C)[1] | table of 256 | flash | 4168 | 0 | 506–543 | 27.0–29.0 |
| libcrc crc_32 (C)[2] | table of 256 | RAM, built at the first call | 140 | 1025 | 405–422 | 22.0–23.0 |
| crc (Rust) Table<1> | table of 256 | flash, computed at compile time | 1250 | 0 | 396–444 | 19.5–22.2 |
| etl crc32_t16 (C++) | table of 16 | flash | 132 | 0 | 754–778 | 45.2–46.4 |
| zephyr crc32_ieee (C) | table of 16 | flash | 150 | 0 | 798–815 | 45.7–47.0 |
| crcany crc32iso_hdlc_word (C) | slicing by 4 | flash (4 KB) | 4296 | 0 | 420–450 | 18.0–19.7 |
| zlib crc32 (C) | other: "braided" words | flash | 5818 | 0 | 431–441 | 20.5–21.3 |
| crcany crc32iso_hdlc_bit (C) | bitwise | none | 96 | 0 | 2453–3002 | 148.0–182.0 |

[1] crcany's generated crc32iso_hdlc.c defines `table_byte` as `table_word[0]` (`#define table_byte table_word[0]`, build/gen/src/crc32iso_hdlc.c line 29): the byte code reads the first row of the word table, so the whole word table (4 x 256 x 4 = 4096 bytes, one symbol `table_word` in the image) is linked in. The flash bytes count it.
[2] libcrc builds its table in RAM at its first call. The adapter's init() makes that call (kinds/crc/adapter_libcrc.c, lc32_init) and bench/main.c calls init() before the timed calls (line 156), so the 256 calls of a scenario find the table built; the building is not measured.

## Variant 2: placement 0, first pass, the range beside it

The plan's starting point: version 2's convention for the ring buffers
(one named placement, first pass), with the range over the eight
placements in brackets where it is not a single value.

### CRC-32/ISO-HDLC on the NUCLEO-G474RE (Cortex-M4F, 170 MHz), cache on

Cycles, cache on, placement 0 of 8 (range over the eight placements in brackets), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| etl crc32_t256 (C++) | table of 256 | flash | 1072 | 0 | 257 (257–258) | 14.7 |
| crcany crc32iso_hdlc_byte (C)[1] | table of 256 | flash | 4168 | 0 | 280 (280–281) | 14.7 |
| libcrc crc_32 (C)[2] | table of 256 | RAM, built at the first call | 140 | 1025 | 196 | 10.0 |
| crc (Rust) Table<1> | table of 256 | flash, computed at compile time | 1250 | 0 | 263 | 13.2 |
| etl crc32_t16 (C++) | table of 16 | flash | 132 | 0 | 293 | 17.0 |
| zephyr crc32_ieee (C) | table of 16 | flash | 150 | 0 | 306 | 17.0 |
| crcany crc32iso_hdlc_word (C) | slicing by 4 | flash (4 KB) | 4296 | 0 | 238 | 9.9 |
| zlib crc32 (C) | other: "braided" words | flash | 5818 | 0 | 248 (247–248) | 12.1 (12.1–12.2) |
| crcany crc32iso_hdlc_bit (C) | bitwise | none | 96 | 0 | 1025 | 61.0 |

[1] crcany's generated crc32iso_hdlc.c defines `table_byte` as `table_word[0]` (`#define table_byte table_word[0]`, build/gen/src/crc32iso_hdlc.c line 29): the byte code reads the first row of the word table, so the whole word table (4 x 256 x 4 = 4096 bytes, one symbol `table_word` in the image) is linked in. The flash bytes count it.
[2] libcrc builds its table in RAM at its first call. The adapter's init() makes that call (kinds/crc/adapter_libcrc.c, lc32_init) and bench/main.c calls init() before the timed calls (line 156), so the 256 calls of a scenario find the table built; the building is not measured.

### CRC-32/ISO-HDLC on the NUCLEO-G474RE (Cortex-M4F, 170 MHz), cache off

Cycles, cache off, placement 0 of 8 (range over the eight placements in brackets), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| etl crc32_t256 (C++) | table of 256 | flash | 1072 | 0 | 463 (463–489) | 27.0 (27.0–29.0) |
| crcany crc32iso_hdlc_byte (C)[1] | table of 256 | flash | 4168 | 0 | 543 (506–543) | 29.0 (27.0–29.0) |
| libcrc crc_32 (C)[2] | table of 256 | RAM, built at the first call | 140 | 1025 | 405 (405–422) | 22.0 (22.0–23.0) |
| crc (Rust) Table<1> | table of 256 | flash, computed at compile time | 1250 | 0 | 396 (396–444) | 19.5 (19.5–22.2) |
| etl crc32_t16 (C++) | table of 16 | flash | 132 | 0 | 754 (754–778) | 45.2 (45.2–46.4) |
| zephyr crc32_ieee (C) | table of 16 | flash | 150 | 0 | 815 (798–815) | 47.0 (45.7–47.0) |
| crcany crc32iso_hdlc_word (C) | slicing by 4 | flash (4 KB) | 4296 | 0 | 450 (420–450) | 19.7 (18.0–19.7) |
| zlib crc32 (C) | other: "braided" words | flash | 5818 | 0 | 441 (431–441) | 21.3 (20.5–21.3) |
| crcany crc32iso_hdlc_bit (C) | bitwise | none | 96 | 0 | 3002 (2453–3002) | 182.0 (148.0–182.0) |

[1] crcany's generated crc32iso_hdlc.c defines `table_byte` as `table_word[0]` (`#define table_byte table_word[0]`, build/gen/src/crc32iso_hdlc.c line 29): the byte code reads the first row of the word table, so the whole word table (4 x 256 x 4 = 4096 bytes, one symbol `table_word` in the image) is linked in. The flash bytes count it.
[2] libcrc builds its table in RAM at its first call. The adapter's init() makes that call (kinds/crc/adapter_libcrc.c, lc32_init) and bench/main.c calls init() before the timed calls (line 156), so the 256 calls of a scenario find the table built; the building is not measured.

## Cache off: on the page or in the records only

Shown both ways above: each variant prints the cache-on table and the
cache-off table. If cache off stays in the records only, the page links
to them per board. With the cache off the spread over the placements is
largest (check 7: up to 23 % on the G474, 447 % on the H723), and the H723's
cache-off numbers carry 7 wait states (below).

## What the owner chooses

1. **The variant**: 1 (ranges only) or 2 (placement 0 with the range).
2. **Cache off**: a second table per board and CRC on the page, or only in
   the records with a link.
3. **The H723's wait states**: its numbers are measured at 7 wait states,
   the power-on default, which our 64 MHz build keeps; RM0468's Table 16
   allows 0 or 1 at 64 MHz. Either the page shows them as they are, stated
   in a sentence, or the H723 is set to the wait states the manual gives
   and its CRC series is run again (3 flash writes). The wait states are
   set in `firmware/common/stm32h723/board.h` (the 64 MHz default leaves
   `FLASH_ACR` as after reset; `h7_clock_520` is the only code that writes
   it). That file is under `firmware/`, which is frozen with version 2's
   method (DECISIONS 2026-11-23), and under `firmware/common`, which counts
   for the test sources of both kinds: a change there is a decision on
   version 2's method as well, and the ring-buffer records of the H723
   would have to be held by a rebuild or measured again.
4. **A series with the tables in RAM**: libcrc and CRC++ build their tables
   in RAM; a table in flash copied to RAM by the application is not
   measured (method page, "What is not measured"). Check 6 shows where it
   would matter most: with the cache off, and on the boards with the
   slowest flash (Pico 2: libcrc's RAM table 259 cycles per byte against
   318–425 for the flash tables of its class; with the cache on the loop
   decides as much as the memory). Whether to plan such a series.
5. **The first call and the median**: whether a later series should leave
   a scenario's first call out of its mean, or record the median of the
   256 calls. A change to the bench program, so new runs of all six
   boards; not now. In the page's figures the first call adds at most
   2.45 % (check 1); the mean lies up to 46 % above the minimum in some
   scenarios because the calls themselves vary (Pico 2, 16 bytes, cache
   on), which a median would show and leaving out one call would not.

## Recommendation (the review)

1. Variant 1. With the cache on the two variants give nearly the same
   table. With the cache off, placement 0 is the lowest or the highest of
   the eight in 9 of the 9 rows of the example, and in 75 of the 120 rows
   of all 18 tables (in both the 16-byte and the per-byte figure in 56;
   `site/crc_tables.py --edges --cache off`): a picked placement shows an
   edge of the range, not a typical value, and the series gives no reason
   to prefer one placement.
2. Cache off as a second table per board and CRC, below the cache-on
   table, with ranges. Some of these chips start with the cache off, so
   the numbers are of use; with ranges they say no more than was
   measured.
3. The H723 as measured, with the sentence on its 7 wait states directly
   above its cache-off table. Changing the wait states changes
   firmware/common, which version 2's records are held against; it
   belongs in the next version of the method, when both kinds are measured
   again, not in a first publication of the CRC kind.
4. The table-in-RAM series after the first publication; until then it
   stands under 'What is not measured'.
5. The median beside the mean in the next version of the method (no extra
   flash writes when the boards are run again anyway); not before.

## Decided 2026-11-25

By the owner, all five as recommended above.

1. Variant 1: the range over the eight placements, first pass; no placement picked.
2. Cache off as a second table per board and CRC, below the cache-on table, with ranges.
3. The H723 as measured, with a sentence on its 7 wait states directly above its cache-off tables; in the long run the H723 is to run with the wait states a user normally would set (an item for the next version of the method).
4. The series with the tables in RAM after the first publication; until then under "What is not measured" on the method page.
5. The median beside the mean in the next version of the method; not before.
