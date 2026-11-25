# What carries over from ring buffers to a second kind of library

2026-11-24. A reading of the tree at `9ce87d3` (the version 2 benchmark
published the day before), made to plan the next kind of library
([plan](../lab/plans/2026-11-24-next-library-kinds.md), step 1). No code
was changed and no board was used. One claim was tested in a throw-away
clone of the repository; that is said where it comes.

Each part of the machinery is put in one of three groups:

- **General**: works for any kind of library as it is.
- **By name**: works for another kind, but its names, directories or
  schema say "ring buffer" (`rb-`, `rb_adapter`, `rb-bench/2`).
- **By design**: made for ring buffers; a second kind needs its own.

## Summary

| Part | Group | What a second kind needs |
|---|---|---|
| Board support (`firmware/common/<board>`): clock, cycle counter, cache control, timers, serial port, start-up, linker scripts | General, one tie by name | Nothing, if its own `bench.h` defines `rb_op` (see below) |
| `time_call` (the timed window `ldr; blx; ldr`) | General | Nothing: any operation of the form `uint32_t op(uintptr_t, uintptr_t)` |
| One image per configuration, placements, `FAR`, the fixed part, the baseline as a control | General | Its own list of configurations and its own baseline |
| Slot table, bundles, boot stub without a table (`benchboot.c`), selection words (`select.h`) | General | Its own slot table (the segments are shared flash) |
| The runner (`run-one.py`), records (`onerecords.py`), rebuild check (`oneverify.sh`) | By name, and partly by design | Its own copies or one tool with the kind as a parameter: they read a result block of ring-buffer shape |
| Same-image rule, ledger, host fixes, archived series | General in principle | A change to the export check: it is tied to `firmware/` as one whole (tested, below) |
| Export (`public-export.py`), embargo, `publish.sh` | General | Nothing |
| Site build, link check, reports page | General | Nothing for reports and survey files |
| Size probe (`rb-size`) | By name | Its own list; the method (one module per instance, `-Os` and `-O2`) carries over |
| Rust as a C-ABI static library | General | One crate per library, as planned for version 2 |
| Toolchain image (GCC, Clang, CBMC, GenMC, Rust stable, Miri) | General | Nothing; CBMC is in the image and not yet used by a published result |
| `repeat.sh` | By name | A level or a section per kind |
| Adapter interface `rb_adapter` and the scenarios of `main.c` | By design | A new interface and new scenarios |
| ISR stress test, interrupt sweep, two-interrupt test, cross-core and DMA tests, their judges and mutants | By design (the mechanism is general) | New judges, controls and mutants; the timer and coverage parts carry over |
| Contract check on a host model (`verify/contract`) | By design (the mechanism is general) | A new verdict (what a correct result is) |
| GenMC models (`verify/genmc`) | By design (the tool is general) | New models per library |
| Page data, comparison page, MCP server, `RESULTS.md` tables | By design | New columns, filters and tools (below) |

## General parts

**Board support.** `firmware/common/<board>/board.h` gives every test
firmware the clock, the cycle counter (DWT on the Cortex-M33, M4 and M7; a
timer on the Cortex-M0+), the cache or flash accelerator switch, the
stress timers, the serial port and the start-up code, for all six boards.
Nothing in it knows what a ring buffer is, with one exception by name:
all six `board.h` files `#include "bench.h"` to get the type
`rb_op`, which `time_call` takes. A firmware of another kind can give its
own `bench.h` on its include path with the same type
(`typedef uint32_t (*rb_op)(uintptr_t, uintptr_t)`), so no file under
`firmware/common` has to change. The name stays wrong, not the code.

**The timed window.** `time_call` times exactly `ldr t0, CYCCNT; blx op;
<op>; ldr t1, CYCCNT`, the same for every operation. Every operation a
second kind needs fits the signature `uint32_t op(uintptr_t a, uintptr_t b)`:
a CRC over a buffer (`a` = address, `b` = length, the CRC returned), a
pool's allocation (`a`, `b` unused, the address returned) and its release
(`a` = the address), an allocator's `malloc(b)` and `free(a)`, a queue's
push and pop.

**One image per configuration** (version 2,
[plan](../lab/plans/2026-11-22-bench-image-per-library.md)): an image holds
the harness, the baseline and one configuration, built with `-D`, eight
placements of 0 to 28 bytes, the library at least `FAR` = 6144 bytes from
its adapter, a fixed part (vector table, harness, the C library's memory
functions, `main`, the baseline) checked to be the same in every image of
a board. None of this depends on what the library does. What a second
kind supplies: its configurations (`configs.txt`), its baseline, and a
harness of its scenarios in the fixed part.

**Slots and bundles.** The slot table (`slots.txt`, written by
`oneslots.py`), the bundles (`onebundle.py`), the boot stub
(`firmware/common/benchboot.c`, 128 to 184 bytes, no table) and the
selection words (`firmware/common/select.h`) are general. One point to
settle: flash is shared. The ring-buffer bundles take 20 segments of
256 KB in their table. A second kind either gets segments of its own in
the same numbering (the table is only appended to), or a table of its own
that is written over the ring-buffer bundles on the board, which then
cost a flash write to put back before the next ring-buffer run.

**The export and the site.** `lab/tools/public-export.py`,
`site/embargo.txt`, `publish.sh`, `site/build.py` and
`site/check_links.py` work on files, not on ring buffers. A new report in
`reports/` becomes a page and is listed on the reports page without any
change (`site/build.py`, the `reports` listing). A survey file in
`candidates/` is exported as a file; no page links it today.

**Rust.** Rust libraries are built as a `no_std` static library with a C
interface and called through the same function pointers as C and C++
(`firmware/rust-adapters`). Nothing in that is particular to ring
buffers; version 2's open point "one crate per library" holds for any
kind.

**The toolchain image** (`toolchain/Containerfile`) holds GCC and Clang
for the host, `arm-none-eabi-gcc` with newlib, CBMC, GenMC (pinned
commit), Rust stable with the two Cortex-M targets, and a nightly Rust
with Miri. So bounded model checking of C (CBMC) and Rust's interpreter
for undefined behaviour (Miri) are there for a second kind without a new
image. Loom is a crate, not in the image.

## Tied by name

- **`rb_op`, `rb_adapter`, `RB_SLOTS`**, the directory names
  (`nrf5340-rb-bench`, which builds for all six boards; `rb-mp-stress`,
  `rb-size`), the schema `rb-bench/2` and the result magic `VLB5`. A second
  kind can reuse the type `rb_op` as said above; for the rest a new
  directory with its own names is cleaner than reusing these.
- **The runner and record tools** (`run-one.py`, `onerecords.py`,
  `oneverify.sh`): their steps (compare the bundle with the flash, write
  the selection words, reset, stay off the probe, read the result block,
  check that it names the image and the run number) are general. The
  result block they decode is not: `struct results` of the benchmark has
  the shape `[library][cache][scenario] → {min, max, sum, first, count}`
  for a push and a pop series. A second kind with other scenarios has
  another block. Under the frozen method these files stay as they are; a
  second kind gets its own copies with a parameter for the block's shape,
  or one shared tool later, at a change of method.
- **`repeat.sh`** knows the benchmark and the two stress tests. A second
  kind would add a section or a level.
- **The size probe** (`firmware/rb-size/size.sh`) builds one, three equal
  and three different instances per library at `-Os` and `-O2`; the list
  of libraries is written into the script. The method carries over (for a
  CRC: the bytes of code and of the table; for a pool or allocator: code
  and bookkeeping per block).

## Tied by design

**The adapter interface.** `rb_adapter` (`firmware/nrf5340-rb-bench/bench.h`)
has `reset`, `push`, `pop`, `push_n`, `pop_n`, the interrupt variants
and four zero-copy calls. A second kind needs its own struct. For the
four kinds of the survey:

| Kind | Operations (all of the form `op(a, b)`) |
|---|---|
| Fixed-block pool | `init`, `alloc` → address or 0, `free(addr)`, optional `alloc_isr`/`free_isr` |
| Heap allocator | `init(arena, size)`, `malloc(n)`, `free(p)`, optional `realloc`, `aligned_alloc`, and a report of free bytes for the fragmentation scenario |
| Several producers or consumers | the ring-buffer interface of today, with roles (producer id) |
| CRC in software | `init`, `update(addr, len)` → running CRC, `final` → CRC; one adapter per algorithm and per implementation |

**The scenarios** of `main.c` (single, burst16, block4/16/64, dma16/64,
each with the cache off and on) are ring-buffer use. A second kind needs
its own, and a baseline: for a pool, a free-list of one word; for an
allocator, a bump allocator; for a CRC, a plain bitwise loop of the same
algorithm compiled from our own source, which also serves as the
reference.

**The stress tests.** Their mechanism is general: a timer interrupt at
random periods, the interrupt sweep with SysTick armed at every delay
until the interrupt comes after the call, the coverage bitmap of
interrupted program counters, two interrupts at two priorities, the
second core of the RP2350 and the nRF5340, the run parameters over the
serial port, one library per reset from a bundle, the negative control
and the mutants that must be caught. Their judges are ring-buffer
judges: a byte stream 0, 1, 2, … that must arrive in order, once. A
second kind needs its own judge and its own controls. For a pool: every
block handed out at most once at a time, never outside the pool, the
count of free blocks back to the start after a drain, and a canary
pattern written by the owner of a block that no one else may change. For
a CRC there is no concurrency to stress, so this whole part falls away
(unless a library claims re-entrancy, which a host test can show).

**The contract check** (`verify/contract`) runs a library's code on the
host with the x86 trap flag, so that an "interrupt" can come after every
instruction, with interrupt masking modelled by a flag (`host_irq.h`,
`hostify.py`). That mechanism is general and is the strongest tool we have
for code that relies on one core rather than on C11 atomics, which is
true of many pools. Its verdict is ring-buffer specific: the result must
be one of the orders in which the calls could have run one after the
other, byte for byte. A pool needs a verdict of its own (the same
properties as its stress judge); the linearisability idea stays.

**GenMC** (`verify/genmc`) checks C11 code under the RC11 memory model
with threads. The tool is general; each model is written per library and
per scenario. A lock-free pool or an MPSC queue is in its reach in the
same way the SPSC queues were; a CRC is not a question for it.

**The page data and the pages.** `site/gen_libdata.py` reads the
benchmark records, the stress campaigns, the contract and GenMC results,
`site/data/libs-meta.json` and labels from
`firmware/nrf5340-rb-stress/decode.py` (zero-copy, documented for two
cores, unsafe by its own documentation), and writes `site/data/libs.json`.
The comparison page (`site/compare.js`) and the MCP server
(`mcp-server/vlquery.py`, a line-by-line port held equal to the page by
`tests/test_parity.py`) have ring-buffer metrics (1-byte push, 1-byte pop,
64-byte block, zero-copy transfer), filters (0 stress errors, permissive
licence, block API, zero-copy, GenMC, contract, not unsafe by its own
documentation, two cores), topologies (SPSC, MPSC, SPMC, MPMC) and the
tool names `list_ring_buffers`, `compare_ring_buffers`,
`get_ring_buffer`. A second kind needs a data file, a page and tools of
its own, or a generalisation of all three with the kind as the first
choice. The parts that do carry over: the state in the URL, the three
groups below the winner instead of a ranking (principle 3), weights shown
openly, the licence filter, the "written by the project owner" label,
and the data file's SHA-256 in every answer of the MCP server.

**`RESULTS.md`** and `site/results_tables.py` (the speed table) are
ring-buffer pages. A second kind would get its own results page.

## The export check holds `firmware/` as one whole (tested)

`public-export.py` takes the *test sources* to be all of `firmware/` plus
three files under `lab/`. A record may be shown if its commit has the same
test sources as the exported tree, or if the ledger
(`records/rebuilt.json`) shows that the tree still builds its image byte
for byte.

Tried in a throw-away clone of the branch (nothing of it committed):

| Change in the clone | `public-export.py --check` |
|---|---|
| None | 0 records that cannot be rebuilt |
| One new host-side file under `firmware/` (a Python script in a new directory) | **265 records that cannot be rebuilt**: every version 2 record, "the scripts and judges at that commit are not those of HEAD" |
| One new C file under `firmware/` in a new directory | **265 records that cannot be rebuilt**: "no rebuild from the sources of HEAD in `records/rebuilt.json`" |

So the first file of a second kind under `firmware/` stops the export of
every published ring-buffer record, until each one is rebuilt into the
ledger (no flash write, about half a minute of build per board, but a
step for every board and a new ledger entry for all 265 records) or the
export check learns that test sources are held per kind. A host-side
file under `firmware/` cannot be fixed by the ledger at all, because the
rule for version 2 records says the runner and judges must be the
record's.

What a second kind needs instead, as options for the owner:

1. **The test sources per kind**: `TEST_SOURCES` becomes a map from a
   records directory to its source directories (ring buffers:
   `firmware` as today; the second kind: its own top-level directory, for
   example `kinds/crc/`), and shared parts (`firmware/common`,
   `lab/boards.conf`) count for both. Changing `public-export.py` is a
   change of method for the export, not for the ring-buffer test; it
   needs the owner's word.
2. **The second kind outside `firmware/`** with no change to the check:
   the export then holds none of the second kind's records against their
   sources, which would break the same-image rule for them.
3. **Under `firmware/`**, with a ledger rebuild of all ring-buffer records
   at every commit that touches the second kind. Costly and easy to get
   wrong.

Option 1 is the one that keeps the rule for both kinds. Until it is
decided, a pilot (step 4 of the plan) lives in a new top-level
directory, `pilot/`, which the check does not count as test sources.

## What a second kind costs in new work, by group

- **Nothing new**: the board support, the timed window, the slot and
  bundle mechanism, the boot stub, the export and embargo, the site
  build, the toolchain image, Rust's way in.
- **A copy with other names or a parameter**: the runner, the record and
  rebuild tools, `repeat.sh`, the size probe, the slot table's segments.
- **New**: the adapter interface, the scenarios and the baseline, the
  stress judges and controls (for a kind with concurrency), a verdict for
  the contract check, models for GenMC or CBMC, the page data, the
  comparison page, the MCP tools, and the results page.
- **A decision first**: how the export check holds the test sources of
  more than one kind (above).
