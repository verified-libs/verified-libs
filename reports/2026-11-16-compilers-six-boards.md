# Four compilers on all six boards (2026-11-16)

The libraries under test and their adapters built with four compilers, on
all six boards, benchmark `SET=spsc`, `-O2`, code in flash; harness, startup
and link stay the Debian arm-none-eabi-gcc 14.2.1 with newlib-nano in every
case (`firmware/common/compiler.mk`). Earlier only the STM32 boards had
been compared ([2026-11-12](2026-11-12-compilers-stm32.md)).

| `COMPILER=` | Compiler | Image |
|---|---|---|
| `gcc` | Arm GNU Toolchain 14.2.1 (Debian `gcc-arm-none-eabi` 14.2.rel1) | 2026-11-05 |
| `clang` | Ubuntu clang 21.1.8, GNU headers | 2026-11-05 |
| `atfe` | Arm Toolchain for Embedded 23.1.0 (clang 23.1.0) | 2026-11-16 |
| `zephyr-gcc` | Zephyr SDK 1.0.1 `arm-zephyr-eabi-gcc` 14.3.0, its own headers | 2026-11-16 |

24 runs (6 boards x 4 compilers), records in
`~/lab-runs/compilers-20261116/` on the lab host, source commit f1551e6
(the G474's clang and ATfE runs at bd9d795: the first build also made the
CCM SRAM image, which no longer fits with clang code, and stopped; run.sh
now builds only the locations that run; the flash image is the same).
Every run: 0 errors in every library.

## Speed against gcc
Geometric mean over all library configurations of mean cycles relative to
gcc (cache on; 1 B: single-byte push and pop; 64 B: 64-byte block write and
read). Below 1.00 is faster than gcc.

| Board | clang 1 B | clang 64 B | ATfE 1 B | ATfE 64 B | Zephyr-gcc 1 B | Zephyr-gcc 64 B |
|---|---|---|---|---|---|---|
| nRF5340 (M33) | 1.02 | 0.92 | 1.02 | 0.92 | 1.00 | 1.00 |
| G0B1 (M0+) | 1.24 | 1.09 | 1.24 | 1.09 | 1.00 | 1.00 |
| G474 (M4) | 1.05 | 0.96 | 1.05 | 0.96 | 1.00 | 1.00 |
| H723 (M7) | 1.03 | 0.97 | 1.02 | 0.97 | 1.00 | 1.00 |
| SAM D20 (M0+) | 1.21 | 1.08 | 1.20 | 1.08 | 1.00 | 1.00 |
| RP2350 (M33) | 1.02 | 0.92 | 1.02 | 0.92 | 1.00 | 1.00 |

- **Zephyr SDK gcc measures the same as Arm GCC.** The firmware differs
  (other hashes; GCC 14.3 against 14.2, other headers), but with the cache
  on every mean on five boards is within 1 % of gcc's (G0B1: 3 of 804 means
  up to 1.6 %; SAM D20: 37 of 804 up to 7 %). The H723 differs in 259 means
  by up to 174 %, all with the cache off, where the code's place in flash
  decides (placement experiment).
- **ATfE measures like upstream clang.** Its clang 23 is within 1 % of
  Ubuntu clang 21 in these ratios on every board.
- **clang/ATfE against gcc depends on the core.** On the M33, M4 and M7
  single bytes cost 2-5 % more and 64-byte blocks 3-9 % less. On the two
  Cortex-M0+ boards single bytes cost 20-24 % more and blocks 8-9 % more:
  clang lowers every C11 atomic load and store on ARMv6-M to a call to
  `__atomic_load_N` / `__atomic_store_N` (`firmware/common/armv6m_atomic.c`
  here), where gcc inlines LDR/STR with DMB; the 2026-11-12 report shows
  the libraries this hits. ATfE does the same. Per library the spread is
  wide (G474, ATfE single push: DNedic lockfree 0.59, polycratia 1.58; G0B1:
  jnk0le and polycratia about 3.1).

## Check against the page
The gcc runs repeat the benchmark the comparison page shows (e9e9c42) at a
newer commit, with the ST-LINK firmware updated the same day (V2J48 /
V3J17): on five boards all 804 means are within 1 % of the page's records.
On the RP2350 23 of 804 differ by up to 19 %, in a different build of the
firmware: the cache-on differences (pxq blocks, ETL queue_spsc_locked by one
cycle) lie within the range the placement experiment found for them on this
board (pxq block 6.6-9.0 cycles/byte, ETL locked push 62.7-63.7); the
cache-off differences (ETL locked, ece-mohammad, up to 3.7 %) are outside
what that experiment covers (it measures with the cache on).
