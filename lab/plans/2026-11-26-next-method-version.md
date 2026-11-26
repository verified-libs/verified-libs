# For the next method version (a list; nothing of it is done now)

Changes decided by the owner for the next version of the benchmark method,
when every board is measured again anyway. Each one changes files that are
frozen today (version 2's test sources, tag `v2-method-freeze`, and the CRC
kind's, tag `crc-method-freeze`), so none is made before the owner starts
that version.

| Item | Why | Decided | Files |
|---|---|---|---|
| The nRF5340 boot stub copies UICR.APPROTECT and UICR.SECUREAPPROTECT into CTRL-AP at every boot, as Nordic's `SystemInit` does | Today only a measured image's `board_init` opens the debug port; after a power-on no image runs, so the board is locked until an erase (nRF5340 PS v1.6, §8.2; [`reproduce.md`](../../site/content/reproduce.md), [lab note](../drafts/2026-11-25-nrf5340-approtect-recovery.md)) | owner, 2026-11-26 | `firmware/common/benchboot.c` |
| The option registers of every board are read and recorded with each series | The NUCLEO-H723ZG came back with CPUFREQ_BOOST set (RM0468 §4.4.3); no series had recorded the option bytes, so when it was set cannot be said ([second series' report](../../reports/2026-11-25-crc-second-series.md)) | owner, 2026-11-26 | the runners (`firmware/nrf5340-rb-bench/run-one.py`, `kinds/crc/bench/run-crc.py`) and the record schemas |
| The NUCLEO-H723ZG with the flash wait states a user would set | Its 64 MHz build keeps the 7 wait states of reset; RM0468 Table 16 allows 0 or 1 at 64 MHz. Check the other boards for the same question | owner, 2026-11-25 | `firmware/common/stm32h723/board.h` |
| The median beside the mean, per scenario | The mean includes the first call and lies up to 46 % above the minimum where calls vary | owner, 2026-11-25 | the benchmarks and the record schemas |

Possibly, not decided: the first call left out of the mean or recorded
apart.
