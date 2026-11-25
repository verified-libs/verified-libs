# Method: how CRC libraries are measured and checked

The method of one of the two kinds of library so far ([all kinds](kinds.md));
the other kind's: [embedded ring buffers](method.md).

The numbers are on the [results page](results-crc.md). The details and
every run's output are in [`kinds/crc/README.md`](../../kinds/crc/README.md),
the first series and the checks of its numbers in its
[report](../../reports/2026-11-25-crc-first-series.md); this page says
what they add up to.

## What is measured

Twenty configurations of eight libraries: one library, one CRC and one
implementation of it each, for three CRCs of the
[CRC RevEng catalogue](https://reveng.sourceforge.io/crc-catalogue/all.htm):
CRC-32/ISO-HDLC, CRC-16/IBM-3740 and CRC-8/SMBUS. The configurations, the
class of each (bitwise, a table of 16, a table of 256, slicing by 4, zlib's
braided words, a table-free byte step) and where its table lies are listed
in [step 2 of the kind's README](../../kinds/crc/README.md). The same six
boards as for the ring buffers ([method](method.md), "Hardware").

**One call, timed.** Each call computes the CRC of a whole message (the
one-shot call); the board's cycle counter is read around it by the same
timing routine as the ring-buffer benchmark (`time_call`,
`firmware/common/<board>/board.h`), and the cost of reading the counter is
subtracted.

**Scenarios.** Messages of 1, 4, 16, 64, 256 and 1024 bytes; the message
at an 8-byte boundary and one byte after it; the cache off and on. That is
24 scenarios. Each is 256 timed calls; one byte of the message changes
between calls, and every call's result is compared with the reference's
(below), outside the timed call. A record holds the minimum, maximum,
mean, first value and count of the 256 calls per scenario.

**One image per configuration and placement.** As version 2 of the
ring-buffer benchmark: an image holds a fixed part (the timing code,
`main`, the reference; the same bytes in every image of a board) and one
configuration. Each configuration is built at eight placements (its code
moved by 0, 4 ... 28 bytes behind the fixed part), with 6144 bytes between
the adapter and the library (a far call). Every image is run in two
passes. A record holds the eight images and both runs of each.

**The baseline** is the reference of the configuration's CRC, timed in
the same image with the same scenarios. It is part of the fixed part, so
it lies at the same offset from the start of every image of a board,
whatever the configuration and its placement.

**What "cache on" is on each board.** The image switches the board's
cache off, runs every scenario, switches it on and runs them again
(`board_cache()`, `firmware/common/<board>/board.h`). The code and the
tables are in flash on every board, so what the switch covers differs
(quoted from the manuals in
[`lab/plans/2026-11-24-crc-flash-read-sources.md`](../../lab/plans/2026-11-24-crc-flash-read-sources.md)):

| Board | Cache on | Flash wait states |
|---|---|---|
| NUCLEO-G474RE, 170 MHz | ART: instruction cache, a data cache of 256 bytes on DCode, prefetch (RM0440) | 4 |
| NUCLEO-G0B1RE, 64 MHz | an instruction cache of two 8-byte lines and prefetch; "No data cache is available on Cortex-M0+" (RM0444) | 2 |
| nRF5340 DK, 64 MHz | the application core's cache, 16-byte lines, instruction and data accesses to flash (nRF5340 Product Specification v1.6) | no setting |
| NUCLEO-H723ZG, 64 MHz | the Cortex-M7 L1 instruction and data caches, 32-byte lines | 7, the power-on default (RM0468 allows 0 or 1 at 64 MHz) |
| SAM D20 Xplained Pro, 48 MHz | the NVM controller's direct-mapped cache; the data sheet does not say whether data reads are cached | 1 |
| Raspberry Pi Pico 2, 150 MHz | the 16 kB XIP cache, 8-byte lines, in front of the external QSPI flash; with it off every read goes to the flash | a miss is a QSPI transfer |

## What "the same as the reference" was checked for, and how

**The reference** (`kinds/crc/ref_crc.c`) is the bitwise algorithm written
from the catalogue's parameters. It is checked against the catalogue's
check value and residue, against an implementation that is not ours
(Python's `zlib.crc32` and `binascii.crc_hqx`, for CRC-32 and CRC-16), and
four builds with one parameter wrong must each be caught (README step 1).

**Every configuration on the host** (README step 3), built plain and with
the address and undefined-behaviour sanitizers: the check value; every
length from 0 to 300 bytes at every start alignment from 0 to 7; every
length cut into two calls at every point; and every input of one step of
the CRC: all of them for CRC-8 and CRC-16, every last byte after 65536
random states for CRC-32. Five deliberately broken adapters must each be
caught. The Rust adapter also runs under Miri.

**CRC-32 for every input** (README step 3b), by CBMC, with the sources
preprocessed by the boards' compiler: for one configuration of each class,
the library's result equals the reference's for every previous CRC value
and every message of the length given. crcany's slicing by 4 is proven in
two parts (a lemma by CBMC, and all 2^32 values computed). zlib's braided
code: every message of 24 bytes at offsets 0 and 1 directly, and of 40
and 60 bytes at offset 0 in parts, where one part (that two functions
which are affine and agree at the zero input and at every input with one
bit set are the same function) is argued, not machine-checked. Every proof
has a control with one wrong value that must fail. What is not covered by
a proof is listed there: other lengths of zlib's braided loop, the C++ and
Rust configurations, and libcrc's table built at run time.

**On the boards**, every timed call's result is compared with the
reference's; a record is made only if every call of every run agreed
(`errors` and `baseline_errors` 0).

## What is not measured

- The boards' CRC hardware (the CRC units of the STM32 parts, for
  example): only software is measured.
- Slicing by 8 or 16, and other configurations of the libraries than the
  twenty.
- A table copied from flash to RAM by the application before use. libcrc
  and CRC++ build their tables in RAM themselves; that is measured as they
  ship it, with the building done before the timed calls. A series with
  the tables in RAM is to follow this first publication
  ([`DECISIONS.md`](../../DECISIONS.md), 2026-11-25); the report's check 6
  shows where it would matter most: with the cache off, and on the boards
  with the slowest flash.
- Code run from RAM: every configuration runs from flash.

## What the placements show

**The measurement repeats exactly.** On five of the six boards every
number of the series is the same in both passes, to the cycle, and the
baseline measures the same in every image of a board of one CRC. On the Pico 2, 90
of 7680 means differ between the passes, all with the cache on, by at
most 1.26 %; the shortest call is the same in both passes, so the
difference lies in a few slower calls (the [series report](../../reports/2026-11-25-crc-first-series.md),
"The numbers, checked", check 1).

**A mean includes the first call.** Each scenario's mean is over its 256
calls, the first included. The scenarios run in a fixed order: the cache
off, then on; within each, lengths 1 to 1024 bytes, and for each length
offset 0, then 1 (`kinds/crc/bench/main.c`, `run_all`). So the 1-byte
figure at offset 0 with the cache on is the first scenario after the
cache is switched on, and its first calls are the first with the cache
on; the tables here do not use it. In the figures they do use, the first call
adds at most 2.45 % to a mean (Pico 2, 16 bytes) and at most 0.25 % on
the other boards (the report, check 1).

**Where the code lies moves the numbers more than repetition does.** The
same configuration, built eight times with its code moved by 0, 4 ... 28
bytes, gives different means. With the cache off the spread over the
eight placements reaches 23 % on the NUCLEO-G474RE, 19 % on the
NUCLEO-G0B1RE, 41 % on the nRF5340 DK and 447 % on the NUCLEO-H723ZG; it
stays at 0 on the SAM D20 and below 14 % on the Pico 2. With the cache
on it is at most 0.12 % on the nRF5340 DK, 0.23 % on the Pico 2, 2.4 % on
the NUCLEO-H723ZG and 4.5 % on the SAM D20, but up to 23 % and 25 % on
the NUCLEO-G474RE and NUCLEO-G0B1RE (check 7).

**The spread repeats with a step that fits each board's flash or cache.**
On the NUCLEO-G474RE and NUCLEO-G0B1RE the numbers with the cache off
repeat every 8 bytes, the width of their flash reads (64 bits, RM0440 3.2
and RM0444 3.2); on the nRF5340 DK every 16 bytes, its cache line (128
bits, nRF5340 Product Specification v1.6, 5.4.1); on the NUCLEO-H723ZG a
configuration is slow exactly where its loop crosses a 32-byte boundary,
the width of the flash word that its read buffer holds (256 bits, RM0468
4.3.8), in the three configurations looked at. The NUCLEO-H723ZG runs at
the 7 wait states it has after power-on, which RM0468 does not require at
64 MHz (Table 16: 0 or 1); its numbers with the cache off carry them.
"Fits" is all that is claimed: the period matches the figure in the
manual; the mechanism was not measured. What is not explained is listed
in the report.

**What this means for the tables.** A difference between two
configurations is a difference only where their ranges over the eight
placements do not overlap. Every table therefore shows the range over the
placements, and with the cache off a single placement says little on the
NUCLEO-H723ZG, the nRF5340 DK and the two STM32 boards with 8-byte reads.

## For the next version of the method

Two changes are noted for when both kinds are measured again, not before
([`DECISIONS.md`](../../DECISIONS.md), 2026-11-25):

- the NUCLEO-H723ZG with the flash wait states a user would set at its
  clock, not the 7 it has after power-on;
- the median of a scenario's 256 calls beside the mean, so that a few slow
  calls can be told from a shifted level.
