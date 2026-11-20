# Finding: diffstorm/cb, two defects (fixed upstream)

| | |
|---|---|
| Library | [diffstorm/cb](https://github.com/diffstorm/cb), MIT |
| Affected | up to commit `547d0812` (2025-07-18) |
| Fixed in | [`91ae20b`](https://github.com/diffstorm/cb/commit/91ae20b) (2026-11-08); checked again at `11e05d6` (v1.3) |
| Defects | 1. the overwrite flag can switch itself on (all platforms); 2. the consumer lacks acquire ordering (multi-core targets) |
| Found by | the verified-libs stress harness and GenMC (RC11 model checking) |

## Timeline

| Date | |
|---|---|
| 2026-11-06 | Found: a host reproducer and GenMC show both defects at `547d0812`. |
| 2026-11-08 | Reported to the maintainer by email, with the reproducer ([`demo.c`](demo.c)) and the GenMC harness ([`diffstorm_spsc.c`](../../genmc/diffstorm_spsc.c)); 90-day notice period. |
| 2026-11-08 | The maintainer pushed a fix the same day (`91ae20b`). Checked here the same evening: the reproducer gives the correct result, every access to `overwrite` is a 1-byte load or store on the Cortex-M33, and GenMC passes. |
| 2026-11-08 | Two further upstream commits (`17ffdc1`, `11e05d6`, v1.3) checked the same way: still fixed. |
| 2026-11-09 | The maintainer agreed to publication before the 90 days were over. `libs.lock` pins `11e05d60`; bench and board stress on it: 0 errors, control caught; GenMC run: all checks as expected. |

Thanks to the maintainer for fixing both defects within hours.

## Defect 1: overwrite mode can switch itself on (all platforms)
`overwrite` is a 1-byte `atomic_bool` (`cb.h`, inside `struct cb`).
`cb_init_ex()` stores it with a 1-byte atomic store, but `cb_insert_ex()`
(`cb.c:373`), `cb_insert_timeout` (`cb.c:499`) and `cb_get_overwrite_ex`
(`cb.c:597`) read it with `CB_ATOMIC_LOAD`, which always casts to a 32-bit
atomic, and `cb_set_overwrite_ex` (`cb.c:577`) writes it with a 32-bit
store. The 3 padding bytes after `overwrite` are never initialised.

Consequence: if the memory holding a `cb` object was not zero before
`cb_init()` (a local variable, a reused buffer, `malloc`), the flag reads as
true although overwrite mode was never enabled. A full buffer then accepts
the insert, overwrites the oldest item, and the producer moves `out`, which
belongs to the consumer (not SPSC-safe).

Why `CB_ATOMIC_LOAD` is always 32-bit: `cb_atomic_access.h` selects the cast
with `#if CB_ATOMIC_INDEX_TYPE == uint32_t`. In a preprocessor expression both
type names are unknown identifiers and evaluate to 0, so the first branch is
always taken. The library already has the correct macro,
`CB_ATOMIC_LOAD_OW` (`cb.c:74/82`), but the lines above do not use it.

Evidence:
- Host demo ([`demo.c`](demo.c), x86-64, gcc):
  ```
  zeroed memory:          overwrite flag=0  insert into full buffer=rejected  first item=1  -> correct
  memory that held 0xAA:  overwrite flag=1  insert into full buffer=accepted  first item=2  -> WRONG
  ```
- Cortex-M33 (arm-none-eabi-gcc 14.2.1 `-O2`): `overwrite` is 1 byte at
  offset 16 (padding 17–19); `cb_insert_ex` loads it with
  `ldr r4, [r0, #16]` (32-bit); `cb_init_ex` stores it with `stlb` (8-bit).
- GenMC: "Mixed-size accesses detected: tried to read with a 32-bit access".

In our benchmark and stress tests the object is a zero-initialised static,
so the defect did not show there.

## Defect 2: consumer lacks acquire ordering (multi-core targets)
`cb_remove_ex()` loads `in` with a relaxed atomic load and then reads the
item from the buffer; the only barrier comes after the read (release side).
Under the C11 memory model that is a data race on the buffer: on a
weakly ordered multi-core CPU (the library lists aarch64, Apple Silicon and
RISC-V among its targets) the consumer can read the slot before the
producer's write is visible.

Evidence (GenMC 0.20, RC11, 1 producer + 1 consumer, 4 items, 4 slots;
`CB_MEMORY_BARRIER` mapped to `atomic_thread_fence(memory_order_seq_cst)`,
the usual C11 mapping of `dmb`; finding 1 neutralised with
`CB_ATOMIC_LOAD_OW` so it does not mask this one):

| Variant | Result |
|---|---|
| overwrite load fixed only | **fail: non-atomic race** on the buffer |
| + one `CB_MEMORY_BARRIER()` after the two index loads in `cb_remove_ex` | pass, 686 executions |

Not a problem for interrupt ↔ main on one Cortex-M core (sequential on one
core); relevant for cross-core use.

## How it was fixed upstream (`91ae20b`)

- Every access to `overwrite` now goes through `CB_ATOMIC_LOAD_OW` /
  `CB_ATOMIC_STORE_OW`, which use the flag's own 1-byte type.
- In `cb_remove_ex` and `cb_peek_ex` the consumer loads `out` with acquire
  semantics and has a `CB_MEMORY_BARRIER()` after the index loads, before it
  reads the item; the producer side stores `in` with release semantics.

## Reproduce

On lib-lab1 with the pinned toolchain image: `bash run.sh` here (defect 1,
host and Cortex-M33, against the pre-fix pin `diffstorm-cb-547d0812`) and
`bash ../../genmc/run.sh` (both defects at `547d0812`; the fixed `11e05d6`
must pass).
