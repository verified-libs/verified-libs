# nrf5340-rb-stress

ISR ↔ main loop stress test of SPSC ring buffers on one Cortex-M33 core
(nRF5340 DK application core, 64 MHz, code in flash, cache on): the use
case of an interrupt-driven UART, ADC or similar.

> The published results of this test are in [RESULTS.md](../../RESULTS.md)
> and under [records/](../../records/README.md). pxq
> RingBuffer_PackedState (⚠) is written by the project owner; see
> principle 6.

## Run
On lib-lab1, with the nRF5340 DK on J2 (~10 minutes per mode):
```sh
bash run.sh single   # push/pop, one byte per call
bash run.sh block    # push_n/pop_n, several bytes per call
bash run.sh dma      # zero-copy API (acquire/commit, acquire/release)
```
Uses the library commits and adapters of
[`../nrf5340-rb-bench`](../nrf5340-rb-bench/README.md). Exit code 0 only if
the real libraries are error-free **and** the negative control was caught;
2 if the run on the board failed, 3 if the build failed, 4 if the test was
still running at the time limit (`POLL_TRIES`, default 600 polls, at least 2.5 h; two reads of the result block
20 s apart differ: too slow, not hung).
A JSON record goes to `~/lab-runs/`.

Environment: `BOARD` (nrf5340 default, stm32g0b1, stm32g474, stm32h723),
`CODE` (flash, sram, or ccm/itcm where the board has it), `PROBE` (probe-rs
selector, needed with several probes), `OPT`/`LTO` (default `-O2`, no LTO),
`STRESS_PARAMS` (seeds, prescaler, cache, transfers; see `main.c`).

The board layer (clock, cache control, the interrupt source) is in
[`../common/<BOARD>/board.h`](../common/): TIMER0 on the nRF5340, TIM2
with its update interrupt on the STM32 boards
([`../common/stm32/tim2_stress.h`](../common/stm32/tim2_stress.h)). One
timer tick is 4 << prescaler core cycles on every board. Only the nRF5340
has run so far; the STM32 boards are built, not yet run.

**DMA mode** (2026-11-07): the producer acquires a contiguous write area,
fills it and commits; the consumer acquires the read area, checks it in
place and releases it, 1–16 bytes per call in main and 1–4 in the ISR, as
in block mode. Only pxq, lwrb and ece-mohammad have such an API; the others
are reported as n/a. The negative control's write area runs to the end of
the buffer without being limited by the free space (a common linear-block
bug), which overwrites unread data whenever the buffer is nearly full.

## One library per reset (`PER_LIB=1`; 2026-11-14)
```sh
PER_LIB=1 BOARD=stm32g474 PROBE=... bash run.sh single
```
The image is flashed once; each library runs alone after a reset, and its
rows are taken from the result block read right after it
([`merge_words.py`](merge_words.py)). A library that does not finish within
`LIB_LIMIT` seconds (default 1800) is listed in the record
(`per_lib.unfinished`, `did_not_finish`), and the run is not error-free.

- **Over the serial port** (default when run.sh finds the probe's serial
  port; `UART_TTY` to name it, `UART_TTY=none` for the debug-port way):
  [`uart_host.py`](../common/uart_host.py). After a reset with no selection the
  firmware says `VLS ready N` and waits about a second for `run <n>` or
  `reset` (no command: all libraries, as before); it then resets itself,
  says `VLS start <n>`, is silent while the library runs, says
  `VLS done <n>` and waits for the next command. Polled, no interrupts,
  115200 baud. The UART per board is in `../common/<BOARD>/board_uart.h`
  (ST-LINK and EDBG virtual COM ports, the J-Link's fourth interface on the
  nRF5340 DK, the Debug Probe's UART on the Pico 2).
  After `VLS done` the host sends `dump`: the firmware returns the whole
  result block (`VLS words N`, the words in hex, `VLS crc C`, zlib's
  CRC-32), the same words a debug-port read gives; a failed CRC is asked
  for again (three times), then the block is read over the debug port.
  Default on every board (`UART_DUMP=0`: debug port). The nRF5340 DK
  needs a current J-Link OB firmware: with the firmware it shipped with,
  its virtual COM port stopped passing data after 0-207 dumps of about
  6 kB in a row (also at 9600 baud, also on a port of the PC instead of the
  hub) until the probe was reset over USB or power-cycled, while the nRF
  kept running. After the update J-Link Commander offers
  (`J-Link OB-K22-NordicSemi compiled Oct 30 2023`) 1000 of 1000 dumps
  passed. The record says
  which (`per_lib.results_read`). Checked 2026-11-14 with
  `VLS_SWD_CHECK=1` (both ways, compared word for word): single and sweep
  on all six boards (Pico 2 also sweep-smp), identical.
- **Over the debug port**: run.sh writes the selection into the last words
  of the result block, resets the board and polls `done` every `LIB_POLL`
  seconds.

Board notes found while making it work:

- **STM32H723**: the last RAM writes before a reset can be lost (the write
  buffers of the ECC RAM); the firmware writes once more to both DTCM banks
  and reads back before it resets itself.
- **RP2350**: the boot ROM uses SRAM, so the selection is kept in the
  watchdog's scratch registers 0-2 (`BOARD_SELECT_ADDR`); a reset through
  AIRCR does not reset core 1, so `board_core1_launch` resets it through the
  PSM first; after `probe-rs download` the core stays halted for about a
  minute. Since 2026-11-16 the startup code (`common/rp2350/startup.c`)
  also resets core 1, before it writes any memory: until then core 1 went
  on running the previous library's code while core 0 copied the next
  image's code over it (code in SRAM), cleared .bss and started the
  library, and could write into all of that. Found in the campaign of
  2026-11-15/16: in the three SMP runs with code in SRAM, rigtorp
  SPSCQueue (right after Contiki-NG) got every byte wrong and jnk0le
  (right after AndersKaloer) did not finish; alone, the same image passed,
  and after Contiki-NG the failure came back every time, until this
  reset. Not an error of these libraries; those runs are not counted for
  them (summarize.py).
- A stray zero byte can arrive around a reset; the firmware ignores control
  characters.

Checked 2026-11-14 on all six boards in every mode (short runs,
`TRANSFERS=20000`, `SWEEP_REPS=16`): every library finished, real libraries
error-free, negative control caught. The old way still works with the
UART firmware (G474 single/sweep, Pico 2 smp/sweep-smp). Faster: an
interrupt sweep took 203 s instead of 626 s on the G474, 177 s instead of
1229 s on the Pico 2 (sweep-smp).

## One image, run parameters over the serial port (2026-11-15)
Since 2026-11-15 one image holds every mode (single, block, dma, each also
as sweep, and smp on the Pico 2). With `PER_LIB=1` over the serial port
(`PARAMS_AT_RUNTIME=1`, the default there) run.sh no longer compiles the
mode and the run parameters in: after `VLS start <n>` the host sends

```
go mode=2 sweep=1 smp=0 main_seed=0x1234abcd isr_seed=0x0badf00d prescaler=2 cache=0 reps=256
```

(`mode` 1 single, 2 block, 3 dma; `transfers` for the random stress, `reps`
for the sweep; names left out keep the build's defaults, decimal or `0x`
hex). The firmware answers `VLS go` with every parameter (`name=0x%08x`),
which uart_host.py compares with what it sent; a line that is not a valid
`go` gets `VLS error bad params`, and the library is not run. Either way the
host resets and tries once more. Without a `go` within about a second the
build's defaults apply, so the old `-D` flags still choose the defaults
(and are the only way with `PARAMS_AT_RUNTIME=0`, the debug-port control).
Code location, compiler and optimisation stay build-time choices.

- overnight.sh is unchanged: run.sh takes `MAIN_SEED`, `ISR_SEED`,
  `TIMER_PRESCALER`, `CACHE_ON`, `TRANSFERS` and `SWEEP_REPS` out of
  `STRESS_PARAMS` and sends them; other `STRESS_PARAMS` stay build flags.
- Every rotation entry with the same code location and compiler flags now
  runs the same image (same `fw_sha256`), and `probe-rs download
  --preverify` (OpenOCD `program ... preverify` on the SAM D20) does not
  write it again when it is already on the board.
- Records: `params_at_runtime`, `run_params` (the `go` line),
  `run_params_confirmed` (the answer), `build_flags` (only what was compiled
  in). The parameters in `params` still come from the result block, i.e.
  what the firmware used.
- The test code around the libraries changed a little: the mode is chosen
  once per interrupt, per main loop or per sweep call (`switch` on the mode,
  each case with its own inlined copy of the transfer code), and the
  result block always has room for the sweep part. The libraries' own code
  is built as before. Results before and after 2026-11-15 are therefore
  two methods and are not pooled.
- The negative control's smp variant: broken.c used to widen its window
  (16 loop turns) when built with `SMP_MODE`; with one image both variants
  are built and main.c takes `adapter_broken_smp` when `smp=1`. Without
  that the control was never caught on two cores (found in the first
  validation, 2026-11-15). The interrupt-mode control compiles as before
  (one equality compare with its operands swapped).
- The `go` line goes out in 16-byte pieces: the SAM D20's EDBG lost a
  130-byte line written at once.
- Validated 2026-11-15: every mode on all six boards (`TRANSFERS=20000`,
  `SWEEP_REPS=16`, serial dump checked against the debug port), non-default
  parameters confirmed and used, the same `fw_sha256` for every mode of a
  board; after the fixes above `check.sh full` on the Pico 2 (10 modes) and
  `check.sh medium` on all six boards passed.

Faster runs (2026-11-15):

- **Build key** (run.sh): the image is reused when the toolchain image, the
  make arguments, the pinned libraries and the sources are unchanged
  (`build/build.key`, which also holds the image's sha256; `REBUILD=1`
  forces a build).
- **fetch-libs.sh** fetches a library only when its pinned commit is not
  there yet (a fetch for every library on every run cost about 20 s).
- **After a skipped flash** the board is not reset; uart_host.py sends
  `reset` over the serial port instead of waiting 90 s for `VLS ready`.
- **SAM D20**: OpenOCD `program` left the core halted (also before
  2026-11-15), and the firmware only started at a later debug access, about
  90 s lost per run and likely the occasional `no 'VLS ready'` of the
  campaigns; the stand-in now programs with `reset`.

A quick check of two libraries and the control took about 5 minutes per
mode before and 15-40 s after; `check.sh medium` on all six boards about 10
minutes.

## One image per library, flashed once (`IMAGES=per_lib`; 2026-11-15)
Since 2026-11-15 (with `PARAMS_AT_RUNTIME=1`, i.e. over the serial port)
each library is tested in an image of its own: the test harness (main.c,
startup, board code) linked with that library's objects alone (`make
ONLY=<n>`, main.c `ONLY_LIB`: the other libraries are weak references,
null in the table, and their code is not in the image). A library that is
added, changed, held back or fails to build cannot change another
library's image, and each library's result can be checked against an image
that holds only its code (records: `images.libs.<n>.sha256`).

Flashing one image before every library would wear out the flash: the
boards are rated for 10k erase cycles (nRF5340, STM32G4/H7, and by the
datasheets' reading also the G0B1), and a campaign runs every library many
times a day. So [`../common/bundle.py`](../common/bundle.py) puts all images
side by side in flash, each linked for its own place ("slot", 4 KB aligned),
with a boot stub ([`../common/slotboot.c`](../common/slotboot.c), about 100
bytes, at the start of flash) that starts the image the selection words
name after each reset (`run <n>` as before; no selection: the first image,
which says `VLS ready`). The stub sets no clock or peripheral and uses no
RAM but a few words of stack, so each image starts as from a reset.

- **Flashed only when an image changes.** uart_host.py remembers per probe
  what the board holds (`~/.cache/verified-libs/flash/`): the same bundle is
  checked with `--preverify` and not written; a new build writes only the
  slots whose image changed (each on its own, `--restore-unwritten`), then
  checks the whole bundle. A campaign therefore writes nothing; a change to
  one library during development erases its few pages; a change to the
  harness rewrites every slot once.
- **Sizes**: 8-10 KB per image (Rust: 18 KB); one bundle of 480-520 KB on
  the nRF5340, G0B1, G474, H723 and RP2350. The SAM D20's 256 KB hold two
  bundles (21 and 19 libraries): a run flashes the one not on the board
  (once per run; it starts with the bundle already there).
- **Addresses**: the images lie in index order, so a library's slot moves
  only when an image before it grows or shrinks across a 4 KB boundary.
  The record has every image's address and sha256 (`images`), and
  `fw_sha256` is that of `bundle.json`; verify-build.sh rebuilds the bundle
  and names the libraries whose image differs.
- **Interrupt sweep coverage** comes per library from its own block and its
  own image (`sweep.per_library`; `sweep.functions` entries name their
  `library`); recompute_coverage.py rebuilds the bundle for it.
- **SAM D20 with EDBG firmware 3.25** (updated from 1.0f, 2026-11-15): after
  the firmware's own reset (`run <n>`) the chip stays in reset until the
  next debug access (the DSU's CPU reset extension; the EDBG now holds SWCLK
  low between sessions). uart_host.py then resets it through the debug port,
  which keeps the selection in RAM (after the first time without waiting).
  The EDBG still loses a long line written at once: the 16-byte pieces stay.
  Switching between its two bundles costs about 110 s (OpenOCD over the
  EDBG's HID link writes about 2.5 KB/s) and one erase cycle of the flash
  per run; runs start with the bundle already on the board.
- `IMAGES=one` builds the old single image (also the only choice with
  `PARAMS_AT_RUNTIME=0`). Results with one image per library are a new
  method again and are not pooled with earlier ones.
- Validated 2026-11-15: `check.sh medium` (all 40 libraries, single and
  sweep) passed on all six boards; quick checks on the G474, H723, Pico 2
  and SAM D20 after the fixes above; a change to one adapter rewrote only
  that library's slot (Pico 2: "1 of 40 images written"), and an unchanged
  bundle is only verified (H723: 1.3 s).

## Quick checks: a few libraries (`LIBS`; 2026-11-15)
```sh
LIBS=11,40 PER_LIB=1 BOARD=stm32g0b1 PROBE=... bash run.sh single
```
runs only libraries 11 and 40 (indices into `decode.py`'s `LIBS`) and the
negative control, which is always added. The other libraries are not run:
the record names them (`not_run`, `per_lib.not_run`) and is marked
`"partial": true`; they never count as passed. Over the serial port only.
Campaigns refuse `LIBS` (overnight.sh), and the site skips partial records
(`site/collect_records.py`).

Test levels during development:

| level | what | time |
|---|---|---|
| quick | the libraries touched + the control, `single` and `sweep`, 2-3 boards | 1-3 min |
| medium | all libraries, `single` and `sweep`, all boards in parallel, `TRANSFERS=20000 SWEEP_REPS=16` | 10-15 min |
| full | every mode on every board, short parameters | about 1 h |

Quick while working on a library or adapter, medium before a commit that
touches the firmware in general, full when the test method itself changes.
Our lab's `check.sh quick|medium|full [BOARD...]` (not published) runs a level on several boards in parallel, each from its own
copy of the working tree and under a lock per board, and prints one line
per board and mode (records in `~/lab-runs/check-<stamp>/`).

## Interrupt sweep (`sweep`, `sweep-block`, `sweep-dma`; 2026-11-12)
```sh
bash run.sh sweep         # one byte per call
bash run.sh sweep-block   # push_n/pop_n
bash run.sh sweep-dma     # zero-copy API
```
The random stress hits a short race window only by chance; at slow
interrupt rates on fast cores it often missed even the negative control.
The sweep places the interrupt deterministically instead:
- SysTick (core clock, the same registers on every Cortex-M, all six
  boards) is armed as a one-shot with reload `d` just before main's push or
  pop, and the handler does one call of the other side (pop or push), then
  stops it. `d` runs 1, 2, 3, … until the interrupt has come after the call
  returned 16 times in a row, so the interrupt lands before every
  instruction of the call, including the call's entry and return.
- Each sweep is repeated with the buffer empty, holding one byte, half
  full, one short of full and full (capacity measured at start), and from
  `SWEEP_REPS` start positions (stream position = r mod 256, r = 0 …
  `SWEEP_REPS`−1; default 16, the campaign uses 256), so wrap-around meets
  every delay.
- The data check is the one of the random stress; "irqs" counts trials,
  `interrupted_during_call` how many of them interrupted the call itself.
- **Count check (since 2026-11-12 evening):** after each delay sweep the
  buffer is drained one byte at a time (each byte checked) and the number
  of bytes must be exactly produced − consumed. A mismatch counts as an
  error and in `count_mismatches`: bytes lost or duplicated in any number,
  also a multiple of 256, which the stream check modulo 256 cannot see.
  The record also has the size: `count_bytes_lost` and `count_bytes_extra`
  (summed over the mismatched drains) and `count_first_mismatch` (bytes
  drained and expected the first time).
- **Coverage, measured:** the handler takes the interrupted PC from the
  exception frame and sets its bit in a bitmap (one bit per halfword, 64 KB
  of code). `decode.py` maps the bitmap onto the disassembly (`fw.lst`,
  `fw.map`) and reports per function how many instructions were the
  interrupted PC, how many are inside masked sections (flow-sensitive:
  `cpsid`/`cpsie`, `mrs`/`msr PRIMASK` pairs, calls to lock helpers;
  instructions between two indirect calls that were never interrupted count
  as "probably masked", e.g. ETL's virtual lock/unlock) and which were not
  interrupted. The latter include instructions on paths that the sweep never
  executes (a split copy at wrap-around in single-byte mode, long `memcpy`
  paths), so "not interrupted" does not by itself mean "missed". The record
  keeps the raw bitmap (`sweep.bitmap_hex`), so the analysis can be rerun on a
  rebuild of the same commit and flags. [`recompute_coverage.py`](recompute_coverage.py) does
  that: it rebuilds the record's firmware from a given source tree in a
  temporary copy (same board, flags, compiler and image), refuses unless the
  new `fw.elf` has the record's `fw_sha256`, and maps the bitmap with the
  current analysis (checked 2026-11-12: a campaign record rebuilt from a
  worktree at its commit matched byte for byte). Records name their source
  commit (`source_commit`, from `lab/tools/source-commit.sh`; campaign
  copies get it from the `COMMIT` file `night-all.sh` writes). `test_decode.py` holds regression
  tests for the analysis (`python3 -m unittest test_decode`, host only);
  before 2026-11-12 evening the target of `cbz`/`cbnz` was misread, so on
  the Thumb-2 boards code behind such a branch inside a critical section
  counted as "not interrupted" instead of masked, and on the RP2350
  (addresses with 8 digits, no leading blank in the listing) no instruction
  was found at all, so its records have no per-function coverage (records
  up to commit 93b6512).
- **SMP sweep (`sweep-smp`, `sweep-smp-block`; RP2350; 2026-11-12):** core 1
  instead of SysTick. Core 0 starts each trial with a flag, waits a fixed
  lead (`SWEEP_SMP_LEAD`, about 300 cycles) and makes its call; core 1 waits
  d steps of about one cycle after it sees the flag (d = 0, 1, 2, ...: d / 4
  turns of a short loop and d % 4 NOPs) and makes the other side's call. So
  core 1's call starts ahead of core 0's and moves through and past it. The
  flag's latency between the cores varies by a few cycles, so the steps are
  approximate and the start positions spread them. No coverage bitmap (core
  1 does not interrupt core 0), and 'interrupt inside the call' also counts
  the trials where core 1 was ahead. In the campaign, every second pass on
  the Pico 2 runs sweep and sweep-block this way, as single and block
  already alternate with smp and smp-block.
  The first version (no lead; core 1 polled its cycle counter) found no
  single-byte race at all, not in the unsafe variants and not in the
  mutants: core 1 was always the later one, and moved in steps of its
  polling loop. The mutants showed it on the first board run (2026-11-13);
  with the lead and the one-cycle steps every mutant and every single-core
  design is caught in both directions, in single-byte and block mode.
- **Two interrupts per call (`sweep2`, `sweep2-block`, `sweep2-dma`;
  `go sweep=2`; 2026-11-15):** the first interrupt at every delay d1 as
  above; while it lands inside the call, its handler arms SysTick again
  with g, so a second interrupt (a second call of the other side) comes
  about g cycles after the first handler returned, for g = 1, 2, 3, ...
  until the second has come after the call `SWEEP_TAIL` times in a row.
  Every pair of interrupt points inside the call is so tried (the second
  no earlier than one handler's length after the first), e.g. a consumer
  that empties the buffer and a producer that refills it between main's
  read and its write. 'Interrupt inside the call' counts the trials with
  both inside; both interrupted PCs go into the coverage bitmap. Not with
  smp. Far more trials than one interrupt per call: check.sh runs it with
  2 start positions (a few seconds per library).
- **Fix found with it (2026-11-15):** with a short reload SysTick could run
  out again between the exception entry and the handler's stop, which left
  a second interrupt pending: an extra, unplanned call of the other side
  right after the first (seen as three interrupts in two-interrupt trials).
  The handler and the arming now stop the timer and clear its pending bit
  (ICSR.PENDSTCLR), and an interrupt after a trial's end does nothing. In
  the one-interrupt sweep this could happen only at the smallest delays;
  records before this fix may have such extra calls there.
- What it does not cover: three or more interrupts within one call,
  hardware reordering on one core (an interrupt sees program order).

## Method
For each library and both directions:
- **isr_to_main:** a TIMER0 interrupt pushes a byte sequence 0, 1, 2, …
  (mod 256), the main loop pops and checks it.
- **main_to_isr:** the main loop pushes the sequence, the interrupt pops and
  checks it.

The producer advances only by what was actually pushed; the consumer checks
that every byte is the next expected one, so any lost, duplicated,
reordered or torn byte is an error. 300 000 bytes per library, direction
and mode.

- **Modes:** `single` uses `push`/`pop`. `block` uses `push_n`/`pop_n` with
  a random length per call: 1–16 bytes in the main loop, 1–4 in the ISR
  (the ISR moves less per interrupt, so the main loop can outpace it and
  the buffer runs full and empty from both sides).
- **Random preemption points:** the interrupt period is random
  (xorshift32, fixed seed) between 40 and 167 timer ticks (16 MHz, i.e.
  160–668 CPU cycles), so the interrupt lands at different instructions of
  the main-loop side.
- **Full and empty paths:** the main loop alternates fast and slow phases
  of 4096 bytes (random busy waits). `full`/`empty` in the tables count
  failed pushes and pops, i.e. how often the buffer was found full or
  empty.
- **ISR API:** ETL queue_spsc_isr uses `push_from_isr`/`pop_from_isr` in the
  interrupt and its locking `push`/`pop` in the main loop, as documented.
  All other libraries use the same calls on both sides.
- **Negative control `broken`:** publishes the new head before writing the
  data, and releases slots before reading them. The test must catch it
  (see "Findings" for where each bug can show).
- **Mutants ([`mutants.c`](mutants.c), since 2026-11-12):** four more broken
  buffers, one common bug class each: a fill counter shared by both sides
  and changed with a plain `++`/`--` (`shared count, no lock`); the same
  with the lock only in push (`pop without lock`, can only show when main
  pops); a full test without the index wrap (`full test misses the wrap`,
  a sequential bug that needs the full state at one position); a pop that
  "drains" by setting tail to a second read of head (`drain re-reads head`,
  can only show when main pops). They do not decide whether a run counts
  (the control does); `decode.py` reports per direction whether each was
  caught (`mutants_caught` in the record) and the summaries count it per
  mode, which measures what each mode can find. No zero-copy API: n/a in
  the `dma` modes.
- The timer runs in 8-bit mode: if it misses a compare (the debugger can
  halt the core while the timer keeps running), it wraps within 16 µs.

## Results (2026-11-06, 20 adapters)
Errors per run (300 000 bytes each). "Full reached" = the buffer was found
full in main_to_isr at least once in block mode (the hardest state to reach;
see Findings for the exceptions).
JSON records: `nrf5340-rb-stress-single-20261106T212351Z.json`,
`nrf5340-rb-stress-block-20261106T205817Z.json`.

| Library | single isr→main | single main→isr | block isr→main | block main→isr | Full reached (block main→isr) |
|---|---|---|---|---|---|
| pxq RingBuffer_PackedState ⚠ | **0** | **0** | **0** | **0** | yes |
| lwrb v3.3.0 | **0** | **0** | **0** | **0** | 2× |
| AndersKaloer Ring-Buffer | **0** | **0** | **0** | **0** | yes |
| jnk0le Ringbuffer | **0** | **0** | **0** | **0** | yes |
| ETL queue_spsc_isr | **0** | **0** | **0** | **0** | yes |
| ETL queue_spsc_atomic | **0** | **0** | **0** | **0** | yes |
| QuantumLeaps LFRB | **0** | **0** | **0** | **0** | no |
| Embedded Artistry cbuf (threadsafe) | **0** | **0** | **0** | **0** | no |
| ece-mohammad RingBuffer | **0** | **0** | **0** | **0** | yes |
| micoring (SPSC mode) | **0** | **0** | **0** | **0** | no |
| kostyk348 lf_spsc | **0** | **0** | **0** | **0** | no |
| diffstorm cb | **0** | **0** | **0** | **0** | no |
| RIOT tsrb | **0** | **0** | **0** | **0** | yes |
| Contiki-NG ringbuf | **0** | **0** | **0** | **0** | no |
| rigtorp SPSCQueue | **0** | **0** | **0** | **0** | no |
| wizard97 + PRIMASK macros | **0** | **0** | **0** | **0** | no |
| polycratia spscring | **0** | **0** | **0** | **0** | yes |
| rt-spsc | **0** | **0** | **0** | **0** | yes |
| *wizard97 as shipped (no ISR protection)* | *3 995* | *4 267* | *12 352* | *13 801* | – |
| broken (control) | 0 | **6 082** | **1 890** | **3 204** | – |

Interrupts per run: 0.7–1.4 million (block), 5–11 million (single).
## Findings
- **18 library configurations: no errors** in either direction, with single
  bytes and with blocks, over 0.7–11 million interrupts per run, with the
  buffer regularly found full and empty under preemption.
- **wizard97 as shipped fails, as its own header warns.** Off AVR/ESP8266,
  RB_ATOMIC_START/END are empty and the header prints *"Operations on the
  buffer in ISRs are not safe! Implement RB_ATOMIC_START and RB_ATOMIC_END
  macros"*; the shared element counter is then updated from both sides
  without protection. With the macros implemented (PRIMASK), 0 errors. The
  test confirms both the warning and the documented fix. Reported as a
  documented limitation, not as a defect.
- **diffstorm cb passes here but has two defects** found by GenMC and a host
  reproducer (see [../../verify/findings](../../verify/findings/)): its
  overwrite flag can turn on by itself when the object was not in zeroed
  memory (here it is a zeroed static, so it does not show), and its consumer
  lacks acquire ordering (irrelevant on one core).
- **The test catches both kinds of ordering bug** in the control: head
  published before the data (caught whenever the buggy producer is the
  preemptible main loop), and slots released before they are read (caught
  in block mode).
- **Releasing one slot before reading it is harmless in a sacrificed-slot
  ring buffer.** With single bytes the control's pop bug never showed
  (0 errors, even with an ~800-cycle window in an earlier run): when the
  buffer is full, head = t − 1, so the producer can only fill slot t − 1
  and the buffer is full again before slot t can be touched. With blocks
  (several slots released at once) the same mistake causes errors.
- **AndersKaloer Ring-Buffer** has no `volatile` or atomics. In this build
  the compiler keeps the safe store order (data before head, read before
  tail), so it passes; that order is not guaranteed by the language and may
  change with another compiler, flags or LTO. Its `ring_buffer_queue`
  overwrites the oldest byte when full (moving the tail from the producer
  side, not SPSC-safe); the adapter avoids that with a space check.
- **Coverage gap (main_to_isr, buffer full):** in block mode eight
  configurations never found the buffer full and lwrb only twice (see table);
  in single-byte mode lwrb and micoring never did. These are the libraries
  whose calls (or loop-based `push_n`) are slow enough that the main loop
  cannot outpace the interrupt. All other directions and modes reached both
  full and empty for every library. To close it: a lower interrupt rate for
  slow libraries.

## Overnight campaigns ([`overnight.sh`](overnight.sh))
Repeats the stress test unattended for N hours (default 8), varying the
settings every run:
- new random seeds for main-loop pauses and interrupt periods;
- a rotation of 17 settings (see `overnight.sh`): since 2026-11-12 six
  interrupt-sweep entries replace the two prescaler-4 single-byte entries
  and the two prescaler-2 block entries, the same on every board; the rest
  vary mode (single/block/dma), interrupt rate (timer prescaler 0/1/2: an
  interrupt every 160–668, 320–1336 or 640–2672 cycles), instruction cache
  on/off and code in flash/SRAM.
  Slower rates move fewer bytes (300k/200k) to keep runs at ~10–30
  minutes, and they let slow libraries fill the buffer (the coverage gap
  above).

Each run's parameters are compiled in (`-DMAIN_SEED` … `-DCACHE_ON`,
`LDSCRIPT`) and reported back by the firmware, so the JSON record states
what actually ran. A run is valid only if its negative control was caught;
a run that does not finish is recorded and the campaign continues.

Hung boards are power-cycled through a monitor hub port
([`lab/tools/boardpower.sh`](../../lab/tools/boardpower.sh), ports in
[`lab/boards.conf`](../../lab/boards.conf)). Before each run the probe must
be on USB, otherwise the board is power-cycled first. When a run fails on the
board (`run.sh` exit 2: probe or flash error, or not finished) the board is
power-cycled and the same settings and seeds run once more, as run `<n>r`; a
failed build (exit 3) and a run that was still running at the time limit
(exit 4) are not retried. The campaign stops early if the probe
does not come back, or after `MAX_FAILS` (default 3) failed runs in a row.
Output: `~/lab-runs/overnight-<UTC>/` with one JSON per run, `runs.tsv`,
`campaign.log` and `report.md` from [`summarize.py`](summarize.py)
(can be run any time during the campaign). For the six boards of one night
(`lab/tools/night-all.sh`), [`summarize_all.py`](summarize_all.py) gives one
report: per board, valid runs per configuration and board, errors per
library, and the interrupt sweep (`python3 summarize_all.py` takes the newest
campaign of each board; or pass the directories).

```sh
nohup setsid bash overnight.sh 8 > /dev/null 2>&1 < /dev/null &   # detached
MAX_RUNS=2 TRANSFERS_OVERRIDE=2000 bash overnight.sh 1            # smoke test
```
Smoke tests with < 4096 bytes never reach the slow phase, so their control
is not caught and they are correctly reported invalid.

First campaign (2026-11-06/07, 8 h, 32 runs): 24 valid, 0 errors in every real library; 5 runs invalid (prescaler 4 in block mode), 3 starved (cache off with prescaler 0). See [the report](../../reports/2026-11-07-overnight-campaign.md); the rotation and a starvation cap were changed accordingly.

## Not covered yet
- Nested interrupts, two producers (MPSC), DMA hardware as the producer
  (DMA mode uses the CPU in the ISR in its place).
- Cross-core use (application core ↔ network core), where ordering needs
  barriers, not just single-core preemption.
- clang; `-Os`, `-O3` and LTO are build parameters now (`OPT`, `LTO`).
