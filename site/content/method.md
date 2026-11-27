# Method: how the embedded ring buffers are measured and tested

The method of one of the three kinds of library so far ([all kinds](kinds.md));
the other kinds': [CRC calculation](method-crc.md) and
[fixed-block memory pools](method-pools.md).

## Hardware

| Board | Core | Clock | Cycle counter |
|---|---|---|---|
| nRF5340 DK (application core) | Cortex-M33 | 64 MHz | DWT CYCCNT |
| NUCLEO-G0B1RE | Cortex-M0+ | 64 MHz | SysTick |
| NUCLEO-G474RE | Cortex-M4F | 170 MHz (boost mode, 4 flash wait states) | DWT CYCCNT |
| NUCLEO-H723ZG | Cortex-M7 | 520 MHz (VOS0, 3 flash wait states; method version 3) | DWT CYCCNT |
| SAM D20 Xplained Pro | Cortex-M0+ | 48 MHz | SysTick |
| Raspberry Pi Pico 2 H (RP2350) | 2 x Cortex-M33 | 150 MHz | DWT CYCCNT |

All boards are driven headless from one Linux machine over their debug
probes, and every board can be power-cycled by switching its USB port, so
long campaigns run unattended. A `counter-check` firmware confirms on each
board that the cycle counter counts core cycles through the same timing
routine the benchmark uses.

## Method version 3

Since 2026-11-26 ([`DECISIONS.md`](../../DECISIONS.md); the plan with its
sources: [`lab/plans/2026-11-26-method-version-3.md`](../../lab/plans/2026-11-26-method-version-3.md)).
It applies to both kinds' benchmarks and to every series after it. Each
board's records say which version they are of, on the results and
comparison pages.

**The clock rule.** Each board runs at the clock its vendor's start-up
code or board template uses, never at one that needs an option byte, with
the fewest flash wait states the reference manual allows at that clock.
Where the vendor's code and the manual differ, the manual's minimum is
taken and the difference is said.
- *NUCLEO-H723ZG*, the only board whose clock changes: from 64 MHz with
  the 7 wait states it has after power-on to **520 MHz** (voltage scale 0,
  AXI bus at 260 MHz, 3 wait states), as ST's template for the board sets
  it (`STM32CubeH7` `Projects/NUCLEO-H723ZG/Templates`; RM0468 Table 16:
  3 wait states for an AXI clock of 210–275 MHz at VOS0). 550 MHz needs an
  option byte (CPU_FREQ_BOOST) and is not used.
- *NUCLEO-G474RE*: ST's template for the board runs 170 MHz in boost mode
  with 8 wait states (`FLASH_LATENCY_8`, `STM32CubeG4`
  `Projects/NUCLEO-G474RE/Templates/Src/main.c`); RM0440 (Table 9) requires
  4 at 170 MHz in boost mode. We measure at 4, as before. It is the only
  board where the template and the manual differ.
- *The others are unchanged:* NUCLEO-G0B1RE 64 MHz with 2 wait states (ST's
  template and RM0444 Table 13 agree); nRF5340 DK 64 MHz, the reset value
  of its clock divider, which Nordic's start-up code keeps;
  Raspberry Pi Pico 2 150 MHz, with the flash clock divider of 3 that the
  boot ROM leaves and an SDK image also runs at; SAM D20 Xplained Pro
  48 MHz with 1 wait state, allowed for its part (ATSAMD20J18A-AUT, 85 °C
  grade, by Microchip's bill of materials for the board).

**The option registers are recorded.** Before each series, and each job of
it, the board's option registers are read through the debug probe without
writing anything: FLASH_OPTR on the two STM32G boards, FLASH_OPTSR_CUR and
FLASH_OPTSR2_CUR on the H723, UICR.APPROTECT and SECUREAPPROTECT on the
nRF5340, the OTP rows of its critical flags, boot configuration and boot
keys on the Pico 2, and the NVM
user row on the SAM D20 (`lab/tools/read-options.py`). The records of
method version 3 carry them (`option_registers`; record versions
`rb-bench/3` and `crc-bench/2`, [records](../../records/README.md)).

**The nRF5340's boot stub opens the debug port at every boot.** Our boot
stub copies UICR.APPROTECT and SECUREAPPROTECT into the debug access port
at start, so that the board stays reachable after a power-on
(`firmware/common/benchboot.c`). It changes only the stub's bytes: the
measured part of every image is unchanged.

**What was measured again.** A record is shown only if the tree builds its
images byte for byte (the same-image rule, DECISIONS 2026-11-22). So:
- the NUCLEO-H723ZG (new clock) and the nRF5340 DK (new boot stub) were
  measured again, ring buffers and CRC; their records before method
  version 3 are kept as archived series, checked against their own
  commit and linked from the results pages;
- on the other four boards method version 3 builds the same images byte
  for byte, so their records stand.

**What is not in method version 3:**
- *The median of a scenario's calls beside the mean* was left out
  explicitly (DECISIONS 2026-11-26): it would need every benchmark measured
  again.
- *The ISR stress test* is unchanged. Its records are of version 1 of the
  benchmark firmware and were made at the clocks of their time: on the
  NUCLEO-H723ZG at 64 MHz, the reset clock. A new stress series would run
  under method version 3.

**Cycles at another clock are not times.** At 520 MHz the H723's numbers
with the cache off are higher in cycles than at 64 MHz, while the time is
far shorter: the flash's wait states count bus cycles, and the bus runs at
half the core clock. The arithmetic is on the
[CRC method page](method-crc.md#the-nucleo-h723zg-at-520-mhz).

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

Each configuration is measured in a firmware image of its own (benchmark
version 2): the timing code is a fixed part, the same bytes in every image
of a board, and the image holds one configuration next to it, so no number
depends on which other libraries were built with it. Every configuration is
built at eight placements (the image moved by 0, 4 ... 28 bytes) and each
image is run in two passes; the pages show the value at placement 0 and the
range over all sixteen runs. A library the compiler inlines pays no call; a
library compiled on its own lies at least 6144 bytes from its caller, the
same for every library
([what the distance costs](../../reports/2026-11-23-bench-v2-far-call.md)).
`memcpy` is in the fixed part: next to the code of an inlined library, and
at that distance from a library compiled on its own, which so pays the
distance once more when it copies a block with `memcpy`. Where `memcpy`
itself lies is the same in every image and is not varied. On the three ST
boards many numbers depend on where the code lies modulo 8 bytes; the
range shows it
([report](../../reports/2026-11-23-bench-v2-placement-period.md)).
The same code and data that is in every image, the baseline, must measure
the same in every run of a board, and is recorded with each run. Design and
decisions:
[plan](../../lab/plans/2026-11-22-bench-image-per-library.md),
[DECISIONS.md](../../DECISIONS.md). In version 1, used until this replaced
it, all libraries were linked into one firmware; its records are kept as an
archived series ([records](../../records/README.md)).

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
([report of 2026-11-22](../../reports/2026-11-22-lwrb-v3.4.0-rerun.md),
[of 2026-11-20](../../reports/2026-11-20-publication-rerun.md),
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
gcc -O2 ([report](../../reports/2026-11-22-lwrb-v3.4.0-rerun.md)); earlier
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
