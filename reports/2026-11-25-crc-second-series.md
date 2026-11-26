# CRC: the second board series (the boards' CRC hardware, tables in RAM)

The second series of the CRC kind measured two things the first did not. One
is **the boards' CRC hardware, driven by our code**: the STM32 CRC unit on the
NUCLEO-G474RE, NUCLEO-G0B1RE and NUCLEO-H723ZG, and the RP2350's DMA sniffer
on the Pico 2. The other is **the fifteen configurations with a table in
flash, with that table copied to RAM** by the image at start. It was decided
on 2026-11-25 ([`DECISIONS.md`](../DECISIONS.md), "A second CRC series"),
planned and counted in
[`lab/plans/2026-11-25-crc-hw-and-ram-series.md`](../lab/plans/2026-11-25-crc-hw-and-ram-series.md),
and run on 2026-11-25 from 11:45 to 21:58 UTC. Every number below is computed
from the records under [`records/crc`](../records/crc); every record was
rebuilt from its commit and matched (`kinds/crc/bench/crcverify.sh`).

## What was measured

- **18 new configurations** (`kinds/crc/configs.txt`, after "# The second
  series"):
  - `adapter_hw_crc32`, `adapter_hw_crc16` and `adapter_hw_crc8`
    ([`kinds/crc/adapter_hw.c`](../kinds/crc/adapter_hw.c)), built only for
    the boards that have the unit ([`kinds/crc/boards.txt`](../kinds/crc/boards.txt)).
    The RP2350's sniffer has no CRC-8 mode, and the SAM D20's DSU and the
    nRF5340 are left out (the plan says why).
  - Fifteen `*_ram` configurations, one per configuration whose table lies in
    flash. The table's section is renamed from `.rodata.*` to `.data.*` in a
    copy of the library's archive (`kinds/crc/bench/onecrc.py`,
    `ram_archive`), so the image's start-up code copies it to RAM. The build
    checks that every table symbol lies once in RAM
    ([`kinds/crc/ramtables.txt`](../kinds/crc/ramtables.txt), `ram_check`).
- **The same method as the first series**: 8 placements, 2 passes, 24
  scenarios of 256 calls, the reference timed in the same image, the method
  frozen at `crc-method-freeze` except the changes listed in the decision.
- **The 160 images per board of the first series** rebuild byte for byte
  from the second series' tree (`VL_TREE=1` crcverify, 20 of 20 per board),
  so the first series' records stand beside the new ones.

## The series, per board

| Board | Commit | Smoke + series runs | Flash writes | Disagreeing calls | Retries | Records (crcverify MATCH) | Time (UTC) |
|---|---|---|---|---|---|---|---|
| NUCLEO-G474RE | 04a2197 | 32 + 288 | 1 + 3 | 0 | 0 | 18 (2 + 18) | 11:45–12:17 |
| NUCLEO-G0B1RE, table in RAM | 04a2197 | 32 + 288 | 1 + 3 | 0 | 1 + 1 | 15 (15) | 12:19–13:18 |
| SAM D20 Xplained Pro | 04a2197 | 16 + 240 | 1 + 6 | 0 | 2 + 2 | 15 (1 + 15) | 13:19–14:54 |
| NUCLEO-G0B1RE, hardware (rerun) | 40f1958 | 16 + 48 | 1 + 0 | 0 | 1 + 1 | 3 (1 + 3) | 15:02–15:14 |
| Raspberry Pi Pico 2 H | 40f1958 | 48 + 272 | 1 + 1 | 0 | 3 + 3 | 17 (3 + 17) | 16:14–20:01 |
| nRF5340 DK | 40f1958 | 16 + 240 | 1 + 1, and one erase | 0 | 1 + 4 | 15 (1 + 15) | 20:03–21:02 |
| NUCLEO-H723ZG (rerun) | 40f1958 | 16 + 288 | 0 + 1 | 0 | 0 + 14 | 18 (1 + 18) | 21:03–21:58 |

- **Records:** 101 in all.
  - The records of 04a2197 (48) were made before the fix below. Their images
    are byte-identical at 40f1958 (the 1768 images of all six boards
    compared by SHA-256: only the 24 hardware images of the NUCLEO-G0B1RE
    differ).
  - They are taken by the export through the ledger
    [`records/rebuilt.json`](../records/rebuilt.json), with the 120 records
    of the first series.
- **Flash writes:** 23 and one erase, against 21 counted. The two more are
  the two reruns.
- **Pico 2 writes:** the bundles were written in parts of at most 250 units,
  as in the first series.

## The two reruns

**The NUCLEO-G0B1RE's hardware rows (a defect in our adapter).**
- *The first run* (04a2197) gave 25.5 cycles per byte with the cache on.
  That is slower than several tables on the same board (crcany's
  slicing by 4 with its table in RAM: 10.25), with errors 0: the values
  were right, the time was not the unit's.
- *The cause:* the adapter's word loop copies each word with
  `__builtin_memcpy(&w, p, 4)`. On the Cortex-M0+, which has no unaligned
  loads, gcc -O2 could not assume `p` aligned (the loop aligns it first). So
  it called newlib's `memcpy` for every word (`bl memcpy` in the image).
- *The fix:* commit 40f1958 adds `__builtin_assume_aligned(p, 4)`. On the
  M4 the code is the same as before.
- *The rerun:* 2.00 cycles per byte with the cache on.
- *The first run's files* are kept as superseded and make no record.
- *A scan of every image of all six boards* (functions reachable from the
  timed call, looking for library helpers) found no second case in our
  code.

**The NUCLEO-H723ZG (an option bit found set).**
- *What was found:* the board came back from other use with unknown
  software on it. FLASH_OPTSR2_CUR read 0x00000004, that is CPUFREQ_BOOST =
  1; its factory value is 0 (RM0468 Rev 3, table 18 "Option byte
  organization"). The other option registers were at their factory values.
  The first series recorded no option bytes, so it is not known whether
  the bit was set then.
- *The decision:* the owner decided that measurements made with wrong
  settings are made again.
- *Setting it back:* the bit was set back to 0 through the probe (RM0468
  §4.4.3: unlock, OPTSR2_PRG = 0, OPTSTART, OPT_BUSY clear, OPTLOCK). Every
  _CUR register was read before, after, and after a power cycle; RDP was
  never written.
- *The rerun with the bit at 0:* all 864 means (18 configurations, 24
  scenarios, results and baseline) are identical to the run with the bit
  at 1.
- *What follows:* at the images' 64 MHz the bit changes no number. The
  run with the bit set is kept as superseded and makes no record.

## The boards that came back

The NUCLEO-H723ZG, the Pico 2 and the nRF5340 DK had unknown software put
on them while away. The series takes as ours only what it wrote. The
first series' bundles on these three boards are treated as gone, which
matters only for a rerun of the first series.

- **nRF5340 DK: locked, then erased.**
  - *What happened:* the first write found the application core's debug
    port locked. probe-rs offered to erase the chip and was not allowed to.
    The port stayed locked after a power cycle.
  - *Why it can lock:* the port opens only when UICR.APPROTECT is
    Unprotected and firmware writes CTRL-AP.APPROTECT.DISABLE after each
    reset (nRF5340 Product Specification v1.6, §8.2 "Access port
    protection"). Our boot stub runs no image after a power-on, so nothing
    opens it. Whether that or the other software locked this board is not
    known.
  - *The erase:* one CTRL-AP ERASEALL of the application core
    (`probe-rs ... --allow-erase-all`, one command). probe-rs then wrote
    both UICR words to 0x50FA50FA itself.
  - *Then:* bundle 27 was written with no reset before it, and the first
    image opened the port. UICR and the results block were read back
    after the smoke.
  - *Not touched:* the network core. It is held in Force-OFF after every
    application-core reset and our firmware never releases it (§4.10.7), so
    it cannot run during a measurement.
- **NUCLEO-H723ZG:**
  - the option bit above;
  - the boot region read back as the build's `boot.bin`.
- **Pico 2: the OTP read back raw.**
  - The critical flags, the boot configuration page and the boot keys are
    all unprogrammed (0).
  - Lock words are set only for pages 0, 1, 2, 62 and 63, the defaults of
    a blank device (RP2350 datasheet RP-008373-DS-2, §13.4 and §13.5).

## The baseline against the first series

The baseline (the bitwise reference, timed in every image) is the same
code in both series. Its means in this series are identical to the first
series' on every board, in all 72 scenarios (24 per CRC, three CRCs),
to the third decimal. This holds also on the three boards that came back.

## Retries

A run whose image has not finished at the first look is repeated with
twice the wait (`kinds/crc/bench/run-crc.py`). The wait is kept per
configuration, so a retry comes at the first image of a configuration that
a run reaches.

- Every retry of this series is of that kind: at p0, or at p4 where the
  H723 rerun reached a configuration first in bundle 28.
- The H723's two series runs today had 14 each, 10 after 5 s and 4 after
  10 s; the first series had 18 in 320 runs.
- The logs show which images were retried and after which wait. They do
  not show why one configuration needs more than 5 s and another does not;
  that is not explained here.

## The hardware rows

What a hardware row is:
- The board's CRC unit, driven by our code
  ([`kinds/crc/adapter_hw.c`](../kinds/crc/adapter_hw.c)); not a library.
- **The STM32 unit:** the clock is enabled once, then CR, POL and INIT are
  set. The message is fed as bytes up to a word boundary, then words with
  their bytes swapped, then the last bytes. For CRC-32 the unit has no
  final XOR, so our code XORs the result with 0xFFFFFFFF.
- **The RP2350:** a DMA transfer of the message to a dummy byte, with the
  sniffer computing CRC-32 or CRC-16 on the way.

Cycles, offset 0 unless named; each the range over the eight placements,
first pass:

| Board | Unit | CRC | 16 B on, offset 0 / 1 | per byte on | 16 B off, offset 0 / 1 | per byte off |
|---|---|---|---|---|---|---|
| Raspberry Pi Pico 2 H | DMA sniffer | CRC-32/ISO-HDLC | 50–51 / 50–51 | 1.25 | 1081 / 1081 | 1.18 |
| Raspberry Pi Pico 2 H | DMA sniffer | CRC-16/IBM-3740 | 51–52 / 51–52 | 1.25 | 764–905 / 764–905 | 1.38 |
| NUCLEO-G474RE | CRC unit | CRC-32/ISO-HDLC | 96 / 118 | 2.25 | 184–188 / 221–227 | 4.25–4.50 |
| NUCLEO-G474RE | CRC unit | CRC-16/IBM-3740 | 96 / 118 | 2.25 | 184–188 / 221–227 | 4.25–4.50 |
| NUCLEO-G474RE | CRC unit | CRC-8/SMBUS | 96 / 118 | 2.25 | 184–188 / 221–227 | 4.25–4.50 |
| NUCLEO-H723ZG | CRC unit | CRC-32/ISO-HDLC | 55 / 71–72 | 1.50 | 130–218 / 146–289 | 1.50–6.50 |
| NUCLEO-H723ZG | CRC unit | CRC-16/IBM-3740 | 55 / 71–72 | 1.50 | 130–218 / 146–289 | 1.50–6.50 |
| NUCLEO-H723ZG | CRC unit | CRC-8/SMBUS | 55 / 71–72 | 1.50 | 130–218 / 146–289 | 1.50–6.50 |
| NUCLEO-G0B1RE | CRC unit | CRC-32/ISO-HDLC | 128 / 167–168 | 2.00 | 156–158 / 211–213 | 3.00–3.50 |
| NUCLEO-G0B1RE | CRC unit | CRC-16/IBM-3740 | 129 / 168–169 | 2.00 | 157–159 / 212–214 | 3.00–3.50 |
| NUCLEO-G0B1RE | CRC unit | CRC-8/SMBUS | 128–131 / 167–171 | 2.00 | 157–159 / 212–214 | 3.00–3.50 |

What the rows show, as facts of these runs:

- With the cache on, the three CRCs cost the same on each STM32 board, at
  2.25 (G474), 2.00 (G0B1) and 1.50 (H723) cycles per byte. The Pico 2's
  sniffer costs 1.25.
- **Against the lowest library on the same board and CRC, cache on, per
  byte:**
  - Pico 2 CRC-32: 1.25 against 5.50 (crcany word, table in RAM).
  - G474 CRC-32: 2.25 against 6.00 (the same).
  - H723 CRC-32: 1.50 against 2.75 (crcany word).
  - G0B1 CRC-32: 2.00 against 10.00–10.50 (crcany word, table in RAM).
- **With the cache off, on the H723,** the unit's per-byte range
  (1.50–6.50) overlaps the lowest CRC-8 library's (AceCRC with its table in
  RAM, 5.00–25.00). By the overlap rule the two are not told apart there.
- **The Pico 2's cache-off rows** cost 764–1081 cycles for 16 bytes, but
  1.18–1.38 per byte. Where the fixed cost goes was not measured.

## Table in RAM against table in flash

For each of the fifteen configurations, per byte at offset 0, the range
over the eight placements (first pass). Under the owner's overlap rule
(DECISIONS 2026-11-25), a difference is a difference only where the ranges
do not overlap. "Same" means the ranges overlap. Three decimals are shown
where two would hide a difference that the unrounded ranges show.

### nRF5340 DK

| Configuration | Class | per byte, cache on: flash / RAM | | per byte, cache off: flash / RAM | |
|---|---|---|---|---|---|
| etl crc32_t256 (C++) | table of 256 | 10.0000 / 10.0000 | RAM lower | 36.00–43.00 / 22.00–30.00 | RAM lower |
| crcany crc32iso_hdlc_byte (C) | table of 256 | 10.0000 / 10.0000 | RAM lower | 36.00–43.00 / 22.00–30.00 | RAM lower |
| crc (Rust) Table<1> | table of 256 | 8.00 / 7.25 | RAM lower | 24.50–30.75 / 15.25–16.50 | RAM lower |
| etl crc32_t16 (C++) | table of 16 | 17.00 / 16.00 | RAM lower | 64.00–70.00 / 35.00–41.00 | RAM lower |
| zephyr crc32_ieee (C) | table of 16 | 17.00 / 17.00 | same | 57.00–71.00 / 35.00–42.00 | RAM lower |
| crcany crc32iso_hdlc_word (C) | slicing by 4 | 6.04–6.05 / 5.50 | RAM lower | 24.50–26.25 / 13.00–14.00 | RAM lower |
| zlib crc32 (C) | other: "braided" words | 8.63–8.65 / 7.98 | RAM lower | 26.72–29.19 / 15.71–16.48 | RAM lower |
| etl crc16_ccitt_t256 (C++) | table of 256 | 11.00 / 11.00 | same | 37.00–45.00 / 24.00–30.00 | RAM lower |
| crcany crc16ibm_3740_byte (C) | table of 256 | 10.00 / 10.00 | same | 38.00–45.00 / 22.00–31.00 | RAM lower |
| etl crc16_ccitt_t16 (C++) | table of 16 | 17.00 / 17.00 | same | 65.00–72.00 / 41.00–44.00 | RAM lower |
| etl crc8_ccitt_t256 (C++) | table of 256 | 7.00 / 6.00 | RAM lower | 21.00–27.00 / 6.00–19.00 | RAM lower |
| crcany crc8smbus_byte (C) | table of 256 | 8.00 / 7.00 | RAM lower | 27.00–29.00 / 19.00–21.00 | RAM lower |
| acecrc crc8_byte (C++) | table of 256 | 7.00 / 6.00 | RAM lower | 21.00–27.00 / 6.00–19.00 | RAM lower |
| etl crc8_ccitt_t16 (C++) | table of 16 | 17.00 / 17.00 | same | 57.00–69.00 / 33.00–43.00 | RAM lower |
| zephyr crc8_ccitt (C) | table of 16 | 16.00 / 16.00 | same | 54.00–69.00 / 33.00–41.00 | RAM lower |

### Raspberry Pi Pico 2 H

| Configuration | Class | per byte, cache on: flash / RAM | | per byte, cache off: flash / RAM | |
|---|---|---|---|---|---|
| etl crc32_t256 (C++) | table of 256 | 10.00 / 10.00 | same | 424.95–425.48 / 259.00 | RAM lower |
| crcany crc32iso_hdlc_byte (C) | table of 256 | 10.00 / 10.00 | same | 425.03–425.51 / 259.00 | RAM lower |
| crc (Rust) Table<1> | table of 256 | 7.37–7.38 / 7.25 | RAM lower | 318.45–318.49 / 152.50 | RAM lower |
| etl crc32_t16 (C++) | table of 16 | 16.48–16.52 / 16.00 | RAM lower | 725.46–725.51 / 394.00 | RAM lower |
| zephyr crc32_ieee (C) | table of 16 | 17.00 / 17.00 | same | 725.96–725.98 / 394.00 | RAM lower |
| crcany crc32iso_hdlc_word (C) | slicing by 4 | 5.69–5.70 / 5.50 | RAM lower | 293.30–293.72 / 132.25 | RAM lower |
| zlib crc32 (C) | other: "braided" words | 6.69 / 6.56 | RAM lower | 321.84–326.74 / 163.31 | RAM lower |
| etl crc16_ccitt_t256 (C++) | table of 256 | 11.00 / 11.00 | same | 439.51–439.99 / 286.00 | RAM lower |
| crcany crc16ibm_3740_byte (C) | table of 256 | 10.00 / 10.00 | same | 439.98–440.51 / 286.00 | RAM lower |
| etl crc16_ccitt_t16 (C++) | table of 16 | 17.00 / 17.00 | same | 729.03–729.99 / 421.00 | RAM lower |
| etl crc8_ccitt_t256 (C++) | table of 256 | 6.50 / 6.00 | RAM lower | 256.00–290.16 / 178.00 | RAM lower |
| crcany crc8smbus_byte (C) | table of 256 | 7.50 / 7.00 | RAM lower | 317.15–353.00 / 205.00 | RAM lower |
| acecrc crc8_byte (C++) | table of 256 | 6.50 / 6.00 | RAM lower | 256.00–290.16 / 178.00 | RAM lower |
| etl crc8_ccitt_t16 (C++) | table of 16 | 17.00 / 17.00 | same | 662.97–663.01 / 367.00 | RAM lower |
| zephyr crc8_ccitt (C) | table of 16 | 16.00 / 16.00 | same | 636.00–636.02 / 340.00 | RAM lower |

### NUCLEO-G474RE

| Configuration | Class | per byte, cache on: flash / RAM | | per byte, cache off: flash / RAM | |
|---|---|---|---|---|---|
| etl crc32_t256 (C++) | table of 256 | 14.70–14.72 / 11.00 | RAM lower | 26.97–28.95 / 23.00–24.00 | RAM lower |
| crcany crc32iso_hdlc_byte (C) | table of 256 | 14.70–14.72 / 11.00 | RAM lower | 26.96–28.96 / 23.00–24.00 | RAM lower |
| crc (Rust) Table<1> | table of 256 | 13.20–13.22 / 9.00 | RAM lower | 19.46–22.19 / 15.25–16.00 | RAM lower |
| etl crc32_t16 (C++) | table of 16 | 17.00 / 17.00 | same | 45.24–46.40 / 35.00–40.00 | RAM lower |
| zephyr crc32_ieee (C) | table of 16 | 17.00 / 17.00 | same | 45.72–47.01 / 37.00–40.00 | RAM lower |
| crcany crc32iso_hdlc_word (C) | slicing by 4 | 9.94–9.95 / 6.00 | RAM lower | 18.00–19.75 / 13.25–14.50 | RAM lower |
| zlib crc32 (C) | other: "braided" words | 12.11–12.16 / 8.56–8.58 | RAM lower | 20.45–21.28 / 15.73–16.07 | RAM lower |
| etl crc16_ccitt_t256 (C++) | table of 256 | 15.23–15.30 / 12.00 | RAM lower | 30.89–32.91 / 25.00–28.00 | RAM lower |
| crcany crc16ibm_3740_byte (C) | table of 256 | 14.23–14.30 / 11.00 | RAM lower | 27.91–33.89 / 23.00–28.00 | same |
| etl crc16_ccitt_t16 (C++) | table of 16 | 19.00 / 19.00 | same | 48.71–49.47 / 41.00–42.00 | RAM lower |
| etl crc8_ccitt_t256 (C++) | table of 256 | 8.00–9.45 / 8.00 | RAM lower | 20.81–21.84 / 16.00–17.00 | RAM lower |
| crcany crc8smbus_byte (C) | table of 256 | 8.00–8.98 / 8.00 | RAM lower | 20.88–21.84 / 17.00–18.00 | RAM lower |
| acecrc crc8_byte (C++) | table of 256 | 8.00–9.96 / 8.00 | RAM lower | 20.81–21.84 / 16.00–17.00 | RAM lower |
| etl crc8_ccitt_t16 (C++) | table of 16 | 19.00 / 19.00 | same | 40.92–41.28 / 35.00–36.00 | RAM lower |
| zephyr crc8_ccitt (C) | table of 16 | 18.00 / 18.00 | same | 35.28–38.95 / 29.00–34.00 | RAM lower |

### NUCLEO-H723ZG

| Configuration | Class | per byte, cache on: flash / RAM | | per byte, cache off: flash / RAM | |
|---|---|---|---|---|---|
| etl crc32_t256 (C++) | table of 256 | 8.00 / 8.00 | same | 18.77–34.00 / 8.00–27.00 | same |
| crcany crc32iso_hdlc_byte (C) | table of 256 | 8.00 / 8.00 | same | 18.77–34.00 / 8.00–27.00 | same |
| crc (Rust) Table<1> | table of 256 | 6.75 / 6.75 | same | 19.20–23.70 / 10.25–13.25 | RAM lower |
| etl crc32_t16 (C++) | table of 16 | 14.00 / 14.00 | same | 40.00–54.00 / 25.00–39.00 | RAM lower |
| zephyr crc32_ieee (C) | table of 16 | 14.00 / 14.00 | same | 39.99–54.00 / 26.00–39.00 | RAM lower |
| crcany crc32iso_hdlc_word (C) | slicing by 4 | 2.75 / 2.75 | same | 18.37–19.75 / 7.25–10.50 | RAM lower |
| zlib crc32 (C) | other: "braided" words | 4.93 / 4.93 | same | 20.32–22.32 / 10.00–12.07 | RAM lower |
| etl crc16_ccitt_t256 (C++) | table of 256 | 7.00 / 7.00 | same | 17.53–34.00 / 7.00–27.00 | same |
| crcany crc16ibm_3740_byte (C) | table of 256 | 7.00 / 7.00 | same | 17.58–34.00 / 7.00–27.00 | same |
| etl crc16_ccitt_t16 (C++) | table of 16 | 14.00 / 14.00 | same | 40.00–54.00 / 27.00–40.00 | same |
| etl crc8_ccitt_t256 (C++) | table of 256 | 5.00 / 5.00 | same | 15.04–34.00 / 5.00–25.00 | same |
| crcany crc8smbus_byte (C) | table of 256 | 5.00 / 5.00 | same | 15.08–34.00 / 5.00–26.00 | same |
| acecrc crc8_byte (C++) | table of 256 | 5.00 / 5.00 | same | 15.04–34.00 / 5.00–25.00 | same |
| etl crc8_ccitt_t16 (C++) | table of 16 | 14.00 / 14.00 | same | 40.00–54.00 / 26.00–39.00 | RAM lower |
| zephyr crc8_ccitt (C) | table of 16 | 13.00 / 13.00 | same | 40.00–54.00 / 26.00–39.00 | RAM lower |

### NUCLEO-G0B1RE

| Configuration | Class | per byte, cache on: flash / RAM | | per byte, cache off: flash / RAM | |
|---|---|---|---|---|---|
| etl crc32_t256 (C++) | table of 256 | 15.00 / 13.00 | RAM lower | 21.00–25.00 / 19.00–21.00 | same |
| crcany crc32iso_hdlc_byte (C) | table of 256 | 15.00 / 13.00 | RAM lower | 21.00–25.00 / 19.00–21.00 | same |
| crc (Rust) Table<1> | table of 256 | 13.75–14.25 / 11.00–11.25 | RAM lower | 17.75 / 14.75 | RAM lower |
| etl crc32_t16 (C++) | table of 16 | 27.00–30.00 / 23.00–24.00 | RAM lower | 37.00 / 31.00 | RAM lower |
| zephyr crc32_ieee (C) | table of 16 | 28.00–33.00 / 23.00–27.00 | RAM lower | 37.00–39.00 / 31.00–33.00 | RAM lower |
| crcany crc32iso_hdlc_word (C) | slicing by 4 | 12.50–13.50 / 10.00–10.50 | RAM lower | 16.50–17.00 / 14.00 | RAM lower |
| zlib crc32 (C) | other: "braided" words | 16.13–16.94 / 13.63–14.14 | RAM lower | 21.48–22.38 / 18.78–19.08 | RAM lower |
| etl crc16_ccitt_t256 (C++) | table of 256 | 16.00 / 14.00 | RAM lower | 24.00–26.00 / 22.00 | RAM lower |
| crcany crc16ibm_3740_byte (C) | table of 256 | 16.00 / 14.00 | RAM lower | 24.00–26.00 / 22.00 | RAM lower |
| etl crc16_ccitt_t16 (C++) | table of 16 | 32.00 / 26.00–28.00 | RAM lower | 40.00–44.00 / 36.00 | RAM lower |
| etl crc8_ccitt_t256 (C++) | table of 256 | 11.00 / 9.00 | RAM lower | 17.00 / 13.00–15.00 | RAM lower |
| crcany crc8smbus_byte (C) | table of 256 | 11.00 / 9.00 | RAM lower | 17.00 / 13.00–15.00 | RAM lower |
| acecrc crc8_byte (C++) | table of 256 | 11.00 / 9.00 | RAM lower | 17.00 / 13.00–15.00 | RAM lower |
| etl crc8_ccitt_t16 (C++) | table of 16 | 27.00–31.00 / 23.00–24.00 | RAM lower | 35.00–39.00 / 31.00 | RAM lower |
| zephyr crc8_ccitt (C) | table of 16 | 26.00–27.00 / 21.00–23.00 | RAM lower | 33.00–37.00 / 29.00 | RAM lower |

### SAM D20 Xplained Pro

| Configuration | Class | per byte, cache on: flash / RAM | | per byte, cache off: flash / RAM | |
|---|---|---|---|---|---|
| etl crc32_t256 (C++) | table of 256 | 15.32–15.59 / 13.00 | RAM lower | 20.00 / 19.00 | RAM lower |
| crcany crc32iso_hdlc_byte (C) | table of 256 | 14.31–14.58 / 13.00 | RAM lower | 20.00 / 19.00 | RAM lower |
| crc (Rust) Table<1> | table of 256 | 12.66–12.87 / 10.75–11.00 | RAM lower | 15.50 / 14.50 | RAM lower |
| etl crc32_t16 (C++) | table of 16 | 23.38 / 21.00 | RAM lower | 32.00 / 30.00 | RAM lower |
| zephyr crc32_ieee (C) | table of 16 | 24.51–25.64 / 21.00 | RAM lower | 33.00 / 31.00 | RAM lower |
| crcany crc32iso_hdlc_word (C) | slicing by 4 | 11.91–12.12 / 10.00–10.25 | RAM lower | 14.75 / 13.75 | RAM lower |
| zlib crc32 (C) | other: "braided" words | 17.56–17.70 / 15.75–15.89 | RAM lower | 19.77 / 18.77 | RAM lower |
| etl crc16_ccitt_t256 (C++) | table of 256 | 16.49–16.50 / 14.00 | RAM lower | 22.00 / 21.00 | RAM lower |
| crcany crc16ibm_3740_byte (C) | table of 256 | 15.56 / 14.00 | RAM lower | 22.00 / 21.00 | RAM lower |
| etl crc16_ccitt_t16 (C++) | table of 16 | 26.65–27.80 / 24.00 | RAM lower | 37.00 / 35.00 | RAM lower |
| etl crc8_ccitt_t256 (C++) | table of 256 | 10.87–11.12 / 9.00 | RAM lower | 14.00 / 13.00 | RAM lower |
| crcany crc8smbus_byte (C) | table of 256 | 10.86–11.14 / 9.00 | RAM lower | 14.00 / 13.00 | RAM lower |
| acecrc crc8_byte (C++) | table of 256 | 10.89–11.13 / 9.00 | RAM lower | 14.00 / 13.00 | RAM lower |
| etl crc8_ccitt_t16 (C++) | table of 16 | 24.94–25.10 / 21.00 | RAM lower | 32.00 / 30.00 | RAM lower |
| zephyr crc8_ccitt (C) | table of 16 | 22.74–23.12 / 19.00 | RAM lower | 30.00 / 28.00 | RAM lower |

What the tables show, as facts of these runs:

- **With the cache off,** the table in RAM is lower on 79 of the 90
  board-and-configuration pairs. The other 11 are the same (overlapping
  ranges): 8 on the H723, whose cache-off ranges are wide, 2 on the G0B1
  and 1 on the G474.
- **With the cache on,** it differs by board:
  - NUCLEO-G0B1RE and SAM D20: lower in all 15.
  - NUCLEO-G474RE: lower in 10, the same in 5 (the tables of 16).
  - nRF5340: lower in 9, the same in 6.
  - Pico 2: lower in 7, the same in 8.
  - NUCLEO-H723ZG: the same in all 15.
- **No configuration is higher with its table in RAM,** on any board, with
  the cache on or off.
- **Bytes:** a table copied to RAM still costs its bytes in flash (the
  initial values the start-up code copies) and the same number of bytes
  of RAM. The code is the library's own, unchanged.

## zlib's division on the Cortex-M0+ boards

zlib's `crc32_z` divides once per call, before its braided loop:
`blks = len / (N * W)` (`crc32.c` line 653, zlib v1.4). On the Cortex-M0+
(NUCLEO-G0B1RE, SAM D20), which has no divide instruction, gcc calls
libgcc's `__aeabi_uidivmod` / `__udivsi3` for it. This holds in both zlib
configurations, in flash and in RAM.

So zlib's rows on those two boards include one library division per
call. That is what a zlib user on these cores gets, not a fault of the
method. The scan above found no other helper call in any timed function.

## What is not explained

- Why a configuration needs more than the first wait of 5 s at its first
  image (the retries above).
- **The NUCLEO-H723ZG with the cache off:**
  - its per-byte ranges are wide for the tables in RAM as for those in
    flash (e.g. ETL's table of 256 for CRC-8: 15.04–34.00 in flash, 5.00–25.00 in
    RAM);
  - with the cache on, the RAM and flash rows are the same.
  - The board's data cache and its 7 flash wait states at 64 MHz (see the
    method) fit both, but neither was measured.
- **The Pico 2's hardware rows** with the cache off: the fixed cost of a
  16-byte call (764–1081 cycles) against 1.18–1.38 per byte.
- **The G474's tables of 16:** they are the same in RAM and flash with the
  cache on, while its tables of 256 are lower in RAM.

## Decided by the owner (2026-11-26)

1. **The reproduce page** says that on the nRF5340 DK our boot stub does
   not open the debug port, so after any power-on the board stays locked
   (nRF5340 PS v1.6, §8.2), and how we recovered it with probe-rs 0.32.0
   ([`reproduce.md`](../site/content/reproduce.md), "Run it on your own
   board").
2. **For the next method version**, on the list
   [`lab/plans/2026-11-26-next-method-version.md`](../lab/plans/2026-11-26-next-method-version.md):
   - the nRF5340 boot stub copies UICR into CTRL-AP at every boot, so a
     power-on leaves the port open;
   - the option registers of every board are read and recorded with each
     series.
3. **The board's CRC unit on the pages** is a row of the same table as the
   libraries, labelled, and scored like any row (DECISIONS.md, the
   2026-11-25 entry's change of 2026-11-26).
