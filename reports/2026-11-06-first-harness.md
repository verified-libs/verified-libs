# First harness results, 2026-11-06

Summary of the first day with real hardware: nRF5340 DK, application core
(Cortex-M33, 64 MHz), connected to lib-lab1. **Harness development, not
published results.** ⚠ marks the project owner's own library
(principle 6: counts only after an independent repetition).

## What exists now
| Piece | What it does | Where |
|---|---|---|
| Cycle benchmark | push/pop and push_n/pop_n cycles per call, 5 patterns, flash (cache on/off) and SRAM | [firmware/nrf5340-rb-bench](../firmware/nrf5340-rb-bench/README.md) |
| ISR stress test | timer interrupt ↔ main loop, both directions, single bytes and blocks, negative control | [firmware/nrf5340-rb-stress](../firmware/nrf5340-rb-stress/README.md) |
| GenMC model check | lwrb as SPSC under the C11 memory model, two negative controls | [verify/genmc](../verify/genmc/README.md) |
| Method decisions | primary number, negative controls, timing rules | [DECISIONS.md](../DECISIONS.md) |

Six libraries, all at pinned commits, fetched at build time and never copied
into the repo: pxq RingBuffer_PackedState ⚠, lwrb, AndersKaloer
Ring-Buffer, jnk0le Ringbuffer, ETL queue_spsc_isr, ETL queue_spsc_atomic.

## Correctness
- **ISR stress: 0 errors for all six libraries**, both directions, single
  bytes and blocks, 300 000 bytes per run, 0.7–11 million interrupts per
  run. The control (head published before data; slots released before
  read) was caught in every case where its bug can show.
- **GenMC: lwrb v3.3.0 passes** (7118 executions under RC11); lwrb without
  atomics and a release → relaxed mutant are both caught as data races.
- **Gaps:** lwrb's buffer never ran full in main → ISR (its calls are too
  slow for the main loop to outpace the interrupt). pxq and the volatile/
  plain-variable libraries have no memory-model check yet: they need a
  model of their single-core ISR contract, not the C11 model alone.

## Speed (flash, cache on, mean cycles per call)
| Library | push / pop, 1 byte | push / pop, 64 bytes | cycles/byte at 64 |
|---|---|---|---|
| pxq ⚠ | 17 / 31 | 208 / 194 | 3.1 |
| jnk0le | 17 / 19 | 607 / 614 | 9.5 |
| ETL atomic | 24 / 31 | 1440 / 1453 | 22.6 |
| ETL isr | 33 / 38 | 1832 / 1696 | 27.6 |
| AndersKaloer | 56 / 40 | 1032 / 1107 | 16.7 |
| lwrb | 220 / 217 | 289 / 274 | 4.4 |

Only pxq and lwrb copy blocks with `memcpy`; the others move one byte at a
time. lwrb's single-byte path is long (`_ex` call, free count, `memcpy` of
one byte).

## Findings worth keeping
1. **Code in SRAM is 1.5–2× slower than flash with the cache on** on the
   nRF5340 (but faster than flash with the cache off). "ramfunc" makes ring
   buffers slower here.
2. **Releasing one slot before reading it is harmless in a sacrificed-slot
   ring buffer**; releasing several (block pop) is a real bug. Measured,
   not just argued.
3. **pxq observations** (for its maintainer): `push_n` is not inlined and
   always calls `memcpy` twice, even with length 0, so 4 bytes via
   `push_n` (132 cycles) cost more than 4 × `push` (~68); `pop` costs ~2×
   `push`, partly from a stack frame GCC creates under the library's
   forced `-Os` (jnk0le's similar pop takes 19 cycles).
4. **AndersKaloer Ring-Buffer** uses plain variables; this build happens to
   keep a safe store order, which the language does not guarantee. Its
   queue overwrites when full (moves the tail from the producer side).
5. **Harness pitfalls fixed:** probe-rs attach/detach stops the DWT cycle
   counter and can halt the core while timers run on; the compiler moved
   work into C timing windows. All now detected or avoided.

## Next steps (proposals)
- STM32G071 (Cortex-M0+, SysTick timing) once the dev kit arrives.
- A fair correctness model for volatile-based single-core ring buffers
  (pxq, AndersKaloer, lwrb with `LWRB_DISABLE_ATOMIC`).
- Other compilers/flags (clang, `-Os`, `-O3`, LTO) for the libraries
  without volatile/atomics.
- Close the lwrb full-buffer gap in the stress test.
- More candidates: Zephyr ring_buf, FreeRTOS stream buffer, Rust
  (heapless, bbqueue, ringbuf).
- Independent repetition of the pxq numbers before anything is published
  (principle 6).
