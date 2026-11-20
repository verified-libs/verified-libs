# Method: how the embedded ring buffers are measured and tested

## Hardware

| Board | Core | Clock | Cycle counter |
|---|---|---|---|
| nRF5340 DK (application core) | Cortex-M33 | 64 MHz | DWT CYCCNT |
| NUCLEO-G0B1RE | Cortex-M0+ | 64 MHz | SysTick |
| NUCLEO-G474RE | Cortex-M4F | 170 MHz | DWT CYCCNT |
| NUCLEO-H723ZG | Cortex-M7 | 64 MHz (reset clock) | DWT CYCCNT |
| SAM D20 Xplained Pro | Cortex-M0+ | 48 MHz | SysTick |
| Raspberry Pi Pico 2 H (RP2350) | 2 x Cortex-M33 | 150 MHz | DWT CYCCNT |

All boards are driven headless from one Linux machine over their debug
probes, and every board can be power-cycled by switching its USB port, so
long campaigns run unattended. A `counter-check` firmware confirms on each
board that the cycle counter counts core cycles through the same timing
routine the benchmark uses.

## Toolchain

One pinned container image builds everything: arm-none-eabi-gcc 14.2.1 with
newlib-nano, clang 21 for the libraries in clang runs, and GenMC for model
checking. Library versions are pinned by commit in `libs.lock`. Each result
record stores the toolchain, flags, firmware hash and library commits.

## Benchmark

Each library operation is timed around a single call with the board's cycle
counter: one byte push and pop, bursts, blocks of 4, 16 and 64 bytes, and
the zero-copy (DMA) API where a library has one, with the cache on and off,
with code in flash and in SRAM. The fixed overhead of the timing call is
measured and subtracted. Numbers are cycles, so boards with different
clocks can be compared.

## ISR stress test

A timer interrupt and the main loop pass a byte sequence through the buffer
in both directions, single bytes, blocks and zero-copy, with random
interrupt periods and random pauses so the buffer runs full and empty under
preemption. Any lost, duplicated, reordered or torn byte is an error.

A run counts only if the **negative control** (a ring buffer with a
deliberate ordering bug) is caught in it, which shows the run was able to
find such a bug.

A library is **starved** when the interrupt load leaves its other side no
time to finish. That is reported and never counted as a pass: the run is
not counted for that library, and in the multi-producer test below the
whole run is left out.

Random interrupts can miss a narrow window. The **interrupt sweep** does not
rely on chance: for every call it fires one interrupt at every delay from
the start of the call, one cycle apart, from five fill levels and 256 start
positions, and afterwards drains the buffer and checks the number of bytes.
The interrupted program counters are recorded, so the record shows which
instructions of each library function were interrupted.

Four **mutants**, ring buffers with one deliberate defect each, run next to
the libraries and show which mode can find which kind of defect: the sweep
catches every mutant in every run in the directions where its defect can
show, the random modes sometimes miss
([report](../../reports/2026-11-13-night-sweep-mutants-wave4.md)).

Multi-producer and multi-consumer libraries are tested with two interrupts
at different priorities. On the RP2350 the other side can also run on the
second core (SMP), where only libraries built for several cores are in
their documented mode.

In the multi-producer test the control is a single-producer buffer used by
two producers or two consumers. Random interrupts catch it less often at
the slow interrupt rates, so at the two slowest rates every run uses
**aimed interrupts** (in the campaign of 2026-11-17/18, half of them): a timer is armed just before each push or pop with a
short random delay, so that the interrupt lands inside the operation
rather than by chance. The runs at those rates also record the address
each interrupt landed on, and the report shows for each library how many
of the places where an interrupt can land were hit
([report of 2026-11-20](../../reports/2026-11-20-publication-rerun.md),
[of 2026-11-18](../../reports/2026-11-18-mp-campaign-coverage.md)).

**One library per reset** (night campaigns from 2026-11-14 on; earlier
campaigns ran all libraries in one start, and the two kinds are not added
together). The board is flashed once; for each
library the host selects it, resets the board and reads that library's
results as soon as it reports that it is done. A library that hangs or
overwrites memory then cannot block or change the results of the others; it
is reported as not finished, and the run does not count as error-free. On
boards with a serial port to the host (all six) the selection and the "done"
go over that port, and the debug port is not touched while a library runs.
Since the campaign of 2026-11-15/16 each library also has its own firmware
image, which holds no other library's code; all images lie side by side in
flash with a small boot stub that starts the selected one. Adding or
changing one library therefore cannot change another library's image or
result. The comparison page shows only campaigns run this way.

## Model checking

Libraries that promise lock-free concurrency with C11 or C++ atomics are
checked with GenMC under the RC11 memory model, for all interleavings of a
producer and a consumer thread. Every pass comes with mutants (a release or
acquire weakened to relaxed) that must fail, and with reachability probes
that show the full and empty states were explored.

## One-core contract check

GenMC cannot judge the libraries that rely on one core instead of C11
atomics (volatile indices, compiler barriers, interrupt masking): under the
C/C++ memory model such code always has data races. The
[contract check](../../verify/contract/README.md) executes their contract
instead. The library is compiled for the lab host; main's call runs one
instruction at a time under the trap flag, and the interrupt's call is made
at every instruction, and in a second pass at every pair of instructions,
from every start position and fill level of an eight-slot buffer. Interrupt
masking becomes a flag, so an interrupt inside a masked section is taken
right after it, as on a Cortex-M. A configuration passes if every result
is one the calls give one after the other (and, for single bytes, what an
ideal FIFO gives). The negative control and the four mutants must fail in
every run. The check does not see what a compiler for the target makes of
the code (the interrupt sweep on the boards does) or two cores.

## Campaigns

Overnight campaigns repeat the stress test with new random seeds, interrupt
rates, cache settings and code locations, and a report lists every run
with its status. The campaign the comparison shows ran at one commit with
gcc -O2 ([report](../../reports/2026-11-20-publication-rerun.md)); earlier
campaigns also rotated the compiler flags (-Os, -O3, -O2 with LTO, -Os
with LTO, and clang).

## Conflict of interest

pxq RingBuffer_PackedState is written by the project owner, and it is
also offered under a commercial licence (GPL-3.0 or commercial). It is
in the comparison because the comparison is meant to help choose a
library, and leaving out one that users can pick would make it less
useful. This is how we handle it, and where it is not even:

- **Marked.** ⚠ next to every pxq row in the comparison and in the
  tables of the results, and `"own": true` in the data files. Not every
  older report carries the mark.
- **The same tests, in every mode it documents.** pxq runs every test
  the others run, in each of its modes (SPSC, MPSC, SPMC, MPMC, producer
  reservations). That is why it has four rows in the multi-producer
  test: more rows, not better treatment. Its weaknesses are measured
  the same way: its modes with several producers or consumers mask
  interrupts, which does nothing against a second core, so on the two
  cores of the Pico 2 they give errors (they do not promise to work
  there, and the results say so); and on the Cortex-M7 its indices share
  a cache line with its data, so a DMA can only use it in non-cacheable
  memory.
- **No test is changed to suit it.** Every change to the method is
  recorded with its reason in `DECISIONS.md` and in the reports, which
  are published with the results; anyone can check whether one favours
  pxq.
- **pxq has changed during the project, and the others have not had
  that chance yet.** It went from 1.3.2 to 1.4.0 and 1.5.0 while these
  tests ran, partly because of what they showed. Every result names the
  version it was measured with. Every other maintainer gets the same
  offer: a new version is tested the same way (diffstorm/cb was, after
  its fix), and each library's adapter, the small piece of code written
  here to drive it, can be reviewed and improved by its maintainer.
- **The owner hears first about pxq; the others hear when we find
  something.** What the lab finds about another library goes to its
  maintainer when found, not at publication; defects first in private,
  with 90 days before publication.
- **Outside repetition.** No result has been repeated outside the
  project yet, pxq's included; [Repeats](repeats.html) shows how to do
  it with one of the boards. In the long run the trust in every result
  here rests on people outside repeating it and getting the same.
  Because the owner has both a library and this comparison, pxq needs
  more outside repetitions than the others before its results count as
  equally certain.
- **No ranking by us.** The comparison is sorted by name until the
  reader sets weights; a ranking comes only from the reader's weights.
