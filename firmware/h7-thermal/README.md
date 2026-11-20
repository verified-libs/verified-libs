# h7-thermal (NUCLEO-H723ZG)

How warm the STM32H723 gets at 520 MHz under full load. The firmware logs
the die temperature once a second from the chip's digital temperature
sensor (DTS, RM0468 chapter 30) through three phases: 60 s idle at the
reset clock (64 MHz), 600 s full load at 520 MHz (FPU and integer work on
DTCM data, caches on), 300 s cooling at 64 MHz. At 85 C (LIMIT_C) the load
stops at once; VOS0 allows a junction temperature of 105 C (DS13313).

```sh
PROBE=0483:374e:<serial> bash run.sh      # ~16 min, one flash write
```

`run.sh` prints the temperature every 10 s while it runs and writes a JSON
record with every sample (raw sensor count, the clock it was counted with,
and the temperature from the chip's factory calibration). The clock setup is
the board layer's (`common/stm32h723/board.h`, BOARD_CLOCK_FAST).
