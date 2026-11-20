# Five C libraries' memcpy on all six boards (2026-11-17)

The bench firmware uses four C library functions, `memcpy`, `memmove`,
`memset` and `memcmp` (its link map); every earlier result linked them from
newlib-nano. `LIBC=` (`firmware/common/libc.mk`, commit ced1c9f) links those
four from another C library for the board's core, ahead of newlib-nano;
harness, libraries and compiler (Arm GCC 14.2.1, `-O2`) stay the same.

| `LIBC=` | Library | Build |
|---|---|---|
| `newlib-nano` | Debian arm-none-eabi newlib-nano (all earlier results) | |
| `newlib` | Debian arm-none-eabi full newlib | |
| `picolibc` | Zephyr SDK 1.0.1 picolibc (Zephyr's default libc) | speed |
| `picolibc-atfe` | picolibc as Arm Toolchain for Embedded 23.1 ships it | size; M0+ and M33 only |
| `llvmlibc` | LLVM libc as ATfE 23.1 ships it | size; M0+ and M33 only |

20 runs, records in `~/lab-runs/libc-20261117/` (newlib-nano: the gcc runs
of the [compiler report](2026-11-16-compilers-six-boards.md), same
firmware); 0 errors in every run.

## memcpy itself
The benchmark's baseline is a bare `memcpy` into a buffer: cycles for a
4-byte / 64-byte write (cache on, flash).

| Board | newlib-nano | newlib | picolibc | picolibc-atfe | llvmlibc |
|---|---|---|---|---|---|
| nRF5340 (M33) | 44 / 76 | 44 / 76 | 44 / 76 | 63 / 363 | 97 / 129 |
| G0B1 (M0+) | 104 / 183 | 104 / 183 | 126 / 267 | 78 / 618 | 111 / 162 |
| G474 (M4) | 45 / 75 | 45 / 75 | 45 / 75 | – | – |
| H723 (M7) | 28 / 44 | 28 / 44 | 28 / 44 | – | – |
| SAM D20 (M0+) | 100 / 189 | 100 / 189 | 127 / 300 | 76 / 616 | 109 / 170 |
| RP2350 (M33) | 37 / 69 | 37 / 69 | 37 / 69 | 48 / 348 | 67 / 98 |

- **On the M33, M4 and M7, newlib-nano's, newlib's and Zephyr picolibc's
  memcpy measure the same**: identical cycles in every cell. The other three
  functions differ: Mbed CE CircularBuffer, for one, gets faster with
  picolibc (below).
- **On the Cortex-M0+ Zephyr's picolibc is slower** than newlib's: 64 bytes
  in 267 instead of 183 cycles on the G0B1 (+46 %), 300 instead of 189 on
  the SAM D20.
- **ATfE's picolibc is a size build**: a byte loop, cheap for 4 bytes (78
  cycles on the M0+, 63 on the M33), but 4-5 times slower for 64 bytes (363
  on the M33 against 76).
- **LLVM libc (ATfE)** is the fastest for 64 bytes on both M0+ boards (162
  and 170 against 183 and 189) and slower for small copies on the M33 (97
  against 44 for 4 bytes).

## Effect on the libraries
Only libraries whose block calls go through `memcpy` move; byte-loop
designs do not. Number of library configurations whose 64-byte write moves
by more than 5 % against newlib-nano: nRF5340 1 (newlib), 4 (picolibc), 16
(ATfE picolibc), 17 (LLVM libc); G0B1 0, 14, 14, 15; G474 0 and 3; H723 3
and 2. Examples (cycles per byte, 64-byte write, newlib-nano -> other):
Mbed CE CircularBuffer 8.94 -> 6.24 with picolibc on the nRF5340; Zephyr
ring_buf 3.11 -> 7.12 with ATfE's picolibc on the nRF5340; TinyUSB tu_fifo
12.25 -> 9.49 with picolibc on the G0B1. A block comparison therefore holds
for the C library it was measured with; the comparison page's numbers are
newlib-nano's.
