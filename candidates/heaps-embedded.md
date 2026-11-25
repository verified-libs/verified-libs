# Candidates: heap allocators for small microcontrollers (survey)

Survey of 2026-11-24 for the choice of the next kind of library
([plan](../lab/plans/2026-11-24-next-library-kinds.md), kind B). Nothing
here is tested yet. What a project says about itself is given as "it
documents"; what the code does is from reading the source at the commit
named. **Verifying the claims would be the point of the tests.**

How the facts were taken: as in the [pool survey](pools-embedded.md)
(shallow clones of 2026-11-24, licence from the repository's licence file
or the file's own header, no GitHub API). ⚠ marks the project owner's own
libraries; the owner has none of this kind in public.

## The problem, and who has it

A heap on a microcontroller has a few kilobytes to a few hundred
kilobytes and runs for years without a restart. What goes wrong in
practice:

- **Fragmentation.** After long enough a request fails although enough
  bytes are free, because no single free block is large enough. This is
  the reason coding rules for safety-related C forbid `malloc` after
  start-up (MISRA C:2012 rule 21.3; the rule's text is in the paid standard, so no link is given). An allocator that documents a bound
  on its worst-case memory need (o1heap, after Robson) or a constant
  time per call (TLSF, o1heap, Zephyr's `sys_heap`) makes a claim that
  can be checked against a workload.
- **Time.** A first-fit search over a long free list takes time that grows
  with the heap's history; a real-time system needs a bound. Zephyr
  documents that every `sys_heap` call completes "within constant time
  ... within 1-200 cycles" on typical architectures
  ([Zephyr heap documentation](https://docs.zephyrproject.org/latest/kernel/memory_management/heap.html)).
- **Interrupts and threads.** Most heaps are not safe to call from two
  contexts. newlib's `malloc` "may become corrupted" unless the
  application supplies `__malloc_lock` and `__malloc_unlock`
  ([newlib `mlock.c`](https://sourceware.org/git/?p=newlib-cygwin.git;a=blob;f=newlib/libc/stdlib/mlock.c));
  Zephyr's `sys_heap` must be serialised by the caller, `k_heap_alloc`
  may be called from an ISR only with `K_NO_WAIT`, and `k_heap_free`
  carries no such marking (`include/zephyr/kernel.h`); FreeRTOS's heaps
  suspend the scheduler, which an interrupt cannot rely on
  (`portable/MemMang/heap_4.c`: `vTaskSuspendAll`).
- **Which heap a project gets** is often decided by the toolchain, not by
  the developer: `arm-none-eabi-gcc` with `--specs=nano.specs` links
  newlib's nano `malloc`; picolibc ships its own.

## Candidates

### Shipped with an RTOS or a C library (C)

| Library | Licence | Newest commit | Release to pin | What it documents about time, fragmentation, interrupts and threads | Where used |
|---|---|---|---|---|---|
| **newlib nano `malloc`** (`newlib/libc/stdlib/nano-mallocr.c`) | BSD-style (ARM Ltd., in the file); newlib as a whole has several licences | 2026-11-19 | newlib-4.6.0 | First fit over a free list; locking only through the application's `__malloc_lock` (`mlock.c`, above) | The default with `arm-none-eabi-gcc --specs=nano.specs`, so most bare-metal Cortex-M projects built with GCC |
| **picolibc `malloc`** (`libc/stdlib/malloc.c`) | BSD-3-Clause (ARM Ltd., in the file) | 2026-11-23 | 1.8.12 | Descends from the same ARM code; "the caller holds the malloc lock" (the file); picolibc documents its locking in `doc/locking.md` | Zephyr (its picolibc option) and other picolibc users |
| **FreeRTOS `heap_4`** and **`heap_5`** (`portable/MemMang`) | MIT | 2026-11-17 | V11.3.3 (as in `libs.lock`) | First fit with coalescing; `heap_5` over several memory regions; calls are bracketed by `vTaskSuspendAll` | FreeRTOS |
| **Zephyr `sys_heap`** / **`k_heap`** (`lib/heap`, `include/zephyr/sys/sys_heap.h`) | Apache-2.0 | 2026-11-23 | v4.5.0 | Constant time per call, "1-200 cycles", bucket search bounded by `CONFIG_SYS_HEAP_ALLOC_LOOPS` (default 3, "at the expense of some fragmentation resistance"); `sys_heap` must be serialised by the caller; `k_heap_alloc` is `@isr_ok` with `K_NO_WAIT` | Zephyr (`k_malloc`, the system heap) |
| **ThreadX byte pool** (`common/src/tx_byte_*.c`) | MIT | 2026-11-01 | v6.5.2.202603_rel | `tx_byte_allocate` and `tx_byte_release`: allowed from "Initialization and threads", not from ISRs ([ThreadX chapter 4](https://github.com/eclipse-threadx/rtos-docs/blob/main/rtos-docs/threadx/chapter4.md)) | ThreadX |
| **RT-Thread small memory** (`src/mem.c`) and **memheap** (`src/memheap.c`) | Apache-2.0 | 2026-11-23 | v5.3.0 | No statement about interrupts found in the files; `memheap.c` turns interrupts off for parts of its work | RT-Thread |
| **NuttX `mm_heap`** and its **TLSF** option (`mm/mm_heap`, `mm/tlsf`) | Apache-2.0 | 2026-11-24 | nuttx-13.1.0 | To be read in detail (not done this night) | NuttX |
| **lwIP `mem`** (`src/core/mem.c`) | BSD-3-Clause | 2026-11-23 | STABLE-2_2_1_RELEASE | Freeing from an interrupt needs `LWIP_ALLOW_MEM_FREE_FROM_OTHER_CONTEXT` ("this leads to dis-/enabling interrupts often, which can be slow!", `opt.h`) | lwIP |

### Stand-alone allocators (C)

| Library | Licence | Newest commit | Release to pin | What it documents | Where used |
|---|---|---|---|---|---|
| **o1heap** (pavel-kirienko) | MIT | 2026-02-09 | 3.0.0 | "constant worst-case execution time (WCET) ... and a well-characterized and easily predictable worst-case memory fragmentation (consumption) (WCMC) bound"; "Avoid concurrent access to the heap. Use locking if necessary." (`README.md`) | Written for hard real-time embedded systems (its README) |
| **TLSF** (mattconte/tlsf) | BSD-3-Clause per its `README.md` ("Released under the BSD license"; no licence file) | 2020-03-29 | head `deff9ab50934` (no tags) | "O(1) cost for malloc, free, realloc, memalign"; "Not designed to be thread safe; the user must provide this" (`README.md`) | Basis of many TLSF ports; RIOT has a `tlsf` package |
| **umm_malloc** (rhempel) | MIT | 2026-06-25 | v1.1.2 | For small heaps: blocks of 8 bytes numbered with 15 bits, up to 32767 blocks (`README.md`); "support for this library in a multitasking environment is provided when you add bodies to the `UMM_CRITICAL_ENTRY` and `UMM_CRITICAL_EXIT` macros" (`src/umm_malloc_cfg.h`) | The ESP8266 Arduino core |
| **lwmem** (MaJerle) | MIT | 2026-10-24 | v2.2.4 | "Operating system ready, thread-safe API, with ready-made ports for CMSIS-OS, pthreads, ThreadX and Win32" (`README.md`) | Embedded projects of the author's ecosystem |
| **libmemory** (Embedded Artistry) | MIT | 2025-03-17 | 1.0.48 | "The freelist implementation is not thread-safe by default"; the application defines `malloc_lock`/`malloc_unlock`; RTOS variants for FreeRTOS and ThreadX (`README.md`) | Embedded Artistry's framework |
| memmgr (Eli Bendersky, `code-for-blog/2008/memmgr`) | Public domain (Unlicense text) | 2026-11-21 (the repository) | head `1ba5b9f235aa` | A small pool-based `malloc` for embedded use, from a blog post; nothing about threads | A blog post's code |

### Rust

| Library | Licence | Newest commit | Version to pin | What it documents | Where used |
|---|---|---|---|---|---|
| **embedded-alloc** (rust-embedded) | MIT OR Apache-2.0 | 2026-09-29 | v0.7.0 | `LlffHeap` (linked list, first fit) and `TlsfHeap`; needs a `critical-section` implementation, on Cortex-M e.g. `critical-section-single-core` (`README.md`) | Embedded Rust projects that need a global allocator |
| **linked_list_allocator** (rust-osdev) | MIT OR Apache-2.0 | 2026-04-14 | v0.10.6 | `LockedHeap` behind a spinlock (`use_spin`, default) (`README.md`) | Inside `LlffHeap` of embedded-alloc; OS kernels |
| **rlsf** (yvt) | MIT OR Apache-2.0 | 2026-07-27 | 0.2.3 | "Allocation and deallocation operations are guaranteed to complete in constant time"; "A whole pool must be locked" (`README.md`) | Inside `TlsfHeap` of embedded-alloc |
| **talc** (SFBdragon) | MIT | 2026-09-09 | v4.4.2 | For "embedded systems, OS kernels, and other no_std environments"; `TalcCell` lock-free for one thread, `TalcLock` with `lock_api` for more (`README.md`) | – |

## What could be proven, and with which tool

- **No overlap, alignment, contents kept.** A host test that replays a
  long random sequence of `malloc`, `free` and `realloc` and keeps a
  shadow map of every live block: no two live blocks overlap, every block
  lies in the heap and is aligned as promised, and its contents survive
  other calls. Clang's libFuzzer and AddressSanitizer are in the
  toolchain image; the sanitizer sees the allocator's own wrong pointers,
  not wrong blocks inside its arena, so the shadow map does that part.
- **Rust allocators under Miri** (in the image): `talc`, `rlsf` and
  `linked_list_allocator` are pure Rust, so Miri can run the same random
  sequences and report undefined behaviour inside them.
- **Bounds that are claimed** can be checked by measurement, not proven:
  the time per call (o1heap, TLSF, rlsf, `sys_heap`) as the largest
  number of cycles seen under adversarial sequences, and o1heap's
  documented memory bound against the peak a sequence needed.
- **Interrupt and thread safety** is mostly the user's lock here (most
  candidates say so). Where a library ships the lock (lwmem's ports,
  `k_heap`, `LockedHeap`), the contract check on the host model applies
  with a new verdict (the shadow map's properties after every interleaving
  of one interrupt's call into one main call). GenMC has little to do:
  none of the candidates uses C11 atomics for its heap.
- **CBMC** (in the image) could prove small properties of one call (the
  free list stays well formed for a heap of a few blocks); it is a new
  tool for the project and the effort is unknown.

## What could be measured on the six boards

- **Operations**: `malloc(n)` and `free(p)`, optionally `realloc`, through
  `time_call`.
- **Scenarios**: fixed size pairs (16, 64, 256 bytes), a burst of
  allocations then frees in both orders, and replay of a recorded or
  generated workload of mixed sizes and lifetimes with a fixed seed; per
  scenario the mean, the largest number of cycles seen, and after the
  workload the largest block that can still be allocated (the
  fragmentation number).
- **Baseline**: a bump allocator (free does nothing): the cost of the
  harness and the cheapest possible allocation.
- **Placement**: the method of version 2 applies to the code. The heap is
  data in SRAM; where data lies matters on the boards with a data cache
  (the NUCLEO-H723ZG) and is not covered by the placement method today.
- **Heap size**: the SAM D20 has 32 KB of RAM, so the heap of a common
  scenario is at most about 16 KB; the other boards could run a second,
  larger heap.
- **Stress** only for the libraries that ship a lock and claim interrupt
  safety; the others are measured as single-context allocators.
- **First guess of a first series**: about 14 configurations × 8
  placements = 112 images per board, plus workload data in each image (a
  few kilobytes); **about 25 to 35 flash writes** on the six boards. The
  workload makes images larger than the ring-buffer ones.

## What a filter and a column would be

- Filters: bounded time per call (documented); bounded memory need
  (documented); safe from an interrupt or between threads as shipped, with
  a user lock, or not; licence; language.
- Columns: mean and largest cycles for `malloc` and `free`; largest
  allocatable block after the workload (bytes and per cent of the heap);
  bytes of overhead per block; code bytes; the minimum alignment.

## Effort, in the terms of the step-1 report

- New: the adapter interface (small), the workloads (the hard part:
  which workload stands for "a firmware"? An unknown; recorded traces of
  real firmware are not at hand), the shadow-map checker and fuzzer on the
  host, the page.
- Reused: boards, `time_call`, images, placements, bundles, export.
- Little use for: the stress tests, GenMC.
