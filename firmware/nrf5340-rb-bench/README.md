# nrf5340-rb-bench

Cycles per call for push/pop of single bytes and of blocks, on the nRF5340
DK application core (Cortex-M33, 64 MHz), per library, with the instruction
cache off and on.

> **Status: harness development, not a published result.** One of the two
> libraries, pxq RingBuffer_PackedState, is written by the project owner.
> Under principle 6 it is tested with the same suite as the others and more
> (every documented mode and topology), its numbers can be repeated outside
> the project like every result, and the conflict of interest is labelled
> wherever they appear (⚠).

## Run
On lib-lab1, with the nRF5340 DK on J2:
```sh
bash run.sh
```
It fetches the libraries at the commits in [`libs.lock`](libs.lock) (they
are never copied into this repo), builds in the pinned toolchain image, and
for each code location (flash, then SRAM; `bash run.sh flash` for one)
flashes, waits, reads the result block with probe-rs, and writes a JSON
record to `~/lab-runs/` (code location, firmware SHA-256, library commits,
toolchain versions, probe-rs version, code sizes, all statistics).

Environment: `BOARD` (nrf5340 default, stm32g0b1, stm32g474, stm32h723),
`PROBE` (probe-rs selector, needed with several probes), `OPT`/`LTO`
(default `-O2`, no LTO; other flags give records with a suffix such as
`flash-Os` or `flash-O2-lto`). The startup code is never built with LTO.

### Boards (2026-11-07)
The directory name is historical: `main.c` gets the board from
[`../common/<BOARD>/board.h`](../common/) (init, clock, cache control,
counter check and `time_call` itself). Result layout version 6 adds the
clock, the board id, the counter read overhead and an empty-call
calibration, so the overhead assumed per board can be checked on the board.

| Board | Core, clock | Counter | Code locations | "Cache" | Status |
|---|---|---|---|---|---|
| nRF5340 DK (`nrf5340`) | Cortex-M33, 64 MHz | DWT CYCCNT | flash, sram | instruction cache | runs |
| NUCLEO-G0B1RE (`stm32g0b1`) | Cortex-M0+, 64 MHz (HSI16 + PLL) | SysTick (24-bit, counts down) | flash, sram | flash ICEN + prefetch | built, board on order |
| NUCLEO-G474RE (`stm32g474`) | Cortex-M4F, 170 MHz (boost) | DWT CYCCNT | flash, sram, ccm | ART: ICEN + DCEN + prefetch | built, board on order |
| NUCLEO-H723ZG (`stm32h723`) | Cortex-M7, 64 MHz (reset HSI) | DWT CYCCNT | flash, sram (AXI), itcm | L1 I- and D-cache | built, board on order |

Register addresses come from ST's cmsis-device headers (pinned commits in
each `board.h`); the clock procedures follow ST's reference manuals and
HAL and are still to be checked on the boards. The H723 runs at its reset
clock until the supply configuration of the board is known (a wrong
SMPS/LDO setting can lock the chip).

## Method
Byte ring buffer with 128 slots (127 usable) for every library.

| Scenario | Pattern | Buffer fill |
|---|---|---|
| single | 1024 × (push 1 byte, pop 1 byte) | 0–1 |
| burst16 | 64 × (16 pushes, then 16 pops) | 0–16 |
| block4 / 16 / 64 | 1024 × (push N bytes in one call, pop N in one call) | 0–N |

- Block scenarios start one slot into the buffer, so some transfers are
  split at the wrap and some are not, as in real use.
- Every popped byte is checked against what was pushed.
- Every call is timed by `time_call` (assembly), so the timed window is
  identical for every operation and library:
  `ldr t0, CYCCNT ; blx op ; <op> ; ldr t1, CYCCNT`. The 1-cycle CYCCNT read
  overhead is subtracted. The window includes the indirect call and the
  adapter function. The **baseline** row (one store/one load, or one
  `memcpy` each way) shows that floor; it is not a FIFO, so its errors are
  not checked.
- Per library: all scenarios with the cache off, then the cache is
  invalidated and enabled and all scenarios run again.
- The firmware rejects a run if CYCCNT stalls (see "Pitfalls").

Configuration (all fetched at the commits in `libs.lock`):
- pxq-dk/RingBuffer-Cortex `312c421a8f61` (v1.3.2),
  `RingBuffer_PackedState<uint8_t, 128, Topology::SPSC<>>`, `push`/`pop`,
  `push_n`/`pop_n`. Header-only; the library forces `-Os` on its functions.
- MaJerle/lwrb v3.3.0 (`413b7093dcad`), default configuration (C11 atomics),
  `lwrb_write`/`lwrb_read`.
- AndersKaloer/Ring-Buffer `8de8fff55a0b`: `ring_buffer_queue`/`_dequeue`,
  `_queue_arr`/`_dequeue_arr`. `ring_buffer_queue` overwrites the oldest
  byte when full (moving the tail from the producer side, not SPSC-safe),
  so the adapter checks for space first.
- jnk0le/Ring-Buffer `9efa07fffc0f`: `Ringbuffer<uint8_t, 128>` (default
  `fake_tso = false`), `insert`/`remove`, `writeBuff`/`readBuff`. Holds 128
  (unmasked indices); the others hold 127.
- ETLCPP/etl 20.49.0 (`7d604f2e4f7f`): `queue_spsc_isr<uint8_t, 128, Access>`
  (main-loop calls disable interrupts via `Access`, the ISR uses
  `push_from_isr`/`pop_from_isr`) and `queue_spsc_atomic<uint8_t, 128>`. No
  block API: `push_n`/`pop_n` loop over single calls. Constructed with
  placement new (their destructors would otherwise register `atexit`).
- Wave 2 (QuantumLeaps LFRB, Embedded Artistry, ece-mohammad, micoring,
  kostyk348, diffstorm, RIOT tsrb, Contiki-NG ringbuf, rigtorp, wizard97 ×2,
  polycratia, rt-spsc): configuration and API calls are documented at the
  top of each adapter in [`adapters_wave2/`](adapters_wave2/); what each
  needed to build is in "Building each library bare-metal" below.
- `memcpy` from newlib-nano (used by pxq, lwrb and ece-mohammad for blocks).
  `malloc`/`operator new` from a static arena (`common/nrf5340/bench_heap*`)
  for the two libraries that allocate at init.
- arm-none-eabi-gcc 14.2.1, `-O2 -DNDEBUG -mcpu=cortex-m33 -mthumb`,
  C11 / C++20.

## Results (2026-11-06, flash, cache on)
Mean cycles per call, overhead subtracted (min equals the mean for single
bytes; full statistics in the JSON records). Errors: 0 for every library in
every scenario, from flash and from SRAM. "burst16" gives the same per-call
numbers as "single" for every library. ⚠ = the project owner's library.

| Library | single push / pop | block4 push / pop | block64 push / pop | block64 cycles/byte |
|---|---|---|---|---|
| baseline | 7 / 10 | 44 / 43 | 76 / 75 | 1.2 |
| pxq RingBuffer_PackedState ⚠ | 17 / 31 | 133 / 135 | 209 / 197 | 3.2 |
| jnk0le Ringbuffer | 17 / 19 | 67 / 74 | 607 / 614 | 9.5 |
| polycratia spscring | 19 / 24 | 75 / 66 | 615 / 486 | 8.6 |
| rt-spsc | 20 / 19 | 145 / 133 | 1765 / 1573 | 26.1 |
| wizard97, as shipped (no ISR protection) | 22 / 22 | 156 / 145 | 1896 / 1765 | 28.6 |
| ETL queue_spsc_atomic | 24 / 31 | 120 / 132 | 1440 / 1452 | 22.6 |
| ETL queue_spsc_isr | 33 / 38 | 152 / 136 | 1832 / 1696 | 27.6 |
| rigtorp SPSCQueue | 35 / 43 | 205 / 202 | 2730 / 2542 | 41.2 |
| wizard97 + PRIMASK macros | 39 / 27 | 214 / 165 | 2854 / 2085 | 38.6 |
| Contiki-NG ringbuf | 40 / 40 | 225 / 217 | 3045 / 2917 | 46.6 |
| RIOT tsrb | 49 / 48 | 119 / 106 | 1139 / 1126 | 17.7 |
| QuantumLeaps LFRB | 50 / 45 | 265 / 239 | 3685 / 3179 | 53.6 |
| Embedded Artistry cbuf (threadsafe) | 54 / 44 | 273 / 234 | 3813 / 3174 | 54.6 |
| AndersKaloer Ring-Buffer | 56 / 40 | 132 / 87 | 1032 / 1107 | 16.7 |
| diffstorm cb | 79 / 68 | 381 / 329 | 5542 / 4710 | 80.1 |
| kostyk348 lf_spsc | 79 / 73 | 383 / 355 | 5635 / 5187 | 84.5 |
| ece-mohammad RingBuffer | 90 / 89 | 158 / 150 | 248 / 229 | 3.7 |
| micoring (SPSC mode) | 118 / 123 | 591 / 580 | 7671 / 7420 | 117.9 |
| lwrb | 222 / 221 | 200 / 198 | 289 / 275 | 4.4 |

Reading:
- **Single bytes:** pxq, jnk0le, polycratia and rt-spsc are within
  17–24 cycles; the slowest (micoring, lwrb) take 5–13× as long.
- **Blocks:** only pxq, lwrb and ece-mohammad copy with `memcpy`
  (3–4 cycles/byte at 64 bytes). polycratia, jnk0le, RIOT and AndersKaloer
  have native block calls that copy byte by byte (9–18). The rest have no
  block API, so `push_n`/`pop_n` loop over single calls (23–118).
- **wizard97 as shipped is not protected** off AVR/ESP8266 (its own header
  warns so); it is fast because it does nothing to guard its shared
  counter. See the ISR stress test for what that means.
- Code in SRAM is slower than flash with the cache on for every library
  (all numbers in the JSON records).

## Zero-copy / DMA scenario (2026-11-07)
Only three libraries have a zero-copy API in both directions: pxq ⚠
(`get_contiguous_push_area`/`commit_push`, `get_contiguous_pop_area`/
`commit_pop`), lwrb (`lwrb_get_linear_block_write_*` + `lwrb_advance`,
`lwrb_get_linear_block_read_*` + `lwrb_skip`) and ece-mohammad
(`RingBuffer_enBlockWrite*` + `enAdvance`, `enBlockRead*` + `enSkipItems`).
rigtorp and ETL only offer `front()` for one element.

Scenario `dma16`/`dma64`: 1024 transfers of 16 or 64 bytes. Producer: get the
write area, fill it (untimed: the DMA hardware's job), commit; consumer: get
the read area, check it in place (untimed), release. A transfer split at the
wrap needs a second pair. The number is the sum of the library calls per
transfer (flash, cache on):

| Library | dma16 write / read | dma64 write / read | minimum per transfer | for comparison: block64 with copy |
|---|---|---|---|---|
| pxq ⚠ | 132 / 130 | 176 / 173 | 117 / 115 | 206 / 192 |
| lwrb | 179 / 174 | 237 / 233 | 159 / 154 | 287 / 272 |
| ece-mohammad | 178 / 168 | 237 / 227 | 158 / 148 | 248 / 229 |

The cost is fixed per transfer, not per byte: the minimum is the same for 16
and 64 bytes (one acquire/commit pair); the mean is higher at 64 bytes
because about every second transfer is split at the wrap. Errors: 0.

## Building each library bare-metal (first-try usability)
What it took to build each library for a bare-metal Cortex-M33 with
arm-none-eabi-gcc 14.2.1, newlib-nano, `-O2 -DNDEBUG`. Facts about the
pinned versions; workarounds are in the adapters and `libs.mk`.

| Library | Needed |
|---|---|
| pxq, lwrb, jnk0le, QuantumLeaps, kostyk348, rt-spsc | nothing beyond the include path (pxq before 1.4.0: CMSIS `__get_PRIMASK` etc. must be declared) |
| ETL | no `-ffreestanding` (hosted STL headers); placement new (destructors would register `atexit`) |
| AndersKaloer | `-DNDEBUG` (an `assert` in init pulls in `fprintf`); space check before `queue` (it overwrites when full) |
| Embedded Artistry | `circular_buffer.h` does not include `<stddef.h>`/`<stdbool.h>`/`<stdint.h>`; init allocates the handle with `malloc` |
| ece-mohammad | `ring_buffer.h` does not include `<stdint.h>`; `ring_buffer.c` includes `main.h` (an STM32CubeMX project file) and needs the repo's `utils` module |
| micoring | SPSC mode must be selected (default is single-context, documented as not ISR-safe); the source tree has no switch, the CMake build generates the config |
| diffstorm | `cb.c` calls `nanosleep()` (POSIX) in its timeout helpers; newlib does not declare it |
| RIOT tsrb | RIOT's `irq.h` (shimmed with RIOT's Cortex-M semantics) and `turb.h` |
| Contiki-NG ringbuf | `contiki.h` (empty shim) and Contiki's own `sys/cc.h` |
| rigtorp | heap via `std::allocator`: `operator new` pulls in `abort` → newlib `malloc` → `sbrk` unless the firmware provides `operator new` |
| wizard97 | `RingBufCPP.h` does not include `<stddef.h>`; ISR safety needs user-supplied `RB_ATOMIC_START/END` off AVR/ESP8266 |
| polycratia | uses `try`/`catch`: does not compile with the usual embedded `-fno-exceptions` |
| TinyUSB tu_fifo (0.21.0) | a `tusb_config.h` from the application (here a two-line shim: `CFG_TUSB_MCU OPT_MCU_NONE`, `CFG_TUSB_OS OPT_OS_NONE`); `osal/osal.h` must be included before `tusb_fifo.h` (as `tusb.h` and `tusb_fifo.c` do), otherwise `osal_none.h` calls `tu_fifo_*` before they are declared |
## Modes for more than one producer or consumer (SET=mp, 2026-11-13)
`SET=mp bash run.sh flash` builds a second firmware with 9 entries instead of
the 37 of the default set (`SET=spsc`); both do not fit in the SAM D20's 32 KB
of RAM at once. It times, with the same scenarios, the modes that
[`../rb-mp-stress`](../rb-mp-stress) tests with two interrupts:
- pxq `Topology::MPSC`, `SPMC` and `MPMC` ([`adapters_mp/adapter_pxq_mp.cpp`](adapters_mp/adapter_pxq_mp.cpp));
- DNedic lockfree `mpmc::Queue` (the adapter of rb-mp-stress; needs
  compare-and-swap, so on Cortex-M0+ the entry is empty and the record says
  "not available on this core");
- RIOT tsrb and wizard97 with its PRIMASK macros, which are the same code in
  every mode;
- the baseline and pxq's SPSC class, as a reference against the default set.

Every call is timed alone, as in the default set: the numbers are the cost of
each mode's protection without contention, not throughput with several
producers or consumers running. The zero-copy scenario is not in this set.
Records are named `<board>-rb-bench-mp-flash-<time>.json` and carry
`"set": "mp"`; the comparison page reads them through `site/gen_libdata.py`.

## clang (COMPILER=clang, 2026-11-08)
`COMPILER=clang bash run.sh` builds the libraries and their adapters with the
toolchain image's clang 21 (`--target=arm-none-eabi`), against the same
newlib and libstdc++ headers as arm-none-eabi-gcc (the multilib for the
board's `ARCH`). The timing harness, startup code and link stay
arm-none-eabi-gcc with the same newlib-nano, so only the library code
changes. Records get the suffix `-clang` and the field `compiler_libs`. The
same switch exists for the stress tests (`COMPILER=clang`, or `+clang` in the
campaign's `FLAGS_ROTATION`). Set up in [`../common/compiler.mk`](../common/compiler.mk):
- `-fshort-enums`: arm-none-eabi-gcc uses variable-size enums, and clang's
  default of 32-bit enums would not link cleanly with the gcc objects.
- newlib's C headers come after clang's builtin headers (`-idirafter`), so
  `stdint.h`, `stddef.h` and `stdatomic.h` are clang's own.
- polycratia needs exceptions. Its clang object pulls in libgcc's unwinder,
  so clang builds define an empty `.ARM.exidx` table (`--defsym`). Nothing
  throws in these tests.
- `LTO=1` is refused with clang (gcc LTO).
- gcc builds are unchanged: the binary images of bench (flash and SRAM),
  stress and both mp-stress modes are byte-identical before and after this
  change.

Library facts seen when building with clang: pxq's
`[[gnu::optimize("Os")]]` attributes are ignored ("unknown attribute"), so
under clang pxq is built with the project's `-O` level, not the forced -Os.
wizard97 as shipped prints its own `#warning` that it is not ISR-safe
without `RB_ATOMIC_START/END`, as under gcc.

## Code in SRAM vs flash (2026-11-06)
`run.sh` builds two images from the same object files: `build/flash`
(code executes from flash) and `build/sram` (all code except the startup
code is copied to the upper half of SRAM, 0x20040000, and executes there;
data and stack stay in the lower half). Confirmed from the symbol table
(`pxq_push` at 0x200404e0 etc.) and by the cache having no effect in the
SRAM image.

Mean cycles per call, push / pop:

| Scenario | Library | Flash, cache on | Flash, cache off | SRAM |
|---|---|---|---|---|
| single | baseline | 7 / 10 | 28 / 29 | 21 / 22 |
| | pxq ⚠ | 17 / 31 | 63 / 73 | 38 / 51 |
| | lwrb | 218 / 215 | 433 / 424 | 326 / 308 |
| block16 | baseline | 52 / 51 | 145 / 144 | 99 / 99 |
| | pxq ⚠ | 151 / 148 | 351 / 347 | 254 / 257 |
| | lwrb | 222 / 218 | 434 / 442 | 339 / 338 |
| block64 | baseline | 76 / 75 | 179 / 178 | 159 / 159 |
| | pxq ⚠ | 206 / 192 | 431 / 421 | 362 / 353 |
| | lwrb | 287 / 272 | 551 / 554 | 471 / 459 |

**On the nRF5340, code runs about 1.5–2× slower from SRAM than from flash
with the cache on**, and faster than from flash with the cache off. So
moving a ring buffer into RAM ("ramfunc") makes it slower here, as long as
the cache is on. The order of the libraries is the same in all three
columns. The SRAM results are deterministic (min = mean in nearly all
cases).

Likely reason (hypothesis, not verified): on the Cortex-M33, instruction
fetches from the SRAM region go over the system bus (S-AHB), shared with
the data accesses, while fetches from the code region use the code bus
(C-AHB) and hit the cache. The nRF5340 Product Specification v0.5.1 has a
table for "CPU wait states, running from RAM" (p. 94) but leaves the values
blank.

## Observations (to verify before any conclusion)
- **Single bytes:** pxq push/pop take 17/31 cycles, lwrb 218/215. lwrb's
  single-byte path goes through `lwrb_write` → `lwrb_write_ex` → free-space
  count → `memcpy` of 1 byte; it is built for streams of any length.
- **pxq pop costs ~2× its push.** The burst16 pattern rules out the first
  guess (a load of the state word right after a store to it): pops after
  16 pushes cost the same 31 cycles. In the generated code, pop sets up a
  stack frame (`push {lr}` … `ldr pc, [sp], #4`) because GCC uses LR as a
  scratch register under the library's forced `-Os`; push needs none. That
  explains part of the gap, not all of it.
- **pxq `push_n` with 4 bytes (130 cycles) is slower than 4 single pushes
  (~68).** `push_n` is not inlined and always calls `memcpy` twice, the
  second time with length 0 when the block does not wrap. From 16 bytes up,
  block calls are cheaper per byte than single calls for both libraries.
- **Blocks narrow the gap:** at 64 bytes pxq is ~1.4× faster than lwrb per
  byte; both are dominated by `memcpy`.

These are facts about the versions and configuration above, not general
rankings.

## Pitfalls found while building this
- **probe-rs stops the cycle counter.** Every probe-rs attach/detach clears
  `DEMCR.TRCENA`, which stops `CYCCNT`. The first version measured 0 cycles
  for everything after the first library. Now the firmware waits ~1 s
  before measuring, `run.sh` stays off the probe until it is done, and any
  timed call that sees no CYCCNT progress rejects the whole run.
- **The compiler can move work into the timed window.** With plain C timing
  code, the pop window contained extra spills and loads that the push
  window did not, adding ~7–10 cycles to every pop. Timing is now done in
  assembly.
- **Code placement changes cache-off numbers** by up to ~10 %, even for code
  that did not change. Report cache-on as the primary number.

## Nordic nrf_ringbuf (SET=nordic, nRF5340 only)

Nordic's `nrf_ringbuf` is part of the nRF5 SDK, which is a zip from
nordicsemi.com, not a git repository, and its licence allows use with Nordic
chips only. It is therefore built for the nRF5340 only, in a firmware of its
own (baseline, pxq as a reference, nrf_ringbuf), and the SDK never enters
this repository: download `nRF5_SDK_17.1.1_8173c8a.zip` yourself and give
its path:

```sh
BOARD=nrf5340 SET=nordic NRF5_SDK=path/to/nRF5_SDK_17.1.1_8173c8a.zip bash run.sh flash
```

`nrf5-sdk.sh` checks the zip against the SHA-256 in `nrf5-sdk.lock` and
takes only the files listed there (the ring buffer, Nordic's atomics and
their utility headers) into `build/libs/nrf5-sdk/`; `shims/nrf5/` stands in
for the device and SoftDevice headers. Records: `nrf5340-rb-bench-nordic-*`.
The stress test has the same option (`NORDIC=1`, library 40, records
`nrf5340-rb-nordic-stress-*`). Without these options both firmwares are
unchanged.
