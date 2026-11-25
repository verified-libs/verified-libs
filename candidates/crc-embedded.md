# Candidates: CRC calculation in software (survey)

Survey of 2026-11-24 for the choice of the next kind of library
([plan](../lab/plans/2026-11-24-next-library-kinds.md), kind D, the
owner's proposal). A kind without concurrency: the question is what a
CRC costs on each core, in cycles per byte and in bytes of flash, and
whether it gives the right value. Nothing here is tested yet. What a
project says about itself is given as "it documents".

How the facts were taken: as in the [pool survey](pools-embedded.md)
(shallow clones of 2026-11-24, licence from the licence file, no GitHub
API). ⚠ marks the project owner's own libraries; the owner has none of
this kind in public.

## The problem, and who has it

Every firmware that stores or sends data checks it: a frame on a UART or
a radio, a block of flash at start-up, a configuration in EEPROM. What
goes wrong in practice:

- **The wrong CRC.** A CRC is defined by width, polynomial, initial
  value, reflection of input and output, and final XOR. The same name
  means different things in different places: the catalogue of
  parametrised CRCs lists "CRC-16/CCITT" as an alias of CRC-16/KERMIT,
  while "CRC-16/CCITT-FALSE" is CRC-16/IBM-3740, a different CRC with the
  same polynomial
  ([CRC RevEng catalogue](https://reveng.sourceforge.io/crc-catalogue/all.htm)).
  Two devices then disagree on every frame, or a hand-written table is
  correct for one of them.
- **Faults in code generation.** pycrc's changelog records a fix (v0.8.2, 2014) for
  table-driven code that produced a wrong checksum for polynomials of a
  width below 8 with a table index width below 8
  ([pycrc changelog, Debian source](https://sources.debian.org/src/pycrc/0.10.0-3/CHANGELOG.md)).
- **Speed against flash.** A bitwise CRC needs no table and costs eight
  steps per byte; a table of 16 entries halves the steps; a byte table
  (256 entries, 1 KB for CRC-32) does one step per byte; slicing-by-8 or
  -16 (8 or 16 KB) does several bytes per step on cores that can load
  words fast. On a microcontroller the table is read from flash, and what
  a read from flash costs differs per chip: wait states, a flash
  accelerator, a data cache or none (below). Which variant is fastest on
  which core is a measurement, not a reading.

Who has it: anyone who picks a CRC routine for a Cortex-M0+ with 64 KB of
flash, or wants to know if the hardware CRC unit is worth the driver.

## Candidates

### Libraries with several implementations

| Library | Lang. | Licence | Newest commit | Version to pin | Implementations it offers | Where used |
|---|---|---|---|---|---|---|
| **ETL `etl::crc*`** (`include/etl/crc*.h`) | C++ | MIT | 2026-11-20 | 20.49.0 | Every CRC as a table of 4, 16 or 256 entries (`crc32_t4`, `crc32_t16`, `crc32_t256`; `crc32.h`) | Embedded C++ projects using ETL |
| **crcany** (Mark Adler) | C (generator) | Zlib | 2025-02-02 | v2.1 | Generates bitwise, bytewise and wordwise C code for any CRC of the catalogue, for 32- or 64-bit words and either byte order (`README.md`) | Reference implementation by zlib's co-author |
| **pycrc** | Python (generator) | MIT (by a secondary source; to be checked) | GitHub repository not reachable on 2026-11-24; Debian packages 0.10.0 | 0.10.0 | Bit-by-bit, bit-by-bit-fast and table-driven C code, optional slicing ([pycrc manual, Debian](https://manpages.debian.org/testing/pycrc/pycrc.1.en.html)) | AceCRC's code is generated with it |
| **AceCRC** (bxparks) | C, C++ | MIT | 2024-04-05 | v1.1.1 | Generated with pycrc: `bit`, `nibble` (16 entries in flash), `nibblem` (16 entries in RAM), `byte` (256 entries in flash), for CRC-8, CRC-16/CCITT and CRC-32 (`README.md`) | Arduino |
| **stbrumme crc32** | C++ | Zlib | 2021-09-29 | head `7a028136d54f` (no tags) | CRC-32 only: bitwise, half-byte table, tableless bytewise, byte table, slicing-by-4, -8 and -16 (`Crc32.h`, `readme.md`) | – |
| **CRC++** (d-bahr) | C++ | BSD-3-Clause | 2026-11-04 | release-1.2.3.0 | Generic, bit-by-bit or with a table (`CRC::Table`) for the catalogued CRCs (`README.md`) | – |
| **crc** crate (mrhooray/crc-rs) | Rust | MIT OR Apache-2.0 | 2026-01-02 | 3.4.0 | `NoTable`, `Table<1>` (256 entries, the default), `Table<16>` (slicing-by-16) for every CRC of `crc-catalog` (`README.md`) | Rust, `no_std` |
| **Boost.CRC** | C++ | BSL-1.0 | 2025-08-22 | boost-1.92.0 | Bitwise (`crc_basic`) and table-driven (`crc_optimal`) for any parameters | Boost users; desktop |

### Libraries with one implementation per CRC

| Library | Lang. | Licence | Newest commit | Version to pin | Implementation | Where used |
|---|---|---|---|---|---|---|
| **zlib `crc32`** | C | Zlib | 2026-11-20 | v1.4 | CRC-32 with byte tables and "braided" multi-word code | zlib, so almost everything |
| **Zephyr CRC** (`subsys/crc/*_sw.c`) | C | Apache-2.0 | 2026-11-23 | v4.5.0 | Tables of 16 entries (`crc32_sw.c`, `crc8_sw.c`) for CRC-4 to CRC-32C | Zephyr (e.g. MCUmgr's file checksum) |
| **libcrc** (lammertb) | C | MIT | 2021-04-21 | v2.0 | Table per CRC: CRC-8, CRC-16, CCITT, Kermit, DNP, Sick, CRC-32, CRC-64 (`src/`) | – |
| **FastCRC** (FrankBoesing) | C++ | MIT | 2024-01-29 | 1.45 | "uses the on-chip hardware for Teensy 3.0 / 3.1 / 3.2 / 3.5 / 3.6" and "uses fast table-algorithms for other chips" (`README.md`) | Arduino, Teensy |
| **RobTillaart CRC** | C++ | MIT | 2026-01-02 | 1.0.4 | Generic classes, calls `yield()` every `yieldPeriod` bytes "to keep RTOS environments happy" (`README.md`) | Arduino |
| **crc32fast** | Rust | MIT OR Apache-2.0 | 2026-11-14 | 1.5.5 | CRC-32 with SIMD where the CPU has it, a table fallback; `no_std` without the `std` feature (`README.md`) | Rust |

Not proposed: Linux `lib/crc32.c` (GPL-2.0, kernel code), crcengine
(GPL-3.0, a Python generator), Michael Barr's public-domain `crc.c`
(no repository found).

## Which CRCs to start with

Three, with the values of the catalogue (above) as the reference:

| CRC | Parameters | Check ("123456789") | Why |
|---|---|---|---|
| CRC-32/ISO-HDLC ("CRC-32") | poly 0x04C11DB7, init 0xFFFFFFFF, reflected, xorout 0xFFFFFFFF | 0xCBF43926 | Ethernet, zip, PNG; every library has it |
| CRC-16/IBM-3740 ("CRC-16/CCITT-FALSE") | poly 0x1021, init 0xFFFF, not reflected, xorout 0 | 0x29B1 | The common 16-bit CRC of serial protocols and bootloaders |
| CRC-8/SMBUS ("CRC-8") | poly 0x07, init 0, not reflected, xorout 0 | 0xF4 | Sensors, SMBus |

Next, if asked for: CRC-16/MODBUS (check 0x4B37), CRC-32/ISCSI
("CRC-32C", check 0xE3069283).

## What could be proven, and with which tool

Correctness can be shown in full, without concurrency:

- **Against a reference** of our own: the bitwise algorithm written from
  the catalogue's parameters (a few lines), checked against the
  catalogue's check value and residue. Every library's result is then
  compared with it on the host for every length from 0 to a few hundred
  bytes, every start alignment of the buffer (0 to 7), and random data,
  and in pieces (`update` called in parts) where the library allows it.
- **For every input of one step**: a CRC step is a function of (state,
  byte). For CRC-8 and CRC-16 all 2^16 × 256 or 2^8 × 256 pairs can be
  run against the reference on the host in seconds; for CRC-32 the
  2^32 × 256 pairs are too many for brute force, but CBMC (in the
  toolchain image) can prove the equivalence of one step for all inputs,
  or the GF(2)-linearity of the reference can be used to reduce the check
  to a basis once the implementation is shown to be linear. Either is
  a full proof for the step, and the loop over bytes follows.
- **On the board**: the same reference in every image (it is also the
  baseline), and every measured call's result compared with it, so a
  compiler or a core that computes it wrongly is seen.
- Miri for the Rust crates (pure Rust paths), sanitizers on the host for
  out-of-bounds table reads.

## What could be measured on the six boards

- **Operation**: `update(addr, len)` → CRC through `time_call`, for lengths
  1, 4, 16, 64, 256 and 1024 bytes, aligned and unaligned: cycles per
  call and per byte.
- **Configurations**: one per library × CRC × implementation, for
  example ETL t4, t16, t256 for three CRCs is nine. With about 12
  libraries that is 30 to 50 configurations, as many as the ring buffers.
- **Baseline**: our bitwise reference.
- **Where the table lies**: in flash (as shipped), and copied to SRAM
  (a second build of the same configuration), with the cache off and on.
  The boards differ here (the boards' `board.h` and manuals; not
  measured):

  | Board | Clock in the lab | Flash reads | What "cache on" covers |
  |---|---|---|---|
  | nRF5340 DK (Cortex-M33) | 64 MHz | flash with a cache | the instruction cache (`board_cache`); whether data reads from flash go through it is to be checked |
  | NUCLEO-G0B1RE (Cortex-M0+) | 64 MHz | wait states per RM0444 | instruction cache and prefetch only: a table read from flash pays the wait states |
  | NUCLEO-G474RE (Cortex-M4F) | 170 MHz | 4 wait states | the ART accelerator: instruction and data cache |
  | NUCLEO-H723ZG (Cortex-M7) | 64 MHz (reset clock) | flash behind the AXI bus | L1 instruction and data caches |
  | SAM D20 Xplained Pro (Cortex-M0+) | 48 MHz | 1 wait state | the NVM read cache |
  | Raspberry Pi Pico 2 (Cortex-M33) | 150 MHz | external QSPI flash | the XIP cache, for code and data from flash |

  So a 1 KB table may cost a wait state per byte on the NUCLEO-G0B1RE and
  nothing on the NUCLEO-H723ZG with its data cache, and a slicing table of
  16 KB may not fit the cache at all. This is the result readers cannot
  get from reading.
- **Hardware CRC as a point of comparison**: the STM32G0, G4 and H7 have a
  CRC unit with a programmable polynomial; the RP2350's DMA has a CRC
  "sniffer"; the SAM D20's DSU computes CRC-32 over memory; the nRF5340's
  application core has no general CRC unit (to be checked against each
  manual). One configuration per board where it exists, not a library.
- **Placement**: the method of version 2 applies to the code; for the
  table, the placement of the data is a new axis (in flash, the table
  moves with the code).
- **Code size**: code and table bytes per configuration, as the size probe
  does for ring buffers.
- **First guess of a first series**: 40 configurations × 8 placements =
  320 images per board; with tables of up to 16 KB the images are larger
  than the ring-buffer ones. **About 35 to 50 flash writes** on the six
  boards, close to the 48 of the ring-buffer series with the far call.
  Halved if the slicing-by-16 variants are left for later.

## What a filter and a column would be

- Filters: the CRC (by catalogue name and its aliases); flash budget
  (code and table at most N bytes); RAM budget; table in flash or RAM;
  language; licence.
- Columns: cycles per byte at 64 and 1024 bytes; cycles for a call of 1
  byte (the fixed cost); bytes of code and table; correct against the
  reference (yes, or the first wrong length).
- A view no ring-buffer page has: cycles per byte against flash bytes as
  a plot per board, with the libraries as points; the user's budget
  picks the point.

## Effort, in the terms of the step-1 report

- New: the adapter interface (`init`, `update`, `final`, small), the
  reference and the host test (small and complete), the scenarios
  (lengths), the build of each implementation per CRC, the table-in-RAM
  build, the page.
- Reused: boards, `time_call`, images, placements, bundles, export, the
  size probe's method.
- Not needed: the stress tests, GenMC, the contract check. That is the
  largest saving, and also why the kind uses less of what makes the
  project different (correctness under concurrency).
