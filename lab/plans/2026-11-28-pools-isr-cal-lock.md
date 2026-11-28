# Pools concurrency: C_Allocator with its interrupt-masking lock (plan)

2026-11-28. The owner said yes on 2026-11-27 to an extra row: C_Allocator built
with one of its interrupt-masking lock options, within its documentation. This
plan covers the host check, one small bundle per board (six writes), the
records and the pages. The 82 records and bundle 300 stay as they are. It is
built and run after review. No other library changes.

## 1. The option, and how the masking is supplied

At the pin 497b465 (`kinds/pools/libs.lock`) the library documents:
- the options: `README.md:385`, `ALLOC_LOCK_CMSIS_RTOS2`, "Cortex-M PRIMASK
  interrupt masking (CMSIS-Core), for any CMSIS-RTOS2 kernel"; the same text is
  in `src/LockGuard.h:20-21`;
- use from interrupts: `README.md:390` and `LockGuard.h:30-32`, "With an
  interrupt-masking option (… CMSIS-RTOS2), `ALLOC_Alloc()`/`ALLOC_Free()` may
  also be called from an interrupt."

**Chosen: `ALLOC_LOCK_CMSIS_RTOS2`.** Its code (`src/LockGuard.cpp:104-113`)
does three things:
- it saves `__get_PRIMASK()`, then calls `__disable_irq()`;
- on unlock it calls `__set_PRIMASK(saved)`;
- it calls no kernel function.

`fb_allocator.c` holds the lock around the free-list pop or push and the
statistics (`ALLOC_Alloc` 112-130, `ALLOC_Free` alike). On exhaustion it calls
`FaultHandler` after the unlock.

Our port supplies nothing of its own: the three functions are CMSIS-Core's
(`cmsis_compiler.h` → `m-profile/cmsis_gcc_m.h`). They are the real `mrs`,
`cpsid i` and `msr primask` instructions on all six cores, the Cortex-M0+
included. CMSIS 6 is already pinned and on the image's include path
(`onepool.flags`). No CMSIS-RTOS2 kernel is linked.

The alternative, `ALLOC_LOCK_THREADX` (`tx_interrupt_control`), would put
ThreadX's port code inside the lock. It is not chosen: the row would measure
two libraries.

The wording on the page: "with its `ALLOC_LOCK_CMSIS_RTOS2` option (PRIMASK
masking through CMSIS-Core); no RTOS kernel is linked, and the option's code
calls none". Whether that counts as *within* is decision **D1** (section 6).

## 2. The configuration and its class

- The configuration id is `adapter_c_allocator_lock`, with class **within**.
  Its verdict is pass or FAIL, and its longest interrupts-off time per board
  and cache state is `result.c[].irq_wait_cycles`, as for ThreadX and lwIP.
- No file of `kinds/pools` that an image or a run is built from changes, and
  `adapter_c_allocator.c` is not changed: the image uses the same adapter
  source and the same symbol (`-DPOOL_ISR_ADAPTER=adapter_c_allocator`). Two
  files of `kinds/pools` do change, and neither is a test source of any kind
  (below).
- The library's `LockGuard.cpp` is compiled once more for this image with
  `-UALLOC_LOCK_NONE -DALLOC_LOCK_CMSIS_RTOS2 -D__PROGRAM_START=_start`. That
  object replaces the first-series one in the link. The last define is
  explained in `lab/drafts/2026-11-28-cmsis6-gcc-start-cxx.md`: CMSIS 6's
  default start function is not valid C++ for this g++, and CMSIS sets the
  same define itself for picolibc. The image's start-up is the boards' own.
  The project's own CI job builds the option the same way
  (`-D__PROGRAM_START=1`, against CMSIS 5 headers;
  `.github/workflows/rtos_locks.yml:39-55`). The README names no CMSIS version.
  The row's note says: "built with ALLOC_LOCK_CMSIS_RTOS2 against CMSIS 6
  headers, no kernel linked, -D__PROGRAM_START=_start as CMSIS sets for
  picolibc", with no word about a fault. `fb_allocator.c` is the same object, because
  it does not read the option.
- Our `FaultHandler` counter (`pool_c_allocator_faults++`) is not atomic. The
  verdict does not read it; the page does not show it.
- `kinds/pools/claims.tsv` gets one row for the new id, citing `README.md:385`
  and `:390`, `LockGuard.h:20-21` and `:30-32`, and `LockGuard.cpp:104-113`.
  The present row (`ALLOC_LOCK_NONE`, `README.md:390`, `LockGuard.h:24-29`)
  stays.

**Which records a change stops** (`lab/tools/public-export.py`, the kinds'
source sets):
- `kinds/pools/claims.tsv` is in `POOLS_NOT_SOURCES` (shown on the pages, not
  used by an image or a run), and so in `POOLS_ISR_NOT_SOURCES`. Its new row
  stops no records: not the 64 pools records, not the 82 concurrency records.
- `kinds/pools/shims/host/cal_lock/cmsis_compiler.h` (section 3) is under
  `shims/host/`, also in `POOLS_NOT_SOURCES`. It stops none either.
- Checked with `source_ids` at the commit before and after: the pools kind's
  checksums (all and host side) are the same; the ring buffers' too. Only the
  concurrency series' host side differs: `build.py`, `onebuild.sh`, `decode.py`
  and `isrverify.sh`.
- So the 64 pools records stand as they are. The 82 concurrency records stand
  through the host fixes and the ledger (section 4).

## 3. The host check (contract.c)

A fourth program, built the way the CMSIS-RTX LDREX/STREX program is
(`#if CAL_LOCK` in contract.c, and one Makefile target; its control is the
fifth):
- The program holds only C_Allocator with the lock option.
- LockGuard.cpp is built against a host `cmsis_compiler.h` that maps the three
  functions onto the check's own mask flag, as `ARMCM_isr.h` does for
  CMSIS-RTX:
  - `__get_PRIMASK` reads the flag;
  - `__disable_irq` sets it;
  - `__set_PRIMASK(v)` restores `v` and takes an interrupt held pending, each
    in one step.
- The header goes in a new directory, `kinds/pools/shims/host/cal_lock/`.
  `shims/host/` is outside both kinds' source sets, so no records change.
- A host control, `CAL_LOCK_BROKEN`: the same build with `__disable_irq` doing
  nothing. It must be caught. It shows that the pass depends on the mask.
- `contract.c` and the Makefile are outside the series' sources (`NOT`), so
  changing them changes no record.

## 4. The board part: bundle 301, its own series commit

- **build.py** gets a bundle number argument:
  - `BUNDLE 300` keeps today's list and output path exactly;
  - `BUNDLE 301` lists `adapter_ref`, `adapter_broken_isr_alloc`,
    `adapter_broken_isr_free`, `adapter_ref_primask` and
    `adapter_c_allocator_lock`. Its output goes to `build/b301/<board>/`.
- The controls are in the bundle, so the run proves itself. `isrrecords.py`
  already requires every control of `decode.CLASS` to have a run and to be
  caught on each board. The reference without a lock is also the latency
  calibration in every image.
- **The 82 records stand through the ledger.** `build.py` and `onebuild.sh`
  are host-side sources that are not host-fixable, so their change makes the
  82 records' sources differ from HEAD. `image-ledger.py` is made again at the
  new commit: it rebuilds bundle 300 with `isrverify.sh` from the tree. Each
  record stands only if it gets the same image, the same bundle number and
  the same bundle checksum, which is what its digest holds. The 64 pools
  records keep their entries, since their sources do not change. If one byte
  differs, the change is wrong and is redone.
- **Before any write:** bundle 300 built at the new commit is compared with
  the boards' bundle 300 checksum (`bundle_sha256` of the 82 records, one per
  board). Bundle 301 is written only when every board matches.
- Host fixes, recorded in `records/host-fixes.json`:
  - `decode.py`: `CLASS["adapter_c_allocator_lock"] = "within"`;
  - `isrverify.sh`: it builds the bundle the record names;
  - `run-isr.py` is used unchanged (`--from build/b301/<board>`).
- **The records of bundle 301** go to `records/pools-isr/b301/<board>/<adapter>.json`
  (`isrrecords.py --out records/pools-isr/b301 --images build/b301`, unchanged).
  The controls of bundle 301 then never overwrite bundle 300's records of the
  same name. The export takes every `.json` under `records/pools-isr/`, at any
  depth. The pages read `records/pools-isr/*/*.json` and so do not see bundle
  301 until the page step teaches them its lock row.
- **The series commit** is the commit that holds all of this. The new records'
  `bench_commit` is that commit, and their bundle is 301. Nothing under
  `kinds/pools-isr` is added or moved.
- **Writes:** six, one per board (approved). Bundle 301 starts where bundle
  300 starts, so it overwrites bundle 300 on the board. The SAM D20's 256 KB
  has no room for both. A later repeat of a bundle 300 record needs bundle 300
  written again: one more write per board.
- **Smoke first:** the full set of steps on the host, shrunk. The board smoke
  is the run itself: the controls come first in the bundle, and a board whose
  controls are not caught gets no record.

- **A FAIL is a possible defect.** The lock row is within its documentation,
  so a FAIL on a board is a possible defect in the library. Then:
  - the run stops for that board;
  - its facts go to `lab/drafts` and to the reviewer only;
  - nothing goes on a page;
  - its record is not written into `records/pools-isr`.

## 5. Run time

From the 82 records' `seconds`:

| Board | ref | broken alloc | broken free | ref primask | C_Allocator lock (estimate) | Sum |
|---|---|---|---|---|---|---|
| nRF5340, G474, H723, G0B1, SAM D20 | 61 s | 61 s | 61 s | 61 s | 61–121 s (the no-lock build's) | about 6 min per board |
| Pico 2 | 1570 s | 1601 s | 1621 s | 1621 s | about 3400 s (the no-lock build's 3364 s; ThreadX with interrupts off took 2314 s) | **about 9,800 s, 2 h 45 min**, plus the write |

- The Pico 2's job timeout should be 14,000 s.
- The other boards keep the series' 1,500 s per job.
- Through the queue with parallel boards, the whole run takes about three
  hours, mostly on the Pico 2.

## 6. Pages, and the decisions

The pages will show two C_Allocator rows, each with what it documents:
- "C_Allocator, no lock (`ALLOC_LOCK_NONE`, the bare-metal default)":
  *outside its documentation*, with what was observed, as now.
- "C_Allocator, `ALLOC_LOCK_CMSIS_RTOS2` (PRIMASK)": *within*, pass or FAIL,
  and the longest interrupts-off time per board and cache state.

They appear in the results fold-out, the compare page's concurrency column,
the method page's table (section 2 of the concurrency plan) and the MCP
`compare_pools` notes.

The one-context tables keep the no-lock build. The fold-out says so: "the
one-context numbers above are the no-lock build".

Decisions:
- **D1, is the CMSIS-RTOS2 option without a kernel *within*?** The README
  names the option "for any CMSIS-RTOS2 kernel". Its code needs CMSIS-Core
  only, and the interrupt sentence names the option without a kernel
  condition. *Recommendation: within, with the wording of section 1.*
- **D2, one-context cycle numbers for the locked build?** They would be a new
  pools configuration:
  - in `configs.txt` and `slots.txt`, at 8 placements on six boards;
  - a new pools bundle per board (six more writes);
  - two passes per board, about 1 to 3 hours per board on the Pico 2 by the
    first series;
  - the pools ledger rebuild, and a regenerated compare table.
  *Recommendation: not now.* The concurrency fold-out shows the locked build's
  interrupts-off time. A one-context row is a later addition in the manner of
  a library update.
- **D3, a broken-lock control on the boards too?** It would be a sixth image:
  about +1 h on the Pico 2, with no extra write. *Recommendation: no.* The
  host control (section 3) and the two broken interrupts-off builds of the
  reference cover it.
