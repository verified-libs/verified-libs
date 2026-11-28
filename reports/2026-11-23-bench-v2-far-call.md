# Benchmark version 2: the series with the far call (2026-11-23)

The series the pages of version 2 are to show. Every library lies at least
6144 bytes behind its adapter (`FAR`, [change log](../site/content/method.md#log-2026-11-23-far-call)), so that a
call from the adapter into the library is a far one on every board, as it
is in an application where the linker places the library. The first run
of version 2, earlier the same day, had the library right behind its
adapter ([report](2026-11-23-bench-v2-first-run.md)); its records are
replaced by the ones of this series and stay in the history (commit
`f3d0682`).

## Result

- **265 records** on six boards (45 on the nRF5340 DK, 44 on each of the
  others), eight placements and two passes each: 4240 runs, every one
  with its run file, no configuration left out.
- **Every image rebuilt** from the records' commit (`d06180e`) and
  compared: 265 of 265 the same bytes (`oneverify.sh`).
- **Baseline** (the same code at the same place in every image of a
  board): 20 of 20 numbers the same in every run on five boards. On the
  NUCLEO-H723ZG 19 of 20; the single push with the cache on is 10.014 or
  10.024.
- The NUCLEO-G0B1RE and the SAM D20 now have a record for the
  configuration the first run could not print there (DNedic lockfree
  mpmc::Queue; it has no numbers on a Cortex-M0+ and the record says so).

## What the distance costs

Far minus near, cycles per call, single push and single pop, the median
over all runs of a configuration. "Inlined whole" are the configurations
with nothing but the stub of every image behind the gap: the compiler put
the whole library into the adapter, so there is no call the distance
could reach.

| Board | Scenario | Inlined whole: configurations, difference | Code behind the gap: configurations, median, lowest to highest |
|---|---|---|---|
| nRF5340 DK | cache on | 12, +0.00 to +0.00 | 33, +0.00, -1.00 to +6.00 |
| nRF5340 DK | cache off | 12, +0.00 to +0.00 | 33, +0.00, +0.00 to +0.00 |
| Raspberry Pi Pico 2 H | cache on | 12, +0.00 to +0.00 | 32, +0.00, +0.00 to +0.70 |
| Raspberry Pi Pico 2 H | cache off | 12, +0.00 to +0.00 | 32, +0.00, -67.00 to +68.00 |
| SAM D20 Xplained Pro | cache on | 10, +0.00 to +0.00 | 33, +0.00, -2.00 to +0.00 |
| SAM D20 Xplained Pro | cache off | 10, +0.00 to +0.00 | 33, +0.00, +0.00 to +0.00 |
| NUCLEO-G0B1RE | cache on | 10, +0.00 to +0.00 | 33, +0.00, +0.00 to +0.00 |
| NUCLEO-G0B1RE | cache off | 10, +0.00 to +0.00 | 33, +0.00, +0.00 to +0.00 |
| NUCLEO-G474RE | cache on | 12, +0.00 to +0.00 | 32, +0.00, +0.00 to +0.00 |
| NUCLEO-G474RE | cache off | 12, +0.00 to +0.00 | 32, +0.00, +0.00 to +0.00 |
| NUCLEO-H723ZG | cache on | 12, +0.00 to +0.01 | 32, +6.00, -0.01 to +15.48 |
| NUCLEO-H723ZG | cache off | 12, +0.00 to +0.00 | 32, +19.98, +0.00 to +65.94 |

- **Only the Cortex-M7 pays for the distance.** On the NUCLEO-H723ZG a
  configuration that calls into its library costs 3 to 15 cycles more per
  operation with the cache on (median 6), and up to 66 more with it off.
  This is the step the experiment of the first report found between 2048
  and 4096 bytes, now measured for every configuration.
- **A configuration that is inlined pays nothing, on any board.** This
  includes configurations with code behind the gap that the single push
  and pop do not call (micoring's default mode; all modes of pxq, whose
  single-byte operations are inlined and whose block operations lie behind
  the gap). pxq is the owner's own library; the page has to say that its
  single-byte numbers contain no call while most others do.
- On the four Cortex-M0+, M4 and M33 boards the series are the same
  within 2 cycles, except one configuration on the nRF5340 DK (+6).
- Pico 2: the same with the cache on (largest difference 0.7). With the
  cache off one configuration moved, embassy-sync Pipe: push 67 cycles
  lower, pop 68 higher. With that cache off every instruction is fetched
  from the external flash, and the number follows where the code lies in
  it; nothing else moved.

NUCLEO-H723ZG, cache on, every configuration (two are not listed):

| ETL queue_spsc_atomic (C++) | 44 | 33.026 / 32.025 | +0.00 / +0.00 |
| ETL queue_spsc_isr (C++) | 44 | 39.025 / 40.026 | +0.00 / +0.00 |
| ETL etl::queue, single-context (C++) | 44 | 22.035 / 21.019 | +0.00 / +0.00 |
| heapless spsc::Queue (Rust) | 44 | 34.031 / 29.008 | +0.00 / +0.00 |
| heapless mpmc::Queue (Rust) | 44 | 55.046 / 52.039 | +0.00 / +0.00 |
| DNedic lockfree mpmc::Queue (C++) | 44 | 50.029 / 51.021 | +0.01 / +0.00 |
| Mbed CE CircularBuffer (C++) | 44 | 60.562 / 58.046 | +0.00 / +0.00 |
| polycratia spscring (C++) | 44 | 32.026 / 29.029 | +0.00 / +0.00 |
| rt-spsc (C++) | 44 | 30.036 / 31.019 | +0.00 / +0.00 |
| Zephyr ring_buf (C) | 44 | 42.197 / 40.206 | +0.00 / +0.00 |
| Zephyr ring_buf, CONFIG_SMP (C) | 44 | 60.717 / 58.23 | +0.00 / +0.00 |
| jnk0le Ringbuffer (C++) | 60 | 30.026 / 30.025 | +0.00 / +0.00 |
| wizard97 as shipped (C++) | 60 | 19.037 / 18.017 | +0.00 / +0.00 |
| wizard97 + PRIMASK macros (C++) | 72 | 48.024 / 44.023 | +0.00 / +0.00 |
| Arduino RingBufferN as shipped (C++) | 80 | 30.035 / 27.026 | +0.00 / +0.00 |
| Arduino SafeRingBufferN (C++) | 80 | 53.029 / 51.021 | +0.00 / +0.00 |
| EmbeddedArtistry cbuf basic, single-context (C) | 84 | 28.047 / 26.024 | +0.00 / +0.00 |
| rigtorp SPSCQueue (C++) | 88 | 31.141 / 39.033 | +0.00 / +0.00 |
| Contiki-NG ringbuf (C) | 124 | 33.0555 / 28.03 | +8.01 / +7.00 |
| ETL queue_spsc_locked (C++) | 160 | 74.0535 / 71.031 | +11.00 / +10.99 |
| QuantumLeaps LFRB (C) | 180 | 47.0515 / 42.0295 | +7.02 / +7.00 |
| EmbeddedArtistry cbuf threadsafe (C) | 216 | 37.0365 / 32.041 | +6.00 / +7.01 |
| AndersKaloer Ring-Buffer (C) | 280 | 33.0705 / 27.0415 | +7.02 / +7.00 |
| DNedic lockfree spsc::RingBuf (C++) | 280 | 69.656 / 67.0615 | +11.50 / +12.00 |
| RIOT tsrb (C) | 288 | 48.561 / 42.0435 | +9.02 / +5.01 |
| pxq Topology::None, single-context (C++) | 312 | 18.0315 / 18.024 | +0.00 / +0.00 |
| pxq RingBuffer_PackedState (C++) | 316 | 17.035 / 16.026 | +0.00 / +0.00 |
| moodycamel ReaderWriterQueue (C++) | 344 | 48.1125 / 48.029 | +6.02 / +6.00 |
| diffstorm cb (C) | 392 | 53.0895 / 67.0485 | +9.01 / +10.00 |
| micoring default, single-context (C) | 424 | 47.1 / 45.048 | +0.00 / +0.00 |
| RT-Thread rt_ringbuffer + interrupt lock (C) | 584 | 54.1465 / 47.1665 | +5.01 / +5.00 |
| RT-Thread rt_ringbuffer, no lock (C) | 584 | 39.139 / 33.7225 | +6.00 / +7.57 |
| micoring SPSC mode (C) | 648 | 78.099 / 71.054 | +10.99 / +11.00 |
| ece-mohammad RingBuffer (C) | 712 | 55.11 / 52.0495 | +13.49 / +12.01 |
| pxq Topology::MPMC (C++) | 900 | 33.0175 / 31.012 | -0.01 / +0.00 |
| pxq Topology::MPSC (C++) | 900 | 33.031 / 16.019 | +0.00 / +0.00 |
| pxq Topology::SPMC (C++) | 900 | 17.0285 / 31.021 | +0.00 / +0.00 |
| lwrb (C) | 948 | 47.042 / 44.033 | +9.00 / +10.00 |
| TinyUSB tu_fifo (C) | 1152 | 63.1425 / 66.13 | +12.24 / +12.49 |
| FreeRTOS stream buffer (C) | 1376 | 210.577 / 164.363 | +3.33 / +3.24 |
| embassy-sync Pipe (Rust) | 6196 | 119.688 / 111.086 | +11.99 / +12.00 |
| bbqueue (Rust) | 6992 | 155.188 / 123.171 | +11.01 / +10.99 |

The FreeRTOS stream buffer is the one whose numbers follow the placement
(first report); its median moved by 3.

## Flash writes

48, as planned: nRF5340 DK 5, NUCLEO-G0B1RE 9, NUCLEO-G474RE 9,
NUCLEO-H723ZG 5, SAM D20 18, Pico 2 2 (its first bundle in four parts,
each sector once). On top of that, three writes of the Pico 2's first
bundle that failed part way.

After the series: one more on the Pico 2, to try the write in parts as
a tool on the board (the second bundle, 117 units, in two parts;
the bundle was on the board afterwards).

## What went wrong

- **The Pico 2 lost power during the flash write, three times.** Cause
  found: while the probe writes, the board's own USB port shows up at the
  hub and does not answer; 65 s after that the kernel power-cycles the
  hub port ("attempt power cycle"), and the board, which is fed from that
  port, is gone in the middle of the write. A bundle of 4 MB takes longer
  than 65 s; 1 MB takes 25 to 30 s. The bundle was then written in four
  parts of about 1 MB, waiting for the power cycle between the parts;
  after it the runner found the whole bundle on the board and wrote
  nothing. This also explains the Pico 2 that "halted about 60 s after a
  download" in earlier notes. `lab/tools/pico2-write.py` now does this, before the runner is
  started; the runner itself is not changed, because it is one of the
  sources the records were made with ([change log](../site/content/method.md#log-2026-11-22-same-image)). A cable that carries power only would remove the cause.
- NUCLEO-H723ZG: two images were not finished 3 s after the reset and
  were run again with a longer wait (the runner's rule); numbers as in
  the other pass.

## Reproduce

`bash firmware/nrf5340-rb-bench/oneverify.sh records/bench-v2/<board>/*.json`
rebuilds and compares, without a board. The table above:
`lab/tools/bench2-near-far.py NEAR records/bench-v2 firmware/nrf5340-rb-bench/build/v2 -v stm32h723`
with NEAR from `git archive f3d0682 records/bench-v2`.

*2026-11-28: links to documents that are no longer published were removed or now point to the change log.*
