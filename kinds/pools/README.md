# Fixed-block pools: the third kind

Work of the [plan of 2026-11-26](../../lab/plans/2026-11-26-pools-kind.md),
decided by the owner on 2026-11-26 ([`DECISIONS.md`](../../DECISIONS.md)). The
first series ran on the six boards on 2026-11-26, under
[method version 3](../../lab/plans/2026-11-26-method-version-3.md)
([series report](../../reports/2026-11-26-pools-first-series.md)); its records
are under [`records/pools`](../../records/README.md). The host test, the proof
and the cross builds below are host work: their numbers are not board results.

`bash run.sh` fetches the pinned libraries (git only, `fetch.sh`), then runs
everything else inside the toolchain image `verified-libs/toolchain:2026-11-13`:
- `make test`: the host test;
- `make san`: the same with ASan and UBSan;
- `make proof`: CBMC on the reference;
- `make miri`: the Rust adapters under Miri;
- `make cross`: cross builds and sizes for the four cores;
- `make memorypool-v010`: our check of MemoryPool's release (below).

## The set

One pool shape for the first series: **32 blocks of 32 bytes** (DECISIONS
2026-11-26). The licence is the one in each repository's licence file, read
again on 2026-11-26.

| Configuration | Library | Pin (`libs.lock`) | Licence | Lock as built here |
|---|---|---|---|---|
| reference free list (ours) | – | – | – | none: the baseline |
| reference free list, interrupts off (ours) | – | – | – | PRIMASK around each call: a row of ours, not a library |
| ETL `etl::pool` (C++) | ETL | 20.49.0, `7d604f2` (the ring buffers' pin) | MIT | none (the header documents none) |
| RIOT `memarray` (C) | RIOT | `9c9a6ab` (the ring buffers' pin) | LGPL-2.1 | none |
| ThreadX block pool (C) | Eclipse ThreadX | v6.5.2.202603_rel, `93387b0` | MIT | interrupts off (`TX_DISABLE`), the release's port for each core |
| CMSIS-RTX `osRtxMemoryPool` (C) | CMSIS-RTX | v5.9.1, `b566de4` (with CMSIS 6 `af1b110`, Cortex_DFP `cd38dbb`) | Apache-2.0 | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M |
| Contiki-NG `memb` (C) | Contiki-NG | release/v5.2, `4ccd1a3` | BSD-3-Clause | none (cooperative processes) |
| C_Allocator `fb_allocator` (C) | endurodave/C_Allocator | v2.1.0, `497b465` | MIT | `ALLOC_LOCK_NONE`, the library's default without threads |
| lwIP `memp` (C) | lwIP | STABLE-2_2_1_RELEASE, `77dcd25` | BSD-3-Clause | `SYS_ARCH_PROTECT`: our port, interrupts off (`shims/lwip/sys_arch.c`) |
| MemoryPool `Fixed` (C++) | bertmelis/MemoryPool | **main `5073178` (unreleased; after v0.1.0)** | MIT | none on the boards; `std::mutex` on the host (below) |
| heapless pool, `BoxPool` (Rust) | heapless | `1918822` (the ring buffers' pin, version 0.9.1) | MIT OR Apache-2.0 | lock-free: LL/SC on the boards, a tagged CAS on the host; not on Cortex-M0+ |
| atomic-pool (Rust) | embassy-rs/atomic-pool | 2.0.1, `ab88f3c` (the head; no tag v2.0.1 exists) | MIT OR Apache-2.0 | atomic bitmap; on Cortex-M0+ portable-atomic's `unsafe-assume-single-core` |

**Left out, with the reason:**
- **eccles-rtmem** (v2.0.0, `0214634`, MIT). It is not a pool of one block
  size: it is a `malloc(size)` over three block classes, which falls back to
  larger classes and takes runs of blocks (`eccles_rtmem.c`,
  `eccles_rt_malloc`). Its storage is two static arrays inside its own file
  (lines 249–256), so this kind's region and canary checks cannot reach it.
- **Zephyr `k_mem_slab`** (v4.5.0, `41d10b5`, Apache-2.0). It cannot be built
  alone: `kernel/mem_slab.c` includes `zephyr/kernel.h` and the kernel's
  private headers, which need a Zephyr build's generated configuration (the
  first errors: "CONFIG_ATOMIC_OPERATIONS_* not defined",
  "CONFIG_NUM_PREEMPT_PRIORITIES undeclared", "processor architecture not
  supported").

**MemoryPool: why the head, not the release** (owner, 2026-11-26):
- **The spacing.** The project's only release, v0.1.0 (`c98ff35`,
  2024-03-05), spaces the blocks of `MemoryPool::Fixed` by the size of a
  pointer, whatever the block size, so blocks overlap. Its `src/Fixed.h`
  (lines 28, 70 and 102) compares `sizeof(sizeof(unsigned char*))` with
  `sizeof(blocksize)`, and both are `sizeof(size_t)`.
- **Fixed by the author.** The author fixed it in pull request
  [#4](https://github.com/bertmelis/MemoryPool/pull/4), "Fix Fixed Mempool
  blocksize", merged 2024-05-14 (`813b79a` on main).
- **The build.** v0.1.0 also does not build for arm-none-eabi (`'mutex' in
  namespace 'std' does not name a type`). The head puts the mutex under
  `#if _GLIBCXX_HAS_GTHREADS` ("Disable mutex when not available", `63056f9`,
  2024-05-15).
- **No release since**, so the kind measures the head.
- **What we saw.** Our host check of v0.1.0 (`make memorypool-v010`,
  `checks/memorypool_v010.cpp`) printed:

  ```
  sizeof(pool) = 80 (4 blocks of 32 would need at least 128)
  block 0 at offset 0
  block 1 at offset 8
  block 2 at offset 16
  block 3 at offset 24
  bytes of block 1 changed by filling block 0: 24 of 32
  -- at the head:
  sizeof(pool) = 176 (4 blocks of 32 would need at least 128)
  block 0 at offset 0
  block 1 at offset 32
  block 2 at offset 64
  block 3 at offset 96
  bytes of block 1 changed by filling block 0: 0 of 32
  ```
- **Its lock.** At the head the mutex is compiled out on the boards (no
  threads in arm-none-eabi's libstdc++), with `#warning "The memory pool is
  not thread safe"`, so the pool has no lock there. On the host, glibc's
  libstdc++ has threads, so the host test runs it with its mutex.

## What each library documents about interrupts

For the column "documented use from interrupts" (plan, section 4). It is
shown as documented: the first series is one context. Whether it holds is
tested by the concurrency series (`kinds/pools-isr`, records under
`records/pools-isr`). `claims.tsv` holds the
same, one line per configuration with its source (file and line at the pin,
or the documentation's URL), for the pages to read; keep the two the same.

| Configuration | What it documents, and where |
|---|---|
| ThreadX | `tx_block_allocate` and `tx_block_release` "Allowed From: Initialization, threads, timers, and ISRs"; allocate from a non-thread only with `TX_NO_WAIT` (ThreadX documentation, chapter 4; its repository `eclipse-threadx/rtos-docs` is archived) |
| CMSIS-RTX | `osMemoryPoolAlloc` "may be called from Interrupt Service Routines if the parameter timeout is set to 0"; `osMemoryPoolFree` from an ISR (CMSIS-RTOS2 documentation, Memory Pool) |
| lwIP `memp` | protected by `SYS_ARCH_PROTECT` "by disabling interrupts for an embedded system or by using a semaphore or mutex" (`lwip/sys.h`); here our port, interrupts off |
| heapless pool | "only available on ... ARM architectures which instruction set include the LDREX, CLREX and STREX instructions" (`src/pool.rs`); lock-free |
| atomic-pool | atomics through `portable-atomic`; on cores without CAS its `critical-section` or `unsafe-assume-single-core` feature (`README.md`) |
| C_Allocator | "With an interrupt-masking option (FreeRTOS on Cortex-M or ESP32, ThreadX, Zephyr, CMSIS-RTOS2), `ALLOC_Alloc()` and `ALLOC_Free()` may also be called from an interrupt"; without threads the default is no lock (`README.md`, `LockGuard.h`) |
| MemoryPool | at the head, without threads: `#warning "The memory pool is not thread safe"` (`src/Fixed.h`); no lock on the boards |
| ETL, RIOT, Contiki-NG | nothing about interrupts or threads |

## How each adapter fits the interface

`pool.h` gives the interface: `init`, `alloc`, `free`, the region, the
promised alignment, and the canaries around the pool's memory. What an
adapter adds around its library:
- *ThreadX.* It runs without its scheduler, through
  `tx_kernel_stubs.c`. The stubs are never reached with `TX_NO_WAIT`, and
  stop the program if they are.
- *CMSIS-RTX.* Its three pool functions are called directly. On the host
  they are cut out unchanged by `extract.py`, as the Armv6-M variant (pool
  prechecks).
- *C_Allocator.* It treats an exhausted pool as a fault: `FaultHandler()`
  ("On a fault, such as an exhausted pool, the allocators call
  FaultHandler() ... define your own FaultHandler() to log or reset
  instead"). The adapter's handler counts the call and returns, and
  `ALLOC_Alloc` then gives NULL.
- *lwIP.* One private pool, as `memp.h` documents (`LWIP_MEMPOOL_DECLARE`
  spelled out inside the guard, with its descriptor filled in `init`).
- *heapless.* A heapless `Box` cannot be made from a raw pointer, so the
  adapter keeps the live boxes in a table indexed by the block's place.
  That costs a few instructions per call, and 128 bytes of the RAM below.
- *atomic-pool.* Its `Box::into_raw`/`from_raw` carry a block across the C
  interface. It has no reset, so the test gives every block back after
  each run.
- *Rust block type.* For both Rust pools it is `MaybeUninit<[u8; 32]>`, so
  neither copies a value into a block when it hands it out.

## The host test, and that it can fail

`test_pool.c`: for every configuration, 64 random sequences of 20 000 calls
and then the fixed patterns of the board scenarios. After every call it
checks:
- capacity, exactly 32 blocks;
- the region and the promised alignment;
- no block twice;
- each holder's pattern intact at its free;
- the canaries around the pool's memory intact;
- interrupts on again after the call;
- at the end, all 32 blocks back.

Four broken builds of the reference must be caught. Run on 2026-11-26
(`make test`; `make san` gives the same lines):

```
pools host test: 32 blocks of 32 bytes, 64 random sequences of 20000 steps and the board patterns
reference free list (ours)                   pass   (expected pass)  interrupt-off sections: 0
reference free list, interrupts off (ours)   pass   (expected pass)  interrupt-off sections: 1290050
broken: block handed out twice               FAIL   (expected FAIL)  random 0, step 5: no block twice: a block handed out that the test holds
broken: block lost                           FAIL   (expected FAIL)  random 0, step 228: capacity: no block although fewer than POOL_BLOCKS are held
broken: write outside the pool               FAIL   (expected FAIL)  random 0, step 9: no write outside: a canary around the pool's memory was changed (free)
broken: block misaligned                     FAIL   (expected FAIL)  random 0, step 4: region: a block at a smaller alignment than promised
ETL etl::pool (C++)                          pass   (expected pass)  interrupt-off sections: 0
RIOT memarray (C)                            pass   (expected pass)  interrupt-off sections: 0
ThreadX block pool (C)                       pass   (expected pass)  interrupt-off sections: 1290243
CMSIS-RTX osRtxMemoryPool (C)                pass   (expected pass)  interrupt-off sections: 1290050
Contiki-NG memb (C)                          pass   (expected pass)  interrupt-off sections: 0
C_Allocator fb_allocator (C)                 pass   (expected pass)  interrupt-off sections: 0
MemoryPool Fixed (C++)                       pass   (expected pass)  interrupt-off sections: 0
heapless pool, BoxPool (Rust)                pass   (expected pass)  interrupt-off sections: 0
atomic-pool (Rust)                           pass   (expected pass)  interrupt-off sections: 0
lwIP memp (C)                                pass   (expected pass)  interrupt-off sections: 1290050
exit 0: every verdict as expected
```

**Where the host differs from the boards, and what the host verdict
covers** (per row; on a board, the per-call checks of the bench image are
then the test of what the host does not run):
- *The sanitizers* cover the C and C++ code. The Rust library is built
  without them, so for heapless and atomic-pool the host verdict is the
  test's own checks and, for atomic-pool, Miri.
- *CMSIS-RTX.*
  - Ran on the host: its Armv6-M variant (interrupts off), the one the
    two Cortex-M0+ boards run.
  - Not run: its LDREX/STREX variant, which the Cortex-M4, M7 and M33
    boards run. It is Arm inline assembly, and no host check runs it; the
    exclusive-monitor model of the prechecks is for the later concurrency
    series.
  - So on those four boards the bench image's per-call checks are the only
    test of the code they run.
- *heapless.*
  - Ran on the host: its CAS path (`treiber/cas.rs`, with portable-atomic's
    `AtomicU128`).
  - Not run: its board path, the LL/SC stack (`treiber/llsc.rs`). No host
    check runs it, and no Miri run does (above).
  - So the per-call checks of the bench image are the only test of the
    heapless code the boards run.
- *MemoryPool.*
  - Ran on the host: the pool with its `std::mutex` taken in every call.
  - On the boards: the same list code without the mutex (compiled out).
  - The host verdict covers the free list; the boards run it without the
    lock calls around it.
- *ThreadX and lwIP.*
  - Ran on the host: their interrupts-off calls, through a counted flag.
  - On the boards: PRIMASK. The library code is the same; only the two
    macros differ.
- *atomic-pool.*
  - Ran on the host: x86-64's native atomics.
  - On the Cortex-M0+: portable-atomic's `unsafe-assume-single-core`
    (interrupts off around each atomic operation). No host check runs that.
  - On the M0+ boards, the per-call checks are the only test of it.
- *The others* (the reference, the PRIMASK row as a flag, ETL, RIOT,
  Contiki-NG, C_Allocator) run the same code on the host as on the boards,
  but for the compiler and the target.

**CBMC on the reference** (`proof/ref_harness.c`, `make proof`):
- *What it proves.* For 4 blocks and every sequence of 8 calls, the free
  list is exactly the blocks not held, without repeats. alloc gives a block
  if and only if one is free, and the block is pointer-aligned and not held.
- *How.* `--unwinding-assertions` makes the bounds part of the proof.
- *That it can fail.* The two broken builds are refuted:

```
reference free list (ours)         pass   (expected pass)  VERIFICATION SUCCESSFUL
broken: block handed out twice     FAIL   (expected FAIL)  [check_list.unwind.0] line 40 unwinding assertion loop 0: FAILURE
broken: block lost                 FAIL   (expected FAIL)  [check_list.assertion.4] line 48 the free list holds every block not held: FAILURE
exit 0: every verdict as expected
```

**Miri** (`make miri`, the image's nightly toolchain):
- atomic-pool's test passes.
- heapless's test is marked ignored under Miri. There heapless reaches its
  LL/SC path, Arm inline assembly (`src/pool/treiber/llsc.rs` line 133,
  `ldrex`), which Miri cannot run. The native host build takes its CAS
  path.
- Miri runs with its default provenance: the C interface passes block
  addresses as integers, as `time_call` does.

## Sizes, from the cross builds

`make cross`: every configuration linked alone for each core, against the
empty program (`sizes.py`; the full table with symbols is in
`build/x/sizes.tsv`). The sizes are provisional; the board images will give
the numbers the pages show.
- *Code* is the library's and the adapter's functions.
- *RAM beyond the blocks* is the pool's memory minus the 32 × 32 bytes of
  blocks and the 32 bytes of canaries.

| Configuration | Code -Os: M0+ / M4 / M7 / M33 | Code -O2: M0+ / M4 / M7 / M33 | RAM beyond the blocks, -O2 |
|---|---|---|---|
| reference (ours) | 100 / 96 / 92 / 96 | 100 / 96 / 100 / 100 | 12 |
| reference, interrupts off (ours) | 120 / 120 / 116 / 120 | 120 / 116 / 120 / 120 | 12 |
| ETL | 160 / 152 / 152 / 152 | 172 / 172 / 172 / 176 | 25 (the pool is built in place at the first init, so no `atexit` record; 1 byte of it the adapter's flag) |
| RIOT | 316 / 440 / 440 / 368 | 306 / 434 / 434 / 362 | 8 |
| ThreadX | 974 / 678 / 678 / 678 | 1050 / 714 / 710 / 722 | 192 (a pointer in front of every block) |
| CMSIS-RTX | 250 / 264 / 264 / 264 | 254 / 286 / 288 / 286 | 24 |
| Contiki-NG | 222 / 198 / 198 / 198 | 222 / 226 / 228 / 228 | 44 (a flag per block) |
| C_Allocator | 346 / 330 / 330 / 330 | 354 / 334 / 334 / 334 | 45 |
| lwIP | 252 / 220 / 216 / 220 | 256 / 232 / 232 / 232 | 20 |
| MemoryPool | 140 / 124 / 124 / 124 | 136 / 120 / 124 / 124 | 5 |
| heapless | – / 386 / 398 / 386 | – / 404 / 412 / 404 | 136 (128 of them the adapter's table) |
| atomic-pool | 3328 / 382 / 390 / 362 | 434 / 514 / 518 / 470 | 4 |

The two Rust rows include the adapter's C wrappers (`adapter_rust.c`), which
put the descriptor's functions in the adapter's own code for the board
images (12 to 28 bytes).

atomic-pool on the Cortex-M0+ at `-Os` keeps Rust's panic formatting
(`core::fmt`, about 2.9 KB), from the `assert!`s in its
`PoolStorageImpl::free`; at `-O2` they are optimised away. heapless is not
built for the Cortex-M0+ (its own documentation).

## On the boards: images, runs and records

The board benchmark (`bench/`) follows the CRC kind's (`kinds/crc/bench`),
under method version 3 (DECISIONS 2026-11-26).

### The image

One configuration per image (`bench/main.c`), with the reference free list
(`adapter_ref.c`, in the image's fixed part) measured in the same image as
the **baseline**. The board's `time_call()` (`firmware/common/<board>`,
unchanged) times every call in cycles, less the board's counter-read
overhead. One context, no interrupts.

Per library (baseline and configuration) and per cache state (off, then on),
after one timed `init`, six scenarios:

| Scenario | What is timed |
|---|---|
| `pair` | 256 times alloc, then free of the same block, the pool almost empty |
| `pair_full` | the same with 31 of the 32 blocks held |
| `fill_drain_lifo` | 8 times: 32 allocs, then 32 frees in reverse order |
| `fill_drain_fifo` | 8 times: 32 allocs, then 32 frees in the order of the allocs |
| `mixed` | 512 calls from a fixed seed, the pool between 25 % and 75 % full; the split between alloc and free is in the counts |
| `empty` | 256 allocs on an exhausted pool (each must fail); no free |

Every call is checked outside the timed window, as in the host test:
- alloc gives a block exactly when fewer than 32 are held;
- the block lies in the pool's region, at the promised alignment, and is not one already held;
- each holder's pattern is intact at the free;
- the canaries around the pool's memory are intact after every call;
- all blocks come back at the end.

A fault counts in `errors`; a run with errors gives no run file.

Images, slots and bundles as in the CRC kind:
- eight placements per configuration;
- the layout "fixed, placement, adapter, far, library", with a gap of 6144 bytes;
- slots in segments 200 to 299 (`slots.txt`, `bench/poolslots.py`);
- built by `bench/onebuild.sh` in the toolchain image of version 2.

heapless is not built for the two Cortex-M0+ boards (`boards.txt`).

### Run files: `pools-bench-run/1`

`bench/run-pools.py` writes one file per run, with the fields of the CRC
kind's run files (`kinds/crc/bench/run-crc.py`, `record()`). The kind's own
fields:
- `kind` is `"pools"`;
- `blocks` and `block_size` are 32 and 32;
- `runs` is 256;
- `libs` is `[baseline, configuration]`, each `{name, results, errors}`.

### Records: `pools-bench/1`

`bench/poolrecords.py` writes one record per board and configuration:
`records/pools/<board>/<adapter>.json`. Fields:
- **The same in every run of the record:**
  - board: `board`, `core`, `board_id`, `board_decoded`;
  - the code: `code_location` (`"flash"`), `kind`, `adapter`, `lang` (`c`, `cpp`, `rust`), `name` (the configuration's name, from `configs.txt`);
  - the build: `bench_commit`, `toolchain_image`;
  - the measurement: `result_version` (1), `clock_hz`, `runs`, `blocks`, `block_size`, `overhead_subtracted`, `empty_call_raw_min`;
  - the image's fixed parts: `fixed_sha256`, `boot_image_sha256`, `far_bytes`, `layout`;
  - `sizes`: the configuration's sizes on this board (below), the same in all eight images.
- **Added:**
  - `toolchain`, `libs_pinned` (from the build);
  - `passes` (2);
  - `option_registers`: the board's option registers (`board-options/1`, `lab/tools/read-options.py`), read zero-write before each job; every distinct reading once, in time order. Every record has them.
- **`images`:** eight entries, one per placement (0, 4, …, 28). Each has `place`, `slot`, `image_base`, `image_bytes`, `fw_sha256`, `image_sha256` and `runs`. A run is:
  - `time`, `host`, `probe_rs`, `pass` (1 or 2), `attempt`, `wait_s`, `seconds`;
  - `run_number`, `bundle`, `bundle_sha256`;
  - `errors`, `baseline_errors` (both 0);
  - `results` and `baseline`.
- **`results` and `baseline`:** keyed `"<scenario>/<op>/cache_<off|on>"` (op `alloc` or `free`), plus `"init/cache_off"` and `"init/cache_on"`.
  - Each value is `{min, max, mean, first, count}` in cycles, the counter-read overhead already subtracted. `mean` is rounded to three decimals; `first` is the first call's.
  - `"empty/free/…"` is `null`: that scenario frees nothing.
  - The counts are fixed (256 per op; `init` 1), except `mixed`: there alloc and free share 512 calls, the same split in every run.
- **A record is made only if it is whole:** all eight placements, each in both passes; every run agreeing on what it ran; option registers in every run directory.

### Sizes: `sizes` in the record

`bench/onepool.py` (`sizes_of`) measures each configuration in its own board
image, at every placement, and the build stops if the placements disagree.

**How a section is attributed.** It compares the image's link map
(`fw.map`) with that of a null image (`bench/null_pool.c`: the same harness
and reference with a pool that does nothing, linked once per board, never
flashed). A configuration's bytes are the input sections its image has and
the null image has not, by object file and section name. So the harness,
the reference, the start-up code and the C library's memory functions (in
every image's fixed part) count for no configuration.

**Not counted:**
- the descriptor (`adapter_*`);
- the placement and gap bytes;
- strings (`.rodata.str*`, names the linker merges across objects).

**The fields, in bytes:**
- `code_bytes`: `.text*` sections, the adapter's and the library's;
- `const_bytes`: `.rodata*`, constant data in flash (for the Rust
  configurations Rust's panic location data, which has no symbol);
- `flash_bytes`: code_bytes + const_bytes;
- `ram_bytes`: `.data*` and `.bss*`, with the block storage included: the 32
  blocks of 32 bytes and the 2 × 16 bytes of canaries (1056 bytes, pool.h).
  ThreadX's pointer in front of each block counts here too.
- `ram_overhead_bytes`: ram_bytes − 1056, what the pool needs beyond the
  blocks: control data and per-block overhead (heapless: with the adapter's
  table of live boxes, 128 bytes).

**Against the cross-build table above** (which counts by symbol against an
empty program):
- `ram_overhead_bytes` is the same on every board.
- Code is up to about 10 bytes more: a section counts its padding, which a
  symbol's size leaves out.
- RIOT's code is about 300 bytes less: its `memcpy` is in every image's
  fixed part, while the empty program of the cross builds had none.

`bench/poolverify.sh` rebuilds a record's eight images and compares them
with the record (flash bytes, addresses, fixed part, boot stub, toolchain,
layout, sizes). `lab/tools/public-export.py` holds the records by the kind's own
test sources (POOLS_TEST_SOURCES).

## Files

| File | What |
|---|---|
| `pool.h` | the interface |
| `adapter_*.c`, `adapter_*.cpp` | one adapter per configuration; `adapter_ref.c` is also the PRIMASK row and the four broken builds |
| `rust/` | the Rust pools' static library with a C interface, and its Miri tests |
| `shims/`, `ports/host/` | what libraries need from their surroundings: RIOT's two headers, ThreadX's host port, CMSIS's host device header and `RTE_Components.h`, Contiki-NG's two headers, lwIP's options, architecture header and port |
| `tx_kernel_stubs.c`, `extract.py` | ThreadX without its scheduler; CMSIS-RTX's pool functions for the host |
| `test_pool.c`, `proof/`, `checks/` | the host test, the CBMC proof, the MemoryPool check |
| `cross.sh`, `cross_main.c`, `sizes.py` | the cross builds and the sizes |
| `libs.lock`, `fetch.sh`, `run.sh`, `Makefile` | pins, fetch, the container run |
| `configs.txt`, `boards.txt`, `slots.txt` | the configurations of the series, those on some boards only, the slots |
| `claims.tsv` | what each library documents about interrupts and threads, with sources, for the pages (no test source) |
| `bench/` | the board image (`main.c`, `bench.h`), its build (`onebuild.sh`, `onepool.py`, `poolslots.py`), runner (`run-pools.py`), records (`poolrecords.py`), their check (`poolverify.sh`) and the record path's host test (`test_poolrecords.py`) |
| `repeat.sh`, `bench/poolscompare.py` | repeat our results on your own board, and compare your records with ours ([reproduce](../../site/content/reproduce.md#the-pools-records)); neither measures anything or checks a record, so neither is a test source (`POOLS_NOT_SOURCES`) |

## Not done yet

- **The ledger for pools records** (`lab/tools/image-ledger.py`): until it
  makes `pools/` entries, a pools record of a commit whose pools test sources
  differ from HEAD's stops the export.
- **The concurrency series** (plan section 4): the stress judge, the contract
  check with the exclusive-monitor model, the interrupts-off time.
