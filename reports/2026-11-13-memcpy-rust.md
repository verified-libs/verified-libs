# Which memcpy the Rust libraries are measured with (2026-11-13)

The benchmark firmware is a C firmware: the Rust libraries are linked into it
as a static library, and their calls to `memcpy` go to the C library's
(newlib's, optimised for speed). A firmware written in Rust links Rust's own
memory functions instead (`compiler_builtins`, as shipped in the `rust-std`
archive for the target). `MEMCPY=rust` builds the benchmark that way, for the
C code in the firmware too, so the two can be compared. Rust and
multi-producer sets, `-O2`, code in flash, five boards (the Pico 2 was busy).

Mean cycles, C library's memcpy → Rust's:

| Board | bbqueue, 64-byte block, per byte (write / read) | embassy-sync Pipe, 64-byte block, per byte | embassy-sync Pipe, 1 byte (write / read) | 64-byte copy alone, per byte |
|---|---|---|---|---|
| nRF5340 DK (M33) | 6.3 → 11.5 / 5.5 → 10.3 | 6.3 → 11.0 / 5.9 → 10.3 | 221 → 298 / 213 → 294 | 1.2 → 2.9 |
| NUCLEO-G474RE (M4) | 7.5 → 13.7 / 6.2 → 11.4 | 6.8 → 12.4 / 5.9 → 11.1 | 190 → 281 / 174 → 264 | 1.2 → 2.6 |
| NUCLEO-H723ZG (M7) | 6.3 → 8.4 / 5.3 → 7.1 | 4.5 → 6.5 / 4.0 → 5.8 | 114 → 134 / 105 → 126 | 0.6 → 1.5 |
| NUCLEO-G0B1RE (M0+) | 15.6 → 15.9 / 14.6 → 14.6 | 13.7 → 14.0 / 13.2 → 13.2 | 270 → 286 / 251 → 267 | 2.9 → 3.8 |
| SAM D20 (M0+) | 15.8 → 16.7 / 14.8 → 15.4 | 14.1 → 15.0 / 13.6 → 14.2 | 290 → 304 / 268 → 280 | 3.0 → 3.6 |

("64-byte copy alone" is the benchmark's baseline: one copy of 64 bytes and
nothing else.)

- **Rust's memcpy is the slower one here**, by more than a factor of two for
  a 64-byte copy on the M33, M4 and M7, and by 20 to 30 % on the M0+ boards.
  The two libraries that copy blocks with it, bbqueue and embassy-sync Pipe,
  need up to 1.8 times the cycles per byte for a 64-byte block on the M4 and
  M33, about 1.4 times on the M7, and almost the same on the M0+.
- **embassy-sync Pipe calls memcpy for a single byte too**, so its one-byte
  write and read slow down by 80 to 90 cycles on the M33 and M4, 20 on the
  M7 and about 15 on the M0+.
- **heapless is not affected**: its queues move one element at a time
  without memcpy (all means equal, except on the H723, where the one-byte
  means of heapless spsc::Queue moved from 40 / 35 to 34 / 29 cycles: the
  other memory functions shift the code, a placement effect).
- The C++ configuration in the same firmwares that calls memcpy, DNedic
  lockfree spsc::RingBuf, slows down in the same way (G474: 98 → 146 cycles
  for one byte, 3.9 → 10.2 per byte for a block), which shows that the
  difference is the memory function and not the libraries.

What it means for the comparison page: its numbers for bbqueue and
embassy-sync Pipe are with the C library's memcpy, the favourable case for
them. In a pure Rust firmware built with the stock `rust-std` they would be
slower by the amounts above, unless the project links another memcpy. The
page does not show the `MEMCPY=rust` numbers; whether it should (as a
second figure for the Rust libraries) is open.

Records: `*-rb-bench-rust-flash-memcpyrust-*` and
`*-rb-bench-mp-flash-memcpyrust-*` of 2026-11-13 (commits `9518bf8` and
`8e9fcd5`; the change between them does not touch the benchmark firmware), compared with the
records of the same sets with the default memcpy.
