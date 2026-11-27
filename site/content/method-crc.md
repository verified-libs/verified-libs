# Method: how CRC libraries are measured and checked

The method of one of the three kinds of library so far ([all kinds](kinds.md));
the other kinds': [embedded ring buffers](method.md) and
[fixed-block memory pools](method-pools.md).

The numbers are on the [results page](results-crc.md). The details and
every run's output are in [`kinds/crc/README.md`](../../kinds/crc/README.md),
the first series and the checks of its numbers in its
[report](../../reports/2026-11-25-crc-first-series.md), the second series
(tables in RAM, the boards' CRC units) in
[its report](../../reports/2026-11-25-crc-second-series.md); this page says
what they add up to.

## What is measured

Thirty-five configurations of eight libraries: one library, one CRC and one
implementation of it each, for three CRCs of the
[CRC RevEng catalogue](https://reveng.sourceforge.io/crc-catalogue/all.htm):
CRC-32/ISO-HDLC, CRC-16/IBM-3740 and CRC-8/SMBUS. The configurations, the
class of each (bitwise, a table of 16, a table of 256, slicing by 4, zlib's
braided words, a table-free byte step) and where its table lies are listed
in [steps 2 and 11 of the kind's README](../../kinds/crc/README.md). Twenty
are the libraries as they ship. Fifteen are those of them whose table lies
in flash, with the table moved to RAM (below). The same six boards as for
the ring buffers ([method](method.md), "Hardware").

**A table in RAM.**
- *How it is moved:* the library is built as for its configuration in
  flash. Then our build renames the section of each table symbol from
  `.rodata.*` to `.data.*` in a copy of the library's archive
  (`kinds/crc/bench/onecrc.py`, `ram_archive`; the symbols are named in
  `kinds/crc/ramtables.txt`). The image's start-up code copies `.data`
  from flash to RAM before `main`, as for any initialised variable.
- *The check:* the build checks that every table symbol lies once in RAM.
- *What is unchanged:* the code is the library's own.
- *Bytes:* the table counts twice. Its bytes stay in flash as the values
  the start-up code copies, and the same number lie in RAM, so flash bytes
  are the table and the code, as in flash, and RAM bytes are the table.
  The table says "RAM (copied at start by the image)", told apart from
  libcrc's and CRC++'s tables, which those libraries build in RAM
  themselves at run time.

**The board's CRC unit.** On four boards the same CRCs are also computed
by the board's own hardware, driven by our code
([`kinds/crc/adapter_hw.c`](../../kinds/crc/adapter_hw.c)); it is not a
library. It is a row of the same tables, after the libraries, labelled
"the board's CRC unit, driven by our code; not a library" in its name
cell; on the comparison it is scored like any row, and a filter takes it
out.
- *The STM32 CRC unit* (NUCLEO-G474RE, NUCLEO-G0B1RE, NUCLEO-H723ZG), for
  all three CRCs:
  - our code enables its clock once and sets its polynomial, size, input
    and output reflection and initial value;
  - it writes the message as bytes up to a word boundary, then words with
    their bytes swapped, then the last bytes, and reads the result;
  - for CRC-32 the unit has no final XOR, so our code XORs the result with
    0xFFFFFFFF.
- *The RP2350's DMA sniffer* (Pico 2), for CRC-32 and CRC-16 (it has no
  CRC-8 mode): one DMA transfer of the message to a dummy byte, with the
  sniffer computing the CRC on the way and our code waiting for the end.
- *Not measured:* the SAM D20's DSU (left out, see the plan), and the
  nRF5340, which has no such unit.
- *Bytes:* those of our code (its functions and its state) read from the
  board images; there is no table.

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
| NUCLEO-G474RE, 170 MHz | ART: instruction cache, a data cache of 256 bytes on DCode, prefetch (RM0440) | 4, as RM0440 requires at 170 MHz in boost mode (Table 9); ST's template for the board sets 8 |
| NUCLEO-G0B1RE, 64 MHz | an instruction cache of two 8-byte lines and prefetch; "No data cache is available on Cortex-M0+" (RM0444) | 2 |
| nRF5340 DK, 64 MHz | the application core's cache, 16-byte lines, instruction and data accesses to flash (nRF5340 Product Specification v1.6) | no setting |
| NUCLEO-H723ZG, 520 MHz | the Cortex-M7 L1 instruction and data caches, 32-byte lines | 3, as RM0468 requires for an AXI clock of 260 MHz (Table 16) |
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

- The SAM D20's DSU, which can compute a CRC-32 (left out of the second
  series, see its plan), and CRC hardware other than the units above.
- Slicing by 8 or 16, and other configurations of the libraries than the
  thirty-five.
- A table that a library builds in RAM is measured as it ships, with the
  building done before the timed calls (libcrc, CRC++). A table moved to
  RAM is measured only as our build moves it, by the start-up code; not
  by an application's own copy at another time.
- Code run from RAM: every configuration runs from flash.

## What the placements show

The figures in this section are those of the first series
([report](../../reports/2026-11-25-crc-first-series.md)); for the
NUCLEO-H723ZG and the nRF5340 DK that is before method version 3, in the
archived series linked from the [results page](results-crc.md).

**The measurement repeats exactly.** On five of the six boards every
number of the series is the same in both passes, to the cycle, and the
baseline measures the same in every image of a board of one CRC. On the Pico 2, 90
of 7680 means differ between the passes, all with the cache on, by at
most 1.26 %; the shortest call is the same in both passes, so the
difference lies in a few slower calls (the [series report](../../reports/2026-11-25-crc-first-series.md),
"The numbers, checked", check 1). That fits the Pico 2's XIP cache, which
replaces a line at random ("Cache eviction policy is random", RP2350
datasheet 4.4.1.2) and is cleared by the boot ROM at every start, so two
runs of one image can miss in different calls
([what was explained later](../../reports/2026-11-27-crc-unexplained.md), item 2).

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
4.3.8), in the three configurations looked at (measured at 64 MHz, before
method version 3). The NUCLEO-H723ZG runs at 520 MHz with 3 wait states,
as ST's template for the board sets it (method version 3); its numbers
with the cache off carry them ([below](#the-nucleo-h723zg-at-520-mhz)).
"Fits" is all that is claimed: the period matches the figure in the
manual; the mechanism was not measured. What is not explained is listed
in the series reports. Two items have been studied since in the data at
hand ([report of 2026-11-27](../../reports/2026-11-27-crc-unexplained.md)):
- on the Pico 2 with the cache off, a configuration's numbers are decided
  by where its loop starts modulo 8 (15 of 20 configurations exactly),
  which is the period of 8 bytes; which of the two positions is the slow
  one is still not explained (item 3);
- the NUCLEO-H723ZG's retries in the first two series came from the
  images' own running time, the untimed reference included, against the
  runner's first wait (item 1).

**What this means for the tables.** A difference between two
configurations is a difference only where their ranges over the eight
placements do not overlap. Every table therefore shows the range over the
placements, and with the cache off a single placement says little on the
NUCLEO-H723ZG, the nRF5340 DK and the two STM32 boards with 8-byte reads.

## Method version 3

Since 2026-11-26 the boards run at the clock of their vendor's start-up
code or template with the fewest flash wait states the manual allows, the
option registers are recorded with every series, and the nRF5340's boot
stub opens its debug port at every boot ([ring buffers' method page,
"Method version 3"](method.md#method-version-3), with the sources). For
the CRC kind that means:
- the NUCLEO-H723ZG runs at 520 MHz with 3 wait states instead of 64 MHz
  with 7, and its configurations were measured again (below);
- the nRF5340 DK's configurations were measured again, as its boot stub
  changed; the measured code is the same;
- the records of the other four boards stand: method version 3 builds
  their images byte for byte the same;
- the two boards' records before method version 3 are archived series,
  linked from the [results page](results-crc.md) under each board;
- the median of a scenario's 256 calls beside the mean was left out of
  method version 3 explicitly ([`DECISIONS.md`](../../DECISIONS.md),
  2026-11-26): it would need every benchmark measured again.

### The NUCLEO-H723ZG at 520 MHz

**Cycles with the cache off rise, the time falls.** The flash's wait
states count cycles of the AXI bus clock (RM0468 4.3.8, "Adjusting read
timing constraints"; Table 16), and since method version 3 the AXI bus
runs at half the core clock, 260 MHz (`firmware/common/stm32h723/board.h`:
the core divider /1, the bus divider /2).
- *A read from the flash array costs the same in core cycles:* before,
  (7 + 1) flash clocks at 64 MHz = 8 core cycles; now (3 + 1) flash clocks
  at 260 MHz = 4 × 2 = 8 core cycles.
- *Everything else an access pays on the bus side* (the bus matrix, the
  flash interface's read queue, the response) is counted in bus cycles,
  which cost one core cycle before and two now. So the cycles with the
  cache off rise by that overhead per flash access, times the number of
  accesses.
- *What the numbers show* (ETL `crc32_t256`,
  [its record](../../records/crc/stm32h723/adapter_etl_crc32_t256.json) of
  method version 3 against the archived one, first pass, cache off): per byte 32 → 38
  cycles at placement 0 and 34 → 42 at placement 4. The step between the
  two placements doubles, from 2 to 4 cycles per byte: one extra bus
  access per byte, caused by where the code lies, costs twice as many core
  cycles. The reference: 59 → 64 cycles per byte. With the cache on
  nothing changes (8 = 8 and 41 = 41 cycles per byte): the loop then makes
  no bus access.
- *Time:* 1024 bytes with the cache off, placement 0, took 32 796 cycles at 64 MHz
  (512 µs) and take 38 968 cycles at 520 MHz (74.9 µs): 19 % more cycles,
  6.8 times less time. Cycles at another clock are not times.

**The board's CRC unit on the H723 is slower in cycles with the cache on
too.** Its rows are the only ones whose numbers with the cache on changed:
per byte from 1.5 to 3.0 cycles, a call on 16 bytes from 55 to 85 cycles,
for all three CRCs ([the H723's records](../../records/crc/stm32h723/adapter_hw_crc32.json)
against the archived ones). The unit is a peripheral that our code writes
and reads over an AHB bus, and since method version 3 the AHB clock is half
the core clock (`firmware/common/stm32h723/board.h`: HPRE /2), so each of
those accesses costs twice as many core cycles; that fits the doubling
exactly, and was not measured further. In time it is faster: 1024 bytes
took 1567 cycles at 64 MHz (24.5 µs) and take 3109 cycles at 520 MHz
(6.0 µs).

**What is not explained.** The number of bus accesses behind each rise
was not counted: how the Cortex-M7 fetches with its instruction cache off,
and how the flash interface queues and overlaps reads. So the overhead of
about 2 bus cycles per access is inferred from one pair of placements, not
measured; the rise per call of 1 byte (+23 cycles for the reference, +28
for the configuration) cannot be split between
instruction fetches and table loads; and why the configuration's rise
exceeds the reference's is not known. A test that counts accesses
(the same loop from ITCM, or the table in DTCM, at both clocks) was not
run.
