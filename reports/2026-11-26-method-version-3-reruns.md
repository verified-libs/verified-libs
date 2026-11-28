# Method version 3: the reruns of the nRF5340 DK and the NUCLEO-H723ZG (2026-11-26)

The boards whose images changed with method version 3 were measured again,
through the board queue, on the job list of our lab (not published), each job with the reviewer's OK.
Series commit `4032f80`, worktree `~/vl-wt-v3-series`. Records in
`kind-pools` `4b12135`.

## Result

- **162 records measured again.** They replace the archived ones at the same
  paths, with the same names and counts:

  | Board | CRC (`crc-bench/2`) | Ring buffers (`rb-bench/3`) |
  |---|---|---|
  | nRF5340 DK | 35 | 45 |
  | NUCLEO-H723ZG | 38 | 44 |

  - None left out.
  - The baseline the same in every run: CRC 24 of 24 numbers per CRC kind;
    ring buffers 20 of 20.
- **All 162 rebuilt at their commit `4032f80`** (`crcverify.sh`,
  `oneverify.sh`): MATCH.
- **The export check passes** (`lab/tools/public-export.py --check` at
  `4b12135`).
  - The three series "before method version 3" are kept in
    `records/archived.json` and in the public history they name: version 2
    and the second CRC series at `be1da88`, the first CRC series at
    `fc7e8ad`.
  - The export takes a series whose records all left the tree as kept there
    (`402cf13`).
- **Every record carries the board's option registers.** Each board's
  readings agree with each other all day (below).

## The jobs and the writes

| Board | Jobs | Runs | Flash writes |
|---|---|---|---|
| nRF5340 DK | N0 smoke (CRC 25, 2 runs); N1–N4 CRC 25–28; N5–N9 version 2 bundles 0–4 | 2 + 560 + 768 | 9 (N0, N2–N9), as counted |
| NUCLEO-H723ZG | H-1 thermal; H0 smoke; H1–H4 CRC; H5–H9 version 2 | 2 + 608 + 704 | 10 (H-1, H0, H2–H9), as counted |

From the queue's ledger, `~/vl-queue/writes.tsv`. No power switching on
either board. The nRF5340 was never power-cycled.

### Stops and interruptions

1. **Enqueuing N1 failed** (11:08 UTC), before any job ran: my enqueue
   script split the pattern `--refuse "FLASH WRITE"`. Fixed in `08d3698`;
   the nRF series resumed at N1.
2. **The H723 was taken by the owner** after H-1 (11:23), for another
   project.
   - Its orchestration was stopped after H-1, before H0.
   - Its option registers were read before it left and again on its return.
     Equal (below).
   - H0 to H9 ran on its return (11:53–13:37).
3. **N9 stopped on the refuse rule `errors [1-9]`** (14:54).
   - The line matched was of version 2's *part* images in the nRF5340's
     bundle 4: `part_nrf_atomics`, `part_memcpy1`, `part_nrf_len0`. They time
     single operations and are no FIFOs, so the FIFO check counts errors on
     them by design.
   - Their counts equal version 2's own runs, image for image: **4086, 1920
     and 4086** (`~/lab-runs/v2-run1` and `v2-far1`).
   - No record is made from them.
   - The job itself was whole: 120 runs, 0 without a file, 1 write, every
     `adapter_*` run with errors 0.
   - The reviewer let N9 stand (decision a). `check_job.py` now skips
     `part_*` by name and still fails on any `adapter_*` error, as a control
     shows. The board's STOPPED was cleared with that reason.

## H-1: the H723 at 520 MHz (thermal and clock)

- **Temperature:**
  - idle 32.1–32.7 °C;
  - under load at 520 MHz from 31.1 °C to a plateau of 50.9 °C, maximum
    51.2 °C (601 samples, not aborted);
  - cooled to 35.3 °C.

  Well under the 85 °C limit.
- **Clock:** the image's CYCCNT time against the host's time over the load:
  591 s against 589.2 s, ratio **1.0030**. The image prints whole seconds,
  so this is good to about ±0.0034. 520 MHz confirmed within 1 %.
- **Writes:** one (the thermal image).

## The option registers

Read zero-write by `lab/tools/read-options.py`, before every job and once at
the end. Files: `~/vl-wt-crc-runs/v3/options-final/`.

| Board | Registers | Value |
|---|---|---|
| nRF5340 DK | UICR.APPROTECT, UICR.SECUREAPPROTECT | 0x50fa50fa, 0x50fa50fa |
| NUCLEO-H723ZG | FLASH_OPTSR_CUR, FLASH_OPTSR2_CUR | 0x0306aad0, 0x00000000 (CPUFREQ_BOOST 0) |
| NUCLEO-G474RE | FLASH_OPTR | 0xfbeff8aa |
| NUCLEO-G0B1RE | FLASH_OPTR | 0xfffffeaa |
| SAM D20 Xplained Pro | NVM User Row | 0x48e0c7cf, 0xffffff5d |
| Pico 2 | OTP rows: CRIT0 copies, page 1, boot keys, lock words (264) | 0 but the lock words of pages 0, 1, 2, 62, 63: 0xf80=0x3f3f3f, 0xf81=0x151515, 0xf83/0xf85/0xffd=0x040404, 0xfff=0x141414 |

- **Each board's final reading equals every reading its jobs took today:**
  nRF5340 10 of 10, H723 10 of 10, G474 4 of 4, G0B1 4 of 4, SAM D20 6 of 6.
- **The H723 left for another project and came back.** Its reading before
  (11:23) and after (11:53) are equal register by register.
- **The Pico 2 also left and came back.**
  - The port check passed, switched through the queue's `power` (zero
    write): CHIP_ID 0x20004927 read with port 3 on; no answer with it off;
    the same ID when on again.
  - Its 264 OTP rows equal the second CRC series' reading of 2026-11-25 row
    by row, 0 different.
  - Its row is that reading.

## Against the archived records

`~/vl-v3-proof/compare_v3.py`. Each run is set against the archived record's
run of the same configuration, placement and pass. The images are matched by
configuration and placement; on the nRF5340 their bytes differ only in the
boot stub. "Within" means within 1 % or 0.05 cycles.

### nRF5340 DK: identical

| | Means | Within | Ratio new/archived |
|---|---|---|---|
| CRC (N1–N4), configuration and baseline, cache off and on | 26 880 | all | 1.0000 (min 1.0000, max 1.0000) |
| Ring buffers (N5–N9), configuration and baseline, cache off and on | 29 888 | all | 1.0000 (min 1.0000, max 1.0000) |

As expected: the new boot stub (`BENCHBOOT_NRF5340`, the UICR copied to the
CTRL-AP at reset) lies outside the measured part. The clock (64 MHz) is
unchanged.

### NUCLEO-H723ZG: ratios, 520 MHz against 64 MHz

| | Cache off: median (min–max), within | Cache on: median (min–max), within |
|---|---|---|
| CRC, baseline | 1.1109 (1.0851–1.3239), 0 of 7296 | 1.0000 (1.0000–1.0021), 7296 of 7296 |
| CRC, configuration | 1.2196 (0.9752–2.0435), 220 of 7296 | 1.0000 (0.9767–1.9876), 6354 of 7296 |
| Ring buffers, baseline | 1.2307 (1.2158–2.3760), 0 of 7040 | 1.0001 (0.9994–1.0020), 7040 of 7040 |
| Ring buffers, configuration | 1.1616 (0.8706–1.9114), 90 of 7520 | 1.0000 (0.8862–1.0926), 7250 of 7520 |

- **With the cache on**, all differences outside 1 % but one group are few
  and small. They are in short scenarios: a share of the means per
  configuration, from −11 % (`pxq_spmc`, one block scenario) to +9 %.
- **The group that differs is the board's hardware CRC unit**
  (`adapter_hw_crc32`, `_crc16`, `_crc8`): ×1.76 median (1.30–1.99) on all
  192 means each, cache on. The unit is a peripheral on the AHB bus, which
  since method version 3 runs at half the core clock (HPRE /2, 260 MHz), so
  each of its register accesses costs twice the core cycles. This is the
  same mechanism as the cache-off rise below.
- **With the cache off**, every library and the baseline take more cycles.
  This is the bus-clock effect below.

### Why cache-off cycles rose although the wait states fell from 7 to 3

The full account, with file:line, RM0468 quotes and the arithmetic, is in
`~/vl-v3-proof/h723-cache-off-cycles.md`. In short:

**The clocks:**
- Version 3 (`firmware/common/stm32h723/board.h` at `4032f80`, lines 120–125)
  runs the core at 520 MHz with HPRE /2: rcc_hclk3 = rcc_aclk = 260 MHz, the
  flash's AXI clock. LATENCY is 3.
- Version 2 ran core and AXI at 64 MHz, with the power-on latency of 7.

**What the manual says:** RM0468 §4.3.8 and Table 16 count the latency in
cycles of the flash's AXI interface clock.

**The arithmetic:**
- An array read costs (7 + 1) × 1 = 8 core cycles before and (3 + 1) × 2 = 8
  now: the same.
- Everything else an access pays on the AXI side is counted in AXI cycles,
  and an AXI cycle is now 2 core cycles.

**Measured** (H0, etl crc32_t256, cache off, per byte from 256 to 1024
bytes):
- 32 → 38 cycles at placement 0, 34 → 42 at placement 4. The placement's
  extra access costs 2 core cycles before and 4 now: the predicted doubling,
  seen directly.
- With the cache on, 8 = 8.

**Time:** 1024 bytes, cache off, is 32 796 cycles at 64 MHz (512 µs) before
and 38 968 cycles at 520 MHz (74.9 µs) now. Cycles at another clock are not
times.

**Not explained:**
- the number of AXI accesses per call (the M7's fetch with the I-cache off,
  the flash's read queue);
- why a configuration's per-call rise (+28 at length 1) exceeds the
  baseline's (+23).

An access-counting test (the loop from ITCM, or the table in DTCM, at both
clocks) would settle both. None was run.

## Tools changed on the way

| Commit | What |
|---|---|
| `08d3698` | `v3-reruns-enqueue.sh`: the refuse pattern of a job without writes passed as one argument |
| `56e5863` | `image-ledger.py`: an archived series counts only for the paths its entry covers. Before, a remade ledger would have dropped the 176 version 2 records of the four boards not measured again, and the export would have stopped them. The tree's ledger predates the archive entries, so nothing was wrong in the tree. |
| `fd9e1a4`, `018ee6c` | `test-public-export.sh`: the ledger cases leave out archived records, and count from the tree's root |
| `402cf13` | `public-export.py`: an archived series none of whose records is in the tree is kept in the public history. A series partly gone, or a changed record, still stops the export. Three quick test cases. |
| (host) | `~/vl-v3-proof/check_job.py`: skips `part_*` (above) |

**`test-public-export.sh` (full runs):**
- **Before these fixes:** 5 ledger cases failed, all traced to `ce79a27`'s
  archiving, none to the pools rule.
- **At `a0f0df6`:** 31 of 31 cases passed. The run then ended on a syntax
  error after the last case, because I edited the script (`402cf13`) while
  bash was still reading it.
- **At `f00be00`:** a clean run is under way (about 70 min).

## The watched power-on of the nRF5340 DK: passed

The owner decided on one watched power-on, after the reruns. It ran after
pools as well, with the reviewer's OK (15:38 UTC). The question was whether
the debug port is open after a power-on with only our boot stub having run.
That is what `BENCHBOOT_NRF5340` is for: it copies the UICR to the CTRL-AP
at reset. All of it was zero write.

**How the switch was made.**
- The queue's rule "never power the nRF5340" stays.
- It was lifted for this one call by an explicit flag,
  `boardqueue.py power nrf5340dk off|on --override-no-power REASON`
  (`4c927bb`). The flag runs the switch under the hub's lock and writes the
  call to `~/vl-queue/power-overrides.tsv` before and after.
- Hub 4B0708619185 had no job. All of today's records were pushed.

**What was done and seen** (`~/vl-v3-proof/nrf-poweron.sh` and `.log`):

| Step | When | Seen |
|---|---|---|
| Before: attach, both UICR words, the first flash words | 15:38:40 | 0x50fa50fa, 0x50fa50fa; flash 0x0: 2007fff0 00000041 000000cd 000000cd 0 0 0 0 |
| The power cycle (port 1, through the queue with the override) | off 15:38:40, on 15:38:48 | both exit 0. The J-Link OB re-enumerated: connected since 15:38:50 (sysfs), so the board was without power. |
| After, with nothing done first: attach, both UICR words, the first flash words | 15:38:50 | attached; 0x50fa50fa, 0x50fa50fa; the same flash words |
| One zero-write pools job (NP): N2's command on bundle 51, without `--flash` | 15:39–15:40 | "bundle 51: on the board, nothing written"; 8 runs, 0 without a file, 0 writes |

- **NP against N2:** 384 means, all equal (largest difference 0.000
  cycles). The image starts and measures as before.
- **So:** with method version 3's boot stub, the nRF5340 DK's debug port is
  open after a power-on.

## Open

- **The ledger (`records/rebuilt.json`):** made again after these records,
  with the pools kind (`125d0ba`).

*2026-11-28: links to documents that are no longer published were removed or now point to the change log.*
