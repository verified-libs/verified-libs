# Plan: MP stress in the bundle, and the areas not covered yet (2026-11-16)

Written for the owner's review; nothing here is implemented yet.

## 1. The two-interrupt (MP) stress test in the same bundle as the ISR test

**Why.** The ISR stress test (`nrf5340-rb-stress`) runs one image per
library, side by side in flash behind a boot stub, selected per reset over
the serial port: a library that hangs or overwrites memory cannot affect the
others, and a campaign flashes once. `rb-mp-stress` still has all its
libraries in one image with parameters written over the debug port. Both in
one bundle means one flash for both tests and the same isolation for MP.

**Steps** (each validated before the next; the current MP test stays the
default until step 5 says otherwise):

1. *Fixed selection address.* Today the selection words live at the end of
   each firmware's result block (`main.c` SEL, read by `common/slotboot.c`
   at an address bundle.py finds per image). Give them their own section at
   one fixed address in every board's linker scripts (`.select`, e.g. the
   last 16 bytes of the RAM the stub never clears), so one stub can start an
   image of either firmware. No change to results.
2. *Per-library MP images.* `rb-mp-stress/Makefile`: `ONLY=<n>`, `LIB_<n>`
   object lists, `SLOT_BASE`/`SLOT_LEN`, `print-<VAR>` (what `bundle.py`
   asks for); `main.c`: weak adapters under `ONLY_LIB`, as the ISR test.
   WITH_EXTRA (held-back libraries) stays an opt-in image set.
3. *One serial protocol.* Factor the ISR test's ready/go/done lines and its
   host side (`uart_host.py`) into `firmware/common/` and use them in
   `rb-mp-stress` instead of the debug-port parameters. The H7's RAM ECC
   needs the result buffer re-checked (word writes; the owner's note of
   2026-11-15).
4. *Bundles of both.* `bundle.py` takes images from two firmwares (ISR libs
   0-40, MP libs after them) into one bundle. Flash budget per board must be
   checked first: the SAM D20 already needs two bundles for the ISR test
   alone (440 KB of images, 256 KB flash); the G0B1 (512 KB) may need two.
5. *Validation.* Same seeds and parameters, old MP image and new per-library
   images, on all six boards: identical verdicts, counts within the random
   spread, the negative control caught. Only then campaigns switch, and the
   old and new MP records are not pooled (new method).

Estimate: 1-2 days with board runs; wear: one bundle write per board per
step that changes images.

## 2. Areas not covered yet (RESULTS.md, "Not covered yet")

**a) nRF5340 network core and cross-core use.** The two cores share RAM;
libraries documented for several cores (lockfree, ETL atomic, heapless,
rigtorp, ...) could be stress-tested with the producer on one core and the
consumer on the other, as the RP2350 SMP mode does. Needs: a network-core
firmware (its own linker script and startup; probe-rs can flash core 1),
shared-RAM placement both cores agree on, start-up handshake. The
application core's 64/128 MHz against the network core's 64 MHz gives
asymmetric speeds, which the RP2350 does not test. Size: large (a new
board layer); value: the second dual-core case, a common real design.

*Status 2026-11-17 (feasibility, `firmware/nrf5340-net-probe/`):* the
network core runs code from its own flash and writes application RAM once
the application firmware sets SPU EXTDOMAIN and releases it. LDREX/STREX is
not atomic between the two cores (21-24 % of a million increments per core
lost, four runs): compare-and-swap libraries cannot work across the cores
of an nRF5340 (a chip property). So 2a becomes: SPSC libraries, producer on
one core and consumer on the other (as the RP2350 SMP mode), the library
object in application RAM at a fixed address, the same library code built
for both cores; plus the MPMC/CAS libraries shown failing across the cores
as a documented chip limit, not as library results.
*Status 2026-11-17 (later):* done, `reports/2026-11-17-nrf5340-cross-core.md`:
15 multi-core SPSC libraries error-free across the cores in both
directions (300000 bytes, single and blocks), the control caught.

**b) DMA as a real producer.** Today the zero-copy API is exercised by the
interrupt and the main loop. A real DMA writes memory without the core:
e.g. on the STM32s a memory-to-memory DMA filling the area a library hands
out (`dma_wr_acquire`), committed from the DMA-complete interrupt, while
the main loop consumes. It tests that a library's acquire/commit is safe
against a writer that is not code (cache maintenance on the M7 included).
Size: medium (one board first, the G474; then the H723 with its D-cache).

**c) Other C libraries.** Every build links newlib-nano; `memcpy` speed
decides block numbers (MEMCPY=stub showed how much). Candidates: picolibc
(ATfE's and Zephyr's default), full newlib, ST's newlib build. A `LIBC=`
option in the bench, records apart, a report like the compiler ones.
Size: small to medium; needs the libraries in the images (no downloads
outside the toolchain images).

Suggested order: 2c (small, extends tonight's compiler report), then 1
(isolation for MP, owner's earlier wish), then 2b, then 2a.

## Status 2026-11-17 (owner's go of 2026-11-16: "follow the proposal as written")

1. *Fixed selection address* - done, 95f7290: `.select` (last 16 bytes of
   RAM) in every linker script but the RP2350's (watchdog scratch).
   check.sh quick on all six boards: error-free, controls caught.
2. *Per-library MP images* - done, acd9ffd: MP library index 0-7 (8 with
   WITH_EXTRA), the same in both modes; built for all six boards
   (3-5 KB each); G474 spot check.
3. *One serial protocol* - done, b2252e0: `common/vls_uart.h` (moved
   unchanged: all 240 ISR images and the stubs byte-identical on all six
   boards), `common/uart_host.py`; MP run.sh `PER_LIB=1`. G474 and H723,
   MPSC and SPMC: libraries error-free, controls caught.
4. *Bundles of both* - done, b2252e0: MP indices from 64, `bundle.py
   --with`, `IMAGES=combined` in both run.sh; the ISR images in the combined
   bundle are byte-identical to the per-library bundle's. Flash: one bundle
   on nRF5340, H723, RP2350; two on G0B1/G474 (ISR alone 518 KB of 512 KiB),
   three on SAM D20: there a switch between the tests still writes flash,
   so campaigns there should run the tests in blocks. Found on the way: a
   selection written over the debug port is also lost to the H7 RAM ECC
   write buffer unless more words follow (uart_host.py writes four).
5. *Validation* - done: `reports/2026-11-17-mp-per-library-validation.md`.
   Every library the same verdict both ways (161 of 161), load the same;
   the control differs only where it is caught by chance (SPMC, prescaler
   3). Switching the MP campaigns: owner's decision.

## 2b design: DMA as a real producer (2026-11-17, owner's go)

**Firmware.** A new test firmware `firmware/rb-dma-stress` (not a new mode
of the ISR test, so the ISR images stay byte-identical), speaking
`common/vls_uart.h` and built per library into the combined bundle
(`bundle.py --with`, selection indices from 96). Only libraries with the
zero-copy API (`dma_wr_acquire/commit`): pxq, lwrb, Zephyr ring_buf,
TinyUSB fifo, ECE, the Rust one(s), and NuttX circbuf only in the
held-back build (embargo).

**Producer.** The DMA controller writes, not the core:
1. In the DMA transfer-complete interrupt: `dma_wr_commit(len)` for the
   transfer that just finished, then `dma_wr_acquire(&p, 1..16)` and
   program the next transfer of `len` bytes into `p`.
2. The source is a pattern table `pat[i] = i & 0xff` (256 + 16 bytes), so
   the transfer copies the next `len` sequence bytes from `&pat[seq]`.
3. Paced, not memory-to-memory at full speed: one byte per request of a
   timer (G474: DMAMUX request from TIM6 update; random period per
   transfer). A transfer is then in flight for many main-loop iterations,
   which is the window a wrong library would expose (the consumer reading
   the area before its commit, or the library handing out an area the
   consumer still reads).
4. If no space (`acquire` returns 0) the interrupt of a second timer tries
   again later; full events counted.

**Consumer.** The main loop with `dma_rd_acquire/release` (and plain pop in
a second variant), checking the sequence byte by byte, as the ISR test.

**Negative control.** The same library with the commit moved to *before*
the transfer (commit at start): the consumer then reads bytes the DMA has
not written yet. It must be caught in every valid run, as in the other
tests.

**Boards.** G474 first (no cache). Then H723: the D-cache needs clean /
invalidate around the DMA area (or the buffer in non-cacheable SRAM): a
library's API decides where that maintenance can go, which is itself a
finding worth reporting. nRF5340 (EasyDMA only in peripherals) and the
others later, if at all.

**Status 2026-11-17:** built and run on the G474
(`reports/2026-11-17-dma-producer.md`): seven libraries error-free,
the control caught, the buffer running full, reads during transfers.
H723 the same with the DMA area not cacheable; with it cacheable and line
maintenance, pxq and bbqueue (indices in the data's first cache line) lose
values. Same report.

**Results.** Records `-rb-dma-stress-`, kept apart; decode with the
ISR test's fields (transferred, errors, first error, full/empty events,
interrupts, plus DMA transfers and in-flight overlaps).
