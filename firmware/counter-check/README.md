# counter-check

Checks, per board, that the cycle counter the benchmark uses counts core
cycles through the benchmark's own `time_call()`: functions of 0-64 NOPs,
256 runs each, min and max. `BOARD=<board> PROBE=<probe> bash run.sh`.

## Results (2026-11-11, code in flash, cache on)

| Board | Counter | Clock | raw min, 0 NOPs | NOPs -> cycles |
|---|---|---|---|---|
| NUCLEO-G474RE (M4) | DWT CYCCNT | 170 MHz | 7 | 1 per NOP (64 NOPs: +64) |
| NUCLEO-G0B1RE (M0+) | SysTick | 64 MHz, 2 WS | 8 | 1 per NOP, plus 3 at the first flash-line crossing (wait states) |
| nRF5340 DK (M33) | DWT CYCCNT | 64 MHz | 5 | 0.5 per NOP: the M33 dual-issues pairs of 16-bit instructions |
| NUCLEO-H723ZG (M7) | DWT CYCCNT | 64 MHz | 2 | ~0.5 per NOP (dual issue) |

So the counters count core cycles on every board; differences in the slope
are the cores, not the counters. raw(0) is the fixed part (blx, bx lr, the
second read) in every benchmark number, before BOARD_READ_OVERHEAD is
subtracted. SAM D20 and Pico 2: to be run.

Found on the way: the H723 board layer cleaned the D-cache right after
reset, when its contents are undefined; that raised an imprecise BusFault
here (fixed in `common/stm32h723/board.h`: clean only a cache that was on).
