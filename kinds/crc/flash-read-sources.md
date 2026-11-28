# CRC kind: how each board reads its flash, from the vendors' documents

2026-11-24. Sources for the section "What the placements show" of the
kind's [method page](../../site/content/method-crc.md), as of the first CRC
series (the NUCLEO-H723ZG then ran at 64 MHz; since method version 3 it runs
at 520 MHz, see the method page). Facts and quotes only. It extends
[`reports/2026-11-25-crc-first-series.md`](../../reports/2026-11-25-crc-first-series.md),
"What "cache on" covers for a table read from flash", which is not
repeated here. "Our setting" is what `firmware/common/<board>/board.h`
does; the quotes are word for word.

## Table

| Board, our clock | Flash read width; prefetch | What `board_cache(1)` turns on; line size | Wait states at our clock |
|---|---|---|---|
| NUCLEO-G474RE, 170 MHz | 64 bits in dual bank mode, 128 bits in single bank mode (the option bit DBANK; ST's production value is dual bank; the board's option bytes were not read). Prefetch on the instruction bus (ICode) only | `FLASH_ACR` ICEN, DCEN, PRFTEN: instruction cache 32 lines, data cache 8 lines, each line "4 x 64" bits (32 bytes) in dual bank mode; prefetch | 4 (range 1 boost mode, 136 to 170 MHz); our setting 4 |
| NUCLEO-G0B1RE, 64 MHz | 64 bits ("72-bit wide data read (64 bits plus 8 ECC bits)"); a prefetch buffer for instructions on the CPU S-bus | `FLASH_ACR` ICEN, PRFTEN: an instruction cache of two lines of 64 bits (8-byte lines, 16 bytes); "No data cache is available on Cortex-M0+"; prefetch | 2 (range 1, up to 64 MHz); our setting 2 |
| NUCLEO-H723ZG, 64 MHz | 256-bit flash word; reads of the same flash word come from a 256-bit read buffer; 64-bit AXI bus to the core. The reference manual names no prefetch | The Cortex-M7 L1 caches (`SCB_CCR` IC, DC): 32-byte lines, instruction cache two-way, data cache four-way | 7: the power-on default, which our 64 MHz build keeps (RM0468's table allows 0 or 1 at 64 MHz, by voltage range) |
| nRF5340 DK, 64 MHz | Not said in the product specification; it names no prefetch | The application core's CACHE (`ENABLE`): two-way, "128-bit cache line" (16 bytes), instruction and data accesses to flash | No setting; the specification gives "CPU wait states, running CoreMark at 64 MHz from flash", typically 5 with the cache disabled and 6 with it enabled (a CoreMark figure, not a flash latency) |
| SAM D20 Xplained Pro, 48 MHz | 32-bit AHB interface to the NVM. The data sheet names no prefetch | The NVM controller's cache (`CTRLB.CACHEDIS` cleared): "direct-mapped"; it does not say whether data reads are cached, nor the line size | 1 (2.7 V to 3.63 V, up to 48 MHz); our setting 1. `CTRLB.READMODE` is not set by us |
| Raspberry Pi Pico 2, 150 MHz | External QSPI flash through the QMI: "64-bit accesses for cache line fills"; QSPI clock 50 MHz (our `board.h`: CLKDIV 3). The data sheet names no prefetch in the XIP path | The XIP cache (`XIP_CTRL` EN_SECURE, EN_NONSECURE): 16 kB, two-way, "1 cycle hit", lines of 8 bytes | Not a wait-state setting: a miss is a QSPI transfer |

## Quotes

### NUCLEO-G474RE: RM0440 Rev 9

- 3.2 "FLASH main features": "Flash memory read operations with two data
  width modes supported: – Single bank mode DBANK = 0: read access of 128
  bits – Dual bank mode DBANK = 1: read access of 64 bits"; "Prefetch on
  ICODE"; "Instruction cache: 32 cache lines of 4 x 64 or 2 x 128 bits on
  ICode (1 KB RAM)"; "Data cache: 8 cache lines of 4 x 64 bits or 2 x 128
  on DCode (256B RAM)".
- 3.3.3 "Read access latency", Table 9: "4 WS (5 CPU cycles) ≤ 170"
  (VCORE Range 1 boost mode).
- 3.3.4 "Adaptive real-time memory accelerator (ART Accelerator)",
  "Instruction prefetch": "When in dual bank mode (DBANK option bit is
  set), each flash memory read operation provides 64 bits from either two
  instructions of 32 bits or four instructions of 16 bits depending on the
  launched program. This 64-bit current instruction line is saved in a
  current buffer, and in the case of sequential code, at least two CPU
  cycles are needed to execute the previous read instruction line." and
  "Prefetch on the ICode bus can be used to read the next sequential
  instruction line from the flash memory while the current instruction
  line is being requested by the CPU."
- 3.4.1 "Option bytes description", user and read protection option
  bytes: "ST production value: 0xFFEF F8AA"; "Bit 22 DBANK: 0: Single bank
  mode with 128 bits data read width 1: Dual bank mode with 64 bits data"
  (the same bit in 3.7.8 "Flash option register (FLASH_OPTR)"). Bit 22 of
  0xFFEFF8AA is 1.

### NUCLEO-G0B1RE: RM0444 Rev 6

- 3.2 "FLASH main features": "72-bit wide data read (64 bits plus 8 ECC
  bits)"; "Prefetch buffer"; "CPU instruction cache: two cache lines of 64
  bits (16 bytes RAM)".
- 3.3.4 "FLASH read access latency", Table 13: "2 WS (3 HCLK cycles) ≤ 64"
  (VCORE Range 1). "After power reset, the HCLK clock frequency is 16 MHz
  in Range 1 and 0 wait state (WS) is configured in the FLASH_ACR
  register."
- 3.3.5 "FLASH memory acceleration", "Instruction prefetch": "Each flash
  memory read operation provides 64 bits from either two instructions of 32
  bits or four instructions of 16 bits according to the program launched.
  This 64-bits current instruction line is saved in a current buffer." and
  "Prefetch on the CPU S-bus can be used to read the next sequential
  instruction line from the flash memory while the current instruction
  line is being requested by the CPU." "Cache memory": "To limit the time
  lost due to jumps, it is possible to retain two cache lines of 64 bits
  (16 bytes) in the instruction cache memory." and "No data cache is
  available on Cortex®-M0+."
- 3.3.5, "Caution": "In rare cases, the instruction prefetch may fail upon
  transiting across flash memory banks." The bank boundary of the 512 KB
  part is 0x0804 0000 (3.3.2, Table 12); the CRC images of the G0B1 lie
  from 0x08001000 to 0x0807d000, and none of them spans the boundary
  (checked on the records of the series).

### nRF5340 DK: nRF5340 Product Specification v1.6 (4406_640, 2025-02-12)

- 5.4.1 "CACHE — Instruction/data cache": "The cache is two-way set
  associative with a least recently used (LRU) replacement policy. Both
  instruction and data accesses towards flash memory or XIP code regions
  are cached." and "128-bit cache line".
- 5.2 "CPU": "Executing code from internal or external flash will have a
  wait state penalty. The instruction cache can be enabled to minimize
  flash wait states when fetching instructions."
- 5.2.2.1 "CPU performance": "WFLASH64 CPU wait states, running CoreMark at
  64 MHz from flash, cache disabled ... 5" and "WFLASHCACHE64 CPU wait
  states, running CoreMark at 64 MHz from flash, cache enabled ... 6"
  (typical values; at 128 MHz 4 and 5).
- Not said: the width of a flash read, and any prefetch.

### NUCLEO-H723ZG: RM0468 Rev 3, DS STM32H723; Arm DDI 0489F

- RM0468 4.2 "FLASH main features": "Flash memory read operations
  supporting multiple length (64 bits, 32bits, 16bits or one byte)";
  "one error detection/correction or two error detections per 256-bit
  Flash word using 10 ECC bits".
- RM0468 4.3.8 "FLASH read operations": "The read commands are associated
  with a 256-bit read data buffer." and "If several consecutive read
  accesses request data that belong to the same Flash data word (256
  bits), the data are read directly from the current data read buffer,
  without triggering additional Flash read operations." Figure 10 shows a
  "64-bit AXI bus" and a "256-bit" memory interface.
- RM0468 4.3.8, "Adjusting system frequency": "After power-on, a default 7
  wait-state latency is specified in FLASH_ACR register, in order to
  accommodate AXI interface clock frequencies with a safety margin (see
  Table 16)." Table 16: 0 WS up to 35, 50, 67 or 70 MHz (VOS3, VOS2, VOS1,
  VOS0), 1 WS above.
- DS STM32H723: "Harvard architecture with L1 caches (32 Kbytes of I-cache
  and 32 Kbytes of D-cache)".
- Arm Cortex-M7 Processor Technical Reference Manual, DDI 0489F (r1p2),
  5.9 "L1 caches": "The data cache is four-way set-associative, the
  instruction cache is two-way set-associative. Both caches use a
  line-length of 32-bytes."

### SAM D20 Xplained Pro: SAM D20 Family Data Sheet DS60001504K

- 20.2 "Features": "32-bit AHB interface for reads and writes";
  "Programmable wait states for read optimization"; "Direct-mapped cache".
- 20.6.7 "Cache": "The NVM Controller cache reduces the device power
  consumption and improves system performance when wait states are
  required. Only the NVM main array address space is cached. It is a
  direct-mapped cache that implements. The NVM Controller cache can be
  enabled by writing a '0' to the Cache Disable bit in the Control B
  register (CTRLB.CACHEDIS)." (The third sentence ends so in the data
  sheet.)
- 20.8.2 CTRLB, "Bits 17:16 – READMODE[1:0]": "0x0 NO_MISS_PENALTY The NVM
  Controller (cache system) does not insert wait states on a cache miss.
  Gives the best system performance." "0x1 LOW_POWER ... inserts a wait
  state each time there is a cache miss." "0x2 DETERMINISTIC The cache
  system ensures that a cache hit or miss takes the same amount of time,
  determined by the number of programmed Flash wait states."
- 32.11 "NVM Characteristics", Table 32-37 "Maximum Operating Frequency":
  2.7V to 3.63V, 0 wait states up to 24 MHz, 1 up to 48 MHz.
- Not said in the data sheet: the cache's line size, and whether data
  reads (a table) are cached as well as instruction fetches.

### Raspberry Pi Pico 2: RP2350 Datasheet, build-version d126e9e-clean, build-date 2025-07-29

- 4.4 "External flash and PSRAM (XIP)": "A 16 kB on-chip cache retains the
  values of recent reads and writes. ... The cache is physically
  structured as two 8 kB banks, interleaving odd and even cache lines of
  8-byte granularity over the two banks."
- 4.4.1 "XIP cache": "The cache is 16 kB, two-way set-associative, 1 cycle
  hit." and "You can disable cache lookup separately for Secure and
  Non-secure accesses via the CTRL.EN_SECURE and CTRL.EN_NONSECURE
  register bits."
- 4.4.2 "QSPI Memory Interface (QMI)": "8/16/32-bit accesses for uncached
  accesses, and 64-bit accesses for cache line fills"; "Automatic chaining
  of sequentially addressed accesses into a single QSPI transfer".

