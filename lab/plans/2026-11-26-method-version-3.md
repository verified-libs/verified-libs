# Plan: method version 3, with the pools kind

**Decided by the owner on 2026-11-26: all nine points of "For the owner"
as recommended, with point 7 as: the median is left out of version 3,
explicitly** ([`DECISIONS.md`](../../DECISIONS.md), 2026-11-26).

Written 2026-11-26. It gathers what the owner has decided goes into the
next method version. Sources:
- [`2026-11-26-next-method-version.md`](2026-11-26-next-method-version.md);
- [`DECISIONS.md`](../../DECISIONS.md) 2026-11-26: the nRF5340 boot stub;
  CRC runs on several boards at once.

For each item it says which frozen files change, the facts per board,
the consequences for the published records, and what must be shown before
any run. The pools kind ([plan](2026-11-26-pools-kind.md)) is to be
measured only under this version.

Nothing here is done yet. The frozen files (version 2's test sources,
tag `v2-method-freeze`; the CRC kind's, tag `crc-method-freeze`) stay as
they are until the owner says go.

## The items

| # | Item | Status |
|---|---|---|
| 1 | Boards run at the clock and flash wait states a user would expect | decided (next-method-version list, 2026-11-25) |
| 2 | Option registers read and recorded for every board with each series | decided (2026-11-26) |
| 3 | The nRF5340 boot stub opens the debug port at every boot | decided (DECISIONS 2026-11-26) |
| 4 | Ring-buffer runs through the queue, after a zero-write trial | decided (DECISIONS 2026-11-26) |
| 5 | The median beside the mean | **open**: listed, not decided |

## 1. Clock and flash wait states

**The rule this plan proposes for "what a user would expect":**
- the clock the vendor's own startup code or board templates use (for the
  Pico 2, the SDK's default), and never one that needs an option byte;
- with the fewest flash wait states the reference manual allows at that
  clock and supply.

Where the vendor's code and the manual differ, the manual's minimum is
taken and the difference is said (G474 below).

| Board | Now (`firmware/common/<board>/board.h`) | What a user would expect, with the source | Change? |
|---|---|---|---|
| nRF5340 DK | 64 MHz (HFCLKCTRL Div2, the reset value). Flash wait states are not configurable on this chip | **64 MHz.** HFCLKCTRL's reset value is Div2, 64 MHz (nRF5340 PS v1.6, §4.11.3.44). Nordic's MDK `SystemInit` (nrfx v3.9.0, `mdk/system_nrf5340_application.c`) writes Div2 only as the errata-42 workaround. Zephyr main (`9ab181f`, 2026-11-26) has no code in `soc/nordic/nrf53/soc.c`, `drivers/clock_control/clock_control_nrf.c` or `nrf5340_cpuapp.dtsi` that changes it. 128 MHz is the user's choice: §4.11.1.1, and §4.1 says it raises the internal voltage. The PS gives the CPU wait states measured with CoreMark (§5.2.2.1: from flash, 5 at 64 MHz and 4 at 128 MHz with the cache off) | no |
| Pico 2 | clk_sys 150 MHz (as pico-sdk). QMI CLKDIV 3, 50 MHz flash SCK, as left by the boot ROM (read 2026-11-11, `board.h` lines 6–9) | **clk_sys 150 MHz:** the RP2350's maximum (RP2350 datasheet, "clk_sys … 150MHz") and pico-sdk's default. **Flash CLKDIV 2 (75 MHz)** is what the SDK's flash builds set. On master (`079c6f3`, 2026-09-04), `pico_standard_link` links a boot stage 2 into flash builds (`CMakeLists.txt` lines 370–372). Its `boot2_w25q080.S` for RP2350 sets `QMI M0_TIMING.CLKDIV = PICO_FLASH_SPI_CLKDIV`, which is 2 for `boards/pico2.h` (lines 74–75). **Not yet confirmed** that this runs at boot on RP2350 as built by default; to be confirmed from the SDK's code path, or by reading QMI after an SDK-built image | clock no; flash divider **to confirm**, then likely 3 → 2 |
| NUCLEO-G474RE | 170 MHz, range 1 boost, 4 wait states | **170 MHz, boost, 4 WS.** RM0440 Table 9: 4 WS up to 170 MHz in boost mode. ST's template (`STM32CubeG4` `140db64`, `Projects/NUCLEO-G474RE/Templates/Src/main.c`) runs 170 MHz with boost, but with `FLASH_LATENCY_8`. ST's GPIO_EXTI example runs 150 MHz, normal range, 4 WS. The manual's minimum is taken; the template's 8 is said | no |
| NUCLEO-H723ZG | 64 MHz HSI, VOS3 (reset), **7 wait states (reset)**. `BOARD_CLOCK_FAST=1` already builds 520 MHz, VOS0, 3 WS, WRHIGHFREQ 11 (`h7_clock_520`) | **520 MHz, VOS0, 3 WS, caches on.** ST's template and GPIO_EXTI example (`STM32CubeH7` `4a358b8`, `Projects/NUCLEO-H723ZG/…/main.c`): SYSCLK 520 MHz, AXI/AHB 260 MHz, `PWR_REGULATOR_VOLTAGE_SCALE0`, `FLASH_LATENCY_3`, `SCB_EnableICache`/`SCB_EnableDCache`. RM0468 Table 16: 3 WS for AXI 210–275 MHz at VOS0. 550 MHz needs CPU_FREQ_BOOST (DS13313 Table 12), an option byte, so it is excluded. (At 64 MHz itself the manual allows 1 WS at VOS3, Table 16) | **yes** |
| NUCLEO-G0B1RE | 64 MHz, 2 wait states | **64 MHz, 2 WS.** RM0444 Table 13: 2 WS up to 64 MHz in range 1. ST's example (`STM32CubeG0` `51075a5`, `Projects/NUCLEO-G0B1RE/Examples/GPIO/GPIO_EXTI`): PLLN 8, `FLASH_LATENCY_2` | no |
| SAM D20 Xplained Pro | 48.005 MHz (DFLL closed loop on the 32 kHz crystal), 1 wait state | **48 MHz, 1 WS.** DS60001504K Table 32-37: 1 WS up to 48 MHz at 2.7–3.63 V. Two caveats: the table of the 105 °C devices, Table 33-23, allows only 32 MHz, so the board's part number is to be read; and Microchip's own default configuration for this board was not found in this pass | no; check the part's temperature grade |

**So the clock changes on one board, the NUCLEO-H723ZG**, and possibly the
flash divider on the Pico 2.
- *Files that change.* `firmware/common/stm32h723/board.h` (make 520 MHz
  the default, or set `BOARD_CLOCK_FAST=1` in `board.mk`). For the Pico 2,
  if confirmed, `firmware/common/rp2350/board.h` (QMI M0_TIMING).
- *What the H723 change brings with it* (from `board.h`'s own notes):
  - The APB1 timers tick at 260 MHz, which is 2 core cycles per tick, not
    1. The stress tests' timer settings and the sweep's step change, so
    the stress images change.
  - USART3 gets a divisor for 130 MHz.
  - `board_idle` returns to 64 MHz between runs.
  - Heat is known: a 52 °C plateau after an hour of full load at 520 MHz
    in the cabinet ([report](../../reports/2026-11-17-h723-thermal.md)).
- *The cache-off scenarios* then carry 3 wait states at 520 MHz instead of
  7 at 64 MHz. The sentence above the H723's cache-off tables
  (`site/crc_tables.py`, `BEFORE_OFF`) is rewritten.

**Checked on 2026-11-26 (the checks this section left open):**
- *G474, ST's template against the manual.*
  - The template (`STM32CubeG4` `140db64`,
    `Projects/NUCLEO-G474RE/Templates/Src/main.c`) runs SYSCLK
    170 000 000 with `PWR_REGULATOR_VOLTAGE_SCALE1_BOOST` (line 97). It
    passes `FLASH_LATENCY_8` to `HAL_RCC_ClockConfig` (line 125; comment
    "Flash Latency(WS) = 8", line 86).
  - `FLASH_LATENCY_8` is `FLASH_ACR_LATENCY_8WS` (`stm32g4xx_hal_flash.h`
    line 480, `stm32g4xx-hal-driver` `a600128`), which is `0x00000008U`
    (`stm32g474xx.h` line 5084, `cmsis-device-g4` `626ee41`): 8 wait states.
  - RM0440 Table 9 gives 4 WS up to 170 MHz in boost mode, so the template
    sets 4 more than the manual's fewest.
  - On the other boards the two agree: the H723 template sets
    `FLASH_LATENCY_3` (RM0468 Table 16: 3 at AXI 260 MHz, VOS0), and the
    G0B1's sets `FLASH_LATENCY_2` (`STM32CubeG0` `51075a5`, `Templates`
    line 142; RM0444 Table 13: 2 up to 64 MHz). The nRF5340, Pico 2 and
    SAM D20 have no template of this kind to compare.
  - The rule takes the manual's fewest, so the G474 stays at 4.
- *Pico 2, the flash divider at boot.* **CLKDIV 3 is what an SDK image
  runs at, the same as ours**, so the Pico 2 does not change.
  - The boot ROM tries its flash read modes with an SCK divisor of 3
    (RP2350 datasheet, §5.2.7 "Flash boot", Table 452). It enters the
    image in the mode that worked: "Any further setup … is performed by
    the flash image itself" (§5.2).
  - pico-sdk runs its XIP setup function (the boot2 with
    `PICO_FLASH_SPI_CLKDIV`) on RP2350 only under `PICO_EMBED_XIP_SETUP`
    (`pico_crt0/crt0.S` line 503, `#if !PICO_RP2040 && PICO_EMBED_XIP_SETUP
    && !PICO_NO_FLASH`).
  - The datasheet calls that a flag to set: "The PICO_EMBED_XIP_SETUP=1
    flag in the SDK enables inclusion and execution of an XIP setup
    function on RP2350 builds" (§5.2). No default for it was found in
    `crt0.S`, `pico_crt0`'s or `pico_standard_link`'s CMake files, or the
    platform headers (master `079c6f3`), and an undefined macro is 0 in
    `#if`.
  - Our earlier reading of "the SDK sets CLKDIV 2" took the linked boot2
    to be executed; on RP2350 it is not, unless the flag is set.
- *SAM D20, the temperature grade.* It cannot be read from the chip.
  - DSU.DID (0x41002018) holds PROCESSOR, FAMILY, SERIES, DIE, REVISION and
    DEVSEL, and no temperature grade (DS60001504K §12.13.9).
  - The grade is the letter after the dash in the ordering code: U for
    −40 to 85 °C, N for −40 to 105 °C (§2 "Ordering Information").
  - Microchip's user guide for the board (Atmel-42102D, 04/2016, now in
    `~/vl-dev/datasheets`) names only "ATSAMD20J18A".
  - So the grade is read from the marking on the chip: a look at the
    board by the owner, with no board access by us.
  - **By the vendor's BOM, the chip's marking not yet read:** the part is
    **SAMD20J18A-AUT**, U = −40 to 85 °C, so Table 32-37 applies: 48 MHz
    with 1 wait state at 2.7–3.63 V, the board's present setting.
    - *The source.* Microchip's design documentation for the board,
      `SAMD20-Xplained-Pro_Design-Documentation.zip` from
      ww1.microchip.com, file
      `SAMD20_Xplained_Pro_design_documentation_rev6.pdf` (document number
      A09-1873, revision 6, dated 22.07.2015; in
      `~/vl-dev/datasheets/samd20-xpro-design`).
    - *The BOM line:* "Fitted U300 1 SAMD20J18A-AUT ATMEL SAMD20J18A-AUT
      Atmel 32-bit RISC MCU". The schematic's target MCU carries the same
      part number.

**The nRF5340's clock, looked at again (2026-11-26, by register and
function).** The terms searched: `HFCLKCTRL`, `hfclk_div`,
`NRF_CLOCK_HFCLK_DIV_1`, `nrf_clock_hfclk_div_set`, `divider_set`.
- **What sets HFCLKCTRL.** In the startup Zephyr builds for the application
  core, `SystemInit` writes it once, to Div2, and only as the workaround for
  erratum 42 ("Reset value of HFCLKCTRL is invalid").
  - The file is `system_nrf5340_application.c`, line 128
    (`NRF_CLOCK_S->HFCLKCTRL = CLOCK_HFCLKCTRL_HCLK_Div2 ...`, under
    `if (nrf53_errata_42())`).
  - Zephyr's glue takes it from its hal_nordic module
    (`modules/hal_nordic/nrfx/CMakeLists.txt` line 48:
    `${MDK_DIR}/nrf53/nrf5340/system_nrf5340_application.c`).
  - The same file is read at hal_nordic `36ffe23` (the revision Zephyr main's
    `west.yml` pins), `nrfx/bsp/stable/mdk/nrf53/nrf5340/`, and at nrfx
    master.
- **What leaves it.** No other place writes HFCLKCTRL or calls a divider
  function:
  - Zephyr main `soc/nordic/nrf53/soc.c`;
  - Zephyr v3.0.0 and v2.7.0 `soc/arm/nordic_nrf/nrf53/soc.c`;
  - Nordic's fork sdk-zephyr main `soc/nordic/nrf53/soc.c`;
  - `drivers/clock_control/clock_control_nrf.c` in Zephyr main and
    sdk-zephyr main;
  - `dts/arm/nordic/nrf5340_cpuapp.dtsi` (cpu@0 has no `clock-frequency`);
  - `boards/nordic/nrf5340dk/nrf5340dk_nrf5340_cpuapp_defconfig` and
    `nrf5340_cpuapp_common.dtsi`;
  - `soc/nordic/nrf53/Kconfig.defconfig` (only `SYS_CLOCK_HW_CYCLES_PER_SEC`,
    the RTC's).
  - `HFCLK192M` is another clock (`HFCLK192MCTRL`, PS §4.11.1.1), not the
    CPU's.
- **What a hello world built for `nrf5340dk/nrf5340/cpuapp` ends up with:**
  HFCLKCTRL's reset value, Div2, which is **64 MHz** (PS v1.6 §4.11.3.44,
  reset 0x00000001 = Div2). 128 MHz is set only by an application that
  asks for it.
- **Not searched:** the applications of sdk-nrf. The vendor's default as
  the SDK builds it is 64 MHz.
- **Our comment.** `firmware/common/nrf5340/nrf5340_bench.h` line 55
  ("as Zephyr runs the application core by default") is therefore not
  right. It is in a frozen file and is corrected with method version 3.

## 2. Option registers, read and recorded

Each read is zero-write, through the probe, at the start of each series
and of each job. The values go into the run files and the records as a
new field.

| Board | What is read | Where (source) |
|---|---|---|
| NUCLEO-G474RE | FLASH_OPTR | 0x40022020 (RM0440 §3.7.8, offset 0x20) |
| NUCLEO-G0B1RE | FLASH_OPTR | 0x40022020 (RM0444 §3.7.8, offset 0x020) |
| NUCLEO-H723ZG | FLASH_OPTSR_CUR, FLASH_OPTSR2_CUR (CPUFREQ_BOOST) | 0x5200201C, 0x52002070 (RM0468 §4.9, offsets 0x01C and 0x070); the 2026-11-25 reads are in the [lab note](../drafts/2026-11-25-nrf5340-approtect-recovery.md) |
| nRF5340 DK | UICR.APPROTECT, UICR.SECUREAPPROTECT | 0x00FF8000, 0x00FF801C (PS v1.6; as read on 2026-11-25) |
| Pico 2 | the OTP rows read raw in the second CRC series (critical flags, boot configuration page, boot keys) | [second series' report](../../reports/2026-11-25-crc-second-series.md), "Pico 2: the OTP read back raw" |
| SAM D20 Xplained Pro | the NVM User Row (fuses: BOOTPROT, EEPROM size, BOD, WDT, region locks) | 0x00804000 (DS60001504K §9.4) |

- *Files that change.* These are all host-side; no image changes:
  - the runners `firmware/nrf5340-rb-bench/run-one.py` and
    `kinds/crc/bench/run-crc.py`, and the stress scripts' run steps;
  - the record makers `firmware/nrf5340-rb-bench/onerecords.py` and
    `kinds/crc/bench/crcrecords.py`, and their checks.
- *Record schemas.* A new optional field, or a new version
  (`bench-v2` and `crc-bench/1` → `/2`). **For the owner:** the runner is
  a host-fixable file (`records/host-fixes.json`), but the export says "a
  fix that touches how the numbers are read … is not a host fix". This
  read touches no number, so it could be a recorded host fix. The plan
  recommends a new record version instead, so that old and new records
  are told apart by their schema.

## 3. The nRF5340 boot stub

Decided (DECISIONS 2026-11-26).
- *The change:* `firmware/common/benchboot.c` copies UICR.APPROTECT and
  SECUREAPPROTECT into CTRL-AP at every boot.
- *Stress images are not affected:* `benchboot` is used only by
  `firmware/nrf5340-rb-bench` and `kinds/crc/bench` (grep of `firmware`,
  `kinds`, `lab/tools`).

What it must show before any run (from the decision):
1. only the nRF5340's stub bytes differ;
2. every other board's images are byte for byte unchanged;
3. the measured part of each nRF5340 image is unchanged;
4. after the rerun, the baseline is compared with the present records.

## 4. Ring-buffer runs through the queue

Decided (DECISIONS 2026-11-26): version 2's runner is tried once through
`lab/tools/boardqueue.py` with no flash write, before ring-buffer runs go
in parallel.
- *Files:* none frozen. The queue is a lab tool, not a test source:
  `TEST_SOURCES` in `lab/tools/public-export.py` holds `firmware`,
  `lab/boards.conf`, `lab/tools/source-commit.sh` and
  `lab/tools/boardpower.sh`.
- *What it must show:* one zero-write job of `run-one.py` on one board
  gives the published records' numbers. The queue counts its "FLASH
  WRITE" line as for the CRC runner, with a budget of 0.

## 5. The median beside the mean (open)

The mean includes the first call and can lie up to 46 % above the minimum
where calls vary (next-method-version list).
- *What a median needs:* every call's cycles, or a histogram, kept in the
  image. That is an image-side change of both benchmarks
  (`firmware/nrf5340-rb-bench/main.c`, `kinds/crc/bench/main.c`), their
  decoders and their record makers.
- *Its cost:* every board's benchmark series of both kinds measured
  again (below). **Not decided.**

## Consequences: what is measured again, and how the published records are kept

**The rule stays as it is:** a record is shown if this tree builds its
images byte for byte (the same-image rule, DECISIONS 2026-11-22 and
2026-11-24; the ledger `records/rebuilt.json`). A changed image means a
new measurement. Under items 1–4:

| Board | What changes in its images | Series measured again |
|---|---|---|
| nRF5340 DK | the boot stub (item 3) | ring-buffer benchmark (45 records); CRC first and second series (35 records). Not its stress records (no stub there) |
| NUCLEO-H723ZG | the clock (item 1) | ring-buffer benchmark (44); CRC both series (38). Not its stress records: every stress record is of the archived series "version 1" (`source_commit` a7a206190337, `records/archived.json`), checked against its own commit, not the tree (corrected 2026-11-26) |
| Pico 2 | nothing: the flash divider stays at 3 (checked 2026-11-26, section 1) | none |
| NUCLEO-G474RE, NUCLEO-G0B1RE, SAM D20 | nothing (item 2 is host-side) | none: their records stay, held by the ledger |

With item 5 decided as well, every board's benchmark series of both kinds
is measured again: 265 ring-buffer and 221 CRC records. The stress records
are measured again only on boards whose images change.

**How the published records are kept.** Records that are measured again
are archived, as version 1 was (`records/archived.json`: name, commit,
`exported_from`, public commit, count, SHA-256).
- They are checked against their own commit in the public history, not
  against the tree.
- The pages show the new records, and say that the earlier ones are
  archived and where they are.
- With item 5 the whole version 2 benchmark series and both CRC series are
  archived as series. Without it, only the measured-again boards' records
  are archived, as "version 2 (NUCLEO-H723ZG and nRF5340 DK, before
  method version 3)" and the same for CRC.

**Cost per board.** The flash writes are those of the published series,
taken from the series reports. The times are the spans of the version 2
records (first to last run timestamp) and the CRC reports' per-board
times:

| Board | Ring-buffer benchmark: writes, time | CRC first + second series: writes, time | Stress (if its images change) |
|---|---|---|---|
| nRF5340 DK | 5, ~58 min | 3 + 2, 88 + 59 min | – |
| NUCLEO-H723ZG | 5, ~1 h 26 at 64 MHz (less at 520) | 3 + 1, 65 + 55 min | 4 bundles, ~5 h ISR stress + ~5 h two-interrupt test ([publication rerun](../../reports/2026-11-20-publication-rerun.md), "Flash writes") |
| Pico 2 (if) | 2 (in parts), ~1 h 33 | 1 + 2, 3 h 40 + 3 h 47 | 7 bundles, ~5 h + ~5 h |
| G474, G0B1, SAM D20 (only with item 5) | 9, 9, 18; ~46, ~47, ~59 min | 5 + 4, 5 + 5, 9 + 7; 33 + 32, 62 + 71, 118 + 95 min | – |

**Totals:**

| Case | Flash writes | Serial | Through the queue |
|---|---|---|---|
| Items 1–4, Pico 2 unchanged | about 25 (nRF5340 10, H723 15 with its stress bundles) | about 17 h: nRF5340 3 h 25, H723 3 h 26 of benchmarks and 10 h of stress | about 13 h 30, the H723 alone |
| The Pico 2's flash divider as well | 12 more (5 benchmark, 7 stress), the Pico 2 writing alone | about 9 h of benchmarks and 10 h of stress more | the Pico 2 then sets the time, about 19 h |
| Item 5 as well (every benchmark on every board) | about 95 benchmark writes (48 ring-buffer, 26 + 21 CRC), plus the stress bundles of the boards whose images change | about 25 h of benchmarks | about 9 h of benchmarks (the Pico 2), plus the stress where images change |

These counts are taken from the published series. Bundles built under
method version 3 may hold the CRC kind's 38 configurations in fewer
bundles than the two series' 26 + 21; step 3 of the pools plan counts
from real sizes.

## What must be shown before any run

| Item | Shown on the host or with zero writes, before the first flash write |
|---|---|
| 1, H723 | Every other board's images (ring buffers, CRC, stress) are byte for byte unchanged. The H723's images differ only in the board layer: the disassembly differs only in `board_init`, the UART divisor and the stress timer constants. One smoke on the board reads back RCC, PWR and FLASH_ACR (VOS0, PLL locked, 3 WS, WRHIGHFREQ 11) and checks the cycle counter against a timer of known clock. Stress: the sweep's step is worked out again for 2 cycles per tick, and the control is still caught |
| 1, Pico 2 | First, the confirmation that the SDK sets CLKDIV 2 at boot. Then, as for the H723: only the Pico 2's board layer differs, and a smoke reads QMI M0_TIMING back |
| 2 | Every board's images are byte for byte unchanged (host side only). The reads are zero-write, and on the H723, nRF5340 and Pico 2 they equal the values read on 2026-11-25. Records with and without the new field both pass the export |
| 3 | The four points of the decision (above) |
| 4 | The zero-write trial gives the published numbers |
| 5 | (if decided) the mean from the new images equals the published mean in every scenario, before the median is shown |

After each rerun, the baseline (the reference timed in the same images) is
compared with the present records per scenario, as the second CRC series
did with the first.

## The draft and what it shows (2026-11-26)

The changes of items 1–3 are drafted on the branch `method-v3-draft`, from
`kind-pools`, not for `main`. Its first draft commit is `0b1ff6d`; the
option reader follows in `5dc4284`.
- **Item 3, the nRF5340 stub.**
  - `firmware/common/benchboot.c` copies UICR.APPROTECT and
    SECUREAPPROTECT into CTRL-AP at the start of `Reset_Handler`, under
    `BENCHBOOT_NRF5340`.
  - `firmware/nrf5340-rb-bench/onebundle.py` passes that define for the
    nRF5340 only, as it passes `BENCHBOOT_RP2350` for the Pico 2.
- **Item 1, the H723 clock.**
  - `firmware/common/stm32h723/board.h` defaults `BOARD_CLOCK_FAST` to 1
    (520 MHz, VOS0, 3 WS, WRHIGHFREQ 11, already in the file as
    `h7_clock_520`). It defines `BOARD_TIMER_CLK_DIV` (2 at 520 MHz).
  - `firmware/common/stm32/tim2_stress.h` and `tim3_stress_b.h` divide
    their prescaler by it, so that one stress-timer tick stays
    4 << prescaler core cycles. They default it to 1 for the other boards.
- **Item 2, the option registers.** `lab/tools/read-options.py` is a
  zero-write reader of the registers in section 2.
  - It runs `probe-rs read` only, takes the board's lock unless the queue
    holds it, and writes one JSON per board (`board-options/1`).
  - Not yet drafted: the record makers taking that file into a new record
    version.

**The proof: every published record rebuilt from the draft tree**
(`lab/tools/image-ledger.py --all`, and for the ring-buffer records of the
two changed boards `oneverify.sh` with `VL_TREE=1`; 486 records, no board):

| Board | Ring-buffer records (version 2) | CRC records | What differs |
|---|---|---|---|
| NUCLEO-G474RE, NUCLEO-G0B1RE, SAM D20, Pico 2 | 44, 44, 44, 44 MATCH | 38, 38, 35, 37 MATCH | nothing (324 of 324) |
| nRF5340 DK | 45 DIFFERS | 35 DIFFERS | in all 80, only "the boot stub differs": every image, address and fixed part is the record's |
| NUCLEO-H723ZG | 44 DIFFERS | 38 DIFFERS | every placement's flash bytes and the fixed part (the clock code in board.h); the boot stub is the record's |

So points 1–3 of the nRF5340 decision are shown:
1. only the nRF5340's stub bytes differ;
2. every other board's images are byte for byte unchanged (and the H723's
   differ only by the clock);
3. the measured part of each nRF5340 image is unchanged.

Point 4 (the baseline against the present records) follows the rerun.

**Found on the way:**
- *The stress records* are all of the archived series "version 1", so no
  change of the draft touches them (the table above is corrected).
  - The stress run scripts' text for the H723, "Cortex-M7, 64 MHz (reset
    clock)" (`firmware/nrf5340-rb-stress/run.sh` line 97,
    `firmware/rb-mp-stress/run.sh` line 48, `firmware/rb-dma-stress/run.sh`
    line 26). **Corrected 2026-11-26: changing it does stop records.** The
    stress records do not depend on it, but the ring-buffer benchmark's
    records do: the export requires every host-side file under `firmware/`
    to be the record's, but for the build-by files and recorded host fixes
    (`lab/tools/public-export.py`, `v2_host_stands`). The stress scripts are
    neither, so the draft's change of the text (`bb60294`) stops all 265
    ring-buffer records, those of the four unchanged boards included. See
    "For the owner" below.
- *Our own comment on Zephyr.* `firmware/common/nrf5340/nrf5340_bench.h`
  says that 128 MHz is how "Zephyr runs the application core by default".
  - No code in Zephyr v3.0.0, v3.5.0, v4.0.0 or main (the nRF53 SoC file,
    the clock driver, the devicetree) changes the divider.
  - The `SystemInit` copy Zephyr builds from its `hal_nordic` module
    (revision `36ffe23`) could not be read at the paths tried.
  - So section 1's "Zephyr leaves 64 MHz" stands with that gap, and the
    comment, in a frozen file, rests on nothing found.
- *Still to draft:*
  - the record makers' new version with the option registers;
  - the stress scripts' H723 text;
  - the pages' sentence above the H723's cache-off tables
    (`site/crc_tables.py`, `BEFORE_OFF`).

## The counted proposal: from the draft to the boards (2026-11-26)

The draft is on `method-v3-draft` (`bb60294`). Nothing goes to `main` or a
board before the owner's word.

**Frozen files that change** (version 2's test sources, all of `firmware/`;
the CRC kind's, `kinds/crc` and `firmware/common`):

| File | Side | Change | What holds the records |
|---|---|---|---|
| `firmware/common/benchboot.c` | image | the nRF5340 stub opens CTRL-AP | the ledger rebuild: only the nRF5340's stub differs (shown) |
| `firmware/nrf5340-rb-bench/onebundle.py` | built by | `-DBENCHBOOT_NRF5340` | the same |
| `firmware/common/stm32h723/board.h` | image | 520 MHz by default, `BOARD_TIMER_CLK_DIV` | the same: only the H723's images differ (shown) |
| `firmware/common/stm32/tim2_stress.h`, `tim3_stress_b.h` | image | the prescaler divided by `BOARD_TIMER_CLK_DIV` (1 elsewhere) | the same |
| `firmware/common/nrf5340/nrf5340_bench.h` | image | line 55's comment on Zephyr's default corrected (not yet in the draft) | the same (a comment) |
| `firmware/nrf5340-rb-bench/onerecords.py`, `oneverify.sh` | host, host-fixable | `rb-bench/3` with `option_registers` | a recorded host fix each (`records/host-fixes.json`) |
| `kinds/crc/bench/crcrecords.py`, `crcverify.sh` | host, host-fixable | `crc-bench/2` with `option_registers` | the same |
| `firmware/nrf5340-rb-stress/run.sh`, `firmware/rb-mp-stress/run.sh`, `firmware/rb-dma-stress/run.sh` | host, **not** host-fixable | the H723's description, 520 MHz | **none: this stops every ring-buffer record** (point 1 below) |

Not frozen, also changed: `lab/tools/read-options.py` (new),
`lab/tools/compare-records.py`, `lab/tools/verify-build.sh`,
`lab/tools/crc-series-checks.py`, `kinds/crc/bench/crccompare.py` (not a
CRC source), and the site's readers and texts (`site/*.py`, the method and
compare pages, `RESULTS.md`).

**Measured again, and how the old records are kept:**

| Board | Ring-buffer benchmark | CRC first + second series | The old records |
|---|---|---|---|
| nRF5340 DK | 45 records, 5 bundles, ~58 min | 35 records, 3 + 2 bundles, 88 + 59 min | archived, as version 1 was |
| NUCLEO-H723ZG | 44 records, 5 bundles, ~1 h 26 at 64 MHz (less at 520) | 38 records, 3 + 1 bundles, 65 + 55 min | archived |
| the other four | – (held by the ledger) | – | stay current |

- The archived series are named "version 2, nRF5340 DK and NUCLEO-H723ZG
  (before method version 3)" and "CRC, nRF5340 DK and NUCLEO-H723ZG
  (before method version 3)": one entry each in `records/archived.json`,
  with count and SHA-256.
- The pages show the new records. A line per board says that the earlier
  ones are archived, and links to them in the public history.
- The cache-off sentence follows each record's clock by itself
  (`site/crc_tables.py`, `before_off`).

**The pools series** (plan A, step 3) runs under version 3 only:
1. one bench image for one board, built and not flashed;
2. then the counted proposal from real sizes;
3. then the series.

Plan A's estimate: 80 images per board (72 on the two Cortex-M0+ boards),
about 11 bundles = flash writes, about 4 h 10 serial, about 2 h through the
queue.

**Per board, everything together** (writes; time, runs and writes):

| Board | Reruns | Pools (estimate) | Writes | Time |
|---|---|---|---|---|
| nRF5340 DK | v2 5 + CRC 5 | 1 | 11 | ~4 h 10 |
| NUCLEO-H723ZG | v2 5 + CRC 4 | 1 | 10 | ~4 h (less at 520 MHz) |
| Pico 2 | – | 1 (in parts, alone) | 1 | ~1 h 50 |
| NUCLEO-G474RE | – | 2 | 2 | ~17 min |
| NUCLEO-G0B1RE | – | 2 | 2 | ~28 min |
| SAM D20 | – | 4 | 4 | ~53 min |

- **Totals:** about 30 flash writes, plus one smoke bundle on each of the
  two changed boards if the smoke needs its own.
- **Time:** serial about 11 h 30. Through the queue, one worker per board,
  about 4 h 15: the nRF5340 and the H723 set it.
- **The Pico 2 writes alone**, so the other boards wait for its write
  (about 3 minutes in parts).
- **The nRF5340 is never power-cycled.**

**The order of jobs:**
1. **On the host, after the owner's word.**
   - Apply the draft to `main`.
   - Record the four host fixes.
   - Rebuild the ledger (`image-ledger.py`; the four unchanged boards'
     records must stay MATCH).
   - Add the archive entries once the new records exist.
   - Build the pools image for one board and count.
2. **Smoke, one board at a time.**
   - *H723:* one v3 bundle written, a few runs. `read-options.py` and a
     zero-write read of RCC, PWR and FLASH_ACR (VOS0, 3 WS, WRHIGHFREQ 11,
     PLL locked). The cycle counter checked against a timer of known clock.
   - *nRF5340:* one v3 bundle written with the board powered as it is, a
     few runs. `read-options.py`.
3. **The reruns through the queue**, the nRF5340 and the H723 side by side
   (v2, then CRC; each job with the reviewer's OK), and `read-options.py`
   before each job.
4. **The pools series**, on all six boards through the queue, the Pico 2's
   one write alone. **That write is the real Pico 2 write whose time is
   measured** (alone, by the rule). Whether it may also be timed beside a
   neighbour's write is point 3 below.
5. **Records and compares.**
   - The baseline of every rerun against the present records (point 4 of
     the nRF5340 decision).
   - The pools records, pages and MCP data.

**What is published when:**
- **After step 5:** version 3's records of the two boards with the
  archived series, the texts of the draft, and the pages. One publication,
  with the owner's go.
- **Later:** the pools kind, with its own go (plan A, steps 5–7).

**For the owner (this proposal):**
1. *The stress scripts' H723 text.* Either the three stress scripts become
   host-fixable (an export-rule change, recorded as host fixes like the
   runners), or their H723 text stays wrong until the stress tests are run
   again. *Recommended: host-fixable for a text-only change.*
2. *The nRF5340 stub is shown working only by a power-on.* The stub's
   effect (the port open after a power-on) is shown only if the board is
   powered on once with the v3 bundle on it. That goes against "never
   power-cycled", and if the stub failed, the known recovery would follow.
   *Recommended: one power-on after the reruns, the recovery at hand,
   with the reviewer watching.*
3. *Time the Pico 2's pools write beside a neighbour's write*, which needs
   the rule "the Pico 2 writes alone" set aside for that one write.
   *Recommended: no; time it alone, and leave the beside-test to a later
   series.*
4. *This order and these counts.* *Recommended: yes.*

## The new kind under the new version

**Yes:** the pools kind is measured only under method version 3, as
expected. Its images are built with the new stub and the new H723 clock
from the start, so its records never need archiving for these items. Its
first series can run in the same queue campaign as the reruns: per board
one job per kind, each with its own write budget.

## For the owner

1. **The rule for the clock:** the vendor's startup or template clock, no
   option bytes, the manual's fewest wait states. *Recommended: yes.*
2. **NUCLEO-H723ZG to 520 MHz, VOS0, 3 WS, caches as today.**
   *Recommended: yes* (ST's template and example; `BOARD_CLOCK_FAST`
   already exists).
3. **nRF5340 stays at 64 MHz** (Nordic's startup and Zephyr leave it
   there). *Recommended: yes; 128 MHz would be a choice of ours, not the
   user's default.*
4. **Pico 2 flash divider:** confirm the SDK's CLKDIV 2 first, then decide.
   *Recommended: confirm on the host, from the SDK's code path.*
5. **SAM D20:** read the chip's temperature grade before the series.
   *Recommended: yes, from the chip's marking or its device ID.*
6. **Option registers in a new record version** rather than as a host
   fix. *Recommended: new version.*
7. **The median:** decide now or leave for later. If decided, every
   benchmark on every board is measured again (about 95 benchmark writes).
   *Recommended: decide it now, so that one campaign covers it, or leave
   it out of version 3 explicitly.*
8. **Superseded records archived**, as version 1 was. *Recommended: yes.*
9. **The pools kind only under version 3.** *Recommended: yes.*
