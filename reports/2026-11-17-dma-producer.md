# DMA as a real producer: first results on the G474 and H723 (2026-11-17)

Plan item 2b (`lab/plans/2026-11-16-mp-bundle-and-open-areas.md`). New test
firmware `firmware/rb-dma-stress`: DMA1 channel 1 of the STM32G474, paced by
TIM6 update requests through DMAMUX (one byte per timer period, random
period), copies the sequence into the area a library hands out with its
zero-copy API (`dma_wr_acquire`); the transfer-complete interrupt commits it
and starts the next. The main loop consumes with `dma_rd_acquire/release`
and checks every byte. A transfer is in flight for many main-loop turns.
Negative control: lwrb with the commit moved to before the DMA writes.
One library per reset over the serial port; firmware commit d31886dc8357.

## Result

NUCLEO-G474RE, 170 MHz, code in flash, 300000 bytes per library:

| Library | Prescaler 0: errors / lost+extra | full events | Prescaler 2: errors / lost+extra | full events |
|---|---|---|---|---|
| pxq RingBuffer_PackedState ⚠ | 0 / 0 | 6510 | 0 / 0 | 60 |
| lwrb | 0 / 0 | 10528 | 0 / 0 | 118 |
| Zephyr ring_buf | 0 / 0 | 15170 | 0 / 0 | 88 |
| TinyUSB tu_fifo | 0 / 0 | 11571 | 0 / 0 | 78 |
| ECE ring_buffer | 0 / 0 | 5671 | 0 / 0 | 10 |
| NuttX circbuf | 0 / 0 | 17839 | 0 / 0 | 188 |
| bbqueue (Rust) | 0 / 0 | 18851 | 0 / 0 | 362 |
| **control** (lwrb, commit before the DMA writes) | **27764** / 0 | 5039 | **44182** / 0 | 99 |

- Every library: 0 sequence errors, 0 lost or extra bytes; the control is
  caught in both runs.
- The window was exercised: in every library the consumer read 43000 to
  50000 times while a transfer was in flight (36500 transfers per run).
- The buffer ran full in every library (acquire gave no area) - thousands
  of times at the fastest DMA rate, tens to hundreds at prescaler 2. A first
  run with shorter consumer pauses hardly filled it (0-5 times); the pauses
  were lengthened before these runs.
- ⚠ pxq is the project owner's library (principle 6).

## H723 (Cortex-M7 with D-cache)

DMA1 stream 0 + DMAMUX1 (TIM6_UP), 64 MHz. DMA1 cannot reach the DTCM, so
the libraries' data is linked into AXI SRAM (`stm32h723_dma.ld`), every
variable on its own 32-byte cache lines; the test's own state stays in
DTCM. Firmware commit 7a61311 (DMA_CACHE runs), d83e3c3 (300000-byte runs).

**DMA area not cacheable** (MPU, the usual way; `DMA_CACHE=0`): the same
result as on the G474. 300000 bytes per library at prescaler 0 and 2, and
100000 at prescaler 1: every library 0 errors, 0 lost or extra bytes; the
control caught (28683, 42412, 13785 errors); reads during transfers in every
library; the buffer full thousands of times at prescaler 0.

**DMA area cacheable, with the maintenance an application does through the
zero-copy API** (`DMA_CACHE=2`: clean + invalidate the acquired area's
lines before the transfer, invalidate them after it, before the commit),
100000 bytes, prescaler 1:

| Library | Errors | Lost + extra | Note |
|---|---|---|---|
| lwrb, Zephyr ring_buf, TinyUSB tu_fifo, ECE ring_buffer, NuttX circbuf | 0 | 0 | data area and state are separate objects: each on its own lines |
| pxq RingBuffer_PackedState ⚠ | 1404 | 26142 | head/tail at offset 0 of the object, the data from offset 4 |
| bbqueue (Rust) | 5 | 56, then stalled | its coordinates before the storage in one struct (0x94 bytes) |
| control | 13988 | 0 | caught |

Why: the maintenance works on whole 32-byte lines. pxq and bbqueue keep
their indices in the same object as the data, in the first cache line of
it; a transfer into the first bytes of the data makes that line part of
the DMA area, and invalidating it after the transfer drops the core's
latest write of the indices. This is a property of their layout, not a
defect in their code: neither promises a layout for cached DMA, and with
the DMA area not cacheable both are error-free. For a user it means: on a
core with a data cache, give pxq's or bbqueue's storage to a DMA only in
non-cacheable memory; the other five can also be used with cache
maintenance if their data array is line-aligned (as here). An earlier run
of this variant (2f44bcd) had the test's own state in the libraries' first
cache line and showed errors in Zephyr too; it is superseded.

Without any maintenance (`DMA_CACHE=1`) every library fails, as expected:
that run only shows that something is needed.

### Repeated with three seed pairs, and the queue's state at the stall (2026-11-18)

The same variant (`DMA_CACHE=2`, 100000 bytes, prescaler 1) with three
pairs of seeds, firmware fce74bc built with `DMA_SNAP=0x24000000`: when a
run stalls, the firmware keeps the first 32 bytes of bbqueue's static as
the core sees them, through the cache (a read over the debug port shows
the memory, not the cache). The image without `DMA_SNAP` is byte-identical
to the one of 7a61311 (all eight image hashes equal).

| Seeds (main, DMA) | Five C libraries | pxq ⚠ errors | bbqueue | Control |
|---|---|---|---|---|
| 0x12345678, 0xCAFEBABE | 0 errors | 1439 | stalled after 33 transfers, 138 bytes (1 error) | 13826, caught |
| 0x9E3779B9, 0x7F4A7C15 | 0 errors | 1437 | stalled after 83 transfers, 591 bytes (10 errors) | 13869, caught |
| 0x2545F491, 0x6C078965 | 0 errors | 1384 | stalled after 65 transfers, 433 bytes (7 errors) | 13748, caught |

bbqueue run again alone from a reset with each seed pair: the same
numbers. With the run of 2026-11-17 (50 transfers, 312 bytes) that is four
of four: in this variant bbqueue always stops within the first few
hundred bytes.

The coordinates at the stall, as the core saw them (`AtomicCoord`: write,
read, last, reserve, read_in_progress, write_in_progress):

| Seeds | write | read | last | reserve | read_in_progress | write_in_progress |
|---|---|---|---|---|---|---|
| 0x12345678, 0xCAFEBABE | 116 | 117 | 127 | 116 | true | false |
| 0x9E3779B9, 0x7F4A7C15 | 114 | 115 | 127 | 114 | true | false |
| 0x2545F491, 0x6C078965 | 111 | 112 | 127 | 111 | true | false |

The snapshot is taken in the main loop between two of its calls, where it
holds no read grant. So `read_in_progress` is left true: every later
`read()` is refused (the adapter reports that as "nothing to read"), the
consumer takes nothing more, and with write one behind read the queue is
full, so the producer gets no grant either. That is the reading above,
now seen in the queue's state: a release by the main loop (which clears
the flag) was dropped when the line was invalidated, after the flag had
been written to memory as true at a transfer's start. The memory read over
the debug port held the same bytes as the core's view in all three.

The first wrong byte was the same kind in every run, here and on
2026-11-17, and in pxq too: a 0 where byte N was expected (N = 11, 2, 1
for the three seed pairs), which is what a consumer gets when its release
of the first N bytes is dropped and it reads from the start again.

Records: `~/lab-runs/dma-h723-20261118/` (six records and `run.log` with
the snapshots). One flash write on the H723 (the snapshot bundle).

## Not covered yet

- The other boards' DMA layers.
- Longer campaigns, code in SRAM, other compilers.
- The test does not end on a library's documented limit cases (e.g. a
  zero-length acquire); it covers the DMA as writer, not every API path.

Records: `~/lab-runs/dma-g474-20261117/` (lib-lab1).
