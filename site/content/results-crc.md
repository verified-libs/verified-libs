# Results: CRC calculation

The results of one of the two kinds of library so far; the other is embedded
ring buffers ([all kinds](kinds.md), [ring buffer results](../../RESULTS.md)).
The same numbers by CRC, board, message and cache, with every length and both
starts: [Compare](compare-crc.html).

> **Status: the kind's first and second board series.** Every number comes from a
> record under [`records/crc`](../../records/README.md) that can be rebuilt
> and repeated from this repository ([how](reproduce.md)). Numbers are
> facts about the pinned versions, the configuration and the board below,
> not general rankings.

Thirty-five configurations of eight libraries, for three CRCs of the
[CRC RevEng catalogue](https://reveng.sourceforge.io/crc-catalogue/all.htm)
(CRC-32/ISO-HDLC, CRC-16/IBM-3740, CRC-8/SMBUS), on six boards. Twenty are
the libraries as they ship. Fifteen are those of them whose table lies in
flash, with the table copied to RAM by the image at start ("table in RAM").
The last row of a table, on the four boards that have one, is the board's
CRC unit, driven by our code; it is not a library, and its name cell says
so.

Every configuration was checked against a reference before it was timed,
and every timed call's result was compared with the reference's on the
board ([method](method-crc.md)). Two series, two passes each:
- the first, commit `6301058`, 2026-11-24 to 2026-11-25
  ([report](../../reports/2026-11-25-crc-first-series.md));
- the second (tables in RAM and the boards' CRC units), commits `04a2197`
  and `40f1958`, 2026-11-25
  ([report](../../reports/2026-11-25-crc-second-series.md)).
Compiler: arm-none-eabi-gcc 14.2.1, `-O2 -DNDEBUG`, newlib-nano; the Rust
crate with rustc 1.99.1 at the same optimisation level; pinned [toolchain image](../../toolchain/README.md). The
libraries are fetched at the commits in
[`kinds/crc/libs.lock`](../../kinds/crc/libs.lock), never copied into this
repository.

## How to read the tables

One table per board, CRC and cache setting: the cache on first, then off.
One row per configuration, in the order of
[`kinds/crc/configs.txt`](../../kinds/crc/configs.txt); the order is not a
ranking. Each configuration's name links to its record.

- **Class** and **Table**: the algorithm and where its table lies
  ([step 2 of the kind's README](../../kinds/crc/README.md)).
- **Flash bytes**: the table in flash and the code at `-O2` for the
  board's core; **RAM bytes**: the table in RAM
  ([step 4 of the kind's README](../../kinds/crc/README.md)). A table
  "RAM (copied at start by the image)" counts in both: its bytes stay in
  flash as the values the start-up code copies
  ([step 11](../../kinds/crc/README.md)). libcrc and CRC++ build their
  tables in RAM themselves, at run time.
- **The board's CRC unit**, the last row where the board has one,
  labelled "the board's CRC unit, driven by our code; not a library": the
  STM32 CRC unit or the RP2350's DMA sniffer, driven by our code
  ([`adapter_hw.c`](../../kinds/crc/adapter_hw.c)). Its class is "hardware
  unit" and it has no table. Its bytes are those of our adapter code, read
  from the board images. On the Pico 2 the unit is a DMA transfer that the
  CPU waits for; for CRC-32 on the STM32 unit the final XOR is in our code.
- **16 B**: cycles of one call on a message of 16 bytes at an 8-byte
  boundary, the mean of 256 calls.
- **per byte**: (mean at 1024 bytes − mean at 256 bytes) / 768, at an
  8-byte boundary.
- Every number is the **range over the eight placements** (the
  configuration's code moved by 0, 4 ... 28 bytes), first pass; one number
  where all eight agree. A difference between two rows is a difference
  only where their ranges do not overlap (the [method](method-crc.md),
  "What the placements show").

The other lengths (1, 4 and 64 bytes), the message one byte after an
8-byte boundary, the second pass, the minimum, maximum and first call of
every scenario, and the baseline (the bitwise reference, timed in the same
image) are in the records. The 1-byte figures are not shown: at an 8-byte
boundary with the cache on, that scenario is the first one after the cache
is switched on ([method](method-crc.md), "A mean includes the first call").

<!-- table:crc -->

## nRF5340 DK

nRF5340 DK, application core (Cortex-M33), 64 MHz.

### CRC-32/ISO-HDLC, nRF5340 DK, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc32_t256 (C++)](../../records/crc/nrf5340/adapter_etl_crc32_t256.json) | table of 256 | flash | 1072 | 0 | 174 | 10.0 |
| [crcany crc32iso_hdlc_byte (C)](../../records/crc/nrf5340/adapter_crcany_crc32_byte.json)[1] | table of 256 | flash | 4168 | 0 | 206 | 10.0 |
| [libcrc crc_32 (C)](../../records/crc/nrf5340/adapter_libcrc_crc32.json)[2] | table of 256 | RAM, built at the first call | 140 | 1025 | 192 | 9.0 |
| [crc (Rust) Table<1>](../../records/crc/nrf5340/adapter_rust_crc32_table1.json) | table of 256 | flash, computed at compile time | 1250 | 0 | 200 | 8.0 |
| [etl crc32_t16 (C++)](../../records/crc/nrf5340/adapter_etl_crc32_t16.json) | table of 16 | flash | 132 | 0 | 294 | 17.0 |
| [zephyr crc32_ieee (C)](../../records/crc/nrf5340/adapter_zephyr_crc32_ieee.json) | table of 16 | flash | 152 | 0 | 308 | 17.0 |
| [crcany crc32iso_hdlc_word (C)](../../records/crc/nrf5340/adapter_crcany_crc32_word.json) | slicing by 4 | flash (4 KB) | 4296 | 0 | 197–198 | 6.0–6.1 |
| [zlib crc32 (C)](../../records/crc/nrf5340/adapter_zlib_crc32.json) | other: "braided" words | flash | 5824 | 0 | 210 | 8.6 |
| [crcany crc32iso_hdlc_bit (C)](../../records/crc/nrf5340/adapter_crcany_crc32_bit.json) | bitwise | none | 96 | 0 | 1033 | 61.0 |
| [etl crc32_t256 (C++), table in RAM](../../records/crc/nrf5340/adapter_etl_crc32_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 1072 | 1024 | 174 | 10.0 |
| [crcany crc32iso_hdlc_byte (C), table in RAM](../../records/crc/nrf5340/adapter_crcany_crc32_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 4168 | 4096 | 206 | 10.0 |
| [crc (Rust) Table<1>, table in RAM](../../records/crc/nrf5340/adapter_rust_crc32_table1_ram.json) | table of 256 | RAM (copied at start by the image) | 1250 | 1028 | 188 | 7.2 |
| [etl crc32_t16 (C++), table in RAM](../../records/crc/nrf5340/adapter_etl_crc32_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 132 | 64 | 278 | 16.0 |
| [zephyr crc32_ieee (C), table in RAM](../../records/crc/nrf5340/adapter_zephyr_crc32_ieee_ram.json) | table of 16 | RAM (copied at start by the image) | 152 | 64 | 308 | 17.0 |
| [crcany crc32iso_hdlc_word (C), table in RAM](../../records/crc/nrf5340/adapter_crcany_crc32_word_ram.json) | slicing by 4 | RAM (copied at start by the image) | 4296 | 4096 | 185 | 5.5 |
| [zlib crc32 (C), table in RAM](../../records/crc/nrf5340/adapter_zlib_crc32_ram.json) | other: "braided" words | RAM (copied at start by the image) | 5824 | 5120 | 194 | 8.0 |

### CRC-32/ISO-HDLC, nRF5340 DK, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc32_t256 (C++)](../../records/crc/nrf5340/adapter_etl_crc32_t256.json) | table of 256 | flash | 1072 | 0 | 621–731 | 36.0–43.0 |
| [crcany crc32iso_hdlc_byte (C)](../../records/crc/nrf5340/adapter_crcany_crc32_byte.json)[1] | table of 256 | flash | 4168 | 0 | 695–807 | 36.0–43.0 |
| [libcrc crc_32 (C)](../../records/crc/nrf5340/adapter_libcrc_crc32.json)[2] | table of 256 | RAM, built at the first call | 140 | 1025 | 444–551 | 21.0–29.0 |
| [crc (Rust) Table<1>](../../records/crc/nrf5340/adapter_rust_crc32_table1.json) | table of 256 | flash, computed at compile time | 1250 | 0 | 513–615 | 24.5–30.8 |
| [etl crc32_t16 (C++)](../../records/crc/nrf5340/adapter_etl_crc32_t16.json) | table of 16 | flash | 132 | 0 | 1067–1166 | 64.0–70.0 |
| [zephyr crc32_ieee (C)](../../records/crc/nrf5340/adapter_zephyr_crc32_ieee.json) | table of 16 | flash | 152 | 0 | 1002–1236 | 57.0–71.0 |
| [crcany crc32iso_hdlc_word (C)](../../records/crc/nrf5340/adapter_crcany_crc32_word.json) | slicing by 4 | flash (4 KB) | 4296 | 0 | 586–614 | 24.5–26.2 |
| [zlib crc32 (C)](../../records/crc/nrf5340/adapter_zlib_crc32.json) | other: "braided" words | flash | 5824 | 0 | 571–628 | 26.7–29.2 |
| [crcany crc32iso_hdlc_bit (C)](../../records/crc/nrf5340/adapter_crcany_crc32_bit.json) | bitwise | none | 96 | 0 | 2758–3734 | 164.0–226.0 |
| [etl crc32_t256 (C++), table in RAM](../../records/crc/nrf5340/adapter_etl_crc32_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 1072 | 1024 | 397–514 | 22.0–30.0 |
| [crcany crc32iso_hdlc_byte (C), table in RAM](../../records/crc/nrf5340/adapter_crcany_crc32_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 4168 | 4096 | 471–583 | 22.0–30.0 |
| [crc (Rust) Table<1>, table in RAM](../../records/crc/nrf5340/adapter_rust_crc32_table1_ram.json) | table of 256 | RAM (copied at start by the image) | 1250 | 1028 | 376–387 | 15.2–16.5 |
| [etl crc32_t16 (C++), table in RAM](../../records/crc/nrf5340/adapter_etl_crc32_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 132 | 64 | 615–707 | 35.0–41.0 |
| [zephyr crc32_ieee (C), table in RAM](../../records/crc/nrf5340/adapter_zephyr_crc32_ieee_ram.json) | table of 16 | RAM (copied at start by the image) | 152 | 64 | 654–772 | 35.0–42.0 |
| [crcany crc32iso_hdlc_word (C), table in RAM](../../records/crc/nrf5340/adapter_crcany_crc32_word_ram.json) | slicing by 4 | RAM (copied at start by the image) | 4296 | 4096 | 396–434 | 13.0–14.0 |
| [zlib crc32 (C), table in RAM](../../records/crc/nrf5340/adapter_zlib_crc32_ram.json) | other: "braided" words | RAM (copied at start by the image) | 5824 | 5120 | 385–415 | 15.7–16.5 |

### CRC-16/IBM-3740, nRF5340 DK, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc16_ccitt_t256 (C++)](../../records/crc/nrf5340/adapter_etl_crc16_t256.json) | table of 256 | flash | 568 | 0 | 190 | 11.0 |
| [crcany crc16ibm_3740_byte (C)](../../records/crc/nrf5340/adapter_crcany_crc16_byte.json) | table of 256 | flash | 594 | 0 | 218 | 10.0 |
| [libcrc crc_ccitt_ffff (C)](../../records/crc/nrf5340/adapter_libcrc_ccitt_ffff.json)[3] | table of 256 | RAM, built at the first call | 180 | 513 | 216 | 10.0 |
| [crcpp CRC_16_CCITTFALSE Table (C++)](../../records/crc/nrf5340/adapter_crcpp_ccittfalse_table.json) | table of 256 | RAM, built by the table's constructor | 336 | 524 | 272 | 14.0 |
| [etl crc16_ccitt_t16 (C++)](../../records/crc/nrf5340/adapter_etl_crc16_t16.json) | table of 16 | flash | 108 | 0 | 294 | 17.0 |
| [zephyr crc16_itu_t (C)](../../records/crc/nrf5340/adapter_zephyr_crc16_itu_t.json) | other: shifts and XORs | none | 60 | 0 | 265 | 15.0 |
| [etl crc16_ccitt_t256 (C++), table in RAM](../../records/crc/nrf5340/adapter_etl_crc16_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 568 | 512 | 190 | 11.0 |
| [crcany crc16ibm_3740_byte (C), table in RAM](../../records/crc/nrf5340/adapter_crcany_crc16_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 594 | 512 | 218 | 10.0 |
| [etl crc16_ccitt_t16 (C++), table in RAM](../../records/crc/nrf5340/adapter_etl_crc16_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 108 | 32 | 294 | 17.0 |

### CRC-16/IBM-3740, nRF5340 DK, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc16_ccitt_t256 (C++)](../../records/crc/nrf5340/adapter_etl_crc16_t256.json) | table of 256 | flash | 568 | 0 | 643–748 | 37.0–45.0 |
| [crcany crc16ibm_3740_byte (C)](../../records/crc/nrf5340/adapter_crcany_crc16_byte.json) | table of 256 | flash | 594 | 0 | 736–864 | 38.0–45.0 |
| [libcrc crc_ccitt_ffff (C)](../../records/crc/nrf5340/adapter_libcrc_ccitt_ffff.json)[3] | table of 256 | RAM, built at the first call | 180 | 513 | 461–608 | 22.0–31.0 |
| [crcpp CRC_16_CCITTFALSE Table (C++)](../../records/crc/nrf5340/adapter_crcpp_ccittfalse_table.json) | table of 256 | RAM, built by the table's constructor | 336 | 524 | 614–631 | 32.0–33.0 |
| [etl crc16_ccitt_t16 (C++)](../../records/crc/nrf5340/adapter_etl_crc16_t16.json) | table of 16 | flash | 108 | 0 | 1083–1202 | 65.0–72.0 |
| [zephyr crc16_itu_t (C)](../../records/crc/nrf5340/adapter_zephyr_crc16_itu_t.json) | other: shifts and XORs | none | 60 | 0 | 598–714 | 34.0–41.0 |
| [etl crc16_ccitt_t256 (C++), table in RAM](../../records/crc/nrf5340/adapter_etl_crc16_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 568 | 512 | 432–523 | 24.0–30.0 |
| [crcany crc16ibm_3740_byte (C), table in RAM](../../records/crc/nrf5340/adapter_crcany_crc16_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 594 | 512 | 481–630 | 22.0–31.0 |
| [etl crc16_ccitt_t16 (C++), table in RAM](../../records/crc/nrf5340/adapter_etl_crc16_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 108 | 32 | 699–760 | 41.0–44.0 |

### CRC-8/SMBUS, nRF5340 DK, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc8_ccitt_t256 (C++)](../../records/crc/nrf5340/adapter_etl_crc8_t256.json) | table of 256 | flash | 296 | 0 | 127 | 7.0 |
| [crcany crc8smbus_byte (C)](../../records/crc/nrf5340/adapter_crcany_crc8_byte.json) | table of 256 | flash | 1090 | 0 | 184 | 8.0 |
| [acecrc crc8_byte (C++)](../../records/crc/nrf5340/adapter_acecrc_crc8_byte.json) | table of 256 | flash | 304 | 0 | 145 | 7.0 |
| [etl crc8_ccitt_t16 (C++)](../../records/crc/nrf5340/adapter_etl_crc8_t16.json) | table of 16 | flash | 84 | 0 | 288 | 17.0 |
| [zephyr crc8_ccitt (C)](../../records/crc/nrf5340/adapter_zephyr_crc8_ccitt.json) | table of 16 | flash | 92 | 0 | 293 | 16.0 |
| [etl crc8_ccitt_t256 (C++), table in RAM](../../records/crc/nrf5340/adapter_etl_crc8_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 296 | 256 | 112 | 6.0 |
| [crcany crc8smbus_byte (C), table in RAM](../../records/crc/nrf5340/adapter_crcany_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 1090 | 1024 | 168 | 7.0 |
| [acecrc crc8_byte (C++), table in RAM](../../records/crc/nrf5340/adapter_acecrc_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 304 | 256 | 129 | 6.0 |
| [etl crc8_ccitt_t16 (C++), table in RAM](../../records/crc/nrf5340/adapter_etl_crc8_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 84 | 16 | 288 | 17.0 |
| [zephyr crc8_ccitt (C), table in RAM](../../records/crc/nrf5340/adapter_zephyr_crc8_ccitt_ram.json) | table of 16 | RAM (copied at start by the image) | 92 | 16 | 293 | 16.0 |

### CRC-8/SMBUS, nRF5340 DK, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc8_ccitt_t256 (C++)](../../records/crc/nrf5340/adapter_etl_crc8_t256.json) | table of 256 | flash | 296 | 0 | 384–482 | 21.0–27.0 |
| [crcany crc8smbus_byte (C)](../../records/crc/nrf5340/adapter_crcany_crc8_byte.json) | table of 256 | flash | 1090 | 0 | 565–590 | 27.0–29.0 |
| [acecrc crc8_byte (C++)](../../records/crc/nrf5340/adapter_acecrc_crc8_byte.json) | table of 256 | flash | 304 | 0 | 410–507 | 21.0–27.0 |
| [etl crc8_ccitt_t16 (C++)](../../records/crc/nrf5340/adapter_etl_crc8_t16.json) | table of 16 | flash | 84 | 0 | 959–1145 | 57.0–69.0 |
| [zephyr crc8_ccitt (C)](../../records/crc/nrf5340/adapter_zephyr_crc8_ccitt.json) | table of 16 | flash | 92 | 0 | 946–1182 | 54.0–69.0 |
| [etl crc8_ccitt_t256 (C++), table in RAM](../../records/crc/nrf5340/adapter_etl_crc8_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 296 | 256 | 151–347 | 6.0–19.0 |
| [crcany crc8smbus_byte (C), table in RAM](../../records/crc/nrf5340/adapter_crcany_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 1090 | 1024 | 430–463 | 19.0–21.0 |
| [acecrc crc8_byte (C++), table in RAM](../../records/crc/nrf5340/adapter_acecrc_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 304 | 256 | 185–380 | 6.0–19.0 |
| [etl crc8_ccitt_t16 (C++), table in RAM](../../records/crc/nrf5340/adapter_etl_crc8_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 84 | 16 | 576–735 | 33.0–43.0 |
| [zephyr crc8_ccitt (C), table in RAM](../../records/crc/nrf5340/adapter_zephyr_crc8_ccitt_ram.json) | table of 16 | RAM (copied at start by the image) | 92 | 16 | 610–734 | 33.0–41.0 |

## Raspberry Pi Pico 2 H

Raspberry Pi Pico 2 H (RP2350A, core 0, Cortex-M33), 150 MHz.

### CRC-32/ISO-HDLC, Raspberry Pi Pico 2 H, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc32_t256 (C++)](../../records/crc/rp2350/adapter_etl_crc32_t256.json) | table of 256 | flash | 1072 | 0 | 168 | 10.0 |
| [crcany crc32iso_hdlc_byte (C)](../../records/crc/rp2350/adapter_crcany_crc32_byte.json)[1] | table of 256 | flash | 4168 | 0 | 190 | 10.0 |
| [libcrc crc_32 (C)](../../records/crc/rp2350/adapter_libcrc_crc32.json)[2] | table of 256 | RAM, built at the first call | 140 | 1025 | 171 | 9.0 |
| [crc (Rust) Table<1>](../../records/crc/rp2350/adapter_rust_crc32_table1.json) | table of 256 | flash, computed at compile time | 1250 | 0 | 157–158 | 7.4 |
| [etl crc32_t16 (C++)](../../records/crc/rp2350/adapter_etl_crc32_t16.json) | table of 16 | flash | 132 | 0 | 276 | 16.5 |
| [zephyr crc32_ieee (C)](../../records/crc/rp2350/adapter_zephyr_crc32_ieee.json) | table of 16 | flash | 152 | 0 | 296 | 17.0 |
| [crcany crc32iso_hdlc_word (C)](../../records/crc/rp2350/adapter_crcany_crc32_word.json) | slicing by 4 | flash (4 KB) | 4296 | 0 | 268–269 | 5.7 |
| [zlib crc32 (C)](../../records/crc/rp2350/adapter_zlib_crc32.json) | other: "braided" words | flash | 5824 | 0 | 168 | 6.7 |
| [crcany crc32iso_hdlc_bit (C)](../../records/crc/rp2350/adapter_crcany_crc32_bit.json) | bitwise | none | 96 | 0 | 1012 | 61.0 |
| [etl crc32_t256 (C++), table in RAM](../../records/crc/rp2350/adapter_etl_crc32_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 1072 | 1024 | 168 | 10.0 |
| [crcany crc32iso_hdlc_byte (C), table in RAM](../../records/crc/rp2350/adapter_crcany_crc32_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 4168 | 4096 | 190 | 10.0 |
| [crc (Rust) Table<1>, table in RAM](../../records/crc/rp2350/adapter_rust_crc32_table1_ram.json) | table of 256 | RAM (copied at start by the image) | 1250 | 1028 | 156 | 7.2 |
| [etl crc32_t16 (C++), table in RAM](../../records/crc/rp2350/adapter_etl_crc32_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 132 | 64 | 269 | 16.0 |
| [zephyr crc32_ieee (C), table in RAM](../../records/crc/rp2350/adapter_zephyr_crc32_ieee_ram.json) | table of 16 | RAM (copied at start by the image) | 152 | 64 | 296 | 17.0 |
| [crcany crc32iso_hdlc_word (C), table in RAM](../../records/crc/rp2350/adapter_crcany_crc32_word_ram.json) | slicing by 4 | RAM (copied at start by the image) | 4296 | 4096 | 145–146 | 5.5 |
| [zlib crc32 (C), table in RAM](../../records/crc/rp2350/adapter_zlib_crc32_ram.json) | other: "braided" words | RAM (copied at start by the image) | 5824 | 5120 | 162 | 6.6 |
| [the board's CRC unit, CRC-32 (our code)](../../records/crc/rp2350/adapter_hw_crc32.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 80 | 1 | 50–51 | 1.2 |

### CRC-32/ISO-HDLC, Raspberry Pi Pico 2 H, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc32_t256 (C++)](../../records/crc/rp2350/adapter_etl_crc32_t256.json) | table of 256 | flash | 1072 | 0 | 7221–7232 | 425.0–425.5 |
| [crcany crc32iso_hdlc_byte (C)](../../records/crc/rp2350/adapter_crcany_crc32_byte.json)[1] | table of 256 | flash | 4168 | 0 | 7825–7838 | 425.0–425.5 |
| [libcrc crc_32 (C)](../../records/crc/rp2350/adapter_libcrc_crc32.json)[2] | table of 256 | RAM, built at the first call | 140 | 1025 | 4938 | 259.0 |
| [crc (Rust) Table<1>](../../records/crc/rp2350/adapter_rust_crc32_table1.json) | table of 256 | flash, computed at compile time | 1250 | 0 | 5978–5980 | 318.5 |
| [etl crc32_t16 (C++)](../../records/crc/rp2350/adapter_etl_crc32_t16.json) | table of 16 | flash | 132 | 0 | 12057–12058 | 725.5 |
| [zephyr crc32_ieee (C)](../../records/crc/rp2350/adapter_zephyr_crc32_ieee.json) | table of 16 | flash | 152 | 0 | 12518–12522 | 726.0 |
| [crcany crc32iso_hdlc_word (C)](../../records/crc/rp2350/adapter_crcany_crc32_word.json) | slicing by 4 | flash (4 KB) | 4296 | 0 | 6337–6340 | 293.3–293.7 |
| [zlib crc32 (C)](../../records/crc/rp2350/adapter_zlib_crc32.json) | other: "braided" words | flash | 5824 | 0 | 6085–6091 | 321.8–326.7 |
| [crcany crc32iso_hdlc_bit (C)](../../records/crc/rp2350/adapter_crcany_crc32_bit.json) | bitwise | none | 96 | 0 | 31696–31697 | 1910.0 |
| [etl crc32_t256 (C++), table in RAM](../../records/crc/rp2350/adapter_etl_crc32_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 1072 | 1024 | 4567 | 259.0 |
| [crcany crc32iso_hdlc_byte (C), table in RAM](../../records/crc/rp2350/adapter_crcany_crc32_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 4168 | 4096 | 5171–5173 | 259.0 |
| [crc (Rust) Table<1>, table in RAM](../../records/crc/rp2350/adapter_rust_crc32_table1_ram.json) | table of 256 | RAM (copied at start by the image) | 1250 | 1028 | 3324 | 152.5 |
| [etl crc32_t16 (C++), table in RAM](../../records/crc/rp2350/adapter_etl_crc32_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 132 | 64 | 6754–6756 | 394.0 |
| [zephyr crc32_ieee (C), table in RAM](../../records/crc/rp2350/adapter_zephyr_crc32_ieee_ram.json) | table of 16 | RAM (copied at start by the image) | 152 | 64 | 7208–7209 | 394.0 |
| [crcany crc32iso_hdlc_word (C), table in RAM](../../records/crc/rp2350/adapter_crcany_crc32_word_ram.json) | slicing by 4 | RAM (copied at start by the image) | 4296 | 4096 | 3729–3731 | 132.2 |
| [zlib crc32 (C), table in RAM](../../records/crc/rp2350/adapter_zlib_crc32_ram.json) | other: "braided" words | RAM (copied at start by the image) | 5824 | 5120 | 3436–3437 | 163.3 |
| [the board's CRC unit, CRC-32 (our code)](../../records/crc/rp2350/adapter_hw_crc32.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 80 | 1 | 1081 | 1.2 |

### CRC-16/IBM-3740, Raspberry Pi Pico 2 H, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc16_ccitt_t256 (C++)](../../records/crc/rp2350/adapter_etl_crc16_t256.json) | table of 256 | flash | 568 | 0 | 184 | 11.0 |
| [crcany crc16ibm_3740_byte (C)](../../records/crc/rp2350/adapter_crcany_crc16_byte.json) | table of 256 | flash | 594 | 0 | 198 | 10.0 |
| [libcrc crc_ccitt_ffff (C)](../../records/crc/rp2350/adapter_libcrc_ccitt_ffff.json)[3] | table of 256 | RAM, built at the first call | 180 | 513 | 191 | 10.0 |
| [crcpp CRC_16_CCITTFALSE Table (C++)](../../records/crc/rp2350/adapter_crcpp_ccittfalse_table.json) | table of 256 | RAM, built by the table's constructor | 336 | 524 | 255 | 14.0 |
| [etl crc16_ccitt_t16 (C++)](../../records/crc/rp2350/adapter_etl_crc16_t16.json) | table of 16 | flash | 108 | 0 | 285 | 17.0 |
| [zephyr crc16_itu_t (C)](../../records/crc/rp2350/adapter_zephyr_crc16_itu_t.json) | other: shifts and XORs | none | 60 | 0 | 257 | 15.0 |
| [etl crc16_ccitt_t256 (C++), table in RAM](../../records/crc/rp2350/adapter_etl_crc16_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 568 | 512 | 184 | 11.0 |
| [crcany crc16ibm_3740_byte (C), table in RAM](../../records/crc/rp2350/adapter_crcany_crc16_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 594 | 512 | 198 | 10.0 |
| [etl crc16_ccitt_t16 (C++), table in RAM](../../records/crc/rp2350/adapter_etl_crc16_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 108 | 32 | 285 | 17.0 |
| [the board's CRC unit, CRC-16 (our code)](../../records/crc/rp2350/adapter_hw_crc16.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 80 | 1 | 51–52 | 1.2 |

### CRC-16/IBM-3740, Raspberry Pi Pico 2 H, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc16_ccitt_t256 (C++)](../../records/crc/rp2350/adapter_etl_crc16_t256.json) | table of 256 | flash | 568 | 0 | 7457–7464 | 439.5–440.0 |
| [crcany crc16ibm_3740_byte (C)](../../records/crc/rp2350/adapter_crcany_crc16_byte.json) | table of 256 | flash | 594 | 0 | 8246–8253 | 440.0–440.5 |
| [libcrc crc_ccitt_ffff (C)](../../records/crc/rp2350/adapter_libcrc_ccitt_ffff.json)[3] | table of 256 | RAM, built at the first call | 180 | 513 | 5496 | 286.0 |
| [crcpp CRC_16_CCITTFALSE Table (C++)](../../records/crc/rp2350/adapter_crcpp_ccittfalse_table.json) | table of 256 | RAM, built by the table's constructor | 336 | 524 | 5886–5889 | 313.0 |
| [etl crc16_ccitt_t16 (C++)](../../records/crc/rp2350/adapter_etl_crc16_t16.json) | table of 16 | flash | 108 | 0 | 12116–12131 | 729.0–730.0 |
| [zephyr crc16_itu_t (C)](../../records/crc/rp2350/adapter_zephyr_crc16_itu_t.json) | other: shifts and XORs | none | 60 | 0 | 6378 | 367.0 |
| [etl crc16_ccitt_t256 (C++), table in RAM](../../records/crc/rp2350/adapter_etl_crc16_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 568 | 512 | 5000–5001 | 286.0 |
| [crcany crc16ibm_3740_byte (C), table in RAM](../../records/crc/rp2350/adapter_crcany_crc16_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 594 | 512 | 5781–5782 | 286.0 |
| [etl crc16_ccitt_t16 (C++), table in RAM](../../records/crc/rp2350/adapter_etl_crc16_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 108 | 32 | 7186–7187 | 421.0 |
| [the board's CRC unit, CRC-16 (our code)](../../records/crc/rp2350/adapter_hw_crc16.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 80 | 1 | 764–905 | 1.4 |

### CRC-8/SMBUS, Raspberry Pi Pico 2 H, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc8_ccitt_t256 (C++)](../../records/crc/rp2350/adapter_etl_crc8_t256.json) | table of 256 | flash | 296 | 0 | 114 | 6.5 |
| [crcany crc8smbus_byte (C)](../../records/crc/rp2350/adapter_crcany_crc8_byte.json) | table of 256 | flash | 1090 | 0 | 155–156 | 7.5 |
| [acecrc crc8_byte (C++)](../../records/crc/rp2350/adapter_acecrc_crc8_byte.json) | table of 256 | flash | 304 | 0 | 124–125 | 6.5 |
| [etl crc8_ccitt_t16 (C++)](../../records/crc/rp2350/adapter_etl_crc8_t16.json) | table of 16 | flash | 84 | 0 | 283 | 17.0 |
| [zephyr crc8_ccitt (C)](../../records/crc/rp2350/adapter_zephyr_crc8_ccitt.json) | table of 16 | flash | 92 | 0 | 280 | 16.0 |
| [etl crc8_ccitt_t256 (C++), table in RAM](../../records/crc/rp2350/adapter_etl_crc8_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 296 | 256 | 106 | 6.0 |
| [crcany crc8smbus_byte (C), table in RAM](../../records/crc/rp2350/adapter_crcany_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 1090 | 1024 | 148 | 7.0 |
| [acecrc crc8_byte (C++), table in RAM](../../records/crc/rp2350/adapter_acecrc_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 304 | 256 | 116 | 6.0 |
| [etl crc8_ccitt_t16 (C++), table in RAM](../../records/crc/rp2350/adapter_etl_crc8_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 84 | 16 | 283 | 17.0 |
| [zephyr crc8_ccitt (C), table in RAM](../../records/crc/rp2350/adapter_zephyr_crc8_ccitt_ram.json) | table of 16 | RAM (copied at start by the image) | 92 | 16 | 280 | 16.0 |

### CRC-8/SMBUS, Raspberry Pi Pico 2 H, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc8_ccitt_t256 (C++)](../../records/crc/rp2350/adapter_etl_crc8_t256.json) | table of 256 | flash | 296 | 0 | 4618–5103 | 256.0–290.2 |
| [crcany crc8smbus_byte (C)](../../records/crc/rp2350/adapter_crcany_crc8_byte.json) | table of 256 | flash | 1090 | 0 | 6262–6826 | 317.2–353.0 |
| [acecrc crc8_byte (C++)](../../records/crc/rp2350/adapter_acecrc_crc8_byte.json) | table of 256 | flash | 304 | 0 | 4893–5347 | 256.0–290.2 |
| [etl crc8_ccitt_t16 (C++)](../../records/crc/rp2350/adapter_etl_crc8_t16.json) | table of 16 | flash | 84 | 0 | 11058–11060 | 663.0 |
| [zephyr crc8_ccitt (C)](../../records/crc/rp2350/adapter_zephyr_crc8_ccitt.json) | table of 16 | flash | 92 | 0 | 10927–10929 | 636.0 |
| [etl crc8_ccitt_t256 (C++), table in RAM](../../records/crc/rp2350/adapter_etl_crc8_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 296 | 256 | 3298–3299 | 178.0 |
| [crcany crc8smbus_byte (C), table in RAM](../../records/crc/rp2350/adapter_crcany_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 1090 | 1024 | 4458–4459 | 205.0 |
| [acecrc crc8_byte (C++), table in RAM](../../records/crc/rp2350/adapter_acecrc_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 304 | 256 | 3574–3575 | 178.0 |
| [etl crc8_ccitt_t16 (C++), table in RAM](../../records/crc/rp2350/adapter_etl_crc8_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 84 | 16 | 6322–6324 | 367.0 |
| [zephyr crc8_ccitt (C), table in RAM](../../records/crc/rp2350/adapter_zephyr_crc8_ccitt_ram.json) | table of 16 | RAM (copied at start by the image) | 92 | 16 | 6194 | 340.0 |

## NUCLEO-G474RE

NUCLEO-G474RE (STM32G474RET6, Cortex-M4F), 170 MHz.

### CRC-32/ISO-HDLC, NUCLEO-G474RE, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc32_t256 (C++)](../../records/crc/stm32g474/adapter_etl_crc32_t256.json) | table of 256 | flash | 1072 | 0 | 257–258 | 14.7 |
| [crcany crc32iso_hdlc_byte (C)](../../records/crc/stm32g474/adapter_crcany_crc32_byte.json)[1] | table of 256 | flash | 4168 | 0 | 280–281 | 14.7 |
| [libcrc crc_32 (C)](../../records/crc/stm32g474/adapter_libcrc_crc32.json)[2] | table of 256 | RAM, built at the first call | 140 | 1025 | 196 | 10.0 |
| [crc (Rust) Table<1>](../../records/crc/stm32g474/adapter_rust_crc32_table1.json) | table of 256 | flash, computed at compile time | 1250 | 0 | 263 | 13.2 |
| [etl crc32_t16 (C++)](../../records/crc/stm32g474/adapter_etl_crc32_t16.json) | table of 16 | flash | 132 | 0 | 293 | 17.0 |
| [zephyr crc32_ieee (C)](../../records/crc/stm32g474/adapter_zephyr_crc32_ieee.json) | table of 16 | flash | 150 | 0 | 306 | 17.0 |
| [crcany crc32iso_hdlc_word (C)](../../records/crc/stm32g474/adapter_crcany_crc32_word.json) | slicing by 4 | flash (4 KB) | 4296 | 0 | 238 | 9.9 |
| [zlib crc32 (C)](../../records/crc/stm32g474/adapter_zlib_crc32.json) | other: "braided" words | flash | 5818 | 0 | 247–248 | 12.1–12.2 |
| [crcany crc32iso_hdlc_bit (C)](../../records/crc/stm32g474/adapter_crcany_crc32_bit.json) | bitwise | none | 96 | 0 | 1025 | 61.0 |
| [etl crc32_t256 (C++), table in RAM](../../records/crc/stm32g474/adapter_etl_crc32_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 1072 | 1024 | 193 | 11.0 |
| [crcany crc32iso_hdlc_byte (C), table in RAM](../../records/crc/stm32g474/adapter_crcany_crc32_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 4168 | 4096 | 216 | 11.0 |
| [crc (Rust) Table<1>, table in RAM](../../records/crc/stm32g474/adapter_rust_crc32_table1_ram.json) | table of 256 | RAM (copied at start by the image) | 1250 | 1028 | 195 | 9.0 |
| [etl crc32_t16 (C++), table in RAM](../../records/crc/stm32g474/adapter_etl_crc32_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 132 | 64 | 293 | 17.0 |
| [zephyr crc32_ieee (C), table in RAM](../../records/crc/stm32g474/adapter_zephyr_crc32_ieee_ram.json) | table of 16 | RAM (copied at start by the image) | 150 | 64 | 306 | 17.0 |
| [crcany crc32iso_hdlc_word (C), table in RAM](../../records/crc/stm32g474/adapter_crcany_crc32_word_ram.json) | slicing by 4 | RAM (copied at start by the image) | 4296 | 4096 | 171 | 6.0 |
| [zlib crc32 (C), table in RAM](../../records/crc/stm32g474/adapter_zlib_crc32_ram.json) | other: "braided" words | RAM (copied at start by the image) | 5818 | 5120 | 173 | 8.6 |
| [the board's CRC unit, CRC-32 (our code)](../../records/crc/stm32g474/adapter_hw_crc32.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 196 | 4 | 96 | 2.2 |

### CRC-32/ISO-HDLC, NUCLEO-G474RE, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc32_t256 (C++)](../../records/crc/stm32g474/adapter_etl_crc32_t256.json) | table of 256 | flash | 1072 | 0 | 463–489 | 27.0–29.0 |
| [crcany crc32iso_hdlc_byte (C)](../../records/crc/stm32g474/adapter_crcany_crc32_byte.json)[1] | table of 256 | flash | 4168 | 0 | 506–543 | 27.0–29.0 |
| [libcrc crc_32 (C)](../../records/crc/stm32g474/adapter_libcrc_crc32.json)[2] | table of 256 | RAM, built at the first call | 140 | 1025 | 405–422 | 22.0–23.0 |
| [crc (Rust) Table<1>](../../records/crc/stm32g474/adapter_rust_crc32_table1.json) | table of 256 | flash, computed at compile time | 1250 | 0 | 396–444 | 19.5–22.2 |
| [etl crc32_t16 (C++)](../../records/crc/stm32g474/adapter_etl_crc32_t16.json) | table of 16 | flash | 132 | 0 | 754–778 | 45.2–46.4 |
| [zephyr crc32_ieee (C)](../../records/crc/stm32g474/adapter_zephyr_crc32_ieee.json) | table of 16 | flash | 150 | 0 | 798–815 | 45.7–47.0 |
| [crcany crc32iso_hdlc_word (C)](../../records/crc/stm32g474/adapter_crcany_crc32_word.json) | slicing by 4 | flash (4 KB) | 4296 | 0 | 420–450 | 18.0–19.7 |
| [zlib crc32 (C)](../../records/crc/stm32g474/adapter_zlib_crc32.json) | other: "braided" words | flash | 5818 | 0 | 431–441 | 20.5–21.3 |
| [crcany crc32iso_hdlc_bit (C)](../../records/crc/stm32g474/adapter_crcany_crc32_bit.json) | bitwise | none | 96 | 0 | 2453–3002 | 148.0–182.0 |
| [etl crc32_t256 (C++), table in RAM](../../records/crc/stm32g474/adapter_etl_crc32_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 1072 | 1024 | 399–410 | 23.0–24.0 |
| [crcany crc32iso_hdlc_byte (C), table in RAM](../../records/crc/stm32g474/adapter_crcany_crc32_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 4168 | 4096 | 443–463 | 23.0–24.0 |
| [crc (Rust) Table<1>, table in RAM](../../records/crc/stm32g474/adapter_rust_crc32_table1_ram.json) | table of 256 | RAM (copied at start by the image) | 1250 | 1028 | 328–345 | 15.2–16.0 |
| [etl crc32_t16 (C++), table in RAM](../../records/crc/stm32g474/adapter_etl_crc32_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 132 | 64 | 593–666 | 35.0–40.0 |
| [zephyr crc32_ieee (C), table in RAM](../../records/crc/stm32g474/adapter_zephyr_crc32_ieee_ram.json) | table of 16 | RAM (copied at start by the image) | 150 | 64 | 656–701 | 37.0–40.0 |
| [crcany crc32iso_hdlc_word (C), table in RAM](../../records/crc/stm32g474/adapter_crcany_crc32_word_ram.json) | slicing by 4 | RAM (copied at start by the image) | 4296 | 4096 | 344–366 | 13.2–14.5 |
| [zlib crc32 (C), table in RAM](../../records/crc/stm32g474/adapter_zlib_crc32_ram.json) | other: "braided" words | RAM (copied at start by the image) | 5818 | 5120 | 348–364 | 15.7–16.1 |
| [the board's CRC unit, CRC-32 (our code)](../../records/crc/stm32g474/adapter_hw_crc32.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 196 | 4 | 184–188 | 4.2–4.5 |

### CRC-16/IBM-3740, NUCLEO-G474RE, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc16_ccitt_t256 (C++)](../../records/crc/stm32g474/adapter_etl_crc16_t256.json) | table of 256 | flash | 568 | 0 | 268–269 | 15.2–15.3 |
| [crcany crc16ibm_3740_byte (C)](../../records/crc/stm32g474/adapter_crcany_crc16_byte.json) | table of 256 | flash | 594 | 0 | 285–286 | 14.2–14.3 |
| [libcrc crc_ccitt_ffff (C)](../../records/crc/stm32g474/adapter_libcrc_ccitt_ffff.json)[3] | table of 256 | RAM, built at the first call | 188 | 513 | 221 | 11.0 |
| [crcpp CRC_16_CCITTFALSE Table (C++)](../../records/crc/stm32g474/adapter_crcpp_ccittfalse_table.json) | table of 256 | RAM, built by the table's constructor | 332 | 524 | 266 | 14.0 |
| [etl crc16_ccitt_t16 (C++)](../../records/crc/stm32g474/adapter_etl_crc16_t16.json) | table of 16 | flash | 108 | 0 | 325 | 19.0 |
| [zephyr crc16_itu_t (C)](../../records/crc/stm32g474/adapter_zephyr_crc16_itu_t.json) | other: shifts and XORs | none | 60 | 0 | 294 | 17.0 |
| [etl crc16_ccitt_t256 (C++), table in RAM](../../records/crc/stm32g474/adapter_etl_crc16_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 568 | 512 | 209 | 12.0 |
| [crcany crc16ibm_3740_byte (C), table in RAM](../../records/crc/stm32g474/adapter_crcany_crc16_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 594 | 512 | 226 | 11.0 |
| [etl crc16_ccitt_t16 (C++), table in RAM](../../records/crc/stm32g474/adapter_etl_crc16_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 108 | 32 | 325 | 19.0 |
| [the board's CRC unit, CRC-16 (our code)](../../records/crc/stm32g474/adapter_hw_crc16.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 192 | 4 | 96 | 2.2 |

### CRC-16/IBM-3740, NUCLEO-G474RE, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc16_ccitt_t256 (C++)](../../records/crc/stm32g474/adapter_etl_crc16_t256.json) | table of 256 | flash | 568 | 0 | 526–553 | 30.9–32.9 |
| [crcany crc16ibm_3740_byte (C)](../../records/crc/stm32g474/adapter_crcany_crc16_byte.json) | table of 256 | flash | 594 | 0 | 548–631 | 27.9–33.9 |
| [libcrc crc_ccitt_ffff (C)](../../records/crc/stm32g474/adapter_libcrc_ccitt_ffff.json)[3] | table of 256 | RAM, built at the first call | 188 | 513 | 437–513 | 23.0–28.0 |
| [crcpp CRC_16_CCITTFALSE Table (C++)](../../records/crc/stm32g474/adapter_crcpp_ccittfalse_table.json) | table of 256 | RAM, built by the table's constructor | 332 | 524 | 539–557 | 29.0–30.0 |
| [etl crc16_ccitt_t16 (C++)](../../records/crc/stm32g474/adapter_etl_crc16_t16.json) | table of 16 | flash | 108 | 0 | 809–820 | 48.7–49.5 |
| [zephyr crc16_itu_t (C)](../../records/crc/stm32g474/adapter_zephyr_crc16_itu_t.json) | other: shifts and XORs | none | 60 | 0 | 600–617 | 35.0–36.0 |
| [etl crc16_ccitt_t256 (C++), table in RAM](../../records/crc/stm32g474/adapter_etl_crc16_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 568 | 512 | 431–474 | 25.0–28.0 |
| [crcany crc16ibm_3740_byte (C), table in RAM](../../records/crc/stm32g474/adapter_crcany_crc16_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 594 | 512 | 469–536 | 23.0–28.0 |
| [etl crc16_ccitt_t16 (C++), table in RAM](../../records/crc/stm32g474/adapter_etl_crc16_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 108 | 32 | 684–701 | 41.0–42.0 |
| [the board's CRC unit, CRC-16 (our code)](../../records/crc/stm32g474/adapter_hw_crc16.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 192 | 4 | 184–188 | 4.2–4.5 |

### CRC-8/SMBUS, NUCLEO-G474RE, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc8_ccitt_t256 (C++)](../../records/crc/stm32g474/adapter_etl_crc8_t256.json) | table of 256 | flash | 296 | 0 | 187–214 | 8.0–9.5 |
| [crcany crc8smbus_byte (C)](../../records/crc/stm32g474/adapter_crcany_crc8_byte.json) | table of 256 | flash | 1090 | 0 | 218–224 | 8.0–9.0 |
| [acecrc crc8_byte (C++)](../../records/crc/stm32g474/adapter_acecrc_crc8_byte.json) | table of 256 | flash | 302 | 0 | 219–247 | 8.0–10.0 |
| [etl crc8_ccitt_t16 (C++)](../../records/crc/stm32g474/adapter_etl_crc8_t16.json) | table of 16 | flash | 84 | 0 | 322 | 19.0 |
| [zephyr crc8_ccitt (C)](../../records/crc/stm32g474/adapter_zephyr_crc8_ccitt.json) | table of 16 | flash | 90 | 0 | 321 | 18.0 |
| [etl crc8_ccitt_t256 (C++), table in RAM](../../records/crc/stm32g474/adapter_etl_crc8_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 296 | 256 | 146 | 8.0 |
| [crcany crc8smbus_byte (C), table in RAM](../../records/crc/stm32g474/adapter_crcany_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 1090 | 1024 | 177 | 8.0 |
| [acecrc crc8_byte (C++), table in RAM](../../records/crc/stm32g474/adapter_acecrc_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 302 | 256 | 159 | 8.0 |
| [etl crc8_ccitt_t16 (C++), table in RAM](../../records/crc/stm32g474/adapter_etl_crc8_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 84 | 16 | 322 | 19.0 |
| [zephyr crc8_ccitt (C), table in RAM](../../records/crc/stm32g474/adapter_zephyr_crc8_ccitt_ram.json) | table of 16 | RAM (copied at start by the image) | 90 | 16 | 321 | 18.0 |
| [the board's CRC unit, CRC-8 (our code)](../../records/crc/stm32g474/adapter_hw_crc8.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 188 | 4 | 96 | 2.2 |

### CRC-8/SMBUS, NUCLEO-G474RE, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc8_ccitt_t256 (C++)](../../records/crc/stm32g474/adapter_etl_crc8_t256.json) | table of 256 | flash | 296 | 0 | 360–381 | 20.8–21.8 |
| [crcany crc8smbus_byte (C)](../../records/crc/stm32g474/adapter_crcany_crc8_byte.json) | table of 256 | flash | 1090 | 0 | 426–442 | 20.9–21.8 |
| [acecrc crc8_byte (C++)](../../records/crc/stm32g474/adapter_acecrc_crc8_byte.json) | table of 256 | flash | 302 | 0 | 386–397 | 20.8–21.8 |
| [etl crc8_ccitt_t16 (C++)](../../records/crc/stm32g474/adapter_etl_crc8_t16.json) | table of 16 | flash | 84 | 0 | 687–689 | 40.9–41.3 |
| [zephyr crc8_ccitt (C)](../../records/crc/stm32g474/adapter_zephyr_crc8_ccitt.json) | table of 16 | flash | 90 | 0 | 619–679 | 35.3–38.9 |
| [etl crc8_ccitt_t256 (C++), table in RAM](../../records/crc/stm32g474/adapter_etl_crc8_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 296 | 256 | 283–298 | 16.0–17.0 |
| [crcany crc8smbus_byte (C), table in RAM](../../records/crc/stm32g474/adapter_crcany_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 1090 | 1024 | 360–374 | 17.0–18.0 |
| [acecrc crc8_byte (C++), table in RAM](../../records/crc/stm32g474/adapter_acecrc_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 302 | 256 | 309–318 | 16.0–17.0 |
| [etl crc8_ccitt_t16 (C++), table in RAM](../../records/crc/stm32g474/adapter_etl_crc8_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 84 | 16 | 592–604 | 35.0–36.0 |
| [zephyr crc8_ccitt (C), table in RAM](../../records/crc/stm32g474/adapter_zephyr_crc8_ccitt_ram.json) | table of 16 | RAM (copied at start by the image) | 90 | 16 | 522–598 | 29.0–34.0 |
| [the board's CRC unit, CRC-8 (our code)](../../records/crc/stm32g474/adapter_hw_crc8.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 188 | 4 | 184–188 | 4.2–4.5 |

## NUCLEO-H723ZG

NUCLEO-H723ZG (STM32H723ZGT6, Cortex-M7), 64 MHz.

### CRC-32/ISO-HDLC, NUCLEO-H723ZG, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc32_t256 (C++)](../../records/crc/stm32h723/adapter_etl_crc32_t256.json) | table of 256 | flash | 1072 | 0 | 137–138 | 8.0 |
| [crcany crc32iso_hdlc_byte (C)](../../records/crc/stm32h723/adapter_crcany_crc32_byte.json)[1] | table of 256 | flash | 4168 | 0 | 165–166 | 8.0 |
| [libcrc crc_32 (C)](../../records/crc/stm32h723/adapter_libcrc_crc32.json)[2] | table of 256 | RAM, built at the first call | 144 | 1025 | 158–159 | 8.0 |
| [crc (Rust) Table<1>](../../records/crc/stm32h723/adapter_rust_crc32_table1.json) | table of 256 | flash, computed at compile time | 1254 | 0 | 144–145 | 6.8 |
| [etl crc32_t16 (C++)](../../records/crc/stm32h723/adapter_etl_crc32_t16.json) | table of 16 | flash | 132 | 0 | 233–234 | 14.0 |
| [zephyr crc32_ieee (C)](../../records/crc/stm32h723/adapter_zephyr_crc32_ieee.json) | table of 16 | flash | 152 | 0 | 251–252 | 14.0 |
| [crcany crc32iso_hdlc_word (C)](../../records/crc/stm32h723/adapter_crcany_crc32_word.json) | slicing by 4 | flash (4 KB) | 4296 | 0 | 96–98 | 2.8 |
| [zlib crc32 (C)](../../records/crc/stm32h723/adapter_zlib_crc32.json) | other: "braided" words | flash | 5820 | 0 | 141–143 | 4.9 |
| [crcany crc32iso_hdlc_bit (C)](../../records/crc/stm32h723/adapter_crcany_crc32_bit.json) | bitwise | none | 96 | 0 | 702–718 | 41.0–42.0 |
| [etl crc32_t256 (C++), table in RAM](../../records/crc/stm32h723/adapter_etl_crc32_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 1072 | 1024 | 137–138 | 8.0 |
| [crcany crc32iso_hdlc_byte (C), table in RAM](../../records/crc/stm32h723/adapter_crcany_crc32_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 4168 | 4096 | 165–166 | 8.0 |
| [crc (Rust) Table<1>, table in RAM](../../records/crc/stm32h723/adapter_rust_crc32_table1_ram.json) | table of 256 | RAM (copied at start by the image) | 1254 | 1028 | 144–145 | 6.8 |
| [etl crc32_t16 (C++), table in RAM](../../records/crc/stm32h723/adapter_etl_crc32_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 132 | 64 | 233–234 | 14.0 |
| [zephyr crc32_ieee (C), table in RAM](../../records/crc/stm32h723/adapter_zephyr_crc32_ieee_ram.json) | table of 16 | RAM (copied at start by the image) | 152 | 64 | 251–252 | 14.0 |
| [crcany crc32iso_hdlc_word (C), table in RAM](../../records/crc/stm32h723/adapter_crcany_crc32_word_ram.json) | slicing by 4 | RAM (copied at start by the image) | 4296 | 4096 | 96–97 | 2.8 |
| [zlib crc32 (C), table in RAM](../../records/crc/stm32h723/adapter_zlib_crc32_ram.json) | other: "braided" words | RAM (copied at start by the image) | 5820 | 5120 | 141–143 | 4.9 |
| [the board's CRC unit, CRC-32 (our code)](../../records/crc/stm32h723/adapter_hw_crc32.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 212 | 4 | 55 | 1.5 |

### CRC-32/ISO-HDLC, NUCLEO-H723ZG, cache off

The NUCLEO-H723ZG runs at 64 MHz with the 7 flash wait states it has after power-on: the board's 64 MHz build leaves `FLASH_ACR` as after reset (`firmware/common/stm32h723/board.h`). RM0468 (Table 16) allows 0 or 1 wait states at 64 MHz. The numbers with the cache off carry the 7 wait states; fewer were not measured.

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc32_t256 (C++)](../../records/crc/stm32h723/adapter_etl_crc32_t256.json) | table of 256 | flash | 1072 | 0 | 336–569 | 18.8–34.0 |
| [crcany crc32iso_hdlc_byte (C)](../../records/crc/stm32h723/adapter_crcany_crc32_byte.json)[1] | table of 256 | flash | 4168 | 0 | 431–673 | 18.8–34.0 |
| [libcrc crc_32 (C)](../../records/crc/stm32h723/adapter_libcrc_crc32.json)[2] | table of 256 | RAM, built at the first call | 144 | 1025 | 208–501 | 8.0–26.0 |
| [crc (Rust) Table<1>](../../records/crc/stm32h723/adapter_rust_crc32_table1.json) | table of 256 | flash, computed at compile time | 1254 | 0 | 424–484 | 19.2–23.7 |
| [etl crc32_t16 (C++)](../../records/crc/stm32h723/adapter_etl_crc32_t16.json) | table of 16 | flash | 132 | 0 | 685–893 | 40.0–54.0 |
| [zephyr crc32_ieee (C)](../../records/crc/stm32h723/adapter_zephyr_crc32_ieee.json) | table of 16 | flash | 152 | 0 | 758–965 | 40.0–54.0 |
| [crcany crc32iso_hdlc_word (C)](../../records/crc/stm32h723/adapter_crcany_crc32_word.json) | slicing by 4 | flash (4 KB) | 4296 | 0 | 474–522 | 18.4–19.8 |
| [zlib crc32 (C)](../../records/crc/stm32h723/adapter_zlib_crc32.json) | other: "braided" words | flash | 5820 | 0 | 439–479 | 20.3–22.3 |
| [crcany crc32iso_hdlc_bit (C)](../../records/crc/stm32h723/adapter_crcany_crc32_bit.json) | bitwise | none | 96 | 0 | 808–3736 | 41.0–225.0 |
| [etl crc32_t256 (C++), table in RAM](../../records/crc/stm32h723/adapter_etl_crc32_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 1072 | 1024 | 167–441 | 8.0–27.0 |
| [crcany crc32iso_hdlc_byte (C), table in RAM](../../records/crc/stm32h723/adapter_crcany_crc32_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 4168 | 4096 | 261–536 | 8.0–27.0 |
| [crc (Rust) Table<1>, table in RAM](../../records/crc/stm32h723/adapter_rust_crc32_table1_ram.json) | table of 256 | RAM (copied at start by the image) | 1254 | 1028 | 262–288 | 10.2–13.2 |
| [etl crc32_t16 (C++), table in RAM](../../records/crc/stm32h723/adapter_etl_crc32_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 132 | 64 | 433–626 | 25.0–39.0 |
| [zephyr crc32_ieee (C), table in RAM](../../records/crc/stm32h723/adapter_zephyr_crc32_ieee_ram.json) | table of 16 | RAM (copied at start by the image) | 152 | 64 | 511–703 | 26.0–39.0 |
| [crcany crc32iso_hdlc_word (C), table in RAM](../../records/crc/stm32h723/adapter_crcany_crc32_word_ram.json) | slicing by 4 | RAM (copied at start by the image) | 4296 | 4096 | 305–359 | 7.2–10.5 |
| [zlib crc32 (C), table in RAM](../../records/crc/stm32h723/adapter_zlib_crc32_ram.json) | other: "braided" words | RAM (copied at start by the image) | 5820 | 5120 | 261–285 | 10.0–12.1 |
| [the board's CRC unit, CRC-32 (our code)](../../records/crc/stm32h723/adapter_hw_crc32.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 212 | 4 | 130–218 | 1.5–6.5 |

### CRC-16/IBM-3740, NUCLEO-H723ZG, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc16_ccitt_t256 (C++)](../../records/crc/stm32h723/adapter_etl_crc16_t256.json) | table of 256 | flash | 568 | 0 | 121–122 | 7.0 |
| [crcany crc16ibm_3740_byte (C)](../../records/crc/stm32h723/adapter_crcany_crc16_byte.json) | table of 256 | flash | 594 | 0 | 153–154 | 7.0 |
| [libcrc crc_ccitt_ffff (C)](../../records/crc/stm32h723/adapter_libcrc_ccitt_ffff.json)[3] | table of 256 | RAM, built at the first call | 180 | 513 | 141–142 | 7.0 |
| [crcpp CRC_16_CCITTFALSE Table (C++)](../../records/crc/stm32h723/adapter_crcpp_ccittfalse_table.json) | table of 256 | RAM, built by the table's constructor | 344 | 524 | 183 | 10.0 |
| [etl crc16_ccitt_t16 (C++)](../../records/crc/stm32h723/adapter_etl_crc16_t16.json) | table of 16 | flash | 112 | 0 | 233 | 14.0 |
| [zephyr crc16_itu_t (C)](../../records/crc/stm32h723/adapter_zephyr_crc16_itu_t.json) | other: shifts and XORs | none | 72 | 0 | 225–226 | 13.0 |
| [etl crc16_ccitt_t256 (C++), table in RAM](../../records/crc/stm32h723/adapter_etl_crc16_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 568 | 512 | 121–122 | 7.0 |
| [crcany crc16ibm_3740_byte (C), table in RAM](../../records/crc/stm32h723/adapter_crcany_crc16_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 594 | 512 | 153–154 | 7.0 |
| [etl crc16_ccitt_t16 (C++), table in RAM](../../records/crc/stm32h723/adapter_etl_crc16_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 112 | 32 | 233 | 14.0 |
| [the board's CRC unit, CRC-16 (our code)](../../records/crc/stm32h723/adapter_hw_crc16.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 212 | 4 | 55 | 1.5 |

### CRC-16/IBM-3740, NUCLEO-H723ZG, cache off

The NUCLEO-H723ZG runs at 64 MHz with the 7 flash wait states it has after power-on: the board's 64 MHz build leaves `FLASH_ACR` as after reset (`firmware/common/stm32h723/board.h`). RM0468 (Table 16) allows 0 or 1 wait states at 64 MHz. The numbers with the cache off carry the 7 wait states; fewer were not measured.

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc16_ccitt_t256 (C++)](../../records/crc/stm32h723/adapter_etl_crc16_t256.json) | table of 256 | flash | 568 | 0 | 317–574 | 17.5–34.0 |
| [crcany crc16ibm_3740_byte (C)](../../records/crc/stm32h723/adapter_crcany_crc16_byte.json) | table of 256 | flash | 594 | 0 | 423–689 | 17.6–34.0 |
| [libcrc crc_ccitt_ffff (C)](../../records/crc/stm32h723/adapter_libcrc_ccitt_ffff.json)[3] | table of 256 | RAM, built at the first call | 180 | 513 | 210–513 | 7.0–27.0 |
| [crcpp CRC_16_CCITTFALSE Table (C++)](../../records/crc/stm32h723/adapter_crcpp_ccittfalse_table.json) | table of 256 | RAM, built by the table's constructor | 344 | 524 | 469–519 | 25.0–28.0 |
| [etl crc16_ccitt_t16 (C++)](../../records/crc/stm32h723/adapter_etl_crc16_t16.json) | table of 16 | flash | 112 | 0 | 683–902 | 40.0–54.0 |
| [zephyr crc16_itu_t (C)](../../records/crc/stm32h723/adapter_zephyr_crc16_itu_t.json) | other: shifts and XORs | none | 72 | 0 | 485–696 | 26.0–40.0 |
| [etl crc16_ccitt_t256 (C++), table in RAM](../../records/crc/stm32h723/adapter_etl_crc16_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 568 | 512 | 150–447 | 7.0–27.0 |
| [crcany crc16ibm_3740_byte (C), table in RAM](../../records/crc/stm32h723/adapter_crcany_crc16_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 594 | 512 | 257–561 | 7.0–27.0 |
| [etl crc16_ccitt_t16 (C++), table in RAM](../../records/crc/stm32h723/adapter_etl_crc16_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 112 | 32 | 482–653 | 27.0–40.0 |
| [the board's CRC unit, CRC-16 (our code)](../../records/crc/stm32h723/adapter_hw_crc16.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 212 | 4 | 130–218 | 1.5–6.5 |

### CRC-8/SMBUS, NUCLEO-H723ZG, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc8_ccitt_t256 (C++)](../../records/crc/stm32h723/adapter_etl_crc8_t256.json) | table of 256 | flash | 296 | 0 | 91–92 | 5.0 |
| [crcany crc8smbus_byte (C)](../../records/crc/stm32h723/adapter_crcany_crc8_byte.json) | table of 256 | flash | 1090 | 0 | 123–124 | 5.0 |
| [acecrc crc8_byte (C++)](../../records/crc/stm32h723/adapter_acecrc_crc8_byte.json) | table of 256 | flash | 304 | 0 | 102–104 | 5.0 |
| [etl crc8_ccitt_t16 (C++)](../../records/crc/stm32h723/adapter_etl_crc8_t16.json) | table of 16 | flash | 92 | 0 | 234 | 14.0 |
| [zephyr crc8_ccitt (C)](../../records/crc/stm32h723/adapter_zephyr_crc8_ccitt.json) | table of 16 | flash | 100 | 0 | 231–232 | 13.0 |
| [etl crc8_ccitt_t256 (C++), table in RAM](../../records/crc/stm32h723/adapter_etl_crc8_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 296 | 256 | 91–92 | 5.0 |
| [crcany crc8smbus_byte (C), table in RAM](../../records/crc/stm32h723/adapter_crcany_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 1090 | 1024 | 123–124 | 5.0 |
| [acecrc crc8_byte (C++), table in RAM](../../records/crc/stm32h723/adapter_acecrc_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 304 | 256 | 102–104 | 5.0 |
| [etl crc8_ccitt_t16 (C++), table in RAM](../../records/crc/stm32h723/adapter_etl_crc8_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 92 | 16 | 234 | 14.0 |
| [zephyr crc8_ccitt (C), table in RAM](../../records/crc/stm32h723/adapter_zephyr_crc8_ccitt_ram.json) | table of 16 | RAM (copied at start by the image) | 100 | 16 | 231–232 | 13.0 |
| [the board's CRC unit, CRC-8 (our code)](../../records/crc/stm32h723/adapter_hw_crc8.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 208 | 4 | 55 | 1.5 |

### CRC-8/SMBUS, NUCLEO-H723ZG, cache off

The NUCLEO-H723ZG runs at 64 MHz with the 7 flash wait states it has after power-on: the board's 64 MHz build leaves `FLASH_ACR` as after reset (`firmware/common/stm32h723/board.h`). RM0468 (Table 16) allows 0 or 1 wait states at 64 MHz. The numbers with the cache off carry the 7 wait states; fewer were not measured.

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc8_ccitt_t256 (C++)](../../records/crc/stm32h723/adapter_etl_crc8_t256.json) | table of 256 | flash | 296 | 0 | 272–569 | 15.0–34.0 |
| [crcany crc8smbus_byte (C)](../../records/crc/stm32h723/adapter_crcany_crc8_byte.json) | table of 256 | flash | 1090 | 0 | 380–678 | 15.1–34.0 |
| [acecrc crc8_byte (C++)](../../records/crc/stm32h723/adapter_acecrc_crc8_byte.json) | table of 256 | flash | 304 | 0 | 311–617 | 15.0–34.0 |
| [etl crc8_ccitt_t16 (C++)](../../records/crc/stm32h723/adapter_etl_crc8_t16.json) | table of 16 | flash | 92 | 0 | 683–893 | 40.0–54.0 |
| [zephyr crc8_ccitt (C)](../../records/crc/stm32h723/adapter_zephyr_crc8_ccitt.json) | table of 16 | flash | 100 | 0 | 729–952 | 40.0–54.0 |
| [etl crc8_ccitt_t256 (C++), table in RAM](../../records/crc/stm32h723/adapter_etl_crc8_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 296 | 256 | 112–425 | 5.0–25.0 |
| [crcany crc8smbus_byte (C), table in RAM](../../records/crc/stm32h723/adapter_crcany_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 1090 | 1024 | 216–534 | 5.0–26.0 |
| [acecrc crc8_byte (C++), table in RAM](../../records/crc/stm32h723/adapter_acecrc_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 304 | 256 | 150–473 | 5.0–25.0 |
| [etl crc8_ccitt_t16 (C++), table in RAM](../../records/crc/stm32h723/adapter_etl_crc8_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 92 | 16 | 451–648 | 26.0–39.0 |
| [zephyr crc8_ccitt (C), table in RAM](../../records/crc/stm32h723/adapter_zephyr_crc8_ccitt_ram.json) | table of 16 | RAM (copied at start by the image) | 100 | 16 | 502–682 | 26.0–39.0 |
| [the board's CRC unit, CRC-8 (our code)](../../records/crc/stm32h723/adapter_hw_crc8.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 208 | 4 | 130–218 | 1.5–6.5 |

## NUCLEO-G0B1RE

NUCLEO-G0B1RE (STM32G0B1RET6, Cortex-M0+), 64 MHz.

### CRC-32/ISO-HDLC, NUCLEO-G0B1RE, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc32_t256 (C++)](../../records/crc/stm32g0b1/adapter_etl_crc32_t256.json) | table of 256 | flash | 1072 | 0 | 266–268 | 15.0 |
| [crcany crc32iso_hdlc_byte (C)](../../records/crc/stm32g0b1/adapter_crcany_crc32_byte.json)[1] | table of 256 | flash | 4170 | 0 | 322–324 | 15.0 |
| [libcrc crc_32 (C)](../../records/crc/stm32g0b1/adapter_libcrc_crc32.json)[2] | table of 256 | RAM, built at the first call | 172 | 1025 | 330–391 | 16.0–20.0 |
| [crc (Rust) Table<1>](../../records/crc/stm32g0b1/adapter_rust_crc32_table1.json) | table of 256 | flash, computed at compile time | 1216 | 0 | 287–288 | 13.8–14.2 |
| [etl crc32_t16 (C++)](../../records/crc/stm32g0b1/adapter_etl_crc32_t16.json) | table of 16 | flash | 128 | 0 | 461–505 | 27.0–30.0 |
| [zephyr crc32_ieee (C)](../../records/crc/stm32g0b1/adapter_zephyr_crc32_ieee.json) | table of 16 | flash | 142 | 0 | 510–583 | 28.0–33.0 |
| [crcany crc32iso_hdlc_word (C)](../../records/crc/stm32g0b1/adapter_crcany_crc32_word.json) | slicing by 4 | flash (4 KB) | 4318 | 0 | 346–355 | 12.5–13.5 |
| [zlib crc32 (C)](../../records/crc/stm32g0b1/adapter_zlib_crc32.json) | other: "braided" words | flash | 6228 | 0 | 346–350 | 16.1–16.9 |
| [crcany crc32iso_hdlc_bit (C)](../../records/crc/stm32g0b1/adapter_crcany_crc32_bit.json) | bitwise | none | 90 | 0 | 1476–1524 | 87.0–90.0 |
| [etl crc32_t256 (C++), table in RAM](../../records/crc/stm32g0b1/adapter_etl_crc32_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 1072 | 1024 | 233–236 | 13.0 |
| [crcany crc32iso_hdlc_byte (C), table in RAM](../../records/crc/stm32g0b1/adapter_crcany_crc32_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 4170 | 4096 | 288–292 | 13.0 |
| [crc (Rust) Table<1>, table in RAM](../../records/crc/stm32g0b1/adapter_rust_crc32_table1_ram.json) | table of 256 | RAM (copied at start by the image) | 1216 | 1028 | 240–243 | 11.0–11.2 |
| [etl crc32_t16 (C++), table in RAM](../../records/crc/stm32g0b1/adapter_etl_crc32_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 128 | 64 | 395–409 | 23.0–24.0 |
| [zephyr crc32_ieee (C), table in RAM](../../records/crc/stm32g0b1/adapter_zephyr_crc32_ieee_ram.json) | table of 16 | RAM (copied at start by the image) | 142 | 64 | 430–488 | 23.0–27.0 |
| [crcany crc32iso_hdlc_word (C), table in RAM](../../records/crc/stm32g0b1/adapter_crcany_crc32_word_ram.json) | slicing by 4 | RAM (copied at start by the image) | 4318 | 4096 | 306–307 | 10.0–10.5 |
| [zlib crc32 (C), table in RAM](../../records/crc/stm32g0b1/adapter_zlib_crc32_ram.json) | other: "braided" words | RAM (copied at start by the image) | 6228 | 5120 | 304–306 | 13.6–14.1 |
| [the board's CRC unit, CRC-32 (our code)](../../records/crc/stm32g0b1/adapter_hw_crc32.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 196 | 4 | 128 | 2.0 |

### CRC-32/ISO-HDLC, NUCLEO-G0B1RE, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc32_t256 (C++)](../../records/crc/stm32g0b1/adapter_etl_crc32_t256.json) | table of 256 | flash | 1072 | 0 | 367–425 | 21.0–25.0 |
| [crcany crc32iso_hdlc_byte (C)](../../records/crc/stm32g0b1/adapter_crcany_crc32_byte.json)[1] | table of 256 | flash | 4170 | 0 | 428–488 | 21.0–25.0 |
| [libcrc crc_32 (C)](../../records/crc/stm32g0b1/adapter_libcrc_crc32.json)[2] | table of 256 | RAM, built at the first call | 172 | 1025 | 471–501 | 24.0–26.0 |
| [crc (Rust) Table<1>](../../records/crc/stm32g0b1/adapter_rust_crc32_table1.json) | table of 256 | flash, computed at compile time | 1216 | 0 | 357–361 | 17.8 |
| [etl crc32_t16 (C++)](../../records/crc/stm32g0b1/adapter_etl_crc32_t16.json) | table of 16 | flash | 128 | 0 | 622–626 | 37.0 |
| [zephyr crc32_ieee (C)](../../records/crc/stm32g0b1/adapter_zephyr_crc32_ieee.json) | table of 16 | flash | 142 | 0 | 660–688 | 37.0–39.0 |
| [crcany crc32iso_hdlc_word (C)](../../records/crc/stm32g0b1/adapter_crcany_crc32_word.json) | slicing by 4 | flash (4 KB) | 4318 | 0 | 431–435 | 16.5–17.0 |
| [zlib crc32 (C)](../../records/crc/stm32g0b1/adapter_zlib_crc32.json) | other: "braided" words | flash | 6228 | 0 | 445–453 | 21.5–22.4 |
| [crcany crc32iso_hdlc_bit (C)](../../records/crc/stm32g0b1/adapter_crcany_crc32_bit.json) | bitwise | none | 90 | 0 | 2319–2511 | 139.0–151.0 |
| [etl crc32_t256 (C++), table in RAM](../../records/crc/stm32g0b1/adapter_etl_crc32_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 1072 | 1024 | 335–361 | 19.0–21.0 |
| [crcany crc32iso_hdlc_byte (C), table in RAM](../../records/crc/stm32g0b1/adapter_crcany_crc32_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 4170 | 4096 | 396–424 | 19.0–21.0 |
| [crc (Rust) Table<1>, table in RAM](../../records/crc/stm32g0b1/adapter_rust_crc32_table1_ram.json) | table of 256 | RAM (copied at start by the image) | 1216 | 1028 | 309–313 | 14.8 |
| [etl crc32_t16 (C++), table in RAM](../../records/crc/stm32g0b1/adapter_etl_crc32_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 128 | 64 | 526–530 | 31.0 |
| [zephyr crc32_ieee (C), table in RAM](../../records/crc/stm32g0b1/adapter_zephyr_crc32_ieee_ram.json) | table of 16 | RAM (copied at start by the image) | 142 | 64 | 564–592 | 31.0–33.0 |
| [crcany crc32iso_hdlc_word (C), table in RAM](../../records/crc/stm32g0b1/adapter_crcany_crc32_word_ram.json) | slicing by 4 | RAM (copied at start by the image) | 4318 | 4096 | 387–391 | 14.0 |
| [zlib crc32 (C), table in RAM](../../records/crc/stm32g0b1/adapter_zlib_crc32_ram.json) | other: "braided" words | RAM (copied at start by the image) | 6228 | 5120 | 401 | 18.8–19.1 |
| [the board's CRC unit, CRC-32 (our code)](../../records/crc/stm32g0b1/adapter_hw_crc32.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 196 | 4 | 156–158 | 3.0–3.5 |

### CRC-16/IBM-3740, NUCLEO-G0B1RE, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc16_ccitt_t256 (C++)](../../records/crc/stm32g0b1/adapter_etl_crc16_t256.json) | table of 256 | flash | 560 | 0 | 285–286 | 16.0 |
| [crcany crc16ibm_3740_byte (C)](../../records/crc/stm32g0b1/adapter_crcany_crc16_byte.json) | table of 256 | flash | 590 | 0 | 337–340 | 16.0 |
| [libcrc crc_ccitt_ffff (C)](../../records/crc/stm32g0b1/adapter_libcrc_ccitt_ffff.json)[3] | table of 256 | RAM, built at the first call | 180 | 513 | 284 | 14.0 |
| [crcpp CRC_16_CCITTFALSE Table (C++)](../../records/crc/stm32g0b1/adapter_crcpp_ccittfalse_table.json) | table of 256 | RAM, built by the table's constructor | 528 | 524 | 335–382 | 17.0–20.0 |
| [etl crc16_ccitt_t16 (C++)](../../records/crc/stm32g0b1/adapter_etl_crc16_t16.json) | table of 16 | flash | 100 | 0 | 542–544 | 32.0 |
| [zephyr crc16_itu_t (C)](../../records/crc/stm32g0b1/adapter_zephyr_crc16_itu_t.json) | other: shifts and XORs | none | 68 | 0 | 360–377 | 20.0–21.0 |
| [etl crc16_ccitt_t256 (C++), table in RAM](../../records/crc/stm32g0b1/adapter_etl_crc16_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 560 | 512 | 253 | 14.0 |
| [crcany crc16ibm_3740_byte (C), table in RAM](../../records/crc/stm32g0b1/adapter_crcany_crc16_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 590 | 512 | 305–306 | 14.0 |
| [etl crc16_ccitt_t16 (C++), table in RAM](../../records/crc/stm32g0b1/adapter_etl_crc16_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 100 | 32 | 446–480 | 26.0–28.0 |
| [the board's CRC unit, CRC-16 (our code)](../../records/crc/stm32g0b1/adapter_hw_crc16.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 200 | 4 | 129 | 2.0 |

### CRC-16/IBM-3740, NUCLEO-G0B1RE, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc16_ccitt_t256 (C++)](../../records/crc/stm32g0b1/adapter_etl_crc16_t256.json) | table of 256 | flash | 560 | 0 | 415–445 | 24.0–26.0 |
| [crcany crc16ibm_3740_byte (C)](../../records/crc/stm32g0b1/adapter_crcany_crc16_byte.json) | table of 256 | flash | 590 | 0 | 472–504 | 24.0–26.0 |
| [libcrc crc_ccitt_ffff (C)](../../records/crc/stm32g0b1/adapter_libcrc_ccitt_ffff.json)[3] | table of 256 | RAM, built at the first call | 180 | 513 | 385–417 | 20.0–22.0 |
| [crcpp CRC_16_CCITTFALSE Table (C++)](../../records/crc/stm32g0b1/adapter_crcpp_ccittfalse_table.json) | table of 256 | RAM, built by the table's constructor | 528 | 524 | 470–500 | 25.0–27.0 |
| [etl crc16_ccitt_t16 (C++)](../../records/crc/stm32g0b1/adapter_etl_crc16_t16.json) | table of 16 | flash | 100 | 0 | 678–738 | 40.0–44.0 |
| [zephyr crc16_itu_t (C)](../../records/crc/stm32g0b1/adapter_zephyr_crc16_itu_t.json) | other: shifts and XORs | none | 68 | 0 | 492–494 | 28.0 |
| [etl crc16_ccitt_t256 (C++), table in RAM](../../records/crc/stm32g0b1/adapter_etl_crc16_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 560 | 512 | 381–383 | 22.0 |
| [crcany crc16ibm_3740_byte (C), table in RAM](../../records/crc/stm32g0b1/adapter_crcany_crc16_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 590 | 512 | 440 | 22.0 |
| [etl crc16_ccitt_t16 (C++), table in RAM](../../records/crc/stm32g0b1/adapter_etl_crc16_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 100 | 32 | 610–614 | 36.0 |
| [the board's CRC unit, CRC-16 (our code)](../../records/crc/stm32g0b1/adapter_hw_crc16.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 200 | 4 | 157–159 | 3.0–3.5 |

### CRC-8/SMBUS, NUCLEO-G0B1RE, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc8_ccitt_t256 (C++)](../../records/crc/stm32g0b1/adapter_etl_crc8_t256.json) | table of 256 | flash | 288 | 0 | 198–201 | 11.0 |
| [crcany crc8smbus_byte (C)](../../records/crc/stm32g0b1/adapter_crcany_crc8_byte.json) | table of 256 | flash | 1086 | 0 | 243–252 | 11.0 |
| [acecrc crc8_byte (C++)](../../records/crc/stm32g0b1/adapter_acecrc_crc8_byte.json) | table of 256 | flash | 298 | 0 | 214–215 | 11.0 |
| [etl crc8_ccitt_t16 (C++)](../../records/crc/stm32g0b1/adapter_etl_crc8_t16.json) | table of 16 | flash | 72 | 0 | 457–522 | 27.0–31.0 |
| [zephyr crc8_ccitt (C)](../../records/crc/stm32g0b1/adapter_zephyr_crc8_ccitt.json) | table of 16 | flash | 78 | 0 | 454–468 | 26.0–27.0 |
| [etl crc8_ccitt_t256 (C++), table in RAM](../../records/crc/stm32g0b1/adapter_etl_crc8_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 288 | 256 | 166–168 | 9.0 |
| [crcany crc8smbus_byte (C), table in RAM](../../records/crc/stm32g0b1/adapter_crcany_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 1086 | 1024 | 211–219 | 9.0 |
| [acecrc crc8_byte (C++), table in RAM](../../records/crc/stm32g0b1/adapter_acecrc_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 298 | 256 | 182 | 9.0 |
| [etl crc8_ccitt_t16 (C++), table in RAM](../../records/crc/stm32g0b1/adapter_etl_crc8_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 72 | 16 | 393–410 | 23.0–24.0 |
| [zephyr crc8_ccitt (C), table in RAM](../../records/crc/stm32g0b1/adapter_zephyr_crc8_ccitt_ram.json) | table of 16 | RAM (copied at start by the image) | 78 | 16 | 372–404 | 21.0–23.0 |
| [the board's CRC unit, CRC-8 (our code)](../../records/crc/stm32g0b1/adapter_hw_crc8.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 192 | 4 | 128–131 | 2.0 |

### CRC-8/SMBUS, NUCLEO-G0B1RE, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc8_ccitt_t256 (C++)](../../records/crc/stm32g0b1/adapter_etl_crc8_t256.json) | table of 256 | flash | 288 | 0 | 294–298 | 17.0 |
| [crcany crc8smbus_byte (C)](../../records/crc/stm32g0b1/adapter_crcany_crc8_byte.json) | table of 256 | flash | 1086 | 0 | 349–355 | 17.0 |
| [acecrc crc8_byte (C++)](../../records/crc/stm32g0b1/adapter_acecrc_crc8_byte.json) | table of 256 | flash | 298 | 0 | 312–314 | 17.0 |
| [etl crc8_ccitt_t16 (C++)](../../records/crc/stm32g0b1/adapter_etl_crc8_t16.json) | table of 16 | flash | 72 | 0 | 589–655 | 35.0–39.0 |
| [zephyr crc8_ccitt (C)](../../records/crc/stm32g0b1/adapter_zephyr_crc8_ccitt.json) | table of 16 | flash | 78 | 0 | 570–632 | 33.0–37.0 |
| [etl crc8_ccitt_t256 (C++), table in RAM](../../records/crc/stm32g0b1/adapter_etl_crc8_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 288 | 256 | 234–262 | 13.0–15.0 |
| [crcany crc8smbus_byte (C), table in RAM](../../records/crc/stm32g0b1/adapter_crcany_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 1086 | 1024 | 291–317 | 13.0–15.0 |
| [acecrc crc8_byte (C++), table in RAM](../../records/crc/stm32g0b1/adapter_acecrc_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 298 | 256 | 250–280 | 13.0–15.0 |
| [etl crc8_ccitt_t16 (C++), table in RAM](../../records/crc/stm32g0b1/adapter_etl_crc8_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 72 | 16 | 525–527 | 31.0 |
| [zephyr crc8_ccitt (C), table in RAM](../../records/crc/stm32g0b1/adapter_zephyr_crc8_ccitt_ram.json) | table of 16 | RAM (copied at start by the image) | 78 | 16 | 504–506 | 29.0 |
| [the board's CRC unit, CRC-8 (our code)](../../records/crc/stm32g0b1/adapter_hw_crc8.json) (the board's CRC unit, driven by our code; not a library) | hardware unit | none | 192 | 4 | 157–159 | 3.0–3.5 |

## SAM D20 Xplained Pro

SAM D20 Xplained Pro (ATSAMD20J18A, Cortex-M0+), 48 MHz.

### CRC-32/ISO-HDLC, SAM D20 Xplained Pro, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc32_t256 (C++)](../../records/crc/samd20/adapter_etl_crc32_t256.json) | table of 256 | flash | 1072 | 0 | 272–274 | 15.3–15.6 |
| [crcany crc32iso_hdlc_byte (C)](../../records/crc/samd20/adapter_crcany_crc32_byte.json)[1] | table of 256 | flash | 4170 | 0 | 307–310 | 14.3–14.6 |
| [libcrc crc_32 (C)](../../records/crc/samd20/adapter_libcrc_crc32.json)[2] | table of 256 | RAM, built at the first call | 172 | 1025 | 332–333 | 16.0 |
| [crc (Rust) Table<1>](../../records/crc/samd20/adapter_rust_crc32_table1.json) | table of 256 | flash, computed at compile time | 1216 | 0 | 270–271 | 12.7–12.9 |
| [etl crc32_t16 (C++)](../../records/crc/samd20/adapter_etl_crc32_t16.json) | table of 16 | flash | 128 | 0 | 409–410 | 23.4 |
| [zephyr crc32_ieee (C)](../../records/crc/samd20/adapter_zephyr_crc32_ieee.json) | table of 16 | flash | 142 | 0 | 460–474 | 24.5–25.6 |
| [crcany crc32iso_hdlc_word (C)](../../records/crc/samd20/adapter_crcany_crc32_word.json) | slicing by 4 | flash (4 KB) | 4318 | 0 | 334–335 | 11.9–12.1 |
| [zlib crc32 (C)](../../records/crc/samd20/adapter_zlib_crc32.json) | other: "braided" words | flash | 6228 | 0 | 366–368 | 17.6–17.7 |
| [crcany crc32iso_hdlc_bit (C)](../../records/crc/samd20/adapter_crcany_crc32_bit.json) | bitwise | none | 90 | 0 | 1475–1476 | 87.0 |
| [etl crc32_t256 (C++), table in RAM](../../records/crc/samd20/adapter_etl_crc32_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 1072 | 1024 | 234–235 | 13.0 |
| [crcany crc32iso_hdlc_byte (C), table in RAM](../../records/crc/samd20/adapter_crcany_crc32_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 4170 | 4096 | 285 | 13.0 |
| [crc (Rust) Table<1>, table in RAM](../../records/crc/samd20/adapter_rust_crc32_table1_ram.json) | table of 256 | RAM (copied at start by the image) | 1216 | 1028 | 242–244 | 10.8–11.0 |
| [etl crc32_t16 (C++), table in RAM](../../records/crc/samd20/adapter_etl_crc32_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 128 | 64 | 368–369 | 21.0 |
| [zephyr crc32_ieee (C), table in RAM](../../records/crc/samd20/adapter_zephyr_crc32_ieee_ram.json) | table of 16 | RAM (copied at start by the image) | 142 | 64 | 396–397 | 21.0 |
| [crcany crc32iso_hdlc_word (C), table in RAM](../../records/crc/samd20/adapter_crcany_crc32_word_ram.json) | slicing by 4 | RAM (copied at start by the image) | 4318 | 4096 | 307 | 10.0–10.2 |
| [zlib crc32 (C), table in RAM](../../records/crc/samd20/adapter_zlib_crc32_ram.json) | other: "braided" words | RAM (copied at start by the image) | 6228 | 5120 | 340–342 | 15.7–15.9 |

### CRC-32/ISO-HDLC, SAM D20 Xplained Pro, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc32_t256 (C++)](../../records/crc/samd20/adapter_etl_crc32_t256.json) | table of 256 | flash | 1072 | 0 | 345 | 20.0 |
| [crcany crc32iso_hdlc_byte (C)](../../records/crc/samd20/adapter_crcany_crc32_byte.json)[1] | table of 256 | flash | 4170 | 0 | 402 | 20.0 |
| [libcrc crc_32 (C)](../../records/crc/samd20/adapter_libcrc_crc32.json)[2] | table of 256 | RAM, built at the first call | 172 | 1025 | 463 | 24.0 |
| [crc (Rust) Table<1>](../../records/crc/samd20/adapter_rust_crc32_table1.json) | table of 256 | flash, computed at compile time | 1216 | 0 | 317 | 15.5 |
| [etl crc32_t16 (C++)](../../records/crc/samd20/adapter_etl_crc32_t16.json) | table of 16 | flash | 128 | 0 | 541 | 32.0 |
| [zephyr crc32_ieee (C)](../../records/crc/samd20/adapter_zephyr_crc32_ieee.json) | table of 16 | flash | 142 | 0 | 587 | 33.0 |
| [crcany crc32iso_hdlc_word (C)](../../records/crc/samd20/adapter_crcany_crc32_word.json) | slicing by 4 | flash (4 KB) | 4318 | 0 | 388 | 14.8 |
| [zlib crc32 (C)](../../records/crc/samd20/adapter_zlib_crc32.json) | other: "braided" words | flash | 6228 | 0 | 406 | 19.8 |
| [crcany crc32iso_hdlc_bit (C)](../../records/crc/samd20/adapter_crcany_crc32_bit.json) | bitwise | none | 90 | 0 | 2279 | 137.0 |
| [etl crc32_t256 (C++), table in RAM](../../records/crc/samd20/adapter_etl_crc32_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 1072 | 1024 | 329 | 19.0 |
| [crcany crc32iso_hdlc_byte (C), table in RAM](../../records/crc/samd20/adapter_crcany_crc32_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 4170 | 4096 | 386 | 19.0 |
| [crc (Rust) Table<1>, table in RAM](../../records/crc/samd20/adapter_rust_crc32_table1_ram.json) | table of 256 | RAM (copied at start by the image) | 1216 | 1028 | 301 | 14.5 |
| [etl crc32_t16 (C++), table in RAM](../../records/crc/samd20/adapter_etl_crc32_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 128 | 64 | 509 | 30.0 |
| [zephyr crc32_ieee (C), table in RAM](../../records/crc/samd20/adapter_zephyr_crc32_ieee_ram.json) | table of 16 | RAM (copied at start by the image) | 142 | 64 | 555 | 31.0 |
| [crcany crc32iso_hdlc_word (C), table in RAM](../../records/crc/samd20/adapter_crcany_crc32_word_ram.json) | slicing by 4 | RAM (copied at start by the image) | 4318 | 4096 | 372 | 13.8 |
| [zlib crc32 (C), table in RAM](../../records/crc/samd20/adapter_zlib_crc32_ram.json) | other: "braided" words | RAM (copied at start by the image) | 6228 | 5120 | 390 | 18.8 |

### CRC-16/IBM-3740, SAM D20 Xplained Pro, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc16_ccitt_t256 (C++)](../../records/crc/samd20/adapter_etl_crc16_t256.json) | table of 256 | flash | 560 | 0 | 293 | 16.5 |
| [crcany crc16ibm_3740_byte (C)](../../records/crc/samd20/adapter_crcany_crc16_byte.json) | table of 256 | flash | 590 | 0 | 322–323 | 15.6 |
| [libcrc crc_ccitt_ffff (C)](../../records/crc/samd20/adapter_libcrc_ccitt_ffff.json)[3] | table of 256 | RAM, built at the first call | 180 | 513 | 279–280 | 14.0 |
| [crcpp CRC_16_CCITTFALSE Table (C++)](../../records/crc/samd20/adapter_crcpp_ccittfalse_table.json) | table of 256 | RAM, built by the table's constructor | 528 | 524 | 333–334 | 17.0 |
| [etl crc16_ccitt_t16 (C++)](../../records/crc/samd20/adapter_etl_crc16_t16.json) | table of 16 | flash | 100 | 0 | 464–482 | 26.7–27.8 |
| [zephyr crc16_itu_t (C)](../../records/crc/samd20/adapter_zephyr_crc16_itu_t.json) | other: shifts and XORs | none | 68 | 0 | 330–331 | 18.0 |
| [etl crc16_ccitt_t256 (C++), table in RAM](../../records/crc/samd20/adapter_etl_crc16_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 560 | 512 | 252 | 14.0 |
| [crcany crc16ibm_3740_byte (C), table in RAM](../../records/crc/samd20/adapter_crcany_crc16_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 590 | 512 | 297–298 | 14.0 |
| [etl crc16_ccitt_t16 (C++), table in RAM](../../records/crc/samd20/adapter_etl_crc16_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 100 | 32 | 418–420 | 24.0 |

### CRC-16/IBM-3740, SAM D20 Xplained Pro, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc16_ccitt_t256 (C++)](../../records/crc/samd20/adapter_etl_crc16_t256.json) | table of 256 | flash | 560 | 0 | 377 | 22.0 |
| [crcany crc16ibm_3740_byte (C)](../../records/crc/samd20/adapter_crcany_crc16_byte.json) | table of 256 | flash | 590 | 0 | 430 | 22.0 |
| [libcrc crc_ccitt_ffff (C)](../../records/crc/samd20/adapter_libcrc_ccitt_ffff.json)[3] | table of 256 | RAM, built at the first call | 180 | 513 | 376 | 20.0 |
| [crcpp CRC_16_CCITTFALSE Table (C++)](../../records/crc/samd20/adapter_crcpp_ccittfalse_table.json) | table of 256 | RAM, built by the table's constructor | 528 | 524 | 463 | 25.0 |
| [etl crc16_ccitt_t16 (C++)](../../records/crc/samd20/adapter_etl_crc16_t16.json) | table of 16 | flash | 100 | 0 | 623 | 37.0 |
| [zephyr crc16_itu_t (C)](../../records/crc/samd20/adapter_zephyr_crc16_itu_t.json) | other: shifts and XORs | none | 68 | 0 | 473 | 27.0 |
| [etl crc16_ccitt_t256 (C++), table in RAM](../../records/crc/samd20/adapter_etl_crc16_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 560 | 512 | 361 | 21.0 |
| [crcany crc16ibm_3740_byte (C), table in RAM](../../records/crc/samd20/adapter_crcany_crc16_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 590 | 512 | 414 | 21.0 |
| [etl crc16_ccitt_t16 (C++), table in RAM](../../records/crc/samd20/adapter_etl_crc16_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 100 | 32 | 591 | 35.0 |

### CRC-8/SMBUS, SAM D20 Xplained Pro, cache on

Cycles, cache on: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc8_ccitt_t256 (C++)](../../records/crc/samd20/adapter_etl_crc8_t256.json) | table of 256 | flash | 288 | 0 | 199–201 | 10.9–11.1 |
| [crcany crc8smbus_byte (C)](../../records/crc/samd20/adapter_crcany_crc8_byte.json) | table of 256 | flash | 1086 | 0 | 244–245 | 10.9–11.1 |
| [acecrc crc8_byte (C++)](../../records/crc/samd20/adapter_acecrc_crc8_byte.json) | table of 256 | flash | 298 | 0 | 212–215 | 10.9–11.1 |
| [etl crc8_ccitt_t16 (C++)](../../records/crc/samd20/adapter_etl_crc8_t16.json) | table of 16 | flash | 72 | 0 | 427–431 | 24.9–25.1 |
| [zephyr crc8_ccitt (C)](../../records/crc/samd20/adapter_zephyr_crc8_ccitt.json) | table of 16 | flash | 78 | 0 | 402–407 | 22.7–23.1 |
| [etl crc8_ccitt_t256 (C++), table in RAM](../../records/crc/samd20/adapter_etl_crc8_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 288 | 256 | 166–167 | 9.0 |
| [crcany crc8smbus_byte (C), table in RAM](../../records/crc/samd20/adapter_crcany_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 1086 | 1024 | 209–211 | 9.0 |
| [acecrc crc8_byte (C++), table in RAM](../../records/crc/samd20/adapter_acecrc_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 298 | 256 | 179–180 | 9.0 |
| [etl crc8_ccitt_t16 (C++), table in RAM](../../records/crc/samd20/adapter_etl_crc8_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 72 | 16 | 366 | 21.0 |
| [zephyr crc8_ccitt (C), table in RAM](../../records/crc/samd20/adapter_zephyr_crc8_ccitt_ram.json) | table of 16 | RAM (copied at start by the image) | 78 | 16 | 343 | 19.0 |

### CRC-8/SMBUS, SAM D20 Xplained Pro, cache off

Cycles, cache off: the range over the eight placements (min–max), first pass.

| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |
|---|---|---|---:|---:|---:|---:|
| [etl crc8_ccitt_t256 (C++)](../../records/crc/samd20/adapter_etl_crc8_t256.json) | table of 256 | flash | 288 | 0 | 245 | 14.0 |
| [crcany crc8smbus_byte (C)](../../records/crc/samd20/adapter_crcany_crc8_byte.json) | table of 256 | flash | 1086 | 0 | 296 | 14.0 |
| [acecrc crc8_byte (C++)](../../records/crc/samd20/adapter_acecrc_crc8_byte.json) | table of 256 | flash | 298 | 0 | 260 | 14.0 |
| [etl crc8_ccitt_t16 (C++)](../../records/crc/samd20/adapter_etl_crc8_t16.json) | table of 16 | flash | 72 | 0 | 539 | 32.0 |
| [zephyr crc8_ccitt (C)](../../records/crc/samd20/adapter_zephyr_crc8_ccitt.json) | table of 16 | flash | 78 | 0 | 516 | 30.0 |
| [etl crc8_ccitt_t256 (C++), table in RAM](../../records/crc/samd20/adapter_etl_crc8_t256_ram.json) | table of 256 | RAM (copied at start by the image) | 288 | 256 | 229 | 13.0 |
| [crcany crc8smbus_byte (C), table in RAM](../../records/crc/samd20/adapter_crcany_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 1086 | 1024 | 280 | 13.0 |
| [acecrc crc8_byte (C++), table in RAM](../../records/crc/samd20/adapter_acecrc_crc8_byte_ram.json) | table of 256 | RAM (copied at start by the image) | 298 | 256 | 244 | 13.0 |
| [etl crc8_ccitt_t16 (C++), table in RAM](../../records/crc/samd20/adapter_etl_crc8_t16_ram.json) | table of 16 | RAM (copied at start by the image) | 72 | 16 | 507 | 30.0 |
| [zephyr crc8_ccitt (C), table in RAM](../../records/crc/samd20/adapter_zephyr_crc8_ccitt_ram.json) | table of 16 | RAM (copied at start by the image) | 78 | 16 | 484 | 28.0 |

[1] crcany's generated crc32iso_hdlc.c defines `table_byte` as `table_word[0]` (`#define table_byte table_word[0]`, build/gen/src/crc32iso_hdlc.c line 29): the byte code reads the first row of the word table, so the whole word table (4 x 256 x 4 = 4096 bytes, one symbol `table_word` in the image) is linked in. The flash bytes count it.

[2] libcrc builds its table in RAM at its first call. The adapter's init() makes that call (kinds/crc/adapter_libcrc.c, lc32_init) and bench/main.c calls init() before the timed calls (line 156), so the 256 calls of a scenario find the table built; the building is not measured.

[3] As libcrc crc_32: the table is built by init() (lc16_init) before the timed calls; the building is not measured.

<!-- /table:crc -->

## What the tables show

Each sentence names the rows it rests on; the rows are those of the tables above.

- **The same class from two libraries.** With the cache on, ETL
  `crc32_t256` and crcany `crc32iso_hdlc_byte`, both a CRC-32 table of 256
  in flash, have the same per-byte figure on five boards (nRF5340 DK 10.0,
  Raspberry Pi Pico 2 H 10.0, NUCLEO-G474RE 14.7, NUCLEO-H723ZG 8.0,
  NUCLEO-G0B1RE 15.0); on the SAM D20 Xplained Pro they are 15.3–15.6 and
  14.3–14.6. Their 16-byte figures differ (NUCLEO-G474RE: 257–258 and
  280–281), which is the part of a call that does not grow with the
  message.
- **The same instructions, the table in flash or in RAM.** ETL
  `crc32_t256` and libcrc `crc_32` run the same loop instructions on the
  Cortex-M4, M7 and M33 cores (the [report](../../reports/2026-11-25-crc-first-series.md),
  check 3); libcrc builds its table in RAM. With the cache on, the
  NUCLEO-G474RE gives 14.7 and 10.0 cycles per byte for the two rows, the
  NUCLEO-H723ZG 8.0 and 8.0.
- **The placements, with the cache off.** On the SAM D20 Xplained Pro
  every row of the cache-off tables is one number: the eight placements
  agree. On the NUCLEO-H723ZG, crcany `crc32iso_hdlc_bit` (CRC-32,
  bitwise) costs 41.0–225.0 cycles per byte with the cache off and
  41.0–42.0 with it on: at its best placements the same with the cache off
  as on (the report, check 7).
