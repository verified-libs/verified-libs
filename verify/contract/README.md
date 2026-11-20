# One-core contract check

Is a ring buffer correct as an interrupt ↔ main queue on **one core**, for
**every instruction** at which the interrupt can come, from **every start
state** of a small buffer?

This is the check for the libraries that [GenMC](../genmc/README.md) cannot
judge: pxq RingBuffer_PackedState, lwrb without atomics, RIOT tsrb, Contiki,
the interrupt-lock designs and others rely on one core (volatile indices,
compiler barriers, interrupt masking) instead of C/C++ atomics. Under the
C/C++ memory model, which GenMC checks with free-running threads, such code
always has data races, whether or not it is correct for its contract. Here
the contract itself is executed.

## How
- **The interrupt at every instruction.** Main's call runs with the x86
  trap flag set, so the CPU stops after every instruction (SIGTRAP). At the
  chosen instruction the signal handler makes the interrupt's call, which
  runs to completion there: an interrupt on one core, at instruction
  granularity, in the library's own code (compiled for the host).
- **Interrupt masking.** PRIMASK becomes a flag ([`host_irq.h`](host_irq.h)):
  an interrupt point inside a masked section is held pending and taken
  right after the unmask, as on a Cortex-M. [`hostify.py`](hostify.py)
  makes a copy of the benchmark tree in which the Cortex-M instructions in
  inline assembly (`mrs/msr primask`, `cpsid/cpsie i`, `mrs ipsr`,
  barriers) become calls of that flag; nothing else changes, and the
  originals are never written. The libraries are then built from that copy
  with the benchmark's own rules (`libs.mk`) and adapters
  ([`Makefile.host`](Makefile.host)); pxq's locking topologies use a host
  lock in [`pxq_host.cpp`](pxq_host.cpp).
- **Every start state:** a buffer of `RB_SLOTS` = 8 slots, every start
  position (0-7) and every fill level (empty to full); with two interrupts
  in one call (every pair of points, quadratic in the call's length) the
  start positions 0 and 7 (the wrap) with the buffer empty, holding one
  byte, one short of full and full. Before each trial
  every slot is overwritten with 0xEE, so a slot read before it was written
  shows.
- **Calls:** main push / interrupt pop and main pop / interrupt push, two
  interrupts in one call (every pair of instruction points), blocks
  (push_n(3) / pop_n(2)), and where a library has a zero-copy API its
  acquire / write / commit and acquire / read / release, on either side; for MPSC, SPMC and MPMC also two producers or two
  consumers.
- **Verdict:** the result (return values, bytes popped, what is left,
  drained) must be one that the calls give one after the other: main's call
  before, between or after the interrupt's calls (linearisable), where a
  block may become visible byte by byte (any split of main's block with the
  interrupt's call between the parts). For single-byte calls the result
  must also be an ideal FIFO's, so a sequential bug fails too (not for
  bbqueue, whose push may be refused while there is room: a grant must be
  contiguous).
- **Controls:** the negative control (`broken.c`) and the four mutants
  (`mutants.c`) of the stress test must fail; otherwise the run fails.

What it does not check: what a compiler for the target makes of the code
(that is the hardware interrupt sweep of
[`../../firmware/nrf5340-rb-stress`](../../firmware/nrf5340-rb-stress/README.md),
on the real machine code of six cores), and more than one core.

## Run
On lib-lab1 (x86-64 Linux, host g++; no board, no toolchain image):
```sh
bash run.sh                       # every library; exit 0 if every verdict is as expected
CONTRACT_DOUBLE=0 bash run.sh     # one interrupt per call only (about 2 minutes)
bash run.sh "pxq SPSC" "lwrb"     # some
```
For the comparison page: `python3 summary.py build/full-double.txt --json
../../site/data/contract.json` (then `site/gen_libdata.py`); it accepts only a
run that ended with `exit 0`.

The Rust libraries are built for the host with the toolchain image's cargo
(offline), their critical section on the same flag
(`../../firmware/rust-adapters/src/cs.rs`, `--cfg vl_host`; the firmware
builds do not set it).

## Results (2026-11-15, libraries as pinned in libs.lock, pxq 1.5.0)
One interrupt per call, every library: the 29 configurations that document
interrupt safety pass, among them pxq in SPSC, MPSC, SPMC, MPMC and MPSC
with its new producer reservations (reserve/commit, 1.5.0). The control and
all four mutants fail, each with the right diagnosis (full_nowrap: not what
an ideal FIFO gives, a sequential bug; the others: no order of the calls
gives the result). The three configurations whose own documentation does
not claim interrupt safety fail, as on the boards: wizard97 as shipped and
Arduino RingBufferN as shipped (shared counter updated by both sides; the
hardware stress test finds errors in both too) and RT-Thread rt_ringbuffer
without a lock: with a full buffer at the wrap, an interrupt that pops 2
bytes in the middle of main's put of 3 lets main see the read index after
and the mirror bit before the pop (or the reverse), so main puts 3 bytes
into 2 free slots: one byte is overwritten and the buffer then holds 9
entries in 8 slots. That window is a few instructions long at one start
state; the boards have not hit it in the stress test so far. The variant
with RT-Thread's interrupt lock (as its serial driver uses it) passes.
`CONTRACT_VERBOSE=1` prints the first failing trial of each configuration
with the result it got and the results that were allowed.

Full run with two interrupts per call and the zero-copy calls (2026-11-16,
about 8.0 million trials, `build/full-double.txt`): every verdict as
expected (exit 0). All 37 configurations that document interrupt safety
pass, the four Rust
ones included (heapless spsc and mpmc, bbqueue, embassy-sync Pipe), and pxq
in SPSC, MPSC, SPMC, MPMC and MPSC with reserve/commit (508 309 trials); the
control, the four mutants and the three configurations that are not
interrupt-safe by their own documentation fail.
