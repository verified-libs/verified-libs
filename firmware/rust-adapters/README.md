# Rust ring buffers (2026-11-13)

The Rust libraries under test, as one `no_std` static library that the C
benchmark (`../nrf5340-rb-bench`, `SET=rust` and `SET=mp`), the ISR stress
test (`../nrf5340-rb-stress`) and the two-interrupt stress test
(`../rb-mp-stress`) link like their C objects. The harness calls the Rust
functions through the same `rb_adapter` function pointers as the C and C++
adapters (`adapters_rust.c`), so the timing and the stress code are the same.

| Configuration | Crate (pinned in `../nrf5340-rb-bench/libs.lock`) | What the adapter uses |
|---|---|---|
| heapless spsc::Queue (Rust) | heapless 0.9.1 | `spsc::Queue<u8, 128>` split into `Producer` / `Consumer`; no block call, so push_n/pop_n loop over push/pop |
| heapless mpmc::Queue (Rust) | heapless 0.9.1 | `mpmc::Queue<u8, 128>` (size a power of two, capacity 128); on Cortex-M0+ with `portable-atomic-critical-section`, as heapless documents for cores without compare-and-swap |
| bbqueue (Rust) | bbqueue 0.6.1 | stream producer/consumer, inline storage, polling; `Churrasco` (atomics) where the core has compare-and-swap, `Jerk` (critical sections) on Cortex-M0+; zero-copy API = its grants |
| embassy-sync Pipe (Rust) | embassy-sync 0.8.0 | `Pipe<CriticalSectionRawMutex, 127>`, `try_write` / `try_read` |

Capacity: 127 bytes usable, as the other adapters (RB_SLOTS - 1), except
heapless's mpmc::Queue (128, a power of two).

## Build

`../common/rust.mk` runs `cargo build --offline --locked --release` in the
toolchain image (2026-11-13 or later: it has the soft-float targets). Per
board: the soft-float target of the core (`thumbv6m-none-eabi`,
`thumbv7em-none-eabi`, `thumbv8m.main-none-eabi`; the C code is
`-mfloat-abi=soft` everywhere) and `-C target-cpu` as the C `-mcpu`.
opt-level follows the C build's `OPT` (-O2 -> 2). Functions are aligned to 32
bytes, as `BENCH_ALIGN` does for the C adapters. Release profile:
`panic = "abort"`, one codegen unit, no LTO.

- **memcpy:** the C library's (newlib-nano), for the C and the Rust code
  alike: the link puts `-lc_nano` before the Rust archive and forces the
  memory functions (`-u`), so compiler_builtins' weak copies are not used.
  The C library's memcpy itself differs by core (newlib-nano: the generic C
  version on ARMv6-M, assembly on ARMv7E-M and ARMv8-M), the same for every
  library on a board. Experiment `MEMCPY=rust` (benchmark, `SET=rust` or `mp`;
  records `-memcpyrust`): the archive's own compiler_builtins functions, as a
  pure Rust firmware links them, for the C code of that firmware too.
- **Critical sections:** `src/cs.rs`. One core: PRIMASK, nested, the same
  as the cortex-m crate's `critical-section-single-core`, written out so the
  build needs no further crates. RP2350 (two cores, `--cfg vl_two_cores` from
  `rust.mk`): PRIMASK plus a spin lock between the cores (an atomic swap in
  SRAM, like the Pico SDK's default spin locks on the RP2350), as a
  multi-core critical-section implementation for the chip provides. With the
  single-core version, embassy-sync's Pipe panicked when both cores used it
  at once (its state is in a RefCell: "already borrowed"), and the SMP stress
  test stalled (2026-11-13).
- **Offline:** every crate comes from the checkouts that `fetch-libs.sh` makes
  (projects' repositories, at the tag of the version cargo would pick; const-init
  is on tangled.sh, the others on GitHub). Cargo resolves optional
  dependencies even when no feature enables them, so `stubs/` has
  placeholders for the two it asks for (maitake-sync, loom); each fails to
  compile if it is ever used.
- **Frame pointer:** rustc keeps the frame pointer on these targets
  (`push {r7, lr}; mov r7, sp`), which gcc -O2 omits. Left as shipped.
