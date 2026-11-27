# What the CRC reports left unexplained, studied in the data we have

2026-11-27. No board was used and nothing was written to one. Every number
below is printed by
[`lab/analysis/unexplained-2026-11-27.py`](../lab/analysis/unexplained-2026-11-27.py)
(the subcommand is named with each number) or by
[`lab/tools/crc-placement.py`](../lab/tools/crc-placement.py), from:
- the records under `records/crc` and `records/pools`;
- the run files of the series (the CRC series' run directories of commits
  6301058 and 40f1958, the first pools series' of commit f12caf7);
- the images of those commits, as built: the Pico 2's CRC images of 40f1958
  are byte for byte those of the records of 6301058 (296 of 296
  `image_sha256` equal), and the pools series' images are those of its
  records.

The items, from the [first](2026-11-25-crc-first-series.md) and
[second](2026-11-25-crc-second-series.md) CRC series reports, and two from
the [pools series](2026-11-26-pools-first-series.md):

| Item | Result |
|---|---|
| 1. The NUCLEO-H723ZG's retries (CRC, 18 and 14 per series, always at the first image of a configuration) | explained by the image's own running time |
| 2. The Pico 2's differences between pass 1 and pass 2 (CRC and pools) | explained by the XIP cache's random replacement, which the RP2350 datasheet states; confirmed by a zero-write job of six passes |
| 3. The Pico 2's period of 8 bytes with the cache off (CRC) | narrowed, not explained; the flash interface's settings read; what would settle it below |
| 4. The NUCLEO-H723ZG's spread over the placements with the cache off (pools, 352 %) | explained for the configuration named (Contiki-NG); the others at the same placements fit the same rule, not shown instruction by instruction |

## 1. The NUCLEO-H723ZG's retries

**What was seen.**
- The runner (`kinds/crc/bench/run-crc.py`) looks at an image after a wait.
  If it has not finished, the run is thrown away and repeated with twice
  the wait. The wait is kept per configuration, and the next configuration
  starts at the shortest wait that has finished (5 s).
- On the H723, at 64 MHz with the cache off and on, the first series had 18
  retries and the second 14. Each came at the first image of a
  configuration that a run reached.

**What it is.** The image's running time is longer than the wait. It is
more than the cycles a record holds: before every timed call, the image
computes the expected CRC with the bitwise reference (`ref_crc()`,
`kinds/crc/bench/main.c`, `scenario()`), untimed, in the configuration's
loop and in the baseline's. So the image runs about the baseline's timed
cycles twice more. The running time estimated that way (`retries`):

| Configurations (second series) | Estimated running time | Retries each | Waits |
|---|---|---|---|
| the 4 CRC-16 configurations | 12.45–12.94 s | 2 | 5 s, 10 s, then 20 s finished |
| the 6 CRC-8 configurations | 9.25–9.74 s | 1 | 5 s, then 10 s finished |
| the 8 CRC-32 configurations | 3.38–3.87 s | 0 | 5 s finished |

- In both series every configuration above 10 s had two retries, every one
  between 5 and 10 s one, and every one below 5 s none.
- Second series: 4 × 2 + 6 × 1 = 14.
- First series: 6 CRC-16 configurations at 12.73–13.10 s give 2 each; 5
  CRC-8 configurations at 9.59–9.90 s and crcany's bitwise CRC-32 at 6.21 s
  give 1 each; 6 × 2 + 6 × 1 = 18.
- CRC-16 and CRC-8 take longer than CRC-32 because their bitwise reference
  is slower on this board. At 1024 bytes it costs 323 464 and 231 449
  cycles with the cache off, against 60 451 for CRC-32; with the cache on
  62 049 and 54 725 against 41 997 (the baseline rows of the second
  series). The reference is in every image, and its cost is the baseline
  row of every table.
- A check of the explanation: under method version 3 the H723 runs at
  520 MHz, and the same images' running time is about an eighth. The CRC
  jobs of method version 3 on the H723 (`~/vl-wt-crc-runs/v3/stm32h723`)
  logged no retry ("not finished": 0).

Nothing about the boards or the libraries follows from the retries: a
retried run is a complete run with a longer wait.

## 2. The Pico 2's differences between the passes

**What was seen** (`passes`):
- **CRC** (`records/crc/rp2350`): 90 means differ between pass 1 and pass 2.
  All are of the configuration, none of the baseline, all with the cache
  on. The minimum of the scenario's calls is the same in both passes in all
  90; the largest difference is 1.26 % (crcany `crc32iso_hdlc_word`, 4
  bytes).
- **Pools** (`records/pools/rp2350`): 116 of 4224 means differ. All are of
  the configuration, all with the cache on. The minimum is the same in 115;
  the largest difference is 6.30 %, heapless's `init`, which is one call.
- On the other five boards no mean differs between the passes, in either
  kind.

**Not the image that ran before** (`order`). The first series' runner runs
odd passes in the bundle's order and even passes in reverse, so an image
follows another image in each pass. In the pools series the Pico 2's images
of atomic-pool and ETL ran in two jobs (the smoke and the series job). Taking
the image that ran just before each run:

| | Cache-on means equal |
|---|---|
| the same image ran before, in both jobs | 311 of 348 |
| another image ran before | 361 of 420 |

The image that ran before does not decide it.

**What the datasheet says.** RP2350 datasheet (RP-008373), 4.4.1.2 "Cache
line states" (page 345 of the PDF): "Cache eviction policy is random, and
the cache only makes one attempt to select an eviction way." The cache is
"16 kB, two-way set-associative" (4.4.1). On a miss in a set whose two ways
are full, which of the two lines is replaced is chosen at random. So a
later access may miss in one run and hit in another, from the same start.

The same section says: "Cache line states are stored in the cache tag
memory (...). This memory contents do not change on reset", and "The
bootrom clears the tag memory upon entering the flash boot or NSBOOT (USB
boot) path". Every run is started by a reset through the boot
ROM and the boot stub. So every run starts from an empty cache, whatever
ran before, as the table above shows.

**It fits what was seen:**
- only with the cache on (with it off nothing is cached);
- only in some means, by a few slower calls: the minimum is the same, and
  the maximum differs (CRC: in 44 of the 90; pools: in 103 of the 116);
- never in the baseline: the reference is short code in the image's fixed
  part, whose lines conflict less.

**A correction.** The first CRC series report says, at check 1: "Which way
of the two-way XIP cache is replaced on a miss is not stated in the RP2350
datasheet (...) no replacement policy found". The datasheet states it, in
the sentence quoted above. That sentence is in the section on pinned lines,
not in the overview, which is presumably why the search missed it.

**What would confirm it** (a zero-write job, as a proposal):
- Run one image of a configuration that differed, six times in the same
  order: `run-pools.py rp2350 DIR --bundle 12 --adapter adapter_heapless
  --passes 6`.
- This is 48 runs and about 5 minutes, with no write: bundle 12 is on the
  board. The pools concurrency bundle (300) lies in the first 232 KB of
  flash, bundle 12 from 2 MB on, so the concurrency series does not touch
  it; the runner compares the flash with the bundle first and refuses to
  run if it differs.
- Read the option registers first (`read-options.py`).
- Expected if the explanation holds: the cache-off means are equal in all
  six passes; the cache-on means differ between passes 1, 3 and 5, which
  ran in the same order after the same images.
- If instead the cache-on means were equal in all passes of the same order,
  the explanation would be wrong.

**Confirmed** (that job, 2026-11-26 22:54 to 22:59 UTC: option registers
read first, 48 runs, no flash write; run files
`~/vl-wt-pools-runs/rp2350/U1`; `sixpass`). Over the 8 placements, 88 means
per cache state and library, `init` left out (one call):

| | All six passes equal | Pairs of the same order | Pairs of reverse order | Fastest call equal in all six |
|---|---|---|---|---|
| heapless, cache off | 88 of 88 | 88 | 88 | 88 of 88 |
| heapless, cache on | 55 of 88 | 64 to 69 | 64 to 71 | 88 of 88 |
| baseline, cache off | 88 of 88 | 88 | 88 | 88 of 88 |
| baseline, cache on | 88 of 88 | 88 | 88 | 88 of 88 |

- With the cache off every mean is the same in all six passes.
- With the cache on, the means differ between passes of the same order
  as often as between passes of reverse order, so the order of the runs
  does not decide them.
- The fastest call is the same in every pass. The largest difference
  between two passes is 12.35 % (placement 20, `mixed/alloc`, cache on).
- The baseline in the same runs is equal in all six passes, with the
  cache on too.

## 3. The Pico 2's period of 8 bytes with the cache off

**What was seen.** With the cache off, the CRC means at 1024 bytes repeat
every 8 bytes of placement in 12 of 20 configurations (first series, check
7).

**What the images show** (`crc-placement.py` on the images of the records,
then `residue`):
- The placements step by 4 bytes, so a loop's first address takes two
  values modulo 8 in each configuration (0 and 4, or 2 and 6).
- In 15 of the 20 configurations the mean is decided by that value alone:
  one mean for each.
- In four others (crcany `crc32iso_hdlc_byte` and `crc32iso_hdlc_word`,
  ETL `crc32_t256`, Rust `Table<1>`) it is decided but for at most 7
  cycles in 300 000 to 440 000.
- zlib moves by up to 1.5 % within one value.
- The size of the effect:

| Configuration | Loop | Mean at 1024 bytes, cache off, by the loop's first address modulo 8 |
|---|---|---|
| AceCRC `crc8` byte table | 12 bytes, 5 instructions | 0: 297 899; 4: 262 949 (13.3 %) |
| ETL `crc8_t256` | 12 bytes, 5 instructions | 0: 297 657; 4: 262 674 (13.3 %) |
| crcany `crc8smbus_byte` | 12 bytes, 5 instructions | 2: 326 024; 6: 362 642 (11.2 %) |
| the other 17 | 14 to 74 bytes | 0.00 to 0.17 %, zlib 1.50 % |

**What is known about the flash path:**
- With the cache disabled, accesses "ignore the cache contents, and always
  access the QSPI interface" (4.4.5, XIP_CTRL CTRL.EN_SECURE).
- The QMI does "8/16/32-bit accesses for uncached accesses, and 64-bit
  accesses for cache line fills" (4.4.2), and chains sequentially addressed
  accesses into one QSPI transfer while M0_TIMING.COOLDOWN is non-zero
  (12.14.2.1, "Transfer chaining").
- The board layer leaves the QMI as the boot ROM sets it; M0_TIMING read
  0x60007203 on 2026-11-11 (`firmware/common/rp2350/board.h`), whose
  COOLDOWN field (bits 31:30) is 1. So chaining is on: a loop's sequential
  fetches chain, and its backward branch starts a new transfer.

**Not explained.**
- Which of the two values is the slow one: it is 0 for two of the 12-byte
  loops and 6 for the third.
- Why the effect is large only for the shortest loops.
- Counting the units the loop touches gives it for one of the three
  12-byte loops only. For crcany the slow value (6) is the one whose loop
  touches three 8-byte units instead of two. For AceCRC and ETL the loop
  touches three 32-bit words and two 8-byte units at both values, and the
  value 0 is still the slow one.

**What would settle it:**
- First, zero-write: read over the probe, after a run, the QMI's
  M0_TIMING, M0_RFMT and M0_RCMD (0x400d000c, 0x400d0010, 0x400d0014) and
  XIP_CTRL CTRL (0x400c8000). That gives the read command, the chaining
  and the page-break setting the measurement ran with, today, under method
  version 3. It does not settle the question; it is what a model of the
  transfers needs.
  **Read** on 2026-11-26 at 22:59 UTC, after the six-pass job, with the
  last heapless image running (`probe-rs read`, no write). The fields
  are from the datasheet's tables (12.14, QMI registers; 4.4, XIP CTRL):
  - **M0_TIMING `0x60007203`:**
    - COOLDOWN 1 (chaining on), as read on 2026-11-11;
    - PAGEBREAK 2 (bursts break at 1024-byte boundaries);
    - SELECT_SETUP 0, SELECT_HOLD 0, MAX_SELECT 0 (no limit);
    - MIN_DESELECT 7, RXDELAY 2;
    - CLKDIV 3 (SCK = clk_sys / 3, 50 MHz at the 150 MHz of the runs).
  - **M0_RFMT `0x000492a8`:**
    - prefix 8 bits single width;
    - address, suffix (8 bits), dummy (16 bits) and data all quad width;
    - no DTR.
  - **M0_RCMD `0x000000eb`:** prefix 0xEB (fast read, quad I/O), suffix
    0x00 (no continuous-read mode).
  - **XIP CTRL `0x00000083`:**
    - EN_SECURE and EN_NONSECURE 1;
    - POWER_DOWN 0, SPLIT_WAYS 0, MAINT_NONSEC 0;
    - NO_UNTRANSLATED_NONSEC 1 (its reset value), the other NO_ bits 0.
  - **One 8-byte line by these settings:**
    - 8 SCK for the command, 6 for the address, 2 for the suffix, 4 for
      the dummy phase and 16 for the data;
    - 36 SCK, which is 108 system clock cycles, before the chip-select
      times;
    - a miss in our records is of that size: heapless's one-call `init`,
      cache on, placement 4, took 1904 cycles in one pass and 1784 in the
      other (`records/pools/rp2350`), 120 more.
- Then one measurement that needs images of its own (so not zero-write;
  for a decision, not a job): one 12-byte loop at the 8 positions of an
  8-byte unit, with the cache off, once as built and once with
  M0_TIMING.COOLDOWN set to 0 at the image's start.
  - If the difference between the values goes away without chaining, it
    is the chaining across the loop's end.
  - If it stays, it is the core's fetch of the instructions after the
    branch.
- The CRC images on the Pico 2 have been overwritten in part by the pools
  series' bundle 12, so the CRC images could not be re-run without a write
  either.

## 4. The NUCLEO-H723ZG's spread over the placements with the cache off (pools)

**What was seen** (`spread`, pass 1). Contiki-NG `memb`, `pair_full` free,
cache off, by placement:
- 298, 271, 278 and 250 cycles at placements 0, 4, 8 and 12;
- 1132, 1046 and 1086 at placements 16, 20 and 24;
- 272 at placement 28.

**Where its loop lies** (`loop memb_free`, the pools series' images):
- `memb_free` looks for the block's index in a loop of 16 bytes.
- At placements 16, 20 and 24 that loop crosses a 32-byte boundary (first
  byte at 20, 24 and 28 modulo 32).
- At the other five placements it lies inside one 32-byte block.
- The slow placements are exactly the crossing ones.
- 32 bytes is the flash word the H723's read buffer holds (256 bits,
  RM0468 4.3.8): the same fit the first CRC series found for its loops on
  this board (check 7).
- `pair_full` frees the block allocated last with 31 held, so the search
  runs many times through the loop each call; hence a factor of about 4.

**The other configurations at the same placements.**
- MemoryPool (`empty` alloc 34 against 19), CMSIS-RTX (`mixed` alloc) and
  RIOT (`empty` alloc, at 20 and 24) are slow at the same placements, or
  some of them.
- Their alloc paths are straight code, not loops. The function spans two
  32-byte blocks from placement 12 (MemoryPool) or 16 (RIOT) on, while the
  slow placements begin one step later.
- That fits the rule if the instructions an exhausted pool executes are
  the first 13 to 16 bytes of the function. The path was not traced
  instruction by instruction, so this is a fit, not shown.

Nothing here is a property of a library: with the cache on, the
factor of about 4 is gone (Contiki-NG `pair_full` free: 162–181 cycles over
the same placements), and the pages show every figure as the range over
the eight placements.

## Not studied tonight

The other items the CRC reports list as not explained:
- the order of AceCRC's seven placements on the G474 with the cache on;
- which loop start modulo 8 is the slow one on the G0B1;
- crcany's slicing by 4 on the Pico 2, faster at offset 1;
- the H723's RAM tables with the cache off;
- the Pico 2's hardware rows' fixed cost with the cache off;
- the G474's tables of 16 in RAM and in flash.
