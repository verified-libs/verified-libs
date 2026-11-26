# CRC: the boards' CRC hardware as reference rows, and the tables in RAM: a proposal

**Decided 2026-11-25** by the owner: all five points of part 5 as proposed
([`DECISIONS.md`](../../DECISIONS.md), 2026-11-25), on the condition that the
present images are built byte for byte unchanged.

2026-11-25. A proposal for the owner, before anything is built: no board
is run, no flash is written and no CRC test source is changed by it. The
CRC kind's method is frozen at the tag `crc-method-freeze`
([`DECISIONS.md`](../../DECISIONS.md), 2026-11-25), so every change named in
part 4 needs the owner's word. Two things that were left open at the first
publication, in one series:

- the boards' CRC hardware, which the method page lists under "What is not
  measured";
- the tables copied to RAM: the open question of the series report
  ([`reports/2026-11-25-crc-first-series.md`](../../reports/2026-11-25-crc-first-series.md),
  "What "cache on" covers for a table read from flash" and check 6),
  decided to follow the first publication (DECISIONS 2026-11-25).

Our three CRCs ([`kinds/crc/ref_crc.c`](../../kinds/crc/ref_crc.c), the
parameters of the CRC RevEng catalogue):

| CRC | width | poly | init | refin | refout | xorout |
|---|---|---|---|---|---|---|
| CRC-32/ISO-HDLC | 32 | 0x04C11DB7 | 0xFFFFFFFF | yes | yes | 0xFFFFFFFF |
| CRC-16/IBM-3740 | 16 | 0x1021 | 0xFFFF | no | no | 0x0000 |
| CRC-8/SMBUS | 8 | 0x07 | 0x00 | no | no | 0x00 |

## 1. The CRC hardware, board by board

From the vendors' manuals in `~/vl-dev/datasheets` (read as text; nothing
fetched). "Computes it" means: the unit produces the catalogue's result
for every message with the settings named, as the manual describes them.
None of it has been tried on a board; every call of a row is checked
against the reference on the board, as for the libraries, and a setting
that is wrong shows there.

### NUCLEO-G474RE, NUCLEO-G0B1RE, NUCLEO-H723ZG: the CRC calculation unit

The same unit in all three manuals: RM0440 Rev 9, section 16 (STM32G4);
RM0444 Rev 6, section 14 (STM32G0); RM0468 Rev 3, section 21 (STM32H723).
Quoted from RM0440 16.2 and 16.3.3 (the list of main features is word for word the same in RM0444 14.2 and RM0468 21.2):
"Uses CRC-32 (Ethernet) polynomial: 0x4C11DB7"; "Alternatively, uses fully
programmable polynomial with programmable size (7, 8, 16, 32 bits)";
"Handles 8-,16-, 32-bit data size"; "Programmable CRC initial value";
"Reversibility option on I/O data"; "CRC computation done in 4 AHB clock
cycles (HCLK) for the 32-bit data size" (2 for 16 bits, 1 for 8); the data
register "can be accessed by word, right-aligned half-word and right-aligned
byte", and "a CRC for 5 bytes can be computed with a word write followed by
a byte write". Input reversal (REV_IN) by byte, half-word or word; output
reversal (REV_OUT) of the whole register. The manuals name no output XOR.
"Even polynomials are not supported" (all three of ours are odd).

| CRC | computes it? | settings |
|---|---|---|
| CRC-32/ISO-HDLC | the CRC register, yes; the final XOR, no | POLYSIZE 32, the default polynomial, INIT 0xFFFFFFFF, REV_IN by word for word writes and by byte for byte writes, REV_OUT 1; the final XOR with 0xFFFFFFFF is one CPU instruction in our code |
| CRC-16/IBM-3740 | yes | POLYSIZE 16, POL 0x1021, INIT 0xFFFF, no reversal; bytes fed in message order (byte writes, or word writes of byte-swapped words) |
| CRC-8/SMBUS | yes | POLYSIZE 8, POL 0x07, INIT 0x00, no reversal; bytes fed in message order |

How the initial value is used with a polynomial of fewer than 32 bits is
not spelled out in the text read; it is checked on the board.

### nRF5340 DK: no unit for a buffer

nRF5340 Product Specification v1.6 (4406_640): the CRC generators are in
RADIO (7.26.4) and NFCT (7.20). RADIO "calculates the CRC over the whole
packet excluding the preamble", and its latches "are not available to be
read by the CPU at any time"; RADIO is a peripheral of the network core,
not of the application core we measure. NFCT adds and checks the 16-bit CRC
of NFC frames. CRYPTOCELL 312 (7.7) lists no CRC. So: no row for the
nRF5340 DK.

### SAM D20 Xplained Pro: the DSU's CRC-32

SAM D20 Family Data Sheet DS60001504K, 12.11.3 "32-bit Cyclic Redundancy
Check CRC32": the Device Service Unit computes "the industry standard CRC32
algorithm using the generator polynomial 0xEDB88320 (reversed
representation)" over a memory range, "including Flash and AHB RAM"; the
initial value is written to DATA ("usually 0xFFFFFFFF"), and "the read value
must be complemented to match standard CRC32 implementations". ADDR and
LENGTH "must be word-aligned". From the CPU it works "at any memory
location" (internal range).

| CRC | computes it? |
|---|---|
| CRC-32/ISO-HDLC | for a word-aligned buffer of a multiple of 4 bytes, yes (seed 0xFFFFFFFF, the complement in our code); one byte after an 8-byte boundary, or 1 byte long: no |
| CRC-16/IBM-3740, CRC-8/SMBUS | no |

The benchmark's grid has 1-byte messages and messages one byte after an
8-byte boundary: the DSU cannot compute 14 of the 24 scenarios, and a
software tail for them would no longer be the hardware. A DSU row needs the
grid to skip scenarios (a change to `kinds/crc/bench/main.c`, the record
writer and its check), so this proposal leaves it out and lists it for the
owner.

### Raspberry Pi Pico 2: the DMA sniffer

RP2350 Datasheet (RP-008373-DS-2), 12.6.8.2 "CRC calculation" and the
register SNIFF_CTRL: "The DMA can watch data from a given channel passing
through the data FIFO, and calculate checksums based on this data"; "CRC-32,
MSB-first and LSB-first"; "CRC-16-CCITT, MSB-first and LSB-first"; the
result register "is both readable and writable, so that the initial seed
value can be set"; on the result, bit inversion, bit reversal and byte swap,
which "do not affect the CRC calculation, just how the data is presented".
CALC: CRC32, CRC32R ("with bit reversed data"), CRC16, CRC16R. No 8-bit
CRC.

| CRC | computes it? | settings |
|---|---|---|
| CRC-32/ISO-HDLC | yes, by the description | CALC CRC32R, seed 0xFFFFFFFF, the result read bit-reversed and inverted (OUT_REV, OUT_INV); to be confirmed on the board |
| CRC-16/IBM-3740 | yes, by the description | CALC CRC16 (polynomial 0x1021, MSB-first), seed 0xFFFF; which bits of the result hold it is not stated in the text read: to be confirmed on the board |
| CRC-8/SMBUS | no | |

The DMA moves the data with byte transfers, so every length and both
offsets are possible.

### Other units that compute a CRC, and whether "one call on a buffer" is fair

- **STM32 CRC unit**: the call writes the buffer to the data register and
  reads the result. A fair one-call comparison: the CPU does the work the
  library's loop would do, through the unit.
- **RP2350 DMA sniffer**: the call starts a DMA transfer of the buffer to a
  dummy destination with the sniffer on, waits for it to end and reads the
  result. Fair as a call that returns the CRC; what it costs is the setup
  and the wait. A program can let the CPU do other work during the transfer;
  the row measures the call, and the page says so.
- **SAM D20 DSU**: the same shape (start, wait, read), but only for
  word-aligned buffers (above).
- **STM32 DMA feeding the CRC unit**: possible (a memory-to-peripheral
  transfer to the data register). Not proposed: the CPU-fed unit is the
  common use, and a second hardware row per CRC would double the images.

## 2. What a hardware row is

- **Our own code calling the unit**, one adapter per board and CRC, as the
  reference (baseline) is our own code: the page says so on every such row
  ("the board's CRC unit, driven by our code; not a library"). It enables
  the unit's clock and sets it up in `init()` (outside the timed calls, as
  libcrc's table is built there), and its one-shot call feeds the message
  and returns the result.
- **The same grid** (6 lengths, 2 offsets, cache off and on, 256 calls),
  each call's result compared with the reference on the board, the
  baseline timed in the same image, eight placements, two passes. Rows
  only where the unit computes the CRC: the STM32 boards 3 CRCs each, the
  Pico 2 CRC-32 and CRC-16, the SAM D20 and the nRF5340 DK none.
- **Flash and RAM**: the adapter's code only; the unit has no table.
  Counted from the image as for every configuration.
- **"Cache on" for a hardware row**: the message lies in RAM and the unit
  reads no flash, so the cache changes only how the feeding loop (STM32)
  or the setup and wait (Pico 2) are fetched. On the NUCLEO-H723ZG the
  message is in DTCM, which the cache does not cover.
- **Host tests and proofs** do not apply to a unit: correctness rests on the
  check of every call on the board. Said on the method page.

## 3. The tables in RAM

- **Which**: the 15 configurations whose table lies in flash (ETL t256 and
  t16 for all three CRCs, crcany byte for all three and word for CRC-32,
  the Rust crate, Zephyr's CRC-32 and CRC-8 tables of 16, zlib, AceCRC).
  libcrc and CRC++ build their tables in RAM already; crcany's bitwise code
  and Zephyr's CRC-16 have none.
- **How**: the same code and the same table, moved from `.rodata` to `.data`
  by the image's linker script, so that the board's start-up code (unchanged,
  `firmware/common/<board>/startup.c`) copies it to RAM before `main`, as it
  copies every initialised variable. Nothing of a library changes. Each
  image is checked for the table's symbol lying in RAM (the symbol per
  configuration named in a list; for the Rust crate the input section has
  to be found first). The copy is not measured, as libcrc's building is not.
- **Bytes**: the table is counted as RAM; the flash bytes stay as they are,
  since the initial copy stays in flash. On the NUCLEO-H723ZG the RAM of the
  images is DTCM (`stm32h723.ld`).
- **What it answers**: the same instructions with the table in flash and in
  RAM, per configuration, on every board, with the cache off and on. The
  report's check 6 could compare only different libraries (libcrc's RAM
  table against the others' flash tables); this compares each configuration
  with itself, and so says how much of a difference is the memory and how
  much the loop, and on the NUCLEO-G474RE whether the 256-byte data cache
  explains its tables of 256 (report, "What "cache on" covers").

## 4. Cost, counted

Images per board: (15 tables in RAM + hardware rows) x 8 placements.

| Board | new configurations | images | segments (est.) | per bundle | flash writes (est.) | runs (2 passes) | time (est.) |
|---|---:|---:|---:|---:|---:|---:|---:|
| NUCLEO-G474RE | 15 + 3 | 144 | 8 | 2 | 4 | 288 | 30 min |
| NUCLEO-G0B1RE | 15 + 3 | 144 | 8 | 2 | 4 | 288 | 56 min |
| NUCLEO-H723ZG | 15 + 3 | 144 | 8 | 4 | 2 | 288 | 59 min |
| nRF5340 DK | 15 | 120 | 7 | 4 | 2 | 240 | 66 min |
| SAM D20 Xplained Pro | 15 | 120 | 7 | 1 | 7 | 240 | 88 min |
| Raspberry Pi Pico 2 | 15 + 2 | 136 | 8 | 16 | 1 (in parts) | 272 | 3 h 7 min |
| **all** | | **808** | | | **20** | **1616** | **about 8 h** |

How these are estimated: the 15 configurations' slots in `slots.txt` (the
same code, so about the same size) add up to 1 605 632 bytes (6.1
segments of 256 KB) and a hardware image is taken at the smallest slot
(12 288 bytes); segments per bundle and writes as in the first series
(writes = segments / segments per bundle, rounded up: 9 segments gave 5, 5,
3, 3, 9 and 1). Times: runs x the first series' time per run of the board
(33, 62, 88, 65, 118 and 220 minutes for 320 runs, flash writes included).
The exact numbers come from `crcslots.py assign` once the configurations
exist, before any write. The Pico 2's bundle of about 8 segments is written
in parts of at most 250 units of 4096 bytes (about 512 units: 3 parts), as
its first bundle was (`kinds/crc/README.md`, step 9); it counts as one
write. Flash writes so far for the lab's boards: 115 (series report).

**What changes** (each a CRC test source, so each needs the owner's word;
the ledger, `lab/tools/image-ledger.py`, must then show that the 160 images
of every board's present records are built byte for byte as before, so that
the 120 records stay):

- new: `kinds/crc/adapter_hw.c` (the hardware adapters, by board);
- new: a list of the table symbols to move to RAM, per configuration
  (e.g. `kinds/crc/ramtables.txt`);
- `kinds/crc/configs.txt`: the new configurations, and a way to say on
  which boards one exists (a hardware row exists on four boards only);
- `kinds/crc/slots.txt`: lines added by `crcslots.py assign`, no line
  touched;
- `kinds/crc/adapters.h`: the new descriptors;
- `kinds/crc/bench/onecrc.py`: the `.data` rule in the image's linker
  script for a RAM configuration, the check that the table lies in RAM, and
  building a configuration only on its boards;
- `kinds/crc/bench/crcslots.py`: the per-board list of configurations.

Not changed: `firmware/common` (board.h, start-up code, linker scripts),
`kinds/crc/bench/main.c` (the grid, the reference), `run-crc.py`,
`crcrecords.py`, `crcverify.sh`, the libraries. Outside the test sources:
`kinds/crc/test_crc.c` (the host test skips the hardware adapters),
`kinds/crc/README.md` (the class table that the pages read), the site's
programs and the MCP server.

## 5. For the owner

1. **Coverage**: hardware rows on the three STM32 boards (3 CRCs) and the
   Pico 2 (CRC-32, CRC-16); none on the nRF5340 DK; the SAM D20's DSU left
   out (it cannot do 14 of the 24 scenarios), or the grid changed for it.
2. **Tables in RAM**: all 15 configurations on all six boards, or fewer.
3. **Flash writes**: about 20 more (counted exactly before any write).
4. **Frozen sources**: the changes listed in part 4, with the ledger
   showing the 120 present records unchanged.
5. **The pages**: hardware rows on the results and comparison pages set
   apart below the configurations, as the reference is, labelled "the
   board's CRC unit, driven by our code; not a library", with no score; the
   RAM variants as configurations of their own ("…, table copied to RAM"),
   with a score like any other.

## Counted (step 3, 2026-11-25, before any flash write)

The configurations, slots and images exist (commit of the build:
`kinds/crc/bench/onecrc.py table` on all six boards, every image checked:
fixed part, placement, the adapter's functions, and for the 15 RAM
configurations every table symbol once in RAM). `crcslots.py assign`: 144
new slots (18 configurations x 8), no line of `slots.txt` changed, 304
images in segments 100 to 115. Per board, from the bundles built (a bundle
that holds a new image is written; the others stay as the first series
left them):

| Board | images (new) | bundles written | units | runs (2 passes) | time (first series' time per run) |
|---|---:|---|---|---:|---:|
| NUCLEO-G474RE | 304 (144) | 54, 55, 56, 57: 4 writes | 125, 124, 117, 106 | 288 | 30 min |
| NUCLEO-G0B1RE | 304 (144) | 54, 55, 56, 57: 4 writes | 125, 124, 117, 106 | 288 | 56 min |
| nRF5340 DK | 280 (120) | 27, 28: 2 writes | 176, 222 | 240 | 66 min |
| NUCLEO-H723ZG | 304 (144) | 27, 28: 2 writes | 248, 222 | 288 | 58 min |
| SAM D20 Xplained Pro | 280 (120) | 109 to 115: 7 writes | 41 to 64 | 240 | 88 min |
| Raspberry Pi Pico 2 | 296 (136) | 6 (716 units, 3 parts), 7 (222 units): 2 writes | | 272 | 3 h 7 min |
| **all** | | **21 writes** | | **1616** | **about 8 h** |

One more write than estimated: the Pico 2's bundle 6 holds 65 new images
beside the first series' 160 and is written again (its old images are the
same bytes), and bundle 7 holds the rest.

**The present images stand.** `crcverify.sh` with `VL_TREE=1` on the 120
records: 20 of 20 `MATCH` on each of the six boards, 160 images each;
`lab/tools/image-ledger.py`: 120 match (`records/rebuilt.json`).

**Smoke, every step shrunk, per board before its series** (the boards at
hand: NUCLEO-G474RE, NUCLEO-G0B1RE, SAM D20 Xplained Pro; one at a time, on
the reviewer's OK per board run): the board's first new bundle is written
(54 on the two NUCLEO boards, 109 on the SAM D20: a write of the series, not
an extra one); `run-crc.py` runs two configurations of it in two passes (the
NUCLEO boards: `adapter_hw_crc32` and `adapter_etl_crc32_t256_ram`; the SAM
D20: `adapter_etl_crc32_t256_ram`), 32 or 16 runs; every call is compared with
the reference on the board, which settles the hardware settings the manual
leaves open (the initial value with a polynomial of 16 or 8 bits is tried by
the series' first CRC-16 and CRC-8 runs); `crcrecords.py` makes their
records in a scratch directory and `crcverify.sh` checks them (`MATCH`). Then
the series: `run-crc.py --flash --passes 2` on the board's new bundles (the
smoke bundle is on the board already and is not written again).
