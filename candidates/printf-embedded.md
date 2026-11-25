# Candidates: small printf implementations (survey)

Survey of 2026-11-24 for the choice of the next kind of library
([plan](../lab/plans/2026-11-24-next-library-kinds.md), kind F; a kind
the owner allowed the night to add after A to D). Nothing here is tested
yet. What a project says about itself is given as "it documents".

How the facts were taken: as in the [pool survey](pools-embedded.md)
(shallow clones of 2026-11-24, licence from the licence file, no GitHub
API). ⚠ marks the project owner's own libraries; the owner has none of
this kind in public.

## Why this kind

Almost every firmware formats text, and the C library's `printf` is
often too large: eyalroz/printf's README says a typical libc `sprintf`
can "bloat code size - typically by as much as 20 KiB". So many small
replacements exist, each with its own trade between flash, stack, speed,
features and conformance to the C standard, and their READMEs disagree
about each other. Like CRC it is a kind without concurrency in the
narrow sense, but with a real correctness question (the C standard's
rules for every flag and conversion, and floating point rounding), and
with a re-entrancy question for logging from interrupts.

## The problem, and who has it

- **Conformance.** eyalroz/printf, a fork of mpaland/printf, says the
  original "as of mid-2021 ... still had many C-standard-non-compliance
  bugs" and pending bug reports (its `README.md`). Every small printf
  makes its own choices of what to leave out.
- **Size against features**: nanoprintf "compiles to between ~480-3500
  bytes of object code on a Cortex-M4 architecture, depending on
  configuration" and uses "less than 100 bytes of stack" (its
  `README.md`). Stack use matters when printing from an interrupt.
- **Re-entrancy**: mpaland/printf and eyalroz/printf claim "reentrant and
  thread-safe" (no static buffers); LwPRINTF claims "reentrant access to
  all API functions" (`README.md`). Whether a function is re-entrant can
  be tested by calling it from an interrupt in the middle of itself.

## Candidates

| Library | Lang. | Licence | Newest commit | Version to pin | What it documents | Where used |
|---|---|---|---|---|---|---|
| **newlib nano `printf`** | C | BSD-style (newlib) | 2026-11-19 | newlib-4.6.0 | Float support only when linked with `-u _printf_float` (toolchain documentation; to be confirmed) | Default with `--specs=nano.specs` |
| **picolibc `printf`** (`libc/stdio`) | C | BSD-3-Clause | 2026-11-23 | 1.8.12 | Its own stdio (`libc/stdio`), documented in "Printf and Scanf in Picolibc" (`doc/printf.md`, not read this night) | Zephyr's picolibc option |
| **Zephyr `cbprintf`** (`lib/os/cbprintf*.c`) | C | Apache-2.0 | 2026-11-23 | v4.5.0 | A complete and a nano variant, and packaging of arguments for deferred logging (`cbprintf_packaged.c`) | Zephyr |
| **eyalroz/printf** | C | MIT | 2026-06-27 | v6.4.1-b3 (newest tag; a release to be chosen) | "Reentrancy and thread-safety; malloc() freeness", "extensive test coverage" (`README.md`) | The "consensus fork" of mpaland/printf (its `README.md`) |
| **mpaland/printf** | C | MIT | 2026-11-23 | v4.2.1 | "Reentrant and thread-safe, malloc free, no static vars/buffers" (`README.md`) | eyalroz/printf's README: "The repository had become quite popular" |
| **nanoprintf** (charlesnicholson) | C | Unlicense or 0BSD | 2026-09-25 | v0.8.1 | ~480 to 3500 bytes on Cortex-M4, under 100 bytes of stack, "raises no issues from UBsan or Asan" (`README.md`) | – |
| **LwPRINTF** (MaJerle) | C | MIT | 2026-10-27 | v1.1.0 | "Reentrant access to all API functions"; ports for CMSIS-OS, pthread, ThreadX, Win32 (`README.md`) | – |
| **tinyprintf** (cjlano) | C | BSD-3-Clause or LGPL-2.1 (two licence files) | 2014-08-28 | head `2ee30120ec15` | A small printf; no floating-point conversion found in its source | – |
| **mini-printf** (mludvig) | C | BSD-2-Clause (in its `README.md`; no licence file) | 2020-10-26 | head `f7479a4bbc10` | "Minimal printf() implementation for embedded projects" | – |
| **SEGGER `SEGGER_RTT_printf`** | C | SEGGER's BSD-style licence | 2026-11-03 | V8.58.0 | A small printf that writes into an RTT buffer (`RTT/SEGGER_RTT_printf.c`) | J-Link users |
| **ufmt** (japaric) | Rust | MIT OR Apache-2.0 | 2022-08-10 | ufmt-v0.2.0 | "A (6-40x) smaller, (2-9x) faster and panic-free alternative to `core::fmt`" (`README.md`) | Embedded Rust |

Baseline and reference: the host C library's `snprintf` (glibc), whose
output for the same format and arguments is the reference for every
conversion the C standard defines. Not proposed: `stb_sprintf` (moved to
`deprecated/` in its repository).

## What could be proven, and with which tool

- **Differential test against the reference** on the host: every
  conversion and flag combination of the C standard that the library
  claims, over boundary values (0, -1, INT_MIN, the largest values,
  NaN, infinities, subnormals, values at rounding boundaries); a fuzzer
  (libFuzzer, in the image) for format strings. A conversion the library
  does not claim is reported as "not supported", not as a defect.
- **Floating point** is the hard part: a correct shortest or fixed
  representation is a known hard problem; the reference is glibc's
  correctly rounded output.
- **Re-entrancy** on the host model: the contract check's trap-flag
  mechanism can call `snprintf` again from the "interrupt" at every
  instruction of an outer `snprintf`; the verdict is that both outputs
  are what they would be alone.
- Sanitizers for buffer bounds with `snprintf` and small buffers.

## What could be measured on the six boards

- **Operation**: `snprintf` into a buffer with a fixed set of formats
  (an integer, a hex word, a string, a float), through `time_call`;
  cycles per call.
- **Code size** per configuration and feature set (with and without
  floating point), and the **largest stack use**, measured by painting
  the stack, a number no other page of the project has yet.
- **Baseline**: newlib nano's `snprintf` without float, as the toolchain
  gives it.
- **On-board check**: the image compares every output with a string made
  on the host, so a core or compiler difference shows.
- **First guess of a first series**: about 15 configurations (11
  libraries, some with and without float) × 8 placements; **about 20 to
  30 flash writes**.

## What a filter and a column would be

- Filters: floating point supported; re-entrant (documented, and
  passed); stack at most N bytes; flash at most N bytes; licence.
- Columns: code bytes; largest stack; cycles for each format; the number
  of reference cases that differ, per kind of conversion.

## Effort, in the terms of the step-1 report

- New: the reference test on the host (large: many cases, the float
  part hard), the stack measurement, the adapter (small), the page.
- Reused: images, placements, bundles, `time_call`, export; the trap-flag
  mechanism for the re-entrancy test.
- Not needed: the stress tests and GenMC, except a re-entrancy test.
