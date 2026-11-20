# Candidates: embedded ring buffers (3-month trial)

Scope: see [DECISIONS.md](../DECISIONS.md), 2026-11-05.
SPSC between an interrupt (or DMA) and the main loop/task, on Cortex-M0+ and
Cortex-M4 (M7 later). Languages: C, C++ and Rust.

Repository facts (license as reported by GitHub, last push) checked
2026-11-05. Claims about thread/ISR safety are what each project documents or
appears to intend; **verifying them is the point of the tests**.

## Harness status (2026-11-06, nRF5340 DK, Cortex-M33)
Harness development, not published results. ⚠ = the project owner's own
library (principle 6).

| Candidate | Pinned | Cycle benchmark | ISR stress, single bytes | ISR stress, blocks | GenMC (C11) |
|---|---|---|---|---|---|
| pxq RingBuffer_PackedState ⚠ | `312c421a8f61` | ✓ | ✓ 0 errors | ✓ 0 errors | not yet (volatile; needs a model of its contract) |
| lwrb | v3.3.0 | ✓ | ✓ 0 errors | ✓ 0 errors | ✓ pass, controls caught |
| AndersKaloer Ring-Buffer | `8de8fff55a0b` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| jnk0le Ringbuffer | `9efa07fffc0f` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| ETL queue_spsc_isr | 20.49.0 | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| ETL queue_spsc_atomic | 20.49.0 | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| QuantumLeaps LFRB | `0d6354a10a3c` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| Embedded Artistry cbuf (no_modulo_threadsafe) | `9733be2eacdc` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| ece-mohammad RingBuffer | `94083a63259e` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| micoring (SPSC mode) | `a6f91ee2991a` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| kostyk348 lf_spsc | `38649b8f964e` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| diffstorm cb | `11e05d60462a` | ✓ | ✓ 0 errors | ✓ 0 errors | **2 defects found in `547d0812`, reported 2026-11-08, fixed upstream the same day; publication agreed 2026-11-09** ([finding](../verify/findings/diffstorm-cb-overwrite-padding/README.md)) |
| RIOT tsrb | `9c9a6abec901` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| Contiki-NG ringbuf | `a3c7119915a5` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| rigtorp SPSCQueue | `59a6a938513e` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| wizard97 RingBufCPP, as shipped | `5cd8410c162a` | ✓ | ✗ 8 262 errors (as its header warns) | ✗ 26 153 errors | – |
| wizard97 RingBufCPP + PRIMASK macros | `5cd8410c162a` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| polycratia spscring | `9d2445a55970` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| rt-spsc | `5454de55a2a1` | ✓ | ✓ 0 errors | ✓ 0 errors | – |
| TinyUSB tu_fifo | `dae3f9a366bf` (0.21.0) | builds, not run yet | not run yet | not run yet | – (volatile, no atomics: needs the single-core contract model) |

Details: [cycle benchmark](../firmware/nrf5340-rb-bench/README.md),
[ISR stress](../firmware/nrf5340-rb-stress/README.md),
[GenMC](../verify/genmc/README.md). Wave 3 (Zephyr ring_buf, DNedic/lockfree,
ETL queue_spsc_locked): see below. Not yet started: FreeRTOS stream buffer,
NuttX circbuf, all Rust candidates.

## Wave 4 (2026-11-12): survey, the most deployed implementations

Selection rule this time: what most firmware actually runs (platform cores,
RTOS and SDK libraries), not more small repositories. Sources read on
GitHub (default branch, 2026-11-12). Order = proposed integration order.

**Integrated 2026-11-12** (bench, ISR stress incl. sweep, rb-size; pins in
`libs.lock`): NuttX `circbuf` at nuttx-13.1.0 `2b5c0de5` (also zero-copy),
Arduino `RingBufferN` at ArduinoCore-API 1.5.2 `cd91833d` (as shipped:
reported, not counted) and `SafeRingBufferN` at ArduinoCore-renesas 1.6.0
`424e86ef`. First board runs (G474): NuttX and SafeRingBufferN 0 errors;
RingBufferN as shipped fails in both directions, as its maintainers'
statement predicts.

**Built 2026-11-12 (night), board runs pending**: RT-Thread `rt_ringbuffer`
at v5.3.0 `99428a1e`, as shipped (no concurrency claim found; RT-Thread's
own serial driver calls it inside `RT_SERIAL_FIFO_LOCK`: reported, not
counted) and with interrupts off around each call, as that driver does;
Mbed CE `CircularBuffer` at mbed-os-7.1.0 `a4c70564` (its header uses
`std::copy` without including `<algorithm>`); moodycamel
`ReaderWriterQueue` v1.0.7 `8b217669` (bare-metal: `atomicops.h` stops with
"Unsupported platform! (No semaphore wrapper available)" although only the
blocking queue uses semaphores; built through its FreeRTOS branch with
declaration-only stubs; calls `abort()` on allocation failure). GenMC on moodycamel (2026-11-12): stops with "Invalid call to
memset()" (destination opaque) while the queue is constructed; not
investigated further, so no model check for it yet.

| Library | License | Latest release seen | What it documents about concurrency | What the code does | Notes |
|---|---|---|---|---|---|
| **NuttX `circbuf`** (`libs/libc/misc/lib_circbuf.c`) | Apache-2.0 | nuttx-13.1.0 | File header: "no locking required while only one reader and one writer"; each read/write function repeats it | `head`/`tail` are free-running `size_t` counters, `% size` for the offset (a division on M0+); plain accesses, no `volatile`, no barriers; `memcpy` then `head += n` | Has a zero-copy API (`get_writeptr`/`writecommit`, `get_readptr`/`readcommit`): DMA mode too. A clear SPSC promise to verify |
| **Arduino `RingBufferN`** (ArduinoCore-API `api/RingBuffer.h`) | LGPL-2.1 | 1.5.2 | Maintainers: not meant to be thread-safe ([ArduinoCore-API #195](https://github.com/arduino/ArduinoCore-API/issues/195)) | Shared `_numElems` changed by both sides with `x = x ± 1` (the `shared count, no lock` mutant, in real code) | Yet the SAMD core's `Uart` calls `store_char` in the IRQ handler and `read_char` from `Serial.read()` without masking. Test as shipped (expected to fail, like wizard97 as shipped) and **`SafeRingBufferN`** (ArduinoCore-renesas `SafeRingBuffer.h`, `synchronized` = interrupts off per call). Known upstream, so no notice needed for the class itself |
| **RT-Thread `rt_ringbuffer`** (`components/drivers/ipc/ringbuffer.c`) | Apache-2.0 | v5.3.0 | None found in the file; to check the docs and how RT-Thread's own serial driver calls it (with interrupts off?) | Mirror-bit design: `{read,write}_mirror:1` and `_index:31` as bitfields in one word per side; plain accesses, no barriers; at wrap the mirror flip and the index reset are two bitfield writes | Widely used (RT-Thread). If it promises nothing, test as shipped and report like wizard97 (not counted) |
| **Mbed OS `CircularBuffer`** (`platform/include/platform/CircularBuffer.h`) | Apache-2.0 | mbed-os-6.17.0; Mbed CE fork mbed-os-7.1.0 | Every push/pop in `core_util_critical_section_enter/exit` | push **overwrites** the oldest data when full; the adapter tests `full()` first (safe: only the producer makes it fuller) | Arm ended Mbed OS in July 2026 (archived); the community fork Mbed CE continues. Large installed base; pin the Mbed CE version |
| **moodycamel `ReaderWriterQueue`** (`readerwriterqueue.h`) | BSD-2-Clause (simplified BSD) | v1.0.7 | "A lock-free queue for a single-consumer, single-producer architecture" | C++11 atomics (own `atomicops.h`), blocks from `malloc`; `try_enqueue` does not allocate | Desktop SPSC like rigtorp; needs the bench heap and `-fno-exceptions` (it disables exceptions itself then). GenMC candidate |
| Nordic nRF5 SDK `nrf_ringbuf` | Nordic 5-clause | SDK 17.1.1 | "thread-safe"; concurrent get/put return `NRF_ERROR_BUSY` ([docs](https://docs.nordicsemi.com/r/bundle/nrf5_sdk_v17.1.1/page/lib_ringbuf.html)) | read 2026-11-16: the SDK zip pinned by SHA-256 (firmware/nrf5340-rb-bench/nrf5-sdk.lock; fetched by the owner, never in this repository) | In test, nRF5340 only (licence: Nordic chips only): benchmark SET=nordic, stress test NORDIC=1, both firmwares of their own; not in the host-side checks (contract check, GenMC), which would run it off a Nordic chip |

Not taken: Linux `kfifo` (no widely used embedded port found that is not
one of the above), SEGGER RTT buffers (target to debugger, a different use
case), Arduino AVR `HardwareSerial` (inline buffer, AVR only).

Rust (`heapless::spsc::Queue`, `bbqueue`): separate step, needs a C-ABI
staticlib adapter; the image has Rust. Planned after wave 4.

## Wave 3 (2026-11-12): survey and first integration

Added to the harness (bench, ISR stress incl. zero-copy where the library
has it, rb-size; board runs pending):

| Library | Pinned | Concurrency it documents | GenMC (RC11) |
|---|---|---|---|
| **Zephyr `ring_buf`** (`include/zephyr/sys/ring_buffer.h`, Apache-2.0) | v4.5.0 `41d10b59` | One producer and one consumer in separate contexts (e.g. a thread and an ISR) without extra locking; more of either must be serialised. Header only since 4.5; two codes: single-core (plain accesses + compiler barriers) and `CONFIG_SMP` (`__atomic` acquire/release) | SMP code: **pass** (34 927 executions), release and acquire mutants fail. The single-core code is a C11 data race by definition: for the single-core contract model |
| **DNedic/lockfree** (991 ★, MIT) `spsc::RingBuf` | 3.0.1 `ae6c4df1` | "Thread and interrupt safe" in each structure's use case; C++11 atomics; README: `LOCKFREE_CACHE_COHERENT=false` on embedded | **pass** (7 118), mutants fail |
| DNedic/lockfree `mpmc::Queue` | 3.0.1 | Several producers and consumers; needs CAS (n/a on Cortex-M0+) | in the multi-producer stress test; GenMC with threads under way |
| **ETL `queue_spsc_locked`** | 20.49.0 | Main side under user lock/unlock functions (here PRIMASK), ISR side `*_from_unlocked` | – (lock-based) |
| **FreeRTOS stream buffer** (FreeRTOS-Kernel, MIT) | V11.3.3 `89592801` | One writer and one reader, tasks or interrupts (`...FromISR` in interrupts). Built without the scheduler: `stream_buffer.c` unchanged, a minimal port (PRIMASK critical sections) and inert task stubs (only reached when a task blocks, which never happens with zero timeouts) | – (critical sections) |

Looked at, not integrated yet:

- **NuttX `circbuf`** (Apache-2.0): checked in wave 4 (promises lock-free SPSC).
- Rust (`heapless`, `bbqueue`, `ringbuf`): need a Rust toolchain in the
  image first.

## Wave 2 (found 2026-11-06)
Found by searching GitHub (`ring buffer`/`ringbuffer`/`circular buffer`/
`spsc` with `cortex-m`, `stm32`, `ISR`, `embedded`, `no_std`, `lock-free`,
including `stars:0..5`) plus known projects the search missed. Out of 200+
hits, application examples (UART drivers, course exercises), desktop/server
code and non-library repos were dropped. Stars, license and last push as
reported by GitHub on 2026-11-06. Bold = in the harness now.

### A. Known or widely used (C/C++)
| Repo | ★ | License | Why |
|---|---|---|---|
| **QuantumLeaps/lock-free-ring-buffer** | 76 | MIT | Miro Samek (QP framework); lock-free, written for MCUs |
| **rigtorp/SPSCQueue** | 1322 | MIT | Very popular server-side SPSC; does it hold up on an MCU? |
| **wizard97/Embedded_RingBuf_CPP** | 109 | MIT | Embedded C++, ISR-safe only with user-supplied macros off AVR/ESP8266 |
| rlogiacco/CircularBuffer | 358 | LGPL-3.0 | Widely used in the Arduino world |
| Locoduino/RingBuffer | 74 | GPL-2.0 | Arduino, made for ISR use |
| **RIOT-OS `sys/tsrb`** | 5835 (RIOT) | LGPL-2.1 | RIOT's "thread-safe ring buffer" (interrupts off per call) |
| **contiki-ng `os/lib/ringbuf`** | 1540 (Contiki) | BSD-3-Clause | Contiki's ISR-safe byte ring |
| **embeddedartistry/embedded-resources** | 674 | CC0-1.0 | Much-read reference circular buffer |
| NetKit-Labs/memkit | 56 | MIT | New embedded C++ container library |
| Crazy-Geeks/RingBuffer | 31 | MIT | Written for STM32 |
| magiczny-kacper/RingBuffer | 19 | GPL-3.0 | Tested on MCUs, according to the author |

### B. Low or no stars, licensed, claim embedded/ISR/SPSC safety
| Repo | ★ | License | Claim |
|---|---|---|---|
| **ece-mohammad/RingBuffer** | 3 | MIT | Lock-free SPSC for embedded |
| ximtech/RingBuffer | 3 | MIT | Embedded |
| DennisCGc/ringbuffer | 4 | BSD-2-Clause | Lock-free (2016) |
| d-mironov/libcircular | 2 | MIT | Static memory, embedded |
| **diffstorm/cb** | 1 | MIT | Lock-free, portable to embedded |
| JoelStienlet/RingBuffer | 1 | MIT | Lockless, "embedded to desktop" |
| jeremyherbert/ringbuf | 1 | MIT | Embedded-friendly |
| **polycratia/spscring** | 1 | MIT | SPSC with its memory model documented |
| merlotqi/spscring | 1 | MIT | Header-only SPSC |
| shpegun60/spsc | 1 | Apache-2.0 | SPSC for desktop and embedded |
| **Vanderhell/micoring** | 0 | MIT | "ISR-safe" C99 (SPSC mode is opt-in) |
| **kostyk348/lockfree** | 0 | Apache-2.0 | SPSC/MPSC for MCUs without an FPU |
| **Saikiran4255/rt-spsc** | 0 | MIT | Wait-free, ISR → task |
| hdp1972be-svg/ringbuff | 0 | MIT | Zero-copy SPSC, C11 |
| jogaja/ring-buffer-c | 0 | MIT | Lock-free, embedded C |
| emreshnn/embedded-c-utils | 0 | MIT | Heap-free C99 |
| zeta-zero/ringbuffer | 0 | Apache-2.0 | Embedded |
| tom-free/letk | 0 | MIT | Embedded toolkit |

### C. Rust `no_std` (in addition to heapless, bbqueue, ringbuf)
| Repo | ★ | License | Notes |
|---|---|---|---|
| Mallets/ringbuffer-spsc | 15 | Apache-2.0 OR EPL-2.0 | GitHub shows NOASSERTION; see license check |
| d-mironov/sushi-belt | 0 | MIT | Fixed-capacity, no allocator |
| ElNeMeR70/rs-ring-buffer | 0 | MIT (declared) | "for interrupt-driven embedded I/O"; see license check |

### D. No license found (test privately only; ask before publishing)
usrnatc/nc_ring (single-file SPSC byte ring), lamarrr/RingBuffer (ISR ↔
task; "Copyright (c) 2019", no license), AliceOh/Ring-Buffer, peterwht/ring-buffer.

### License check (2026-11-06)
GitHub's license detection missed some licenses, so every repo shown as
"none"/"NOASSERTION" was checked by hand: license-like files under any
name, README license sections, SPDX lines and copyright headers in the
sources, and `Cargo.toml`.

| Repo | GitHub shows | Actual |
|---|---|---|
| Mallets/ringbuffer-spsc | NOASSERTION | **Apache-2.0 OR EPL-2.0** (dual LICENSE file, README badges, `Cargo.toml`) |
| ElNeMeR70/rs-ring-buffer | none | **MIT**, declared in README ("MIT © ElNeMeR70") and `Cargo.toml`; no LICENSE file |
| usrnatc/nc_ring | none | none in any file |
| lamarrr/RingBuffer | none | "Copyright (c) 2019" only, no license (all rights reserved) |
| AliceOh/Ring-Buffer | none | none in any file |
| peterwht/ring-buffer | none | none; `Cargo.toml` has no `license` field |

### Observation
Many 0-star repos are from 2026 and have very polished descriptions
("ultra-low latency", "industrial-grade", "lock-free"). They are exactly
what an AI agent finds and picks without a way to judge quality, which is
the case this registry is for. Who or what wrote them is not visible; this
is only a pattern.
## C

| Library | Component | License | Notes |
|---|---|---|---|
| [MaJerle/lwrb](https://github.com/MaJerle/lwrb) | `lwrb` | MIT | Lightweight ring buffer aimed at embedded and DMA use; optional C11 atomics. |
| [zephyrproject-rtos/zephyr](https://github.com/zephyrproject-rtos/zephyr) | `ring_buf` (`include/zephyr/sys/ring_buffer.h`) | Apache-2.0 | RTOS-wide utility. Check what locking the caller is expected to provide. |
| [FreeRTOS/FreeRTOS-Kernel](https://github.com/FreeRTOS/FreeRTOS-Kernel) | stream buffer / message buffer | MIT | Designed for one writer and one reader, including task-to-ISR. |
| [apache/nuttx](https://github.com/apache/nuttx) | `circbuf` (`libs/libc/misc/lib_circbuf.c`) | Apache-2.0 | RTOS utility; check concurrency guarantees. |
| [hathach/tinyusb](https://github.com/hathach/tinyusb) | `tu_fifo` (`src/common/tusb_fifo.c`) | MIT | FIFO used between USB interrupts and application code in real products. |
| [AndersKaloer/Ring-Buffer](https://github.com/AndersKaloer/Ring-Buffer) | `ringbuffer` | MIT | Small, widely copied C ring buffer. |

## C++

| Library | Component | License | Notes |
|---|---|---|---|
| [ETLCPP/etl](https://github.com/ETLCPP/etl) | `queue_spsc_isr`, `queue_spsc_atomic`, `queue_spsc_locked` | MIT | Embedded Template Library; several SPSC variants for ISR use. |
| [jnk0le/Ring-Buffer](https://github.com/jnk0le/Ring-Buffer) | `Ringbuffer` | MIT | C++11-atomics ring buffer targeting Cortex-M. |
| [pxq-dk/RingBuffer-Cortex](https://github.com/pxq-dk/RingBuffer-Cortex) | `RingBuffer_PackedState` | GPL-3.0-only OR commercial | **Written by the project owner**, Erik N (pxq.dk), who also sells a commercial license. Conflict-of-interest rules apply ([PROJECT.md](../PROJECT.md), principle 6). |

## Rust

| Library | Component | License | Notes |
|---|---|---|---|
| [rust-embedded/heapless](https://github.com/rust-embedded/heapless) | `spsc::Queue` | Apache-2.0 (check for dual MIT) | The standard `no_std` SPSC queue. |
| [jamesmunns/bbqueue](https://github.com/jamesmunns/bbqueue) | `BBBuffer` | Apache-2.0 (check for dual MIT) | Bip-buffer designed for DMA: contiguous grants instead of single elements. |
| [agerasev/ringbuf](https://github.com/agerasev/ringbuf) | `StaticRb` | Apache-2.0 (check for dual MIT) | Lock-free SPSC with `no_std` support. |

## Baselines (our own)

- **Critical section:** interrupts disabled around every access. Correct by
  construction; the reference for speed and code size.
- **Lamport SPSC with C11/C++11 atomics:** the classic minimal lock-free
  version.
- **Deliberately broken:** `volatile` indices without barriers, and a variant
  with a wrong full/empty check. Proves that the tests catch real bugs.

## Considered, not in the trial

- **mbed-os `CircularBuffer`:** license not detected by GitHub, last push
  2024-10; the Mbed platform is being retired.
- **rigtorp/SPSCQueue, folly, boost.lockfree, DPDK `rte_ring`, Linux
  `kfifo`:** server/host queues. They belong to a later server-side niche,
  not the embedded trial.

## What to check per candidate (first pass)

1. Can it be built for Cortex-M0+ and M4 with GCC (arm-none-eabi) without an
   OS, or with its RTOS where the component depends on it?
2. Does it document ISR safety, and under which conditions (single
   producer/consumer, element size, required locking)?
3. Index handling at wraparound (counter overflow) and the full/empty
   boundary at capacity 1, 2 and 3.
4. Memory ordering on Cortex-M: barriers or atomics where M7 caches/write
   buffers and compiler reordering require them.
