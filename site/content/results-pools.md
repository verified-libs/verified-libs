# Results: fixed-block memory pools

The results of one of the three kinds of library so far; the others are
embedded ring buffers and CRC calculation ([all kinds](kinds.md)).

Cycles and bytes of fixed-block memory pools on six boards, alloc and free
in six patterns, measured in one context; every number comes from a record.
Every number is the range over eight placements of the code: two rows whose
ranges overlap are not told apart. The same numbers by board, pattern and
cache:

**[Compare them with your own weights →](compare-pools.html)**

Each part below opens with a click. In each board's first table the last
column is what each library documents about use from interrupts, with its
source: documented, not tested ([method](method-pools.md)).

<details id="what-was-measured" markdown="1">
<summary><strong>What was measured</strong>: what a pool is here, the pool's shape, what every call was checked for</summary>

A pool here is a library that hands out blocks of one size from storage
fixed at start, with `alloc` (a block, or none left) and `free`. One pool
shape is measured: 32 blocks of 32 bytes. Every number comes from a record
under [`records/pools`](../../records/README.md) and is a fact about the
pinned version, the configuration and the board it names, not a general
ranking.

Every call was checked on the board, outside the timed window: a block is
given exactly when fewer than 32 are held, lies in the pool at the promised
alignment and is not held already, its pattern is intact at its free, the
canaries around the pool are intact, and all blocks come back at the end
([method](method-pools.md)). A run with a fault gives no record.

</details>

<details id="how-to-read-the-tables" markdown="1">
<summary><strong>How to read the tables</strong>: the columns, the patterns, our two rows</summary>

Per board one fold-out: a table of bytes, init, and the pattern `pair`
(alloc, then free of the same block, the pool almost empty: the common use
in a driver), with the cache on and off; inside it a second fold-out with
every pattern: a table of bytes and init, and one table per pattern. One
row per configuration, in the order of
[`kinds/pools/configs.txt`](../../kinds/pools/configs.txt); the order is not
a ranking. Each configuration's name links to its record.

- **Cycles**: the mean of the scenario's calls, the first call included, in
  CPU cycles with the counter-read overhead subtracted, as the range over
  eight placements of the code (min–max), first pass. Two rows differ only
  where their ranges do not overlap.
- **The scenarios**: `pair` (alloc, then free of the same block, the pool
  almost empty), `pair_full` (the same with 31 of the 32 blocks held),
  `fill_drain_lifo` and `fill_drain_fifo` (32 allocs, then 32 frees in
  reverse or in the same order), `mixed` (a fixed-seed sequence, the pool
  between 25 % and 75 % full), `empty` (alloc on an exhausted pool, which
  must fail). `init` is one call.
- **Flash bytes**: the library's and the adapter's code and constant data,
  measured in the board's own images at `-O2` (what the image has that an
  image with a pool that does nothing has not;
  [the kind's README](../../kinds/pools/README.md), "Sizes"). **RAM bytes**:
  what the pool needs beyond the 32 blocks of 32 bytes and the canaries
  around them: its control data and any overhead per block.
- **Pin**: the version measured ([`kinds/pools/libs.lock`](../../kinds/pools/libs.lock)).
  MemoryPool is measured at a commit that is not a release; the
  [method page](method-pools.md) says why.
- **Lock as built**: what the library takes around a call in the build
  measured, from [the kind's README](../../kinds/pools/README.md).
- **Documented use from interrupts (not tested)**: the library's own
  words about use from interrupts or threads, with their source
  ([`kinds/pools/claims.tsv`](../../kinds/pools/claims.tsv)). This series
  does not test them.
- **Our two rows**, not libraries: the reference free list with interrupts
  off, labelled in its name cell; and, as the last row of every table, the
  reference free list itself, the baseline timed in the same images.

</details>

<!-- table:pools -->

10 libraries and 1 configuration of ours on 6 boards, 64 records; series at commit `f12caf72e130`.

<div class="onectx"><strong>Use from interrupts was tested</strong> in a series of its own, the concurrency series: an interrupt at every cycle of a call, on every board, with controls that must be caught (<a href="method-pools.html#use-from-interrupts">method</a>). What it observed is in each board's fold-out "Use from interrupts"; a library used in a way it does not document is never called failing. The numbers in the tables are of one context.</div>

<details id="nrf5340-dk" markdown="1">
<summary><strong>nRF5340 DK</strong>, 64 MHz, method version 3: 10 configurations and a row of ours, <code>pair</code> alloc 10–76 cycles with the cache on</summary>

nRF5340 DK, application core (Cortex-M33), 64 MHz. Method version 3, at 64 MHz, with the board's option registers in every record.

<div class="onectx"><strong>Use from interrupts was tested</strong> in a series of its own, the concurrency series: an interrupt at every cycle of a call, on every board, with controls that must be caught (<a href="method-pools.html#use-from-interrupts">method</a>). What it observed is in each board's fold-out "Use from interrupts"; a library used in a way it does not document is never called failing. The numbers in the tables are of one context.</div>

Pattern `pair`: alloc, then free of the same block, 256 times, the pool almost empty. Cycles per call, and of the one call of init: the range over the eight placements, first pass. Flash: code and constants; RAM: beyond the blocks and their canaries.

| Configuration · pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | alloc, cache on | free, cache on | alloc, cache off | free, cache off | Documented use from interrupts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| [ETL etl::pool (C++)](../../records/pools/nrf5340/adapter_etl.json) · 20.49.0, 7d604f2 (the ring buffers' pin) | none (the header documents none) | 176 | 25 | 81–93 | 150–172 | 42 | 14 | 84–94 | 42–59 | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) |
| [RIOT memarray (C)](../../records/pools/nrf5340/adapter_riot.json) · 9c9a6ab (the ring buffers' pin) | none | 128 | 8 | 1175–1188 | 3348–3573 | 10 | 57 | 31–49 | 132–160 | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) |
| [ThreadX block pool (C)](../../records/pools/nrf5340/adapter_threadx.json)[4] · v6.5.2.202603_rel, 93387b0 | interrupts off (TX_DISABLE), the release's port for each core | 732 | 192 | 691–707 | 1112–1167 | 76 | 40–41 | 128–141 | 97–109 | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/nrf5340/adapter_cmsis_rtx.json) · v5.9.1, b566de4 (with CMSIS 6 af1b110, Cortex_DFP cd38dbb) | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M | 288 | 24 | 296–310 | 737–783 | 34 | 66 | 77–105 | 122–151 | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) |
| [Contiki-NG memb (C)](../../records/pools/nrf5340/adapter_contiki.json) · release/v5.2, 4ccd1a3 | none (cooperative processes) | 232 | 44 | 852–858 | 1690–1709 | 33 | 46 | 68–76 | 96–111 | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) |
| [C_Allocator fb_allocator (C)](../../records/pools/nrf5340/adapter_c_allocator.json)[3] · v2.1.0, 497b465 | ALLOC_LOCK_NONE, the library's default without threads | 336 | 45 | 91–101 | 141–166 | 69 | 73 | 153–170 | 150–173 | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) |
| [lwIP memp (C)](../../records/pools/nrf5340/adapter_lwip.json) · STABLE-2_2_1_RELEASE, 77dcd25 | SYS_ARCH_PROTECT: our port, interrupts off (shims/lwip/sys_arch.c) | 236 | 20 | 333–349 | 765–833 | 43 | 68 | 110–131 | 137–156 | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) |
| [MemoryPool Fixed (C++)](../../records/pools/nrf5340/adapter_memorypool.json)[1] · main 5073178 (unreleased; after v0.1.0) | none on the boards; std::mutex on the host | 124 | 5 | 932–945 | 2125–2133 | 11 | 10 | 39–51 | 38–58 | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) |
| [heapless pool, BoxPool (Rust)](../../records/pools/nrf5340/adapter_heapless.json)[2] · 1918822 (the ring buffers' pin, version 0.9.1) | lock-free: LL/SC on the boards, a tagged CAS on the host; not on Cortex-M0+ | 404 | 136 | 369–388 | 1553–1775 | 43 | 47 | 96–104 | 101–108 | only on ARM cores with LDREX, CLREX and STREX; lock-free (source: src/pool.rs:7 at 1918822) |
| [atomic-pool (Rust)](../../records/pools/nrf5340/adapter_atomic_pool.json) · 2.0.1, ab88f3c (the head; no tag v2.0.1 exists) | atomic bitmap; on Cortex-M0+ portable-atomic's unsafe-assume-single-core | 560 | 4 | 127–146 | 204–225 | 55 | 41 | 108–124 | 86–94 | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) |
| [reference free list, interrupts off (ours)](../../records/pools/nrf5340/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | PRIMASK around each call: a row of ours, not a library | 120 | 12 | 264–272 | 712–755 | 14 | 12 | 42–59 | 40–59 | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) |
| reference free list (ours; the baseline, timed in the same images; not a library) | none | – | – | 257 | 729 | 10 | 9 | 49 | 37 | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) |

The same numbers with your own weights: the [comparison page for this board](compare-pools.html#board=nrf5340dk&scen=pair).

<details id="nrf5340-dk-use-from-interrupts" markdown="1">
<summary>Use from interrupts on this board (the concurrency series)</summary>

**Use from interrupts.** What the concurrency series observed with an interrupt at every cycle of the main context's alloc or free, cache off and on, in the classes of its method: within the library's documentation (passed, or a finding), ours, outside the library's documentation (only what was observed), and our controls, which must be caught. The longest wait of an interrupt is shown where the configuration takes interrupts off as built. Not part of any score.

| Configuration | Documented use from interrupts | Observed in the concurrency series | Trials | Instructions reached by an interrupt |
|---|---|---|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/nrf5340/adapter_etl.json) | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) | [outside its documentation; observed in 1 of 87 trials: a crash; the sweep stopped at trial 87 with the cache off, in the check after the trial; cache on not run](../../records/pools-isr/nrf5340/adapter_etl.json) | 87 | 3 of 69 |
| [RIOT memarray (C)](../../records/pools/nrf5340/adapter_riot.json) | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) | [outside its documentation; observed in 3696 of 61104 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/nrf5340/adapter_riot.json) | 61104 | 15 of 49 |
| [ThreadX block pool (C)](../../records/pools/nrf5340/adapter_threadx.json)[4] | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) | [passed: nothing observed in 74384 trials; an interrupt waited at most 44 cycles with the cache off, 21 with it on](../../records/pools-isr/nrf5340/adapter_threadx.json) | 74384 | 29 of 275 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/nrf5340/adapter_cmsis_rtx.json) | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) | [passed: nothing observed in 67708 trials](../../records/pools-isr/nrf5340/adapter_cmsis_rtx.json) | 67708 | 50 of 111 |
| [Contiki-NG memb (C)](../../records/pools/nrf5340/adapter_contiki.json) | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) | [outside its documentation; observed in 1008 of 113886 trials: a block although none was free; a block twice](../../records/pools-isr/nrf5340/adapter_contiki.json) | 113886 | 47 of 91 |
| [C_Allocator fb_allocator (C)](../../records/pools/nrf5340/adapter_c_allocator.json)[3] | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) | [outside its documentation; observed in 2536 of 90840 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/nrf5340/adapter_c_allocator.json) | 90840 | 73 of 126 |
| [lwIP memp (C)](../../records/pools/nrf5340/adapter_lwip.json) | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) | [passed: nothing observed in 77936 trials; an interrupt waited at most 60 cycles with the cache off, 28 with it on](../../records/pools-isr/nrf5340/adapter_lwip.json) | 77936 | 23 of 88 |
| [MemoryPool Fixed (C++)](../../records/pools/nrf5340/adapter_memorypool.json)[1] | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) | [outside its documentation; observed in 1600 of 44100 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/nrf5340/adapter_memorypool.json) | 44100 | 12 of 40 |
| [heapless pool, BoxPool (Rust)](../../records/pools/nrf5340/adapter_heapless.json)[2] | only on ARM cores with LDREX, CLREX and STREX; lock-free (source: src/pool.rs:7 at 1918822) | [passed: nothing observed in 63105 trials](../../records/pools-isr/nrf5340/adapter_heapless.json) | 63105 | 54 of 143 |
| [atomic-pool (Rust)](../../records/pools/nrf5340/adapter_atomic_pool.json) | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) | [passed: nothing observed in 63736 trials](../../records/pools-isr/nrf5340/adapter_atomic_pool.json) | 63736 | 47 of 164 |
| [reference free list, interrupts off (ours)](../../records/pools/nrf5340/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) | [passed: nothing observed in 43736 trials; an interrupt waited at most 28 cycles with the cache off, 15 with it on](../../records/pools-isr/nrf5340/adapter_ref_primask.json) | 43736 | 4 of 42 |
| reference free list (ours; the baseline, timed in the same images; not a library); the control without a lock | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) | [caught in 784 of 42048 trials](../../records/pools-isr/nrf5340/adapter_ref.json) | 42048 | 12 of 36 |
| broken: interrupts on too early in alloc (our control) | – | [caught in 1428 of 43248 trials; an interrupt waited at most 26 cycles with the cache off, 13 with it on](../../records/pools-isr/nrf5340/adapter_broken_isr_alloc.json) | 43248 | 7 of 37 |
| broken: interrupts on too early in free (our control) | – | [caught in 1260 of 43960 trials; an interrupt waited at most 28 cycles with the cache off, 15 with it on](../../records/pools-isr/nrf5340/adapter_broken_isr_free.json) | 43960 | 6 of 37 |

</details>

<details id="nrf5340-dk-every-pattern" markdown="1">
<summary>Every pattern on this board: bytes and init, and <code>pair</code>, <code>pair_full</code>, <code>fill_drain_lifo</code>, <code>fill_drain_fifo</code>, <code>mixed</code>, <code>empty</code></summary>

**Bytes and init.** Flash: the library's and the adapter's code and constants at `-O2`, measured in the board's images; RAM: beyond the 32 blocks of 32 bytes and the canaries. Init: cycles of one call that creates the pool in the adapter's storage, the range over the eight placements, first pass.

| Configuration | Library | Pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | Documented use from interrupts |
|---|---|---|---|---:|---:|---:|---:|---|
| [ETL etl::pool (C++)](../../records/pools/nrf5340/adapter_etl.json) | ETL | 20.49.0, 7d604f2 (the ring buffers' pin) | none (the header documents none) | 176 | 25 | 81–93 | 150–172 | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) |
| [RIOT memarray (C)](../../records/pools/nrf5340/adapter_riot.json) | RIOT | 9c9a6ab (the ring buffers' pin) | none | 128 | 8 | 1175–1188 | 3348–3573 | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) |
| [ThreadX block pool (C)](../../records/pools/nrf5340/adapter_threadx.json)[4] | Eclipse ThreadX | v6.5.2.202603_rel, 93387b0 | interrupts off (TX_DISABLE), the release's port for each core | 732 | 192 | 691–707 | 1112–1167 | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/nrf5340/adapter_cmsis_rtx.json) | CMSIS-RTX | v5.9.1, b566de4 (with CMSIS 6 af1b110, Cortex_DFP cd38dbb) | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M | 288 | 24 | 296–310 | 737–783 | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) |
| [Contiki-NG memb (C)](../../records/pools/nrf5340/adapter_contiki.json) | Contiki-NG | release/v5.2, 4ccd1a3 | none (cooperative processes) | 232 | 44 | 852–858 | 1690–1709 | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) |
| [C_Allocator fb_allocator (C)](../../records/pools/nrf5340/adapter_c_allocator.json)[3] | endurodave/C_Allocator | v2.1.0, 497b465 | ALLOC_LOCK_NONE, the library's default without threads | 336 | 45 | 91–101 | 141–166 | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) |
| [lwIP memp (C)](../../records/pools/nrf5340/adapter_lwip.json) | lwIP | STABLE-2_2_1_RELEASE, 77dcd25 | SYS_ARCH_PROTECT: our port, interrupts off (shims/lwip/sys_arch.c) | 236 | 20 | 333–349 | 765–833 | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) |
| [MemoryPool Fixed (C++)](../../records/pools/nrf5340/adapter_memorypool.json)[1] | bertmelis/MemoryPool | main 5073178 (unreleased; after v0.1.0) | none on the boards; std::mutex on the host | 124 | 5 | 932–945 | 2125–2133 | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) |
| [heapless pool, BoxPool (Rust)](../../records/pools/nrf5340/adapter_heapless.json)[2] | heapless | 1918822 (the ring buffers' pin, version 0.9.1) | lock-free: LL/SC on the boards, a tagged CAS on the host; not on Cortex-M0+ | 404 | 136 | 369–388 | 1553–1775 | only on ARM cores with LDREX, CLREX and STREX; lock-free (source: src/pool.rs:7 at 1918822) |
| [atomic-pool (Rust)](../../records/pools/nrf5340/adapter_atomic_pool.json) | embassy-rs/atomic-pool | 2.0.1, ab88f3c (the head; no tag v2.0.1 exists) | atomic bitmap; on Cortex-M0+ portable-atomic's unsafe-assume-single-core | 560 | 4 | 127–146 | 204–225 | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) |
| [reference free list, interrupts off (ours)](../../records/pools/nrf5340/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | – | – | PRIMASK around each call: a row of ours, not a library | 120 | 12 | 264–272 | 712–755 | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) |
| reference free list (ours; the baseline, timed in the same images; not a library) | – | – | none | – | – | 257 | 729 | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) |

**`pair`**: alloc, then free of the same block, 256 times, the pool almost empty. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/nrf5340/adapter_etl.json) | 42 | 14 | 84–94 | 42–59 |
| [RIOT memarray (C)](../../records/pools/nrf5340/adapter_riot.json) | 10 | 57 | 31–49 | 132–160 |
| [ThreadX block pool (C)](../../records/pools/nrf5340/adapter_threadx.json)[4] | 76 | 40–41 | 128–141 | 97–109 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/nrf5340/adapter_cmsis_rtx.json) | 34 | 66 | 77–105 | 122–151 |
| [Contiki-NG memb (C)](../../records/pools/nrf5340/adapter_contiki.json) | 33 | 46 | 68–76 | 96–111 |
| [C_Allocator fb_allocator (C)](../../records/pools/nrf5340/adapter_c_allocator.json)[3] | 69 | 73 | 153–170 | 150–173 |
| [lwIP memp (C)](../../records/pools/nrf5340/adapter_lwip.json) | 43 | 68 | 110–131 | 137–156 |
| [MemoryPool Fixed (C++)](../../records/pools/nrf5340/adapter_memorypool.json)[1] | 11 | 10 | 39–51 | 38–58 |
| [heapless pool, BoxPool (Rust)](../../records/pools/nrf5340/adapter_heapless.json)[2] | 43 | 47 | 96–104 | 101–108 |
| [atomic-pool (Rust)](../../records/pools/nrf5340/adapter_atomic_pool.json) | 55 | 41 | 108–124 | 86–94 |
| [reference free list, interrupts off (ours)](../../records/pools/nrf5340/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 14 | 12 | 42–59 | 40–59 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 10 | 9 | 49 | 37 |

**`pair_full`**: the same with 31 of the 32 blocks held. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/nrf5340/adapter_etl.json) | 40 | 14 | 83–92 | 42–59 |
| [RIOT memarray (C)](../../records/pools/nrf5340/adapter_riot.json) | 10 | 57 | 31–49 | 132–160 |
| [ThreadX block pool (C)](../../records/pools/nrf5340/adapter_threadx.json)[4] | 76 | 40–41 | 128–141 | 97–109 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/nrf5340/adapter_cmsis_rtx.json) | 34 | 66 | 77–105 | 122–151 |
| [Contiki-NG memb (C)](../../records/pools/nrf5340/adapter_contiki.json) | 281 | 263 | 688–758 | 716–750 |
| [C_Allocator fb_allocator (C)](../../records/pools/nrf5340/adapter_c_allocator.json)[3] | 69 | 73 | 153–170 | 150–173 |
| [lwIP memp (C)](../../records/pools/nrf5340/adapter_lwip.json) | 43 | 68 | 110–131 | 137–156 |
| [MemoryPool Fixed (C++)](../../records/pools/nrf5340/adapter_memorypool.json)[1] | 11 | 10 | 39–51 | 38–58 |
| [heapless pool, BoxPool (Rust)](../../records/pools/nrf5340/adapter_heapless.json)[2] | 43 | 47 | 96–104 | 101–108 |
| [atomic-pool (Rust)](../../records/pools/nrf5340/adapter_atomic_pool.json) | 55 | 41 | 108–124 | 86–94 |
| [reference free list, interrupts off (ours)](../../records/pools/nrf5340/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 14 | 12 | 42–59 | 40–59 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 10 | 9 | 49 | 37 |

**`fill_drain_lifo`**: 8 times: 32 allocs, then 32 frees in reverse order. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/nrf5340/adapter_etl.json) | 41 | 14 | 83–93 | 42–59 |
| [RIOT memarray (C)](../../records/pools/nrf5340/adapter_riot.json) | 10 | 57 | 31–49 | 132–160 |
| [ThreadX block pool (C)](../../records/pools/nrf5340/adapter_threadx.json)[4] | 76 | 40–41 | 128–141 | 97–109 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/nrf5340/adapter_cmsis_rtx.json) | 34 | 66 | 77–105 | 122–151 |
| [Contiki-NG memb (C)](../../records/pools/nrf5340/adapter_contiki.json) | 157 | 154 | 378–417 | 406–424 |
| [C_Allocator fb_allocator (C)](../../records/pools/nrf5340/adapter_c_allocator.json)[3] | 69 | 73 | 153–170 | 150–173 |
| [lwIP memp (C)](../../records/pools/nrf5340/adapter_lwip.json) | 43 | 68 | 110–131 | 137–156 |
| [MemoryPool Fixed (C++)](../../records/pools/nrf5340/adapter_memorypool.json)[1] | 11 | 10 | 39–51 | 38–58 |
| [heapless pool, BoxPool (Rust)](../../records/pools/nrf5340/adapter_heapless.json)[2] | 43 | 47 | 96–104 | 101–108 |
| [atomic-pool (Rust)](../../records/pools/nrf5340/adapter_atomic_pool.json) | 55 | 41 | 108–124 | 86–94 |
| [reference free list, interrupts off (ours)](../../records/pools/nrf5340/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 14 | 12 | 42–59 | 40–59 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 10 | 9 | 49 | 37 |

**`fill_drain_fifo`**: 8 times: 32 allocs, then 32 frees in the order of the allocs. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/nrf5340/adapter_etl.json) | 41 | 14 | 83–93 | 42–59 |
| [RIOT memarray (C)](../../records/pools/nrf5340/adapter_riot.json) | 10 | 57 | 31–49 | 132–160 |
| [ThreadX block pool (C)](../../records/pools/nrf5340/adapter_threadx.json)[4] | 76 | 40–41 | 128–141 | 97–109 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/nrf5340/adapter_cmsis_rtx.json) | 34 | 66 | 77–105 | 122–151 |
| [Contiki-NG memb (C)](../../records/pools/nrf5340/adapter_contiki.json) | 157 | 154 | 378–417 | 406–424 |
| [C_Allocator fb_allocator (C)](../../records/pools/nrf5340/adapter_c_allocator.json)[3] | 69 | 73–74 | 153–170 | 150–173 |
| [lwIP memp (C)](../../records/pools/nrf5340/adapter_lwip.json) | 43 | 68 | 110–131 | 137–156 |
| [MemoryPool Fixed (C++)](../../records/pools/nrf5340/adapter_memorypool.json)[1] | 11 | 10 | 39–51 | 38–58 |
| [heapless pool, BoxPool (Rust)](../../records/pools/nrf5340/adapter_heapless.json)[2] | 43–44 | 47 | 96–104 | 101–108 |
| [atomic-pool (Rust)](../../records/pools/nrf5340/adapter_atomic_pool.json) | 55 | 41–42 | 108–124 | 86–94 |
| [reference free list, interrupts off (ours)](../../records/pools/nrf5340/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 14 | 12 | 42–59 | 40–59 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 10 | 9 | 49 | 37 |

**`mixed`**: 512 calls from a fixed seed, the pool between 25 % and 75 % full. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/nrf5340/adapter_etl.json) | 41 | 14 | 83–93 | 42–59 |
| [RIOT memarray (C)](../../records/pools/nrf5340/adapter_riot.json) | 10 | 57 | 31–49 | 132–160 |
| [ThreadX block pool (C)](../../records/pools/nrf5340/adapter_threadx.json)[4] | 76 | 40–41 | 128–141 | 97–109 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/nrf5340/adapter_cmsis_rtx.json) | 35–36 | 66–67 | 77–105 | 122–151 |
| [Contiki-NG memb (C)](../../records/pools/nrf5340/adapter_contiki.json) | 108–110 | 112–113 | 256–283 | 283–298 |
| [C_Allocator fb_allocator (C)](../../records/pools/nrf5340/adapter_c_allocator.json)[3] | 69–70 | 73–74 | 153–170 | 150–173 |
| [lwIP memp (C)](../../records/pools/nrf5340/adapter_lwip.json) | 44–45 | 69–70 | 110–131 | 137–156 |
| [MemoryPool Fixed (C++)](../../records/pools/nrf5340/adapter_memorypool.json)[1] | 11 | 10 | 39–51 | 38–58 |
| [heapless pool, BoxPool (Rust)](../../records/pools/nrf5340/adapter_heapless.json)[2] | 43–45 | 48–49 | 96–104 | 101–108 |
| [atomic-pool (Rust)](../../records/pools/nrf5340/adapter_atomic_pool.json) | 55–56 | 41 | 108–124 | 86–94 |
| [reference free list, interrupts off (ours)](../../records/pools/nrf5340/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 14 | 12 | 42–59 | 40–59 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 10 | 9 | 49 | 37 |

**`empty`**: 256 allocs on an exhausted pool, each of which must fail; no free. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/nrf5340/adapter_etl.json) | 13 | – | 52–66 | – |
| [RIOT memarray (C)](../../records/pools/nrf5340/adapter_riot.json) | 10 | – | 31–50 | – |
| [ThreadX block pool (C)](../../records/pools/nrf5340/adapter_threadx.json)[4] | 71–72 | – | 130–154 | – |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/nrf5340/adapter_cmsis_rtx.json) | 24 | – | 69–82 | – |
| [Contiki-NG memb (C)](../../records/pools/nrf5340/adapter_contiki.json) | 283 | – | 698–781 | – |
| [C_Allocator fb_allocator (C)](../../records/pools/nrf5340/adapter_c_allocator.json)[3] | 77–78 | – | 206–238 | – |
| [lwIP memp (C)](../../records/pools/nrf5340/adapter_lwip.json) | 39 | – | 108–127 | – |
| [MemoryPool Fixed (C++)](../../records/pools/nrf5340/adapter_memorypool.json)[1] | 10 | – | 38–51 | – |
| [heapless pool, BoxPool (Rust)](../../records/pools/nrf5340/adapter_heapless.json)[2] | 29 | – | 71–85 | – |
| [atomic-pool (Rust)](../../records/pools/nrf5340/adapter_atomic_pool.json) | 45–46 | – | 92–101 | – |
| [reference free list, interrupts off (ours)](../../records/pools/nrf5340/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 13 | – | 41–60 | – |
| reference free list (ours; the baseline, timed in the same images; not a library) | 10 | – | 50 | – |

</details>

</details>

<details id="raspberry-pi-pico-2-h" markdown="1">
<summary><strong>Raspberry Pi Pico 2 H</strong>, 150 MHz, method version 3: 10 configurations and a row of ours, <code>pair</code> alloc 10–60 cycles with the cache on</summary>

Raspberry Pi Pico 2 H (RP2350A, core 0, Cortex-M33), 150 MHz. Method version 3, at 150 MHz, with the board's option registers in every record.

<div class="onectx"><strong>Use from interrupts was tested</strong> in a series of its own, the concurrency series: an interrupt at every cycle of a call, on every board, with controls that must be caught (<a href="method-pools.html#use-from-interrupts">method</a>). What it observed is in each board's fold-out "Use from interrupts"; a library used in a way it does not document is never called failing. The numbers in the tables are of one context.</div>

Pattern `pair`: alloc, then free of the same block, 256 times, the pool almost empty. Cycles per call, and of the one call of init: the range over the eight placements, first pass. Flash: code and constants; RAM: beyond the blocks and their canaries.

| Configuration · pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | alloc, cache on | free, cache on | alloc, cache off | free, cache off | Documented use from interrupts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| [ETL etl::pool (C++)](../../records/pools/rp2350/adapter_etl.json) · 20.49.0, 7d604f2 (the ring buffers' pin) | none (the header documents none) | 176 | 25 | 615–848 | 1715–1787 | 34 | 15 | 865–866 | 549–551 | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) |
| [RIOT memarray (C)](../../records/pools/rp2350/adapter_riot.json) · 9c9a6ab (the ring buffers' pin) | none | 128 | 8 | 2663–2768 | 36340–36409 | 10–11 | 42 | 493–494 | 1410–1412 | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) |
| [ThreadX block pool (C)](../../records/pools/rp2350/adapter_threadx.json)[4] · v6.5.2.202603_rel, 93387b0 | interrupts off (TX_DISABLE), the release's port for each core | 732 | 192 | 4316–4419 | 11443–11649 | 49 | 34–35 | 1093–1094 | 970 | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/rp2350/adapter_cmsis_rtx.json) · v5.9.1, b566de4 (with CMSIS 6 af1b110, Cortex_DFP cd38dbb) | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M | 288 | 24 | 1191–1316 | 7844–7913 | 33 | 51–52 | 1190–1191 | 1503–1572 | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) |
| [Contiki-NG memb (C)](../../records/pools/rp2350/adapter_contiki.json) · release/v5.2, 4ccd1a3 | none (cooperative processes) | 232 | 44 | 1787–1836 | 17155–17225 | 28 | 35 | 791–792 | 1012–1081 | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) |
| [C_Allocator fb_allocator (C)](../../records/pools/rp2350/adapter_c_allocator.json)[3] · v2.1.0, 497b465 | ALLOC_LOCK_NONE, the library's default without threads | 336 | 45 | 785–840 | 1825–1896 | 59–60 | 52–54 | 1615–1616 | 1629–1632 | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) |
| [lwIP memp (C)](../../records/pools/rp2350/adapter_lwip.json) · STABLE-2_2_1_RELEASE, 77dcd25 | SYS_ARCH_PROTECT: our port, interrupts off (shims/lwip/sys_arch.c) | 236 | 20 | 1373–1423 | 8202–8271 | 39 | 46–47 | 1287–1288 | 1437–1438 | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) |
| [MemoryPool Fixed (C++)](../../records/pools/rp2350/adapter_memorypool.json)[1] · main 5073178 (unreleased; after v0.1.0) | none on the boards; std::mutex on the host | 124 | 5 | 1769–1770 | 21885–21955 | 12 | 11 | 547 | 547–549 | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) |
| [heapless pool, BoxPool (Rust)](../../records/pools/rp2350/adapter_heapless.json)[2] · 1918822 (the ring buffers' pin, version 0.9.1) | lock-free: LL/SC on the boards, a tagged CAS on the host; not on Cortex-M0+ | 404 | 136 | 1784–1975 | 16320–16322 | 37–38 | 41 | 954 | 965 | only on ARM cores with LDREX, CLREX and STREX; lock-free (source: src/pool.rs:7 at 1918822) |
| [atomic-pool (Rust)](../../records/pools/rp2350/adapter_atomic_pool.json) · 2.0.1, ab88f3c (the head; no tag v2.0.1 exists) | atomic bitmap; on Cortex-M0+ portable-atomic's unsafe-assume-single-core | 560 | 4 | 1145–1192 | 1958–1960 | 41–42 | 35–36 | 954 | 803 | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) |
| [reference free list, interrupts off (ours)](../../records/pools/rp2350/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | PRIMASK around each call: a row of ours, not a library | 120 | 12 | 846–957 | 7793–7864 | 15–16 | 13 | 574–576 | 574–576 | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) |
| reference free list (ours; the baseline, timed in the same images; not a library) | none | – | – | 1069 | 7790 | 11 | 10 | 493 | 520 | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) |

The same numbers with your own weights: the [comparison page for this board](compare-pools.html#board=pico2&scen=pair).

<details id="raspberry-pi-pico-2-h-use-from-interrupts" markdown="1">
<summary>Use from interrupts on this board (the concurrency series)</summary>

**Use from interrupts.** What the concurrency series observed with an interrupt at every cycle of the main context's alloc or free, cache off and on, in the classes of its method: within the library's documentation (passed, or a finding), ours, outside the library's documentation (only what was observed), and our controls, which must be caught. The longest wait of an interrupt is shown where the configuration takes interrupts off as built. Not part of any score.

On this board with the cache off, a call longer than about 2,900 cycles is interrupted only in its first part: the sweep moves the interrupt up to 4,096 cycles after it is armed, and about 1,200 of those come before the call. The record's coverage per function names the instructions no interrupt landed on.

| Configuration | Documented use from interrupts | Observed in the concurrency series | Trials | Instructions reached by an interrupt |
|---|---|---|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/rp2350/adapter_etl.json) | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) | [outside its documentation; observed in 7104 of 67181 trials: a block twice; a crash; blocks lost; the sweep stopped at trial 67181 with the cache off, in the check after the trial; cache on not run](../../records/pools-isr/rp2350/adapter_etl.json) | 67181 | 27 of 69 |
| [RIOT memarray (C)](../../records/pools/rp2350/adapter_riot.json) | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) | [outside its documentation; observed in 30380 of 506364 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/rp2350/adapter_riot.json) | 506364 | 15 of 49 |
| [ThreadX block pool (C)](../../records/pools/rp2350/adapter_threadx.json)[4] | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) | [passed: nothing observed in 542468 trials; an interrupt waited at most 380 cycles with the cache off, 20 with it on](../../records/pools-isr/rp2350/adapter_threadx.json) | 542468 | 31 of 275 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/rp2350/adapter_cmsis_rtx.json) | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) | [passed: nothing observed in 605152 trials](../../records/pools-isr/rp2350/adapter_cmsis_rtx.json) | 605152 | 52 of 111 |
| [Contiki-NG memb (C)](../../records/pools/rp2350/adapter_contiki.json) | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) | [outside its documentation; observed in 3616 of 684569 trials: a block although none was free; a block twice](../../records/pools-isr/rp2350/adapter_contiki.json) | 684569 | 46 of 91 |
| [C_Allocator fb_allocator (C)](../../records/pools/rp2350/adapter_c_allocator.json)[3] | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) | [outside its documentation; observed in 12868 of 702360 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/rp2350/adapter_c_allocator.json) | 702360 | 77 of 126 |
| [lwIP memp (C)](../../records/pools/rp2350/adapter_lwip.json) | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) | [passed: nothing observed in 626024 trials; an interrupt waited at most 478 cycles with the cache off, 21 with it on](../../records/pools-isr/rp2350/adapter_lwip.json) | 626024 | 24 of 88 |
| [MemoryPool Fixed (C++)](../../records/pools/rp2350/adapter_memorypool.json)[1] | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) | [outside its documentation; observed in 14516 of 412712 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/rp2350/adapter_memorypool.json) | 412712 | 13 of 40 |
| [heapless pool, BoxPool (Rust)](../../records/pools/rp2350/adapter_heapless.json)[2] | only on ARM cores with LDREX, CLREX and STREX; lock-free (source: src/pool.rs:7 at 1918822) | [passed: nothing observed in 489480 trials](../../records/pools-isr/rp2350/adapter_heapless.json) | 489480 | 56 of 143 |
| [atomic-pool (Rust)](../../records/pools/rp2350/adapter_atomic_pool.json) | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) | [passed: nothing observed in 472892 trials](../../records/pools-isr/rp2350/adapter_atomic_pool.json) | 472892 | 50 of 164 |
| [reference free list, interrupts off (ours)](../../records/pools/rp2350/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) | [passed: nothing observed in 420684 trials; an interrupt waited at most 395 cycles with the cache off, 15 with it on](../../records/pools-isr/rp2350/adapter_ref_primask.json) | 420684 | 6 of 42 |
| reference free list (ours; the baseline, timed in the same images; not a library); the control without a lock | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) | [caught in 12740 of 412096 trials](../../records/pools-isr/rp2350/adapter_ref.json) | 412096 | 13 of 36 |
| broken: interrupts on too early in alloc (our control) | – | [caught in 17272 of 420440 trials; an interrupt waited at most 313 cycles with the cache off, 13 with it on](../../records/pools-isr/rp2350/adapter_broken_isr_alloc.json) | 420440 | 8 of 37 |
| broken: interrupts on too early in free (our control) | – | [caught in 16920 of 421020 trials; an interrupt waited at most 395 cycles with the cache off, 15 with it on](../../records/pools-isr/rp2350/adapter_broken_isr_free.json) | 421020 | 7 of 37 |

</details>

<details id="raspberry-pi-pico-2-h-every-pattern" markdown="1">
<summary>Every pattern on this board: bytes and init, and <code>pair</code>, <code>pair_full</code>, <code>fill_drain_lifo</code>, <code>fill_drain_fifo</code>, <code>mixed</code>, <code>empty</code></summary>

**Bytes and init.** Flash: the library's and the adapter's code and constants at `-O2`, measured in the board's images; RAM: beyond the 32 blocks of 32 bytes and the canaries. Init: cycles of one call that creates the pool in the adapter's storage, the range over the eight placements, first pass.

| Configuration | Library | Pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | Documented use from interrupts |
|---|---|---|---|---:|---:|---:|---:|---|
| [ETL etl::pool (C++)](../../records/pools/rp2350/adapter_etl.json) | ETL | 20.49.0, 7d604f2 (the ring buffers' pin) | none (the header documents none) | 176 | 25 | 615–848 | 1715–1787 | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) |
| [RIOT memarray (C)](../../records/pools/rp2350/adapter_riot.json) | RIOT | 9c9a6ab (the ring buffers' pin) | none | 128 | 8 | 2663–2768 | 36340–36409 | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) |
| [ThreadX block pool (C)](../../records/pools/rp2350/adapter_threadx.json)[4] | Eclipse ThreadX | v6.5.2.202603_rel, 93387b0 | interrupts off (TX_DISABLE), the release's port for each core | 732 | 192 | 4316–4419 | 11443–11649 | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/rp2350/adapter_cmsis_rtx.json) | CMSIS-RTX | v5.9.1, b566de4 (with CMSIS 6 af1b110, Cortex_DFP cd38dbb) | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M | 288 | 24 | 1191–1316 | 7844–7913 | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) |
| [Contiki-NG memb (C)](../../records/pools/rp2350/adapter_contiki.json) | Contiki-NG | release/v5.2, 4ccd1a3 | none (cooperative processes) | 232 | 44 | 1787–1836 | 17155–17225 | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) |
| [C_Allocator fb_allocator (C)](../../records/pools/rp2350/adapter_c_allocator.json)[3] | endurodave/C_Allocator | v2.1.0, 497b465 | ALLOC_LOCK_NONE, the library's default without threads | 336 | 45 | 785–840 | 1825–1896 | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) |
| [lwIP memp (C)](../../records/pools/rp2350/adapter_lwip.json) | lwIP | STABLE-2_2_1_RELEASE, 77dcd25 | SYS_ARCH_PROTECT: our port, interrupts off (shims/lwip/sys_arch.c) | 236 | 20 | 1373–1423 | 8202–8271 | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) |
| [MemoryPool Fixed (C++)](../../records/pools/rp2350/adapter_memorypool.json)[1] | bertmelis/MemoryPool | main 5073178 (unreleased; after v0.1.0) | none on the boards; std::mutex on the host | 124 | 5 | 1769–1770 | 21885–21955 | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) |
| [heapless pool, BoxPool (Rust)](../../records/pools/rp2350/adapter_heapless.json)[2] | heapless | 1918822 (the ring buffers' pin, version 0.9.1) | lock-free: LL/SC on the boards, a tagged CAS on the host; not on Cortex-M0+ | 404 | 136 | 1784–1975 | 16320–16322 | only on ARM cores with LDREX, CLREX and STREX; lock-free (source: src/pool.rs:7 at 1918822) |
| [atomic-pool (Rust)](../../records/pools/rp2350/adapter_atomic_pool.json) | embassy-rs/atomic-pool | 2.0.1, ab88f3c (the head; no tag v2.0.1 exists) | atomic bitmap; on Cortex-M0+ portable-atomic's unsafe-assume-single-core | 560 | 4 | 1145–1192 | 1958–1960 | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) |
| [reference free list, interrupts off (ours)](../../records/pools/rp2350/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | – | – | PRIMASK around each call: a row of ours, not a library | 120 | 12 | 846–957 | 7793–7864 | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) |
| reference free list (ours; the baseline, timed in the same images; not a library) | – | – | none | – | – | 1069 | 7790 | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) |

**`pair`**: alloc, then free of the same block, 256 times, the pool almost empty. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/rp2350/adapter_etl.json) | 34 | 15 | 865–866 | 549–551 |
| [RIOT memarray (C)](../../records/pools/rp2350/adapter_riot.json) | 10–11 | 42 | 493–494 | 1410–1412 |
| [ThreadX block pool (C)](../../records/pools/rp2350/adapter_threadx.json)[4] | 49 | 34–35 | 1093–1094 | 970 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/rp2350/adapter_cmsis_rtx.json) | 33 | 51–52 | 1190–1191 | 1503–1572 |
| [Contiki-NG memb (C)](../../records/pools/rp2350/adapter_contiki.json) | 28 | 35 | 791–792 | 1012–1081 |
| [C_Allocator fb_allocator (C)](../../records/pools/rp2350/adapter_c_allocator.json)[3] | 59–60 | 52–54 | 1615–1616 | 1629–1632 |
| [lwIP memp (C)](../../records/pools/rp2350/adapter_lwip.json) | 39 | 46–47 | 1287–1288 | 1437–1438 |
| [MemoryPool Fixed (C++)](../../records/pools/rp2350/adapter_memorypool.json)[1] | 12 | 11 | 547 | 547–549 |
| [heapless pool, BoxPool (Rust)](../../records/pools/rp2350/adapter_heapless.json)[2] | 37–38 | 41 | 954 | 965 |
| [atomic-pool (Rust)](../../records/pools/rp2350/adapter_atomic_pool.json) | 41–42 | 35–36 | 954 | 803 |
| [reference free list, interrupts off (ours)](../../records/pools/rp2350/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 15–16 | 13 | 574–576 | 574–576 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 11 | 10 | 493 | 520 |

**`pair_full`**: the same with 31 of the 32 blocks held. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/rp2350/adapter_etl.json) | 29 | 14 | 860–861 | 549–551 |
| [RIOT memarray (C)](../../records/pools/rp2350/adapter_riot.json) | 10 | 41 | 493–494 | 1410–1412 |
| [ThreadX block pool (C)](../../records/pools/rp2350/adapter_threadx.json)[4] | 46 | 32 | 1093–1094 | 970 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/rp2350/adapter_cmsis_rtx.json) | 31 | 49 | 1190–1191 | 1503–1572 |
| [Contiki-NG memb (C)](../../records/pools/rp2350/adapter_contiki.json) | 274 | 250 | 7146–7147 | 7367–7436 |
| [C_Allocator fb_allocator (C)](../../records/pools/rp2350/adapter_c_allocator.json)[3] | 53 | 49–50 | 1615–1616 | 1629–1632 |
| [lwIP memp (C)](../../records/pools/rp2350/adapter_lwip.json) | 36 | 44–45 | 1287–1288 | 1437–1438 |
| [MemoryPool Fixed (C++)](../../records/pools/rp2350/adapter_memorypool.json)[1] | 11 | 10 | 547 | 547–549 |
| [heapless pool, BoxPool (Rust)](../../records/pools/rp2350/adapter_heapless.json)[2] | 35 | 39 | 954 | 965 |
| [atomic-pool (Rust)](../../records/pools/rp2350/adapter_atomic_pool.json) | 39 | 33 | 954 | 803 |
| [reference free list, interrupts off (ours)](../../records/pools/rp2350/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 14 | 12 | 574–576 | 574–576 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 10 | 9 | 493 | 520 |

**`fill_drain_lifo`**: 8 times: 32 allocs, then 32 frees in reverse order. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/rp2350/adapter_etl.json) | 30 | 14 | 860–861 | 549–551 |
| [RIOT memarray (C)](../../records/pools/rp2350/adapter_riot.json) | 10 | 41 | 493–494 | 1410–1412 |
| [ThreadX block pool (C)](../../records/pools/rp2350/adapter_threadx.json)[4] | 46 | 32 | 1093–1094 | 970 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/rp2350/adapter_cmsis_rtx.json) | 31 | 49 | 1190–1191 | 1503–1572 |
| [Contiki-NG memb (C)](../../records/pools/rp2350/adapter_contiki.json) | 150 | 142 | 3968–3970 | 4190–4258 |
| [C_Allocator fb_allocator (C)](../../records/pools/rp2350/adapter_c_allocator.json)[3] | 53 | 49–50 | 1614–1615 | 1629–1632 |
| [lwIP memp (C)](../../records/pools/rp2350/adapter_lwip.json) | 36 | 44–45 | 1287–1288 | 1437–1438 |
| [MemoryPool Fixed (C++)](../../records/pools/rp2350/adapter_memorypool.json)[1] | 11 | 10 | 547 | 547–549 |
| [heapless pool, BoxPool (Rust)](../../records/pools/rp2350/adapter_heapless.json)[2] | 35 | 39 | 954 | 965 |
| [atomic-pool (Rust)](../../records/pools/rp2350/adapter_atomic_pool.json) | 39 | 33 | 954 | 803 |
| [reference free list, interrupts off (ours)](../../records/pools/rp2350/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 14 | 12 | 574–576 | 574–576 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 10 | 9 | 493 | 520 |

**`fill_drain_fifo`**: 8 times: 32 allocs, then 32 frees in the order of the allocs. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/rp2350/adapter_etl.json) | 30 | 14 | 860–861 | 549–551 |
| [RIOT memarray (C)](../../records/pools/rp2350/adapter_riot.json) | 10 | 41 | 493–494 | 1410–1412 |
| [ThreadX block pool (C)](../../records/pools/rp2350/adapter_threadx.json)[4] | 46 | 32 | 1093–1094 | 970 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/rp2350/adapter_cmsis_rtx.json) | 31 | 49–50 | 1190–1191 | 1503–1572 |
| [Contiki-NG memb (C)](../../records/pools/rp2350/adapter_contiki.json) | 150 | 142 | 3968–3970 | 4190–4258 |
| [C_Allocator fb_allocator (C)](../../records/pools/rp2350/adapter_c_allocator.json)[3] | 53 | 49–50 | 1614–1615 | 1629–1632 |
| [lwIP memp (C)](../../records/pools/rp2350/adapter_lwip.json) | 36 | 44–45 | 1287–1288 | 1437–1438 |
| [MemoryPool Fixed (C++)](../../records/pools/rp2350/adapter_memorypool.json)[1] | 11 | 10 | 547 | 547–549 |
| [heapless pool, BoxPool (Rust)](../../records/pools/rp2350/adapter_heapless.json)[2] | 35 | 39–41 | 954 | 965 |
| [atomic-pool (Rust)](../../records/pools/rp2350/adapter_atomic_pool.json) | 39 | 33 | 954 | 803 |
| [reference free list, interrupts off (ours)](../../records/pools/rp2350/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 14 | 12 | 574–576 | 574–576 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 10 | 9 | 493 | 520 |

**`mixed`**: 512 calls from a fixed seed, the pool between 25 % and 75 % full. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/rp2350/adapter_etl.json) | 30 | 14 | 860–861 | 549–551 |
| [RIOT memarray (C)](../../records/pools/rp2350/adapter_riot.json) | 10 | 41 | 493–494 | 1410–1412 |
| [ThreadX block pool (C)](../../records/pools/rp2350/adapter_threadx.json)[4] | 46–48 | 32 | 1093–1094 | 970 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/rp2350/adapter_cmsis_rtx.json) | 31 | 49 | 1190–1191 | 1503–1572 |
| [Contiki-NG memb (C)](../../records/pools/rp2350/adapter_contiki.json) | 101–102 | 98 | 2718–2719 | 2926–2995 |
| [C_Allocator fb_allocator (C)](../../records/pools/rp2350/adapter_c_allocator.json)[3] | 53–56 | 49–50 | 1614–1615 | 1629–1632 |
| [lwIP memp (C)](../../records/pools/rp2350/adapter_lwip.json) | 36 | 44–45 | 1287–1288 | 1437–1438 |
| [MemoryPool Fixed (C++)](../../records/pools/rp2350/adapter_memorypool.json)[1] | 11 | 10 | 547 | 547–549 |
| [heapless pool, BoxPool (Rust)](../../records/pools/rp2350/adapter_heapless.json)[2] | 35–37 | 39 | 954 | 965 |
| [atomic-pool (Rust)](../../records/pools/rp2350/adapter_atomic_pool.json) | 39–41 | 33 | 954 | 803 |
| [reference free list, interrupts off (ours)](../../records/pools/rp2350/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 14 | 12 | 574–576 | 574–576 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 10 | 9 | 493 | 520 |

**`empty`**: 256 allocs on an exhausted pool, each of which must fail; no free. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/rp2350/adapter_etl.json) | 13 | – | 644–645 | – |
| [RIOT memarray (C)](../../records/pools/rp2350/adapter_riot.json) | 10 | – | 590–591 | – |
| [ThreadX block pool (C)](../../records/pools/rp2350/adapter_threadx.json)[4] | 44–45 | – | 1314–1315 | – |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/rp2350/adapter_cmsis_rtx.json) | 21 | – | 931–932 | – |
| [Contiki-NG memb (C)](../../records/pools/rp2350/adapter_contiki.json) | 276 | – | 7340–7341 | – |
| [C_Allocator fb_allocator (C)](../../records/pools/rp2350/adapter_c_allocator.json)[3] | 62–64 | – | 2538–2539 | – |
| [lwIP memp (C)](../../records/pools/rp2350/adapter_lwip.json) | 32 | – | 1330–1331 | – |
| [MemoryPool Fixed (C++)](../../records/pools/rp2350/adapter_memorypool.json)[1] | 10 | – | 617 | – |
| [heapless pool, BoxPool (Rust)](../../records/pools/rp2350/adapter_heapless.json)[2] | 21–22 | – | 711 | – |
| [atomic-pool (Rust)](../../records/pools/rp2350/adapter_atomic_pool.json) | 29 | – | 792 | – |
| [reference free list, interrupts off (ours)](../../records/pools/rp2350/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 13 | – | 671–673 | – |
| reference free list (ours; the baseline, timed in the same images; not a library) | 10 | – | 590 | – |

</details>

</details>

<details id="nucleo-g474re" markdown="1">
<summary><strong>NUCLEO-G474RE</strong>, 170 MHz, method version 3: 10 configurations and a row of ours, <code>pair</code> alloc 13–90 cycles with the cache on</summary>

NUCLEO-G474RE (STM32G474RET6, Cortex-M4F), 170 MHz. Method version 3, at 170 MHz, with the board's option registers in every record.

<div class="onectx"><strong>Use from interrupts was tested</strong> in a series of its own, the concurrency series: an interrupt at every cycle of a call, on every board, with controls that must be caught (<a href="method-pools.html#use-from-interrupts">method</a>). What it observed is in each board's fold-out "Use from interrupts"; a library used in a way it does not document is never called failing. The numbers in the tables are of one context.</div>

Pattern `pair`: alloc, then free of the same block, 256 times, the pool almost empty. Cycles per call, and of the one call of init: the range over the eight placements, first pass. Flash: code and constants; RAM: beyond the blocks and their canaries.

| Configuration · pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | alloc, cache on | free, cache on | alloc, cache off | free, cache off | Documented use from interrupts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| [ETL etl::pool (C++)](../../records/pools/stm32g474/adapter_etl.json) · 20.49.0, 7d604f2 (the ring buffers' pin) | none (the header documents none) | 172 | 25 | 84–90 | 114–121 | 42–46 | 18–22 | 63–68 | 34–39 | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) |
| [RIOT memarray (C)](../../records/pools/stm32g474/adapter_riot.json) · 9c9a6ab (the ring buffers' pin) | none | 128 | 8 | 1233–1238 | 2954–3237 | 17 | 54 | 28–33 | 106–110 | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) |
| [ThreadX block pool (C)](../../records/pools/stm32g474/adapter_threadx.json)[4] · v6.5.2.202603_rel, 93387b0 | interrupts off (TX_DISABLE), the release's port for each core | 724 | 192 | 720–723 | 935–978 | 64–68 | 50 | 89–98 | 83–87 | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g474/adapter_cmsis_rtx.json) · v5.9.1, b566de4 (with CMSIS 6 af1b110, Cortex_DFP cd38dbb) | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M | 288 | 24 | 305–307 | 650–675 | 41–49 | 68–72 | 72–91 | 105–127 | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) |
| [Contiki-NG memb (C)](../../records/pools/stm32g474/adapter_contiki.json) · release/v5.2, 4ccd1a3 | none (cooperative processes) | 232 | 44 | 969–975 | 1491–1492 | 38–46 | 46–50 | 64–67 | 79–82 | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g474/adapter_c_allocator.json)[3] · v2.1.0, 497b465 | ALLOC_LOCK_NONE, the library's default without threads | 336 | 45 | 113–118 | 121–122 | 75–90 | 72–82 | 121–125 | 111–117 | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) |
| [lwIP memp (C)](../../records/pools/stm32g474/adapter_lwip.json) · STABLE-2_2_1_RELEASE, 77dcd25 | SYS_ARCH_PROTECT: our port, interrupts off (shims/lwip/sys_arch.c) | 236 | 20 | 373–383 | 667–827 | 44–52 | 57–61 | 96–97 | 104–114 | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g474/adapter_memorypool.json)[1] · main 5073178 (unreleased; after v0.1.0) | none on the boards; std::mutex on the host | 120 | 5 | 1039–1050 | 1741–1833 | 13–17 | 13–17 | 32–34 | 30–33 | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32g474/adapter_heapless.json)[2] · 1918822 (the ring buffers' pin, version 0.9.1) | lock-free: LL/SC on the boards, a tagged CAS on the host; not on Cortex-M0+ | 404 | 136 | 392–406 | 1475–1541 | 44–45 | 49 | 79–88 | 84–99 | only on ARM cores with LDREX, CLREX and STREX; lock-free (source: src/pool.rs:7 at 1918822) |
| [atomic-pool (Rust)](../../records/pools/stm32g474/adapter_atomic_pool.json) · 2.0.1, ab88f3c (the head; no tag v2.0.1 exists) | atomic bitmap; on Cortex-M0+ portable-atomic's unsafe-assume-single-core | 604 | 4 | 141 | 152–156 | 50–72 | 43–62 | 97–98 | 81–82 | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g474/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | PRIMASK around each call: a row of ours, not a library | 116 | 12 | 270–276 | 584–621 | 17–21 | 16–20 | 34–38 | 34–36 | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) |
| reference free list (ours; the baseline, timed in the same images; not a library) | none | – | – | 270 | 584 | 17 | 17 | 33 | 31 | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) |

The same numbers with your own weights: the [comparison page for this board](compare-pools.html#board=nucleo-g474re&scen=pair).

<details id="nucleo-g474re-use-from-interrupts" markdown="1">
<summary>Use from interrupts on this board (the concurrency series)</summary>

**Use from interrupts.** What the concurrency series observed with an interrupt at every cycle of the main context's alloc or free, cache off and on, in the classes of its method: within the library's documentation (passed, or a finding), ours, outside the library's documentation (only what was observed), and our controls, which must be caught. The longest wait of an interrupt is shown where the configuration takes interrupts off as built. Not part of any score.

| Configuration | Documented use from interrupts | Observed in the concurrency series | Trials | Instructions reached by an interrupt |
|---|---|---|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g474/adapter_etl.json) | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) | [outside its documentation; observed in 704 of 4963 trials: a block twice; a crash; blocks lost; the sweep stopped at trial 4963 with the cache off, in the check after the trial; cache on not run](../../records/pools-isr/stm32g474/adapter_etl.json) | 4963 | 27 of 68 |
| [RIOT memarray (C)](../../records/pools/stm32g474/adapter_riot.json) | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) | [outside its documentation; observed in 3244 of 60308 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/stm32g474/adapter_riot.json) | 60308 | 15 of 49 |
| [ThreadX block pool (C)](../../records/pools/stm32g474/adapter_threadx.json)[4] | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) | [passed: nothing observed in 73272 trials; an interrupt waited at most 30 cycles with the cache off, 29 with it on](../../records/pools-isr/stm32g474/adapter_threadx.json) | 73272 | 30 of 276 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g474/adapter_cmsis_rtx.json) | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) | [passed: nothing observed in 73088 trials](../../records/pools-isr/stm32g474/adapter_cmsis_rtx.json) | 73088 | 54 of 110 |
| [Contiki-NG memb (C)](../../records/pools/stm32g474/adapter_contiki.json) | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) | [outside its documentation; observed in 1088 of 123546 trials: a block although none was free; a block twice](../../records/pools-isr/stm32g474/adapter_contiki.json) | 123546 | 52 of 91 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g474/adapter_c_allocator.json)[3] | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) | [outside its documentation; observed in 1824 of 83280 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/stm32g474/adapter_c_allocator.json) | 83280 | 75 of 126 |
| [lwIP memp (C)](../../records/pools/stm32g474/adapter_lwip.json) | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) | [passed: nothing observed in 74236 trials; an interrupt waited at most 35 cycles with the cache off, 18 with it on](../../records/pools-isr/stm32g474/adapter_lwip.json) | 74236 | 24 of 88 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g474/adapter_memorypool.json)[1] | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) | [outside its documentation; observed in 984 of 47268 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/stm32g474/adapter_memorypool.json) | 47268 | 12 of 38 |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32g474/adapter_heapless.json)[2] | only on ARM cores with LDREX, CLREX and STREX; lock-free (source: src/pool.rs:7 at 1918822) | [passed: nothing observed in 67052 trials](../../records/pools-isr/stm32g474/adapter_heapless.json) | 67052 | 56 of 143 |
| [atomic-pool (Rust)](../../records/pools/stm32g474/adapter_atomic_pool.json) | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) | [passed: nothing observed in 68156 trials](../../records/pools-isr/stm32g474/adapter_atomic_pool.json) | 68156 | 56 of 175 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g474/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) | [passed: nothing observed in 48904 trials; an interrupt waited at most 17 cycles with the cache off, 12 with it on](../../records/pools-isr/stm32g474/adapter_ref_primask.json) | 48904 | 5 of 40 |
| reference free list (ours; the baseline, timed in the same images; not a library); the control without a lock | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) | [caught in 900 of 46644 trials](../../records/pools-isr/stm32g474/adapter_ref.json) | 46644 | 12 of 34 |
| broken: interrupts on too early in alloc (our control) | – | [caught in 1496 of 49076 trials; an interrupt waited at most 16 cycles with the cache off, 12 with it on](../../records/pools-isr/stm32g474/adapter_broken_isr_alloc.json) | 49076 | 7 of 37 |
| broken: interrupts on too early in free (our control) | – | [caught in 1456 of 49524 trials; an interrupt waited at most 18 cycles with the cache off, 12 with it on](../../records/pools-isr/stm32g474/adapter_broken_isr_free.json) | 49524 | 7 of 37 |

</details>

<details id="nucleo-g474re-every-pattern" markdown="1">
<summary>Every pattern on this board: bytes and init, and <code>pair</code>, <code>pair_full</code>, <code>fill_drain_lifo</code>, <code>fill_drain_fifo</code>, <code>mixed</code>, <code>empty</code></summary>

**Bytes and init.** Flash: the library's and the adapter's code and constants at `-O2`, measured in the board's images; RAM: beyond the 32 blocks of 32 bytes and the canaries. Init: cycles of one call that creates the pool in the adapter's storage, the range over the eight placements, first pass.

| Configuration | Library | Pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | Documented use from interrupts |
|---|---|---|---|---:|---:|---:|---:|---|
| [ETL etl::pool (C++)](../../records/pools/stm32g474/adapter_etl.json) | ETL | 20.49.0, 7d604f2 (the ring buffers' pin) | none (the header documents none) | 172 | 25 | 84–90 | 114–121 | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) |
| [RIOT memarray (C)](../../records/pools/stm32g474/adapter_riot.json) | RIOT | 9c9a6ab (the ring buffers' pin) | none | 128 | 8 | 1233–1238 | 2954–3237 | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) |
| [ThreadX block pool (C)](../../records/pools/stm32g474/adapter_threadx.json)[4] | Eclipse ThreadX | v6.5.2.202603_rel, 93387b0 | interrupts off (TX_DISABLE), the release's port for each core | 724 | 192 | 720–723 | 935–978 | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g474/adapter_cmsis_rtx.json) | CMSIS-RTX | v5.9.1, b566de4 (with CMSIS 6 af1b110, Cortex_DFP cd38dbb) | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M | 288 | 24 | 305–307 | 650–675 | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) |
| [Contiki-NG memb (C)](../../records/pools/stm32g474/adapter_contiki.json) | Contiki-NG | release/v5.2, 4ccd1a3 | none (cooperative processes) | 232 | 44 | 969–975 | 1491–1492 | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g474/adapter_c_allocator.json)[3] | endurodave/C_Allocator | v2.1.0, 497b465 | ALLOC_LOCK_NONE, the library's default without threads | 336 | 45 | 113–118 | 121–122 | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) |
| [lwIP memp (C)](../../records/pools/stm32g474/adapter_lwip.json) | lwIP | STABLE-2_2_1_RELEASE, 77dcd25 | SYS_ARCH_PROTECT: our port, interrupts off (shims/lwip/sys_arch.c) | 236 | 20 | 373–383 | 667–827 | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g474/adapter_memorypool.json)[1] | bertmelis/MemoryPool | main 5073178 (unreleased; after v0.1.0) | none on the boards; std::mutex on the host | 120 | 5 | 1039–1050 | 1741–1833 | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32g474/adapter_heapless.json)[2] | heapless | 1918822 (the ring buffers' pin, version 0.9.1) | lock-free: LL/SC on the boards, a tagged CAS on the host; not on Cortex-M0+ | 404 | 136 | 392–406 | 1475–1541 | only on ARM cores with LDREX, CLREX and STREX; lock-free (source: src/pool.rs:7 at 1918822) |
| [atomic-pool (Rust)](../../records/pools/stm32g474/adapter_atomic_pool.json) | embassy-rs/atomic-pool | 2.0.1, ab88f3c (the head; no tag v2.0.1 exists) | atomic bitmap; on Cortex-M0+ portable-atomic's unsafe-assume-single-core | 604 | 4 | 141 | 152–156 | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g474/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | – | – | PRIMASK around each call: a row of ours, not a library | 116 | 12 | 270–276 | 584–621 | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) |
| reference free list (ours; the baseline, timed in the same images; not a library) | – | – | none | – | – | 270 | 584 | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) |

**`pair`**: alloc, then free of the same block, 256 times, the pool almost empty. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g474/adapter_etl.json) | 42–46 | 18–22 | 63–68 | 34–39 |
| [RIOT memarray (C)](../../records/pools/stm32g474/adapter_riot.json) | 17 | 54 | 28–33 | 106–110 |
| [ThreadX block pool (C)](../../records/pools/stm32g474/adapter_threadx.json)[4] | 64–68 | 50 | 89–98 | 83–87 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g474/adapter_cmsis_rtx.json) | 41–49 | 68–72 | 72–91 | 105–127 |
| [Contiki-NG memb (C)](../../records/pools/stm32g474/adapter_contiki.json) | 38–46 | 46–50 | 64–67 | 79–82 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g474/adapter_c_allocator.json)[3] | 75–90 | 72–82 | 121–125 | 111–117 |
| [lwIP memp (C)](../../records/pools/stm32g474/adapter_lwip.json) | 44–52 | 57–61 | 96–97 | 104–114 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g474/adapter_memorypool.json)[1] | 13–17 | 13–17 | 32–34 | 30–33 |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32g474/adapter_heapless.json)[2] | 44–45 | 49 | 79–88 | 84–99 |
| [atomic-pool (Rust)](../../records/pools/stm32g474/adapter_atomic_pool.json) | 50–72 | 43–62 | 97–98 | 81–82 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g474/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 17–21 | 16–20 | 34–38 | 34–36 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 17 | 17 | 33 | 31 |

**`pair_full`**: the same with 31 of the 32 blocks held. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g474/adapter_etl.json) | 41–45 | 18–22 | 62–66 | 34–39 |
| [RIOT memarray (C)](../../records/pools/stm32g474/adapter_riot.json) | 17 | 54 | 28–33 | 106–110 |
| [ThreadX block pool (C)](../../records/pools/stm32g474/adapter_threadx.json)[4] | 64–68 | 50 | 89–98 | 83–87 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g474/adapter_cmsis_rtx.json) | 41–49 | 68–72 | 72–91 | 105–127 |
| [Contiki-NG memb (C)](../../records/pools/stm32g474/adapter_contiki.json) | 348–356 | 325–329 | 591–811 | 606–764 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g474/adapter_c_allocator.json)[3] | 75–90 | 72–82 | 121–125 | 111–117 |
| [lwIP memp (C)](../../records/pools/stm32g474/adapter_lwip.json) | 44–52 | 57–61 | 96–97 | 104–114 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g474/adapter_memorypool.json)[1] | 13–17 | 13–17 | 32–34 | 30–33 |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32g474/adapter_heapless.json)[2] | 44–45 | 49 | 79–88 | 84–99 |
| [atomic-pool (Rust)](../../records/pools/stm32g474/adapter_atomic_pool.json) | 50–72 | 43–62 | 97–98 | 81–82 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g474/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 17–21 | 16–20 | 34–38 | 34–36 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 17 | 17 | 33 | 31 |

**`fill_drain_lifo`**: 8 times: 32 allocs, then 32 frees in reverse order. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g474/adapter_etl.json) | 41 | 18 | 62–66 | 34–39 |
| [RIOT memarray (C)](../../records/pools/stm32g474/adapter_riot.json) | 13 | 50 | 28–33 | 106–110 |
| [ThreadX block pool (C)](../../records/pools/stm32g474/adapter_threadx.json)[4] | 64 | 50 | 89–98 | 83–87 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g474/adapter_cmsis_rtx.json) | 41 | 68 | 72–91 | 105–127 |
| [Contiki-NG memb (C)](../../records/pools/stm32g474/adapter_contiki.json) | 193 | 186 | 328–439 | 342–423 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g474/adapter_c_allocator.json)[3] | 67–68 | 64–65 | 121–125 | 111–117 |
| [lwIP memp (C)](../../records/pools/stm32g474/adapter_lwip.json) | 44 | 57 | 96–97 | 104–114 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g474/adapter_memorypool.json)[1] | 13 | 13 | 32–34 | 30–33 |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32g474/adapter_heapless.json)[2] | 44–45 | 49–50 | 79–88 | 84–99 |
| [atomic-pool (Rust)](../../records/pools/stm32g474/adapter_atomic_pool.json) | 50–51 | 43–44 | 97–98 | 81–82 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g474/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 17 | 16 | 34–38 | 34–36 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 13 | 13 | 33 | 31 |

**`fill_drain_fifo`**: 8 times: 32 allocs, then 32 frees in the order of the allocs. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g474/adapter_etl.json) | 41–42 | 18 | 62–66 | 34–39 |
| [RIOT memarray (C)](../../records/pools/stm32g474/adapter_riot.json) | 13 | 50 | 28–33 | 106–110 |
| [ThreadX block pool (C)](../../records/pools/stm32g474/adapter_threadx.json)[4] | 64–65 | 50–51 | 89–98 | 83–87 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g474/adapter_cmsis_rtx.json) | 41–42 | 68 | 72–91 | 105–127 |
| [Contiki-NG memb (C)](../../records/pools/stm32g474/adapter_contiki.json) | 193 | 186 | 328–439 | 342–423 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g474/adapter_c_allocator.json)[3] | 68 | 65 | 121–125 | 111–117 |
| [lwIP memp (C)](../../records/pools/stm32g474/adapter_lwip.json) | 44 | 57 | 96–97 | 104–114 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g474/adapter_memorypool.json)[1] | 13 | 13 | 32–34 | 30–33 |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32g474/adapter_heapless.json)[2] | 45 | 50 | 79–88 | 84–99 |
| [atomic-pool (Rust)](../../records/pools/stm32g474/adapter_atomic_pool.json) | 51 | 43–44 | 97–98 | 81–82 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g474/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 17 | 16 | 34–38 | 34–36 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 13 | 13 | 33 | 31 |

**`mixed`**: 512 calls from a fixed seed, the pool between 25 % and 75 % full. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g474/adapter_etl.json) | 41–43 | 18–20 | 62–66 | 34–39 |
| [RIOT memarray (C)](../../records/pools/stm32g474/adapter_riot.json) | 15 | 52 | 28–33 | 106–110 |
| [ThreadX block pool (C)](../../records/pools/stm32g474/adapter_threadx.json)[4] | 64–68 | 50–60 | 89–98 | 83–87 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g474/adapter_cmsis_rtx.json) | 41–45 | 68–70 | 72–91 | 105–127 |
| [Contiki-NG memb (C)](../../records/pools/stm32g474/adapter_contiki.json) | 132–136 | 130–132 | 224–293 | 238–287 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g474/adapter_c_allocator.json)[3] | 75–83 | 73–75 | 121–125 | 111–117 |
| [lwIP memp (C)](../../records/pools/stm32g474/adapter_lwip.json) | 44–48 | 57–59 | 96–97 | 104–114 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g474/adapter_memorypool.json)[1] | 13–15 | 13–15 | 32–34 | 30–33 |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32g474/adapter_heapless.json)[2] | 44–58 | 49–63 | 79–88 | 84–99 |
| [atomic-pool (Rust)](../../records/pools/stm32g474/adapter_atomic_pool.json) | 50–65 | 43–53 | 97–98 | 81–82 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g474/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 17–19 | 16–18 | 34–38 | 34–36 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 15 | 13 | 33 | 31 |

**`empty`**: 256 allocs on an exhausted pool, each of which must fail; no free. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g474/adapter_etl.json) | 15 | – | 39 | – |
| [RIOT memarray (C)](../../records/pools/stm32g474/adapter_riot.json) | 13 | – | 29–38 | – |
| [ThreadX block pool (C)](../../records/pools/stm32g474/adapter_threadx.json)[4] | 59 | – | 102–103 | – |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g474/adapter_cmsis_rtx.json) | 28 | – | 67 | – |
| [Contiki-NG memb (C)](../../records/pools/stm32g474/adapter_contiki.json) | 348 | – | 601–822 | – |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g474/adapter_c_allocator.json)[3] | 76 | – | 176 | – |
| [lwIP memp (C)](../../records/pools/stm32g474/adapter_lwip.json) | 41 | – | 95 | – |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g474/adapter_memorypool.json)[1] | 13 | – | 30–33 | – |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32g474/adapter_heapless.json)[2] | 29 | – | 53–62 | – |
| [atomic-pool (Rust)](../../records/pools/stm32g474/adapter_atomic_pool.json) | 37 | – | 66–73 | – |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g474/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 17 | – | 35–39 | – |
| reference free list (ours; the baseline, timed in the same images; not a library) | 13 | – | 29 | – |

</details>

</details>

<details id="nucleo-h723zg" markdown="1">
<summary><strong>NUCLEO-H723ZG</strong>, 520 MHz, method version 3: 10 configurations and a row of ours, <code>pair</code> alloc 11–60 cycles with the cache on</summary>

NUCLEO-H723ZG (STM32H723ZGT6, Cortex-M7), 520 MHz. Method version 3, at 520 MHz, with the board's option registers in every record.

<div class="onectx"><strong>Use from interrupts was tested</strong> in a series of its own, the concurrency series: an interrupt at every cycle of a call, on every board, with controls that must be caught (<a href="method-pools.html#use-from-interrupts">method</a>). What it observed is in each board's fold-out "Use from interrupts"; a library used in a way it does not document is never called failing. The numbers in the tables are of one context.</div>

Pattern `pair`: alloc, then free of the same block, 256 times, the pool almost empty. Cycles per call, and of the one call of init: the range over the eight placements, first pass. Flash: code and constants; RAM: beyond the blocks and their canaries.

| Configuration · pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | alloc, cache on | free, cache on | alloc, cache off | free, cache off | Documented use from interrupts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| [ETL etl::pool (C++)](../../records/pools/stm32h723/adapter_etl.json) · 20.49.0, 7d604f2 (the ring buffers' pin) | none (the header documents none) | 172 | 25 | 121–160 | 212–250 | 25 | 15 | 68–94 | 52–64 | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) |
| [RIOT memarray (C)](../../records/pools/stm32h723/adapter_riot.json) · 9c9a6ab (the ring buffers' pin) | none | 128 | 8 | 927–983 | 3688–4784 | 11–14 | 25–31 | 54–64 | 136–154 | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) |
| [ThreadX block pool (C)](../../records/pools/stm32h723/adapter_threadx.json)[4] · v6.5.2.202603_rel, 93387b0 | interrupts off (TX_DISABLE), the release's port for each core | 720 | 192 | 662–722 | 716–1580 | 48–50 | 47–49 | 122–152 | 120–164 | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32h723/adapter_cmsis_rtx.json) · v5.9.1, b566de4 (with CMSIS 6 af1b110, Cortex_DFP cd38dbb) | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M | 292 | 24 | 272–314 | 314–1208 | 36–38 | 51–62 | 88–140 | 128–178 | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) |
| [Contiki-NG memb (C)](../../records/pools/stm32h723/adapter_contiki.json) · release/v5.2, 4ccd1a3 | none (cooperative processes) | 232 | 44 | 583–623 | 852–880 | 29–37 | 32–43 | 78–133 | 112–182 | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32h723/adapter_c_allocator.json)[3] · v2.1.0, 497b465 | ALLOC_LOCK_NONE, the library's default without threads | 336 | 45 | 198–232 | 244–270 | 55–59 | 46–47 | 178–220 | 174–212 | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) |
| [lwIP memp (C)](../../records/pools/stm32h723/adapter_lwip.json) · STABLE-2_2_1_RELEASE, 77dcd25 | SYS_ARCH_PROTECT: our port, interrupts off (shims/lwip/sys_arch.c) | 236 | 20 | 298–344 | 384–1268 | 56–60 | 54–60 | 178–216 | 184–252 | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) |
| [MemoryPool Fixed (C++)](../../records/pools/stm32h723/adapter_memorypool.json)[1] · main 5073178 (unreleased; after v0.1.0) | none on the boards; std::mutex on the host | 124 | 5 | 568–620 | 762–1574 | 11 | 10 | 44–64 | 38–56 | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32h723/adapter_heapless.json)[2] · 1918822 (the ring buffers' pin, version 0.9.1) | lock-free: LL/SC on the boards, a tagged CAS on the host; not on Cortex-M0+ | 412 | 136 | 344–392 | 820–1700 | 39–40 | 44–45 | 108–128 | 98–130 | only on ARM cores with LDREX, CLREX and STREX; lock-free (source: src/pool.rs:7 at 1918822) |
| [atomic-pool (Rust)](../../records/pools/stm32h723/adapter_atomic_pool.json) · 2.0.1, ab88f3c (the head; no tag v2.0.1 exists) | atomic bitmap; on Cortex-M0+ portable-atomic's unsafe-assume-single-core | 608 | 4 | 202–236 | 292–334 | 55–59 | 47–48 | 120–148 | 94–126 | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) |
| [reference free list, interrupts off (ours)](../../records/pools/stm32h723/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | PRIMASK around each call: a row of ours, not a library | 120 | 12 | 219–275 | 294–1186 | 24 | 25 | 55–79 | 50–70 | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) |
| reference free list (ours; the baseline, timed in the same images; not a library) | none | – | – | 225 | 1110 | 11 | 11 | 54 | 38 | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) |

The same numbers with your own weights: the [comparison page for this board](compare-pools.html#board=nucleo-h723zg&scen=pair).

<details id="nucleo-h723zg-use-from-interrupts" markdown="1">
<summary>Use from interrupts on this board (the concurrency series)</summary>

**Use from interrupts.** What the concurrency series observed with an interrupt at every cycle of the main context's alloc or free, cache off and on, in the classes of its method: within the library's documentation (passed, or a finding), ours, outside the library's documentation (only what was observed), and our controls, which must be caught. The longest wait of an interrupt is shown where the configuration takes interrupts off as built. Not part of any score.

| Configuration | Documented use from interrupts | Observed in the concurrency series | Trials | Instructions reached by an interrupt |
|---|---|---|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32h723/adapter_etl.json) | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) | [outside its documentation; observed in 442 of 8168 trials: a block twice; a crash; blocks lost; the sweep stopped at trial 8168 with the cache off, in the check after the trial; cache on not run](../../records/pools-isr/stm32h723/adapter_etl.json) | 8168 | 19 of 69 |
| [RIOT memarray (C)](../../records/pools/stm32h723/adapter_riot.json) | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) | [outside its documentation; observed in 3519 of 79461 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/stm32h723/adapter_riot.json) | 79461 | 13 of 49 |
| [ThreadX block pool (C)](../../records/pools/stm32h723/adapter_threadx.json)[4] | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) | [passed: nothing observed in 86024 trials; an interrupt waited at most 66 cycles with the cache off, 33 with it on](../../records/pools-isr/stm32h723/adapter_threadx.json) | 86024 | 32 of 277 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32h723/adapter_cmsis_rtx.json) | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) | [passed: nothing observed in 94062 trials](../../records/pools-isr/stm32h723/adapter_cmsis_rtx.json) | 94062 | 47 of 111 |
| [Contiki-NG memb (C)](../../records/pools/stm32h723/adapter_contiki.json) | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) | [outside its documentation; observed in 1072 of 108150 trials: a block although none was free; a block twice](../../records/pools-isr/stm32h723/adapter_contiki.json) | 108150 | 43 of 91 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32h723/adapter_c_allocator.json)[3] | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) | [outside its documentation; observed in 4312 of 102868 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/stm32h723/adapter_c_allocator.json) | 102868 | 54 of 126 |
| [lwIP memp (C)](../../records/pools/stm32h723/adapter_lwip.json) | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) | [passed: nothing observed in 94516 trials; an interrupt waited at most 77 cycles with the cache off, 37 with it on](../../records/pools-isr/stm32h723/adapter_lwip.json) | 94516 | 19 of 88 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32h723/adapter_memorypool.json)[1] | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) | [outside its documentation; observed in 392 of 62725 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/stm32h723/adapter_memorypool.json) | 62725 | 9 of 40 |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32h723/adapter_heapless.json)[2] | only on ARM cores with LDREX, CLREX and STREX; lock-free (source: src/pool.rs:7 at 1918822) | [passed: nothing observed in 77186 trials](../../records/pools-isr/stm32h723/adapter_heapless.json) | 77186 | 44 of 147 |
| [atomic-pool (Rust)](../../records/pools/stm32h723/adapter_atomic_pool.json) | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) | [passed: nothing observed in 79104 trials](../../records/pools-isr/stm32h723/adapter_atomic_pool.json) | 79104 | 45 of 177 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32h723/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) | [passed: nothing observed in 67232 trials; an interrupt waited at most 67 cycles with the cache off, 27 with it on](../../records/pools-isr/stm32h723/adapter_ref_primask.json) | 67232 | 6 of 42 |
| reference free list (ours; the baseline, timed in the same images; not a library); the control without a lock | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) | [caught in 452 of 61140 trials](../../records/pools-isr/stm32h723/adapter_ref.json) | 61140 | 11 of 36 |
| broken: interrupts on too early in alloc (our control) | – | [caught in 3128 of 67068 trials; an interrupt waited at most 41 cycles with the cache off, 24 with it on](../../records/pools-isr/stm32h723/adapter_broken_isr_alloc.json) | 67068 | 8 of 37 |
| broken: interrupts on too early in free (our control) | – | [caught in 1800 of 67968 trials; an interrupt waited at most 63 cycles with the cache off, 27 with it on](../../records/pools-isr/stm32h723/adapter_broken_isr_free.json) | 67968 | 8 of 37 |

</details>

<details id="nucleo-h723zg-every-pattern" markdown="1">
<summary>Every pattern on this board: bytes and init, and <code>pair</code>, <code>pair_full</code>, <code>fill_drain_lifo</code>, <code>fill_drain_fifo</code>, <code>mixed</code>, <code>empty</code></summary>

**Bytes and init.** Flash: the library's and the adapter's code and constants at `-O2`, measured in the board's images; RAM: beyond the 32 blocks of 32 bytes and the canaries. Init: cycles of one call that creates the pool in the adapter's storage, the range over the eight placements, first pass.

| Configuration | Library | Pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | Documented use from interrupts |
|---|---|---|---|---:|---:|---:|---:|---|
| [ETL etl::pool (C++)](../../records/pools/stm32h723/adapter_etl.json) | ETL | 20.49.0, 7d604f2 (the ring buffers' pin) | none (the header documents none) | 172 | 25 | 121–160 | 212–250 | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) |
| [RIOT memarray (C)](../../records/pools/stm32h723/adapter_riot.json) | RIOT | 9c9a6ab (the ring buffers' pin) | none | 128 | 8 | 927–983 | 3688–4784 | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) |
| [ThreadX block pool (C)](../../records/pools/stm32h723/adapter_threadx.json)[4] | Eclipse ThreadX | v6.5.2.202603_rel, 93387b0 | interrupts off (TX_DISABLE), the release's port for each core | 720 | 192 | 662–722 | 716–1580 | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32h723/adapter_cmsis_rtx.json) | CMSIS-RTX | v5.9.1, b566de4 (with CMSIS 6 af1b110, Cortex_DFP cd38dbb) | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M | 292 | 24 | 272–314 | 314–1208 | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) |
| [Contiki-NG memb (C)](../../records/pools/stm32h723/adapter_contiki.json) | Contiki-NG | release/v5.2, 4ccd1a3 | none (cooperative processes) | 232 | 44 | 583–623 | 852–880 | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32h723/adapter_c_allocator.json)[3] | endurodave/C_Allocator | v2.1.0, 497b465 | ALLOC_LOCK_NONE, the library's default without threads | 336 | 45 | 198–232 | 244–270 | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) |
| [lwIP memp (C)](../../records/pools/stm32h723/adapter_lwip.json) | lwIP | STABLE-2_2_1_RELEASE, 77dcd25 | SYS_ARCH_PROTECT: our port, interrupts off (shims/lwip/sys_arch.c) | 236 | 20 | 298–344 | 384–1268 | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) |
| [MemoryPool Fixed (C++)](../../records/pools/stm32h723/adapter_memorypool.json)[1] | bertmelis/MemoryPool | main 5073178 (unreleased; after v0.1.0) | none on the boards; std::mutex on the host | 124 | 5 | 568–620 | 762–1574 | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32h723/adapter_heapless.json)[2] | heapless | 1918822 (the ring buffers' pin, version 0.9.1) | lock-free: LL/SC on the boards, a tagged CAS on the host; not on Cortex-M0+ | 412 | 136 | 344–392 | 820–1700 | only on ARM cores with LDREX, CLREX and STREX; lock-free (source: src/pool.rs:7 at 1918822) |
| [atomic-pool (Rust)](../../records/pools/stm32h723/adapter_atomic_pool.json) | embassy-rs/atomic-pool | 2.0.1, ab88f3c (the head; no tag v2.0.1 exists) | atomic bitmap; on Cortex-M0+ portable-atomic's unsafe-assume-single-core | 608 | 4 | 202–236 | 292–334 | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) |
| [reference free list, interrupts off (ours)](../../records/pools/stm32h723/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | – | – | PRIMASK around each call: a row of ours, not a library | 120 | 12 | 219–275 | 294–1186 | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) |
| reference free list (ours; the baseline, timed in the same images; not a library) | – | – | none | – | – | 225 | 1110 | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) |

**`pair`**: alloc, then free of the same block, 256 times, the pool almost empty. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32h723/adapter_etl.json) | 25 | 15 | 68–94 | 52–64 |
| [RIOT memarray (C)](../../records/pools/stm32h723/adapter_riot.json) | 11–14 | 25–31 | 54–64 | 136–154 |
| [ThreadX block pool (C)](../../records/pools/stm32h723/adapter_threadx.json)[4] | 48–50 | 47–49 | 122–152 | 120–164 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32h723/adapter_cmsis_rtx.json) | 36–38 | 51–62 | 88–140 | 128–178 |
| [Contiki-NG memb (C)](../../records/pools/stm32h723/adapter_contiki.json) | 29–37 | 32–43 | 78–133 | 112–182 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32h723/adapter_c_allocator.json)[3] | 55–59 | 46–47 | 178–220 | 174–212 |
| [lwIP memp (C)](../../records/pools/stm32h723/adapter_lwip.json) | 56–60 | 54–60 | 178–216 | 184–252 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32h723/adapter_memorypool.json)[1] | 11 | 10 | 44–64 | 38–56 |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32h723/adapter_heapless.json)[2] | 39–40 | 44–45 | 108–128 | 98–130 |
| [atomic-pool (Rust)](../../records/pools/stm32h723/adapter_atomic_pool.json) | 55–59 | 47–48 | 120–148 | 94–126 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32h723/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 24 | 25 | 55–79 | 50–70 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 11 | 11 | 54 | 38 |

**`pair_full`**: the same with 31 of the 32 blocks held. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32h723/adapter_etl.json) | 24 | 15 | 68–94 | 54–64 |
| [RIOT memarray (C)](../../records/pools/stm32h723/adapter_riot.json) | 11–14 | 25–31 | 54–64 | 136–154 |
| [ThreadX block pool (C)](../../records/pools/stm32h723/adapter_threadx.json)[4] | 48–50 | 47–49 | 122–152 | 120–164 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32h723/adapter_cmsis_rtx.json) | 36–43 | 50–58 | 88–140 | 128–178 |
| [Contiki-NG memb (C)](../../records/pools/stm32h723/adapter_contiki.json) | 220–234 | 162–181 | 272–1114 | 250–1132 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32h723/adapter_c_allocator.json)[3] | 55–58 | 47 | 191–224 | 174–218 |
| [lwIP memp (C)](../../records/pools/stm32h723/adapter_lwip.json) | 56–57 | 54–57 | 178–220 | 188–252 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32h723/adapter_memorypool.json)[1] | 11 | 10 | 44–64 | 38–56 |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32h723/adapter_heapless.json)[2] | 39 | 44–45 | 108–128 | 98–130 |
| [atomic-pool (Rust)](../../records/pools/stm32h723/adapter_atomic_pool.json) | 55 | 47–48 | 120–148 | 94–126 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32h723/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 24 | 25 | 55–79 | 50–70 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 11 | 11 | 54 | 38 |

**`fill_drain_lifo`**: 8 times: 32 allocs, then 32 frees in reverse order. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32h723/adapter_etl.json) | 18 | 9 | 49–61 | 25–35 |
| [RIOT memarray (C)](../../records/pools/stm32h723/adapter_riot.json) | 5 | 20–21 | 21–35 | 113–133 |
| [ThreadX block pool (C)](../../records/pools/stm32h723/adapter_threadx.json)[4] | 43–45 | 42–43 | 99–121 | 103–133 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32h723/adapter_cmsis_rtx.json) | 31–32 | 46–47 | 87–113 | 117–131 |
| [Contiki-NG memb (C)](../../records/pools/stm32h723/adapter_contiki.json) | 122 | 95–98 | 179–588 | 176–605 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32h723/adapter_c_allocator.json)[3] | 38 | 35–37 | 155–189 | 132–189 |
| [lwIP memp (C)](../../records/pools/stm32h723/adapter_lwip.json) | 50 | 45–46 | 163–195 | 155–190 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32h723/adapter_memorypool.json)[1] | 5 | 5 | 21–35 | 20–35 |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32h723/adapter_heapless.json)[2] | 34 | 39 | 96–107 | 99–114 |
| [atomic-pool (Rust)](../../records/pools/stm32h723/adapter_atomic_pool.json) | 50 | 42 | 107–119 | 94–109 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32h723/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 20 | 21 | 35–50 | 35–51 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 5 | 5 | 35 | 21 |

**`fill_drain_fifo`**: 8 times: 32 allocs, then 32 frees in the order of the allocs. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32h723/adapter_etl.json) | 18 | 9 | 49–61 | 25–35 |
| [RIOT memarray (C)](../../records/pools/stm32h723/adapter_riot.json) | 5 | 21 | 22–36 | 116–135 |
| [ThreadX block pool (C)](../../records/pools/stm32h723/adapter_threadx.json)[4] | 43–45 | 42–43 | 99–121 | 103–133 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32h723/adapter_cmsis_rtx.json) | 31–32 | 46–48 | 87–115 | 120–132 |
| [Contiki-NG memb (C)](../../records/pools/stm32h723/adapter_contiki.json) | 122 | 96–97 | 178–588 | 176–605 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32h723/adapter_c_allocator.json)[3] | 38 | 36–37 | 156–189 | 132–190 |
| [lwIP memp (C)](../../records/pools/stm32h723/adapter_lwip.json) | 50 | 46–47 | 163–195 | 156–191 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32h723/adapter_memorypool.json)[1] | 5 | 5 | 21–35 | 20–35 |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32h723/adapter_heapless.json)[2] | 34 | 39 | 97–107 | 99–114 |
| [atomic-pool (Rust)](../../records/pools/stm32h723/adapter_atomic_pool.json) | 50 | 42 | 107–119 | 94–109 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32h723/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 20 | 21 | 35–50 | 35–51 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 5 | 5 | 35 | 21 |

**`mixed`**: 512 calls from a fixed seed, the pool between 25 % and 75 % full. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32h723/adapter_etl.json) | 21 | 12 | 58–73 | 40–50 |
| [RIOT memarray (C)](../../records/pools/stm32h723/adapter_riot.json) | 8–11 | 23–28 | 38–52 | 125–147 |
| [ThreadX block pool (C)](../../records/pools/stm32h723/adapter_threadx.json)[4] | 47–49 | 46–48 | 112–137 | 111–149 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32h723/adapter_cmsis_rtx.json) | 34–41 | 51–56 | 88–147 | 142–163 |
| [Contiki-NG memb (C)](../../records/pools/stm32h723/adapter_contiki.json) | 89–94 | 76–82 | 144–422 | 160–424 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32h723/adapter_c_allocator.json)[3] | 47–49 | 41–42 | 174–201 | 159–205 |
| [lwIP memp (C)](../../records/pools/stm32h723/adapter_lwip.json) | 53–55 | 50–53 | 170–207 | 174–223 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32h723/adapter_memorypool.json)[1] | 8 | 8 | 33–50 | 29–45 |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32h723/adapter_heapless.json)[2] | 37 | 42 | 102–117 | 98–121 |
| [atomic-pool (Rust)](../../records/pools/stm32h723/adapter_atomic_pool.json) | 54–55 | 45 | 113–133 | 94–117 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32h723/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 22 | 23 | 47–65 | 43–60 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 8 | 8 | 44 | 29 |

**`empty`**: 256 allocs on an exhausted pool, each of which must fail; no free. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32h723/adapter_etl.json) | 7 | – | 32–50 | – |
| [RIOT memarray (C)](../../records/pools/stm32h723/adapter_riot.json) | 4 | – | 19–34 | – |
| [ThreadX block pool (C)](../../records/pools/stm32h723/adapter_threadx.json)[4] | 41–42 | – | 112–144 | – |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32h723/adapter_cmsis_rtx.json) | 18 | – | 84–98 | – |
| [Contiki-NG memb (C)](../../records/pools/stm32h723/adapter_contiki.json) | 215 | – | 270–1110 | – |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32h723/adapter_c_allocator.json)[3] | 44–45 | – | 250–290 | – |
| [lwIP memp (C)](../../records/pools/stm32h723/adapter_lwip.json) | 48–49 | – | 162–184 | – |
| [MemoryPool Fixed (C++)](../../records/pools/stm32h723/adapter_memorypool.json)[1] | 4 | – | 19–34 | – |
| [heapless pool, BoxPool (Rust)](../../records/pools/stm32h723/adapter_heapless.json)[2] | 21 | – | 74–92 | – |
| [atomic-pool (Rust)](../../records/pools/stm32h723/adapter_atomic_pool.json) | 30 | – | 86–106 | – |
| [reference free list, interrupts off (ours)](../../records/pools/stm32h723/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 19 | – | 34–49 | – |
| reference free list (ours; the baseline, timed in the same images; not a library) | 4 | – | 34 | – |

</details>

Cache off: The NUCLEO-H723ZG runs at 520 MHz with 3 flash wait states (voltage scale 0), as ST's template for the board sets it (`firmware/common/stm32h723/board.h`, method version 3). RM0468 (Table 16) requires 3 wait states for its AXI clock of 260 MHz. The numbers with the cache off carry the 3 wait states.

</details>

<details id="nucleo-g0b1re" markdown="1">
<summary><strong>NUCLEO-G0B1RE</strong>, 64 MHz, method version 3: 9 configurations and a row of ours, <code>pair</code> alloc 22–106 cycles with the cache on</summary>

NUCLEO-G0B1RE (STM32G0B1RET6, Cortex-M0+), 64 MHz. Method version 3, at 64 MHz, with the board's option registers in every record.

<div class="onectx"><strong>Use from interrupts was tested</strong> in a series of its own, the concurrency series: an interrupt at every cycle of a call, on every board, with controls that must be caught (<a href="method-pools.html#use-from-interrupts">method</a>). What it observed is in each board's fold-out "Use from interrupts"; a library used in a way it does not document is never called failing. The numbers in the tables are of one context.</div>

Pattern `pair`: alloc, then free of the same block, 256 times, the pool almost empty. Cycles per call, and of the one call of init: the range over the eight placements, first pass. Flash: code and constants; RAM: beyond the blocks and their canaries.

| Configuration · pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | alloc, cache on | free, cache on | alloc, cache off | free, cache off | Documented use from interrupts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| [ETL etl::pool (C++)](../../records/pools/stm32g0b1/adapter_etl.json) · 20.49.0, 7d604f2 (the ring buffers' pin) | none (the header documents none) | 172 | 25 | 69–71 | 99 | 56–59 | 28–29 | 67–69 | 32 | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) |
| [RIOT memarray (C)](../../records/pools/stm32g0b1/adapter_riot.json) · 9c9a6ab (the ring buffers' pin) | none | 140 | 8 | 3349–3350 | 3840 | 22 | 115 | 24 | 128–130 | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) |
| [ThreadX block pool (C)](../../records/pools/stm32g0b1/adapter_threadx.json)[4] · v6.5.2.202603_rel, 93387b0 | interrupts off (TX_DISABLE), the release's port for each core | 780 | 192 | 940–943 | 1202–1264 | 76–77 | 66–71 | 90–92 | 75–77 | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g0b1/adapter_cmsis_rtx.json) · v5.9.1, b566de4 (with CMSIS 6 af1b110, Cortex_DFP cd38dbb) | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M | 256 | 24 | 355 | 499–557 | 50–53 | 65–66 | 58–60 | 79–83 | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) |
| [Contiki-NG memb (C)](../../records/pools/stm32g0b1/adapter_contiki.json) · release/v5.2, 4ccd1a3 | none (cooperative processes) | 224 | 44 | 1021–1025 | 1441–1443 | 57–59 | 66–68 | 69 | 79 | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g0b1/adapter_c_allocator.json)[3] · v2.1.0, 497b465 | ALLOC_LOCK_NONE, the library's default without threads | 356 | 45 | 84–92 | 94–102 | 106 | 93–99 | 124–130 | 113–115 | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) |
| [lwIP memp (C)](../../records/pools/stm32g0b1/adapter_lwip.json) · STABLE-2_2_1_RELEASE, 77dcd25 | SYS_ARCH_PROTECT: our port, interrupts off (shims/lwip/sys_arch.c) | 260 | 20 | 404–406 | 609–615 | 72–77 | 78–82 | 82–90 | 96–98 | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g0b1/adapter_memorypool.json)[1] · main 5073178 (unreleased; after v0.1.0) | none on the boards; std::mutex on the host | 136 | 5 | 1127–1128 | 1652–1712 | 23 | 25 | 26–28 | 27–29 | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) |
| [atomic-pool (Rust)](../../records/pools/stm32g0b1/adapter_atomic_pool.json) · 2.0.1, ab88f3c (the head; no tag v2.0.1 exists) | atomic bitmap; on Cortex-M0+ portable-atomic's unsafe-assume-single-core | 948 | 4 | 110–117 | 131 | 101 | 65 | 122 | 77–79 | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g0b1/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | PRIMASK around each call: a row of ours, not a library | 120 | 12 | 316–317 | 454–512 | 28–31 | 28 | 33–35 | 32 | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) |
| reference free list (ours; the baseline, timed in the same images; not a library) | none | – | – | 317 | 454 | 22 | 21 | 24 | 21 | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) |

The same numbers with your own weights: the [comparison page for this board](compare-pools.html#board=nucleo-g0b1re&scen=pair).

<details id="nucleo-g0b1re-use-from-interrupts" markdown="1">
<summary>Use from interrupts on this board (the concurrency series)</summary>

**Use from interrupts.** What the concurrency series observed with an interrupt at every cycle of the main context's alloc or free, cache off and on, in the classes of its method: within the library's documentation (passed, or a finding), ours, outside the library's documentation (only what was observed), and our controls, which must be caught. The longest wait of an interrupt is shown where the configuration takes interrupts off as built. Not part of any score.

| Configuration | Documented use from interrupts | Observed in the concurrency series | Trials | Instructions reached by an interrupt |
|---|---|---|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g0b1/adapter_etl.json) | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) | [outside its documentation; observed in 689 of 4838 trials: a block twice; a crash; blocks lost; the sweep stopped at trial 4838 with the cache off, in the check after the trial; cache on not run](../../records/pools-isr/stm32g0b1/adapter_etl.json) | 4838 | 27 of 76 |
| [RIOT memarray (C)](../../records/pools/stm32g0b1/adapter_riot.json) | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) | [outside its documentation; observed in 6652 of 70640 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/stm32g0b1/adapter_riot.json) | 70640 | 16 of 59 |
| [ThreadX block pool (C)](../../records/pools/stm32g0b1/adapter_threadx.json)[4] | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) | [passed: nothing observed in 75808 trials; an interrupt waited at most 31 cycles with the cache off, 25 with it on](../../records/pools-isr/stm32g0b1/adapter_threadx.json) | 75808 | 34 of 336 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g0b1/adapter_cmsis_rtx.json) | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) | [passed: nothing observed in 67892 trials; an interrupt waited at most 22 cycles with the cache off, 16 with it on](../../records/pools-isr/stm32g0b1/adapter_cmsis_rtx.json) | 67892 | 29 of 115 |
| [Contiki-NG memb (C)](../../records/pools/stm32g0b1/adapter_contiki.json) | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) | [outside its documentation; observed in 672 of 105496 trials: a block although none was free; a block twice](../../records/pools-isr/stm32g0b1/adapter_contiki.json) | 105496 | 58 of 97 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g0b1/adapter_c_allocator.json)[3] | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) | [outside its documentation; observed in 3416 of 92392 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/stm32g0b1/adapter_c_allocator.json) | 92392 | 85 of 140 |
| [lwIP memp (C)](../../records/pools/stm32g0b1/adapter_lwip.json) | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) | [passed: nothing observed in 77200 trials; an interrupt waited at most 30 cycles with the cache off, 23 with it on](../../records/pools-isr/stm32g0b1/adapter_lwip.json) | 77200 | 31 of 105 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g0b1/adapter_memorypool.json)[1] | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) | [outside its documentation; observed in 1688 of 49664 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/stm32g0b1/adapter_memorypool.json) | 49664 | 19 of 55 |
| [atomic-pool (Rust)](../../records/pools/stm32g0b1/adapter_atomic_pool.json) | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) | [passed: nothing observed in 79388 trials; an interrupt waited at most 26 cycles with the cache off, 20 with it on](../../records/pools-isr/stm32g0b1/adapter_atomic_pool.json) | 79388 | 55 of 370 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g0b1/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) | [passed: nothing observed in 52540 trials; an interrupt waited at most 20 cycles with the cache off, 16 with it on](../../records/pools-isr/stm32g0b1/adapter_ref_primask.json) | 52540 | 7 of 48 |
| reference free list (ours; the baseline, timed in the same images; not a library); the control without a lock | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) | [caught in 1552 of 48128 trials](../../records/pools-isr/stm32g0b1/adapter_ref.json) | 48128 | 13 of 42 |
| broken: interrupts on too early in alloc (our control) | – | [caught in 2448 of 52092 trials; an interrupt waited at most 14 cycles with the cache off, 13 with it on](../../records/pools-isr/stm32g0b1/adapter_broken_isr_alloc.json) | 52092 | 11 of 44 |
| broken: interrupts on too early in free (our control) | – | [caught in 1620 of 52540 trials; an interrupt waited at most 20 cycles with the cache off, 16 with it on](../../records/pools-isr/stm32g0b1/adapter_broken_isr_free.json) | 52540 | 8 of 44 |

</details>

<details id="nucleo-g0b1re-every-pattern" markdown="1">
<summary>Every pattern on this board: bytes and init, and <code>pair</code>, <code>pair_full</code>, <code>fill_drain_lifo</code>, <code>fill_drain_fifo</code>, <code>mixed</code>, <code>empty</code></summary>

**Bytes and init.** Flash: the library's and the adapter's code and constants at `-O2`, measured in the board's images; RAM: beyond the 32 blocks of 32 bytes and the canaries. Init: cycles of one call that creates the pool in the adapter's storage, the range over the eight placements, first pass.

| Configuration | Library | Pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | Documented use from interrupts |
|---|---|---|---|---:|---:|---:|---:|---|
| [ETL etl::pool (C++)](../../records/pools/stm32g0b1/adapter_etl.json) | ETL | 20.49.0, 7d604f2 (the ring buffers' pin) | none (the header documents none) | 172 | 25 | 69–71 | 99 | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) |
| [RIOT memarray (C)](../../records/pools/stm32g0b1/adapter_riot.json) | RIOT | 9c9a6ab (the ring buffers' pin) | none | 140 | 8 | 3349–3350 | 3840 | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) |
| [ThreadX block pool (C)](../../records/pools/stm32g0b1/adapter_threadx.json)[4] | Eclipse ThreadX | v6.5.2.202603_rel, 93387b0 | interrupts off (TX_DISABLE), the release's port for each core | 780 | 192 | 940–943 | 1202–1264 | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g0b1/adapter_cmsis_rtx.json) | CMSIS-RTX | v5.9.1, b566de4 (with CMSIS 6 af1b110, Cortex_DFP cd38dbb) | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M | 256 | 24 | 355 | 499–557 | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) |
| [Contiki-NG memb (C)](../../records/pools/stm32g0b1/adapter_contiki.json) | Contiki-NG | release/v5.2, 4ccd1a3 | none (cooperative processes) | 224 | 44 | 1021–1025 | 1441–1443 | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g0b1/adapter_c_allocator.json)[3] | endurodave/C_Allocator | v2.1.0, 497b465 | ALLOC_LOCK_NONE, the library's default without threads | 356 | 45 | 84–92 | 94–102 | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) |
| [lwIP memp (C)](../../records/pools/stm32g0b1/adapter_lwip.json) | lwIP | STABLE-2_2_1_RELEASE, 77dcd25 | SYS_ARCH_PROTECT: our port, interrupts off (shims/lwip/sys_arch.c) | 260 | 20 | 404–406 | 609–615 | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g0b1/adapter_memorypool.json)[1] | bertmelis/MemoryPool | main 5073178 (unreleased; after v0.1.0) | none on the boards; std::mutex on the host | 136 | 5 | 1127–1128 | 1652–1712 | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) |
| [atomic-pool (Rust)](../../records/pools/stm32g0b1/adapter_atomic_pool.json) | embassy-rs/atomic-pool | 2.0.1, ab88f3c (the head; no tag v2.0.1 exists) | atomic bitmap; on Cortex-M0+ portable-atomic's unsafe-assume-single-core | 948 | 4 | 110–117 | 131 | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g0b1/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | – | – | PRIMASK around each call: a row of ours, not a library | 120 | 12 | 316–317 | 454–512 | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) |
| reference free list (ours; the baseline, timed in the same images; not a library) | – | – | none | – | – | 317 | 454 | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) |

**`pair`**: alloc, then free of the same block, 256 times, the pool almost empty. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g0b1/adapter_etl.json) | 56–59 | 28–29 | 67–69 | 32 |
| [RIOT memarray (C)](../../records/pools/stm32g0b1/adapter_riot.json) | 22 | 115 | 24 | 128–130 |
| [ThreadX block pool (C)](../../records/pools/stm32g0b1/adapter_threadx.json)[4] | 76–77 | 66–71 | 90–92 | 75–77 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g0b1/adapter_cmsis_rtx.json) | 50–53 | 65–66 | 58–60 | 79–83 |
| [Contiki-NG memb (C)](../../records/pools/stm32g0b1/adapter_contiki.json) | 57–59 | 66–68 | 69 | 79 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g0b1/adapter_c_allocator.json)[3] | 106 | 93–99 | 124–130 | 113–115 |
| [lwIP memp (C)](../../records/pools/stm32g0b1/adapter_lwip.json) | 72–77 | 78–82 | 82–90 | 96–98 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g0b1/adapter_memorypool.json)[1] | 23 | 25 | 26–28 | 27–29 |
| [atomic-pool (Rust)](../../records/pools/stm32g0b1/adapter_atomic_pool.json) | 101 | 65 | 122 | 77–79 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g0b1/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 28–31 | 28 | 33–35 | 32 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 22 | 21 | 24 | 21 |

**`pair_full`**: the same with 31 of the 32 blocks held. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g0b1/adapter_etl.json) | 50–52 | 28–29 | 56–58 | 32 |
| [RIOT memarray (C)](../../records/pools/stm32g0b1/adapter_riot.json) | 22 | 115 | 24 | 128–130 |
| [ThreadX block pool (C)](../../records/pools/stm32g0b1/adapter_threadx.json)[4] | 76–77 | 66–71 | 90–92 | 75–77 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g0b1/adapter_cmsis_rtx.json) | 50–53 | 65–66 | 58–60 | 79–83 |
| [Contiki-NG memb (C)](../../records/pools/stm32g0b1/adapter_contiki.json) | 305–307 | 345–347 | 441–503 | 544 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g0b1/adapter_c_allocator.json)[3] | 106 | 93–99 | 124–130 | 113–115 |
| [lwIP memp (C)](../../records/pools/stm32g0b1/adapter_lwip.json) | 72–77 | 78–82 | 82–90 | 96–98 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g0b1/adapter_memorypool.json)[1] | 23 | 25 | 26–28 | 27–29 |
| [atomic-pool (Rust)](../../records/pools/stm32g0b1/adapter_atomic_pool.json) | 101 | 65 | 122 | 77–79 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g0b1/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 28–31 | 28 | 33–35 | 32 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 22 | 21 | 24 | 21 |

**`fill_drain_lifo`**: 8 times: 32 allocs, then 32 frees in reverse order. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g0b1/adapter_etl.json) | 55–58 | 28–29 | 65–67 | 32 |
| [RIOT memarray (C)](../../records/pools/stm32g0b1/adapter_riot.json) | 22 | 115 | 24 | 128–130 |
| [ThreadX block pool (C)](../../records/pools/stm32g0b1/adapter_threadx.json)[4] | 76–77 | 66–71 | 90–92 | 75–77 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g0b1/adapter_cmsis_rtx.json) | 50–53 | 65–66 | 58–60 | 79–83 |
| [Contiki-NG memb (C)](../../records/pools/stm32g0b1/adapter_contiki.json) | 181–183 | 206–208 | 255–286 | 312 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g0b1/adapter_c_allocator.json)[3] | 106 | 93–99 | 124–130 | 113–115 |
| [lwIP memp (C)](../../records/pools/stm32g0b1/adapter_lwip.json) | 72–74 | 78–82 | 82–90 | 96–98 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g0b1/adapter_memorypool.json)[1] | 23 | 25 | 26–28 | 27–29 |
| [atomic-pool (Rust)](../../records/pools/stm32g0b1/adapter_atomic_pool.json) | 101 | 65 | 122 | 77–79 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g0b1/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 28–31 | 28 | 33–35 | 32 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 22 | 21 | 24 | 21 |

**`fill_drain_fifo`**: 8 times: 32 allocs, then 32 frees in the order of the allocs. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g0b1/adapter_etl.json) | 55–58 | 28–29 | 65–67 | 32 |
| [RIOT memarray (C)](../../records/pools/stm32g0b1/adapter_riot.json) | 22 | 115 | 24 | 128–130 |
| [ThreadX block pool (C)](../../records/pools/stm32g0b1/adapter_threadx.json)[4] | 76–77 | 66–71 | 90–92 | 75–77 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g0b1/adapter_cmsis_rtx.json) | 50–53 | 65–66 | 58–60 | 79–83 |
| [Contiki-NG memb (C)](../../records/pools/stm32g0b1/adapter_contiki.json) | 181–183 | 206–208 | 255–286 | 312 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g0b1/adapter_c_allocator.json)[3] | 106 | 93–99 | 124–130 | 113–115 |
| [lwIP memp (C)](../../records/pools/stm32g0b1/adapter_lwip.json) | 72–77 | 78–82 | 82–90 | 96–98 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g0b1/adapter_memorypool.json)[1] | 23 | 25 | 26–28 | 27–29 |
| [atomic-pool (Rust)](../../records/pools/stm32g0b1/adapter_atomic_pool.json) | 101 | 65 | 122 | 77–79 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g0b1/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 28–31 | 28 | 33–35 | 32 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 22 | 21 | 24 | 21 |

**`mixed`**: 512 calls from a fixed seed, the pool between 25 % and 75 % full. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g0b1/adapter_etl.json) | 55–58 | 28–29 | 65–67 | 32 |
| [RIOT memarray (C)](../../records/pools/stm32g0b1/adapter_riot.json) | 22 | 115 | 24 | 128–130 |
| [ThreadX block pool (C)](../../records/pools/stm32g0b1/adapter_threadx.json)[4] | 76–77 | 66–71 | 90–92 | 75–77 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g0b1/adapter_cmsis_rtx.json) | 50–53 | 65–66 | 58–60 | 79–83 |
| [Contiki-NG memb (C)](../../records/pools/stm32g0b1/adapter_contiki.json) | 132–134 | 150–152 | 182–201 | 219 |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g0b1/adapter_c_allocator.json)[3] | 106 | 93–99 | 124–130 | 113–115 |
| [lwIP memp (C)](../../records/pools/stm32g0b1/adapter_lwip.json) | 72–77 | 78–82 | 82–90 | 96–98 |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g0b1/adapter_memorypool.json)[1] | 23 | 25 | 26–28 | 27–29 |
| [atomic-pool (Rust)](../../records/pools/stm32g0b1/adapter_atomic_pool.json) | 101 | 65 | 122 | 77–79 |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g0b1/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 28–31 | 28 | 33–35 | 32 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 22 | 21 | 24 | 21 |

**`empty`**: 256 allocs on an exhausted pool, each of which must fail; no free. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/stm32g0b1/adapter_etl.json) | 39–41 | – | 40–42 | – |
| [RIOT memarray (C)](../../records/pools/stm32g0b1/adapter_riot.json) | 19–20 | – | 21 | – |
| [ThreadX block pool (C)](../../records/pools/stm32g0b1/adapter_threadx.json)[4] | 76–78 | – | 87–89 | – |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/stm32g0b1/adapter_cmsis_rtx.json) | 44–47 | – | 50 | – |
| [Contiki-NG memb (C)](../../records/pools/stm32g0b1/adapter_contiki.json) | 302–304 | – | 436–500 | – |
| [C_Allocator fb_allocator (C)](../../records/pools/stm32g0b1/adapter_c_allocator.json)[3] | 131–138 | – | 148–152 | – |
| [lwIP memp (C)](../../records/pools/stm32g0b1/adapter_lwip.json) | 69–71 | – | 76–82 | – |
| [MemoryPool Fixed (C++)](../../records/pools/stm32g0b1/adapter_memorypool.json)[1] | 20–21 | – | 23–25 | – |
| [atomic-pool (Rust)](../../records/pools/stm32g0b1/adapter_atomic_pool.json) | 59–60 | – | 66 | – |
| [reference free list, interrupts off (ours)](../../records/pools/stm32g0b1/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 25–28 | – | 30–32 | – |
| reference free list (ours; the baseline, timed in the same images; not a library) | 19 | – | 21 | – |

</details>

</details>

<details id="sam-d20-xplained-pro" markdown="1">
<summary><strong>SAM D20 Xplained Pro</strong>, 48 MHz, method version 3: 9 configurations and a row of ours, <code>pair</code> alloc 19–107 cycles with the cache on</summary>

SAM D20 Xplained Pro (ATSAMD20J18A, Cortex-M0+), 48 MHz. Method version 3, at 48 MHz, with the board's option registers in every record.

<div class="onectx"><strong>Use from interrupts was tested</strong> in a series of its own, the concurrency series: an interrupt at every cycle of a call, on every board, with controls that must be caught (<a href="method-pools.html#use-from-interrupts">method</a>). What it observed is in each board's fold-out "Use from interrupts"; a library used in a way it does not document is never called failing. The numbers in the tables are of one context.</div>

Pattern `pair`: alloc, then free of the same block, 256 times, the pool almost empty. Cycles per call, and of the one call of init: the range over the eight placements, first pass. Flash: code and constants; RAM: beyond the blocks and their canaries.

| Configuration · pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | alloc, cache on | free, cache on | alloc, cache off | free, cache off | Documented use from interrupts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| [ETL etl::pool (C++)](../../records/pools/samd20/adapter_etl.json) · 20.49.0, 7d604f2 (the ring buffers' pin) | none (the header documents none) | 172 | 25 | 60–61 | 84 | 56–57 | 26 | 61 | 28 | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) |
| [RIOT memarray (C)](../../records/pools/samd20/adapter_riot.json) · 9c9a6ab (the ring buffers' pin) | none | 140 | 8 | 3091–3186 | 3540 | 19 | 109 | 20 | 117 | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) |
| [ThreadX block pool (C)](../../records/pools/samd20/adapter_threadx.json)[4] · v6.5.2.202603_rel, 93387b0 | interrupts off (TX_DISABLE), the release's port for each core | 780 | 192 | 941–942 | 1127 | 77 | 64–66 | 87 | 70 | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/samd20/adapter_cmsis_rtx.json) · v5.9.1, b566de4 (with CMSIS 6 af1b110, Cortex_DFP cd38dbb) | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M | 256 | 24 | 353–355 | 485 | 49–50 | 66 | 55 | 74 | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) |
| [Contiki-NG memb (C)](../../records/pools/samd20/adapter_contiki.json) · release/v5.2, 4ccd1a3 | none (cooperative processes) | 224 | 44 | 1005–1008 | 1293 | 57 | 65–67 | 63 | 72 | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) |
| [C_Allocator fb_allocator (C)](../../records/pools/samd20/adapter_c_allocator.json)[3] · v2.1.0, 497b465 | ALLOC_LOCK_NONE, the library's default without threads | 356 | 45 | 74–79 | 83 | 104–107 | 94 | 116 | 102 | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) |
| [lwIP memp (C)](../../records/pools/samd20/adapter_lwip.json) · STABLE-2_2_1_RELEASE, 77dcd25 | SYS_ARCH_PROTECT: our port, interrupts off (shims/lwip/sys_arch.c) | 260 | 20 | 397–400 | 564 | 67–73 | 79–82 | 77 | 87 | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) |
| [MemoryPool Fixed (C++)](../../records/pools/samd20/adapter_memorypool.json)[1] · main 5073178 (unreleased; after v0.1.0) | none on the boards; std::mutex on the host | 136 | 5 | 1120–1123 | 1510 | 20–21 | 22 | 23 | 24 | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) |
| [atomic-pool (Rust)](../../records/pools/samd20/adapter_atomic_pool.json) · 2.0.1, ab88f3c (the head; no tag v2.0.1 exists) | atomic bitmap; on Cortex-M0+ portable-atomic's unsafe-assume-single-core | 948 | 4 | 99–103 | 111 | 99–101 | 66 | 114 | 72 | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) |
| [reference free list, interrupts off (ours)](../../records/pools/samd20/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | PRIMASK around each call: a row of ours, not a library | 120 | 12 | 312–313 | 441 | 26–27 | 25 | 31 | 29 | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) |
| reference free list (ours; the baseline, timed in the same images; not a library) | none | – | – | 312 | 441 | 19 | 18 | 20 | 18 | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) |

The same numbers with your own weights: the [comparison page for this board](compare-pools.html#board=sam-d20-xpro&scen=pair).

<details id="sam-d20-xplained-pro-use-from-interrupts" markdown="1">
<summary>Use from interrupts on this board (the concurrency series)</summary>

**Use from interrupts.** What the concurrency series observed with an interrupt at every cycle of the main context's alloc or free, cache off and on, in the classes of its method: within the library's documentation (passed, or a finding), ours, outside the library's documentation (only what was observed), and our controls, which must be caught. The longest wait of an interrupt is shown where the configuration takes interrupts off as built. Not part of any score.

| Configuration | Documented use from interrupts | Observed in the concurrency series | Trials | Instructions reached by an interrupt |
|---|---|---|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/samd20/adapter_etl.json) | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) | [outside its documentation; observed in 667 of 4217 trials: a block twice; a crash; blocks lost; the sweep stopped at trial 4217 with the cache off, in the check after the trial; cache on not run](../../records/pools-isr/samd20/adapter_etl.json) | 4217 | 27 of 76 |
| [RIOT memarray (C)](../../records/pools/samd20/adapter_riot.json) | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) | [outside its documentation; observed in 6488 of 62648 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/samd20/adapter_riot.json) | 62648 | 16 of 59 |
| [ThreadX block pool (C)](../../records/pools/samd20/adapter_threadx.json)[4] | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) | [passed: nothing observed in 69212 trials; an interrupt waited at most 29 cycles with the cache off, 25 with it on](../../records/pools-isr/samd20/adapter_threadx.json) | 69212 | 34 of 336 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/samd20/adapter_cmsis_rtx.json) | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) | [passed: nothing observed in 61672 trials; an interrupt waited at most 22 cycles with the cache off, 19 with it on](../../records/pools-isr/samd20/adapter_cmsis_rtx.json) | 61672 | 29 of 115 |
| [Contiki-NG memb (C)](../../records/pools/samd20/adapter_contiki.json) | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) | [outside its documentation; observed in 704 of 99060 trials: a block although none was free; a block twice](../../records/pools-isr/samd20/adapter_contiki.json) | 99060 | 58 of 97 |
| [C_Allocator fb_allocator (C)](../../records/pools/samd20/adapter_c_allocator.json)[3] | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) | [outside its documentation; observed in 3536 of 84328 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/samd20/adapter_c_allocator.json) | 84328 | 85 of 140 |
| [lwIP memp (C)](../../records/pools/samd20/adapter_lwip.json) | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) | [passed: nothing observed in 70360 trials; an interrupt waited at most 29 cycles with the cache off, 25 with it on](../../records/pools-isr/samd20/adapter_lwip.json) | 70360 | 31 of 105 |
| [MemoryPool Fixed (C++)](../../records/pools/samd20/adapter_memorypool.json)[1] | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) | [outside its documentation; observed in 1560 of 43128 trials: a block although none was free; a block twice; a block twice, afterwards; blocks lost](../../records/pools-isr/samd20/adapter_memorypool.json) | 43128 | 19 of 55 |
| [atomic-pool (Rust)](../../records/pools/samd20/adapter_atomic_pool.json) | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) | [passed: nothing observed in 74139 trials; an interrupt waited at most 23 cycles with the cache off, 21 with it on](../../records/pools-isr/samd20/adapter_atomic_pool.json) | 74139 | 55 of 370 |
| [reference free list, interrupts off (ours)](../../records/pools/samd20/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) | [passed: nothing observed in 45984 trials; an interrupt waited at most 18 cycles with the cache off, 14 with it on](../../records/pools-isr/samd20/adapter_ref_primask.json) | 45984 | 7 of 48 |
| reference free list (ours; the baseline, timed in the same images; not a library); the control without a lock | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) | [caught in 1688 of 41592 trials](../../records/pools-isr/samd20/adapter_ref.json) | 41592 | 13 of 42 |
| broken: interrupts on too early in alloc (our control) | – | [caught in 2176 of 45984 trials; an interrupt waited at most 15 cycles with the cache off, 13 with it on](../../records/pools-isr/samd20/adapter_broken_isr_alloc.json) | 45984 | 11 of 44 |
| broken: interrupts on too early in free (our control) | – | [caught in 1620 of 45984 trials; an interrupt waited at most 18 cycles with the cache off, 14 with it on](../../records/pools-isr/samd20/adapter_broken_isr_free.json) | 45984 | 8 of 44 |

</details>

<details id="sam-d20-xplained-pro-every-pattern" markdown="1">
<summary>Every pattern on this board: bytes and init, and <code>pair</code>, <code>pair_full</code>, <code>fill_drain_lifo</code>, <code>fill_drain_fifo</code>, <code>mixed</code>, <code>empty</code></summary>

**Bytes and init.** Flash: the library's and the adapter's code and constants at `-O2`, measured in the board's images; RAM: beyond the 32 blocks of 32 bytes and the canaries. Init: cycles of one call that creates the pool in the adapter's storage, the range over the eight placements, first pass.

| Configuration | Library | Pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | Documented use from interrupts |
|---|---|---|---|---:|---:|---:|---:|---|
| [ETL etl::pool (C++)](../../records/pools/samd20/adapter_etl.json) | ETL | 20.49.0, 7d604f2 (the ring buffers' pin) | none (the header documents none) | 172 | 25 | 60–61 | 84 | nothing about interrupts or threads (source: include/etl/pool.h at 7d604f2 (no statement)) |
| [RIOT memarray (C)](../../records/pools/samd20/adapter_riot.json) | RIOT | 9c9a6ab (the ring buffers' pin) | none | 140 | 8 | 3091–3186 | 3540 | nothing about interrupts or threads (source: sys/include/memarray.h at 9c9a6ab (no statement)) |
| [ThreadX block pool (C)](../../records/pools/samd20/adapter_threadx.json)[4] | Eclipse ThreadX | v6.5.2.202603_rel, 93387b0 | interrupts off (TX_DISABLE), the release's port for each core | 780 | 192 | 941–942 | 1127 | allocate and release allowed from ISRs; allocate from an ISR only with TX_NO_WAIT (source: https://raw.githubusercontent.com/eclipse-threadx/rtos-docs/refs/heads/main/rtos-docs/threadx/chapter4.md (tx_block_allocate, tx_block_release: Allowed From)) |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/samd20/adapter_cmsis_rtx.json) | CMSIS-RTX | v5.9.1, b566de4 (with CMSIS 6 af1b110, Cortex_DFP cd38dbb) | LDREX/STREX on Armv7-M and Armv8-M; interrupts off on Armv6-M | 256 | 24 | 353–355 | 485 | alloc from an ISR with timeout 0; free from an ISR (source: https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__PoolMgmt.html (osMemoryPoolAlloc, osMemoryPoolFree: Note)) |
| [Contiki-NG memb (C)](../../records/pools/samd20/adapter_contiki.json) | Contiki-NG | release/v5.2, 4ccd1a3 | none (cooperative processes) | 224 | 44 | 1005–1008 | 1293 | nothing about interrupts or threads (source: os/lib/memb.h at 4ccd1a3 (no statement)) |
| [C_Allocator fb_allocator (C)](../../records/pools/samd20/adapter_c_allocator.json)[3] | endurodave/C_Allocator | v2.1.0, 497b465 | ALLOC_LOCK_NONE, the library's default without threads | 356 | 45 | 74–79 | 83 | may be called from an interrupt with an interrupt-masking lock option; without threads the default is no lock (as built here) (source: README.md:390 and src/LockGuard.h:24-29 at 497b465) |
| [lwIP memp (C)](../../records/pools/samd20/adapter_lwip.json) | lwIP | STABLE-2_2_1_RELEASE, 77dcd25 | SYS_ARCH_PROTECT: our port, interrupts off (shims/lwip/sys_arch.c) | 260 | 20 | 397–400 | 564 | protected by SYS_ARCH_PROTECT, by disabling interrupts or a semaphore or mutex as the port does it; here our port: interrupts off (source: src/include/lwip/sys.h:486-489 at 77dcd25; kinds/pools/shims/lwip/sys_arch.c) |
| [MemoryPool Fixed (C++)](../../records/pools/samd20/adapter_memorypool.json)[1] | bertmelis/MemoryPool | main 5073178 (unreleased; after v0.1.0) | none on the boards; std::mutex on the host | 136 | 5 | 1120–1123 | 1510 | without threads not thread safe (#warning); no lock on the boards (source: src/Fixed.h:16 at 5073178) |
| [atomic-pool (Rust)](../../records/pools/samd20/adapter_atomic_pool.json) | embassy-rs/atomic-pool | 2.0.1, ab88f3c (the head; no tag v2.0.1 exists) | atomic bitmap; on Cortex-M0+ portable-atomic's unsafe-assume-single-core | 948 | 4 | 99–103 | 111 | atomics through portable-atomic; on cores without CAS its critical-section or unsafe-assume-single-core feature (source: README.md:13-14 at ab88f3c) |
| [reference free list, interrupts off (ours)](../../records/pools/samd20/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | – | – | PRIMASK around each call: a row of ours, not a library | 120 | 12 | 312–313 | 441 | the reference with interrupts off (PRIMASK) around each call: a row of ours, not a library (source: kinds/pools/adapter_ref.c (POOL_PRIMASK)) |
| reference free list (ours; the baseline, timed in the same images; not a library) | – | – | none | – | – | 312 | 441 | the baseline: no lock; measured in one context only (source: kinds/pools/adapter_ref.c) |

**`pair`**: alloc, then free of the same block, 256 times, the pool almost empty. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/samd20/adapter_etl.json) | 56–57 | 26 | 61 | 28 |
| [RIOT memarray (C)](../../records/pools/samd20/adapter_riot.json) | 19 | 109 | 20 | 117 |
| [ThreadX block pool (C)](../../records/pools/samd20/adapter_threadx.json)[4] | 77 | 64–66 | 87 | 70 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/samd20/adapter_cmsis_rtx.json) | 49–50 | 66 | 55 | 74 |
| [Contiki-NG memb (C)](../../records/pools/samd20/adapter_contiki.json) | 57 | 65–67 | 63 | 72 |
| [C_Allocator fb_allocator (C)](../../records/pools/samd20/adapter_c_allocator.json)[3] | 104–107 | 94 | 116 | 102 |
| [lwIP memp (C)](../../records/pools/samd20/adapter_lwip.json) | 67–73 | 79–82 | 77 | 87 |
| [MemoryPool Fixed (C++)](../../records/pools/samd20/adapter_memorypool.json)[1] | 20–21 | 22 | 23 | 24 |
| [atomic-pool (Rust)](../../records/pools/samd20/adapter_atomic_pool.json) | 99–101 | 66 | 114 | 72 |
| [reference free list, interrupts off (ours)](../../records/pools/samd20/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 26–27 | 25 | 31 | 29 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 19 | 18 | 20 | 18 |

**`pair_full`**: the same with 31 of the 32 blocks held. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/samd20/adapter_etl.json) | 49 | 26 | 52 | 28 |
| [RIOT memarray (C)](../../records/pools/samd20/adapter_riot.json) | 19 | 109 | 20 | 117 |
| [ThreadX block pool (C)](../../records/pools/samd20/adapter_threadx.json)[4] | 77 | 64–66 | 87 | 70 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/samd20/adapter_cmsis_rtx.json) | 49–50 | 66 | 55 | 74 |
| [Contiki-NG memb (C)](../../records/pools/samd20/adapter_contiki.json) | 305 | 345–347 | 435 | 506 |
| [C_Allocator fb_allocator (C)](../../records/pools/samd20/adapter_c_allocator.json)[3] | 104–107 | 94 | 116 | 102 |
| [lwIP memp (C)](../../records/pools/samd20/adapter_lwip.json) | 67–73 | 79–82 | 77 | 87 |
| [MemoryPool Fixed (C++)](../../records/pools/samd20/adapter_memorypool.json)[1] | 20–21 | 22 | 23 | 24 |
| [atomic-pool (Rust)](../../records/pools/samd20/adapter_atomic_pool.json) | 99–102 | 66 | 114 | 72 |
| [reference free list, interrupts off (ours)](../../records/pools/samd20/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 26–27 | 25 | 31 | 29 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 19 | 18 | 20 | 18 |

**`fill_drain_lifo`**: 8 times: 32 allocs, then 32 frees in reverse order. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/samd20/adapter_etl.json) | 54–55 | 26 | 59 | 28 |
| [RIOT memarray (C)](../../records/pools/samd20/adapter_riot.json) | 19 | 109 | 20 | 117 |
| [ThreadX block pool (C)](../../records/pools/samd20/adapter_threadx.json)[4] | 77 | 64–66 | 87 | 70 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/samd20/adapter_cmsis_rtx.json) | 49–50 | 66 | 55 | 74 |
| [Contiki-NG memb (C)](../../records/pools/samd20/adapter_contiki.json) | 181 | 205–207 | 249 | 289 |
| [C_Allocator fb_allocator (C)](../../records/pools/samd20/adapter_c_allocator.json)[3] | 104–107 | 94 | 116 | 102 |
| [lwIP memp (C)](../../records/pools/samd20/adapter_lwip.json) | 67–73 | 79–82 | 77 | 87 |
| [MemoryPool Fixed (C++)](../../records/pools/samd20/adapter_memorypool.json)[1] | 20–21 | 22 | 23 | 24 |
| [atomic-pool (Rust)](../../records/pools/samd20/adapter_atomic_pool.json) | 100–102 | 66 | 114 | 72 |
| [reference free list, interrupts off (ours)](../../records/pools/samd20/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 26–27 | 25 | 31 | 29 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 19 | 18 | 20 | 18 |

**`fill_drain_fifo`**: 8 times: 32 allocs, then 32 frees in the order of the allocs. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/samd20/adapter_etl.json) | 54–55 | 26 | 59 | 28 |
| [RIOT memarray (C)](../../records/pools/samd20/adapter_riot.json) | 19 | 109 | 20 | 117 |
| [ThreadX block pool (C)](../../records/pools/samd20/adapter_threadx.json)[4] | 77 | 64–66 | 87 | 70 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/samd20/adapter_cmsis_rtx.json) | 49–50 | 66 | 55 | 74 |
| [Contiki-NG memb (C)](../../records/pools/samd20/adapter_contiki.json) | 181 | 205–207 | 249 | 289 |
| [C_Allocator fb_allocator (C)](../../records/pools/samd20/adapter_c_allocator.json)[3] | 104–107 | 94 | 116 | 102 |
| [lwIP memp (C)](../../records/pools/samd20/adapter_lwip.json) | 67–73 | 79–82 | 77 | 87 |
| [MemoryPool Fixed (C++)](../../records/pools/samd20/adapter_memorypool.json)[1] | 20–21 | 22 | 23 | 24 |
| [atomic-pool (Rust)](../../records/pools/samd20/adapter_atomic_pool.json) | 100–102 | 66 | 114 | 72 |
| [reference free list, interrupts off (ours)](../../records/pools/samd20/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 26–27 | 25 | 31 | 29 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 19 | 18 | 20 | 18 |

**`mixed`**: 512 calls from a fixed seed, the pool between 25 % and 75 % full. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/samd20/adapter_etl.json) | 54–55 | 26 | 59 | 28 |
| [RIOT memarray (C)](../../records/pools/samd20/adapter_riot.json) | 19 | 109 | 20 | 117 |
| [ThreadX block pool (C)](../../records/pools/samd20/adapter_threadx.json)[4] | 77 | 64–66 | 87 | 70 |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/samd20/adapter_cmsis_rtx.json) | 49–50 | 66 | 55 | 74 |
| [Contiki-NG memb (C)](../../records/pools/samd20/adapter_contiki.json) | 132 | 150–152 | 176 | 203 |
| [C_Allocator fb_allocator (C)](../../records/pools/samd20/adapter_c_allocator.json)[3] | 104–107 | 94 | 116 | 102 |
| [lwIP memp (C)](../../records/pools/samd20/adapter_lwip.json) | 67–73 | 79–82 | 77 | 87 |
| [MemoryPool Fixed (C++)](../../records/pools/samd20/adapter_memorypool.json)[1] | 20–21 | 22 | 23 | 24 |
| [atomic-pool (Rust)](../../records/pools/samd20/adapter_atomic_pool.json) | 100–102 | 66 | 114 | 72 |
| [reference free list, interrupts off (ours)](../../records/pools/samd20/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 26–27 | 25 | 31 | 29 |
| reference free list (ours; the baseline, timed in the same images; not a library) | 19 | 18 | 20 | 18 |

**`empty`**: 256 allocs on an exhausted pool, each of which must fail; no free. Cycles per call: the range over the eight placements, first pass.

| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |
|---|---:|---:|---:|---:|
| [ETL etl::pool (C++)](../../records/pools/samd20/adapter_etl.json) | 34 | – | 35 | – |
| [RIOT memarray (C)](../../records/pools/samd20/adapter_riot.json) | 16–17 | – | 17 | – |
| [ThreadX block pool (C)](../../records/pools/samd20/adapter_threadx.json)[4] | 72 | – | 82 | – |
| [CMSIS-RTX osRtxMemoryPool (C)](../../records/pools/samd20/adapter_cmsis_rtx.json) | 41 | – | 45 | – |
| [Contiki-NG memb (C)](../../records/pools/samd20/adapter_contiki.json) | 298–299 | – | 429 | – |
| [C_Allocator fb_allocator (C)](../../records/pools/samd20/adapter_c_allocator.json)[3] | 118–119 | – | 130 | – |
| [lwIP memp (C)](../../records/pools/samd20/adapter_lwip.json) | 62–66 | – | 69 | – |
| [MemoryPool Fixed (C++)](../../records/pools/samd20/adapter_memorypool.json)[1] | 17–18 | – | 20 | – |
| [atomic-pool (Rust)](../../records/pools/samd20/adapter_atomic_pool.json) | 55–56 | – | 60 | – |
| [reference free list, interrupts off (ours)](../../records/pools/samd20/adapter_ref_primask.json) (our reference free list with interrupts off; not a library) | 23–24 | – | 28 | – |
| reference free list (ours; the baseline, timed in the same images; not a library) | 16 | – | 17 | – |

</details>

</details>

<details id="notes-to-the-tables" markdown="1">
<summary>Notes to the tables: MemoryPool's pin, heapless, C_Allocator, ThreadX</summary>

[1] MemoryPool is measured at its main branch, commit `5073178`, which is not a release. The project's only release, v0.1.0, spaces the blocks of `MemoryPool::Fixed` by the size of a pointer, so blocks of 32 bytes overlap, and it does not build for arm-none-eabi; the author fixed the spacing in pull request #4 (merged 2024-05-14) and made the mutex optional (2024-05-15), with no release since ([kinds/pools/README.md](../../kinds/pools/README.md), "MemoryPool: why the head, not the release").

[2] A heapless `Box` cannot be made from a raw pointer, so the adapter keeps the live boxes in a table indexed by the block's place: a few instructions per call, and 128 of the RAM bytes. heapless is not built for the Cortex-M0+ (its documentation).

[3] C_Allocator treats an exhausted pool as a fault and calls `FaultHandler()`; the adapter's handler counts the call and returns, and `ALLOC_Alloc` then gives NULL (scenario empty).

[4] ThreadX runs without its scheduler (`kinds/pools/tx_kernel_stubs.c`); the stubs are never reached with `TX_NO_WAIT`. Its RAM bytes include a pointer in front of every block.

</details>

<!-- /table:pools -->

<details id="what-the-tables-show" markdown="1">
<summary><strong>What the tables show</strong>: rows not told apart from the reference, interrupts off around the reference, the cache, the Cortex-M0+ boards, the bytes</summary>

Each sentence names the rows it rests on; the rows are those of the tables
above (open a board). Cycles are quoted as the tables give them, in whole
cycles, alloc before free; whether two ranges overlap is judged on the
records' unrounded means.

- **Not told apart from the reference free list.** In `pair`, the alloc
  range of RIOT `memarray` overlaps the baseline's on all six boards, with
  the cache on and off (cache on: nRF5340 DK 10 against 10, Raspberry Pi
  Pico 2 H 10–11 against 11, NUCLEO-G474RE 17 against 17, NUCLEO-H723ZG
  11–14 against 11, NUCLEO-G0B1RE 22 against 22, SAM D20 Xplained Pro 19
  against 19); its free does not (nRF5340 DK, cache on: 57 against 9).
  MemoryPool `Fixed` overlaps the baseline in both `pair` figures on the
  NUCLEO-G474RE, with the cache on (13–17 and 13–17 against 17 and 17) and
  off (32–34 and 30–33 against 33 and 31); in `pair` alloc on the
  NUCLEO-H723ZG, with the cache on (11 against 11) and off (44–64 against
  54); and in `pair` alloc on the nRF5340 DK with the cache off (39–51
  against 49). No other library's `pair` figure overlaps the baseline's.
- **Interrupts off around the reference.** Our row "reference free list,
  interrupts off" is the baseline's free list with interrupts off
  (PRIMASK) around each call; the two rows differ by that lock and by
  where their code lies (the baseline is in every image's fixed part).
  With the cache on, in `pair`, our row gives 14 and 12 against the
  baseline's 10 and 9 on the nRF5340 DK, 15–16 and 13 against 11 and 10 on
  the Raspberry Pi Pico 2 H, 24 and 25 against 11 and 11 on the
  NUCLEO-H723ZG, 28–31 and 28 against 22 and 21 on the NUCLEO-G0B1RE, and
  26–27 and 25 against 19 and 18 on the SAM D20 Xplained Pro. On the
  NUCLEO-G474RE its alloc range begins 0.02 cycles above the baseline's
  (17–21 against 17), and its free range overlaps the baseline's (16–20
  against 17).
- **A library's own lock is not measured apart.** ThreadX and lwIP take
  interrupts off around a call, and CMSIS-RTX does on the two Cortex-M0+
  boards (the column "Lock as built"). No build of a library without its
  lock was run, so a library's lock is in its figures together with the
  rest of its code, and two libraries with different locks differ in both.
- **The cache.** With the cache off, every `pair` figure, the baseline's
  included, is higher than with the cache on on the nRF5340 DK, the
  Raspberry Pi Pico 2 H, the NUCLEO-G474RE and the NUCLEO-H723ZG. On the
  Raspberry Pi Pico 2 H, whose code is then read from the external QSPI
  flash on every fetch ([CRC method](method-crc.md), "What is measured"),
  each is 22 to 54 times its figure with the cache on (the baseline's
  alloc: 493 against 11). On the NUCLEO-G0B1RE and the SAM D20 Xplained Pro
  a cache-off figure is at most 1.28 and 1.19 times its cache-on figure,
  and the baseline's free is the same in both (21 and 18).
- **The two Cortex-M0+ boards** (NUCLEO-G0B1RE, SAM D20 Xplained Pro).
  heapless is not built for them: its pool needs LDREX and STREX, which the
  Cortex-M0+ does not have (its `src/pool.rs`). atomic-pool takes 948 flash
  bytes there against 560–608 on the other four boards; there it uses
  portable-atomic's `unsafe-assume-single-core`, interrupts off around each
  atomic operation ([the kind's README](../../kinds/pools/README.md)). On
  the SAM D20 Xplained Pro every figure with the cache off is the same at
  all eight placements.
- **The bytes.** A configuration's RAM bytes are the same on all six
  boards. Its flash bytes differ between the boards by at most 60 (ThreadX:
  720–780), but for atomic-pool's (560–948, above).

</details>
