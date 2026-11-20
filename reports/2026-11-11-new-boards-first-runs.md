# New boards: first runs (2026-11-11)

First bench and stress runs on the three Nucleo boards from the DigiKey
order. Same firmware, libraries (`libs.lock`), toolchain image and adapters as
on the nRF5340; only the board layer (`firmware/common/<board>/`) differs.
Records are in `~/lab-runs/` on lib-lab1.

## Boards

| Board | Core | Clock | Cycle counter | Probe | Port (power cycling) |
|---|---|---|---|---|---|
| NUCLEO-G0B1RE | Cortex-M0+ | 64 MHz (HSI16 + PLL) | SysTick (no DWT on M0+) | ST-LINK/V2-1 | monitor 1, hub `4B0708619185` port 2 (yes) |
| NUCLEO-G474RE | Cortex-M4F | 170 MHz (HSI16 + PLL, boost) | DWT `CYCCNT` | STLINK-V3 | monitor 1, port 3 (yes) |
| NUCLEO-H723ZG | Cortex-M7 | 64 MHz (HSI, reset default) | DWT `CYCCNT` | STLINK-V3 | monitor 2, hub `9E0C0069B5FA` port 2 (yes) |

The H723ZG runs at its reset clock on purpose: 550 MHz needs a supply
configuration that matches the board, and a wrong one can lock the chip.
Cycle counts are what the bench reports, so the comparison holds; flash
numbers with the cache off include the reset-default wait states.

## Bench (flash, cache/accelerator on, gcc -O2, newlib-nano memcpy)

Mean cycles, 1-byte push / pop · 64-byte block, cycles per byte. All 25
adapters ran with 0 FIFO errors on every board and code location (flash,
SRAM, and CCM on the G474 / ITCM on the H723).

| Library | NUCLEO-G0B1RE (M0+, 64 MHz) | NUCLEO-G474RE (M4, 170 MHz) | NUCLEO-H723ZG (M7, 64 MHz HSI) |
|---|---|---|---|
| pxq RingBuffer_PackedState (C++) | 35 / 38 · 10.2 | 20 / 21 · 7.5 | 17 / 16 · 3.5 |
| lwrb (C) | 263 / 256 · 13.5 | 180 / 176 · 5.1 | 145 / 136 · 3.8 |
| AndersKaloer Ring-Buffer (C) | 73 / 50 · 27.3 | 57 / 41 · 20.1 | 33 / 26 · 9.2 |
| jnk0le Ringbuffer (C++) | 36 / 42 · 11.8 | 23 / 26 · 9.5 | 35 / 35 · 6.6 |
| ETL queue_spsc_isr (C++) | 73 / 68 · 53.6 | 40 / 45 · 31.9 | 42 / 45 · 28.5 |
| ETL queue_spsc_atomic (C++) | 54 / 51 · 40.0 | 30 / 27 · 23.9 | 38 / 37 · 26.2 |
| QuantumLeaps LFRB (C) | 69 / 61 · 79.9 | 46 / 46 · 53.4 | 46 / 41 · 35.7 |
| EmbeddedArtistry cbuf threadsafe (C) | 74 / 60 · 81.9 | 56 / 46 · 58.4 | 37 / 31 · 25.4 |
| ece-mohammad RingBuffer (C) | 111 / 109 · 12.4 | 81 / 80 · 4.2 | 51 / 50 · 3.0 |
| micoring SPSC mode (C) | 127 / 131 · 128.2 | 98 / 97 · 96.9 | 72 / 71 · 59.9 |
| kostyk348 lf_spsc (C) | 159 / 154 · 212.6 | 72 / 67 · 79.4 | 65 / 59 · 56.2 |
| diffstorm cb (C) | 122 / 131 · 141.4 | 72 / 69 · 77.9 | 51 / 63 · 48.4 |
| RIOT tsrb (C) | 65 / 64 · 30.1 | 52 / 51 · 19.6 | 46 / 44 · 11.4 |
| Contiki-NG ringbuf (C) | 61 / 53 · 71.9 | 45 / 42 · 51.9 | 31 / 29 · 22.2 |
| rigtorp SPSCQueue (C++) | 52 / 83 · 73.2 | 35 / 49 · 45.5 | 36 / 43 · 29.1 |
| wizard97 as shipped (C++) | 41 / 41 · 55.9 | 29 / 25 · 33.4 | 24 / 22 · 16.5 |
| wizard97 + PRIMASK macros (C++) | 57 / 61 · 73.9 | 40 / 32 · 43.9 | 52 / 49 · 43.9 |
| polycratia spscring (C++) | 39 / 46 · 11.8 | 24 / 28 · 9.5 | 38 / 32 · 5.2 |
| rt-spsc (C++) | 45 / 44 · 59.4 | 26 / 24 · 31.9 | 36 / 36 · 28.9 |
| TinyUSB tu_fifo (C) | 138 / 131 · 12.3 | 101 / 100 · 4.2 | 57 / 60 · 3.5 |
| pxq Topology::None, single-context (C++) | 35 / 38 · 10.2 | 19 / 20 · 7.5 | 23 / 21 · 3.7 |
| micoring default, single-context (C) | 103 / 98 · 90.9 | 78 / 75 · 66.5 | 49 / 53 · 29.0 |
| EmbeddedArtistry cbuf basic, single-context (C) | 87 / 80 · 98.4 | 40 / 36 · 43.9 | 33 / 29 · 24.9 |
| ETL etl::queue, single-context (C++) | 46 / 47 · 61.4 | 32 / 34 · 38.9 | 25 / 26 · 19.4 |

- NUCLEO-G0B1RE (M0+, 64 MHz): `stm32g0b1-rb-bench-flash-20261111T184412Z.json`
- NUCLEO-G474RE (M4, 170 MHz): `stm32g474-rb-bench-flash-20261111T183917Z.json`
- NUCLEO-H723ZG (M7, 64 MHz HSI): `stm32h723-rb-bench-flash-20261111T184631Z.json`

Not yet checked: the read overheads `BOARD_READ_OVERHEAD` (G0B1 2, G474 2,
H723 1) are assumed from the core manuals; the empty-call calibration in the
records (raw minimum 9 / 8 / 2 cycles in flash) is consistent with them, but
an independent check against a known instruction sequence (as
`nrf5340-cyccnt` did for the M33) is still to do. Until then these numbers
are preliminary.

## Stress (ISR <-> main, 50 000 values per library and direction)

`~/lab-runs/stm32-stress-first-20261111T191247Z`: single, block and zero-copy
(dma) on each board, 9 runs, all valid: real libraries error-free, the
negative control caught in every run, nothing starved. wizard97 as shipped
(not ISR-safe by its own docs) fails on all three boards (761–7989 errors),
as on the nRF5340. Interrupt every 160–668 core cycles (prescaler 0).

These are short runs, not a campaign.

### Fix found on the way

The first G474 run stalled: TIM2 is a 32-bit timer, and when the interrupt
acknowledged a new period that the counter had already passed, it counted
on to 2^32 (about 100 s at 170 MHz / 4) before the next interrupt.
`common/stm32/tim2_stress.h` now restarts the counter in that case
(commit `6a58fbc`), which matches the nRF5340's 8-bit timer behaviour. Two
records made while an old test process still used the same board were
discarded (`~/lab-runs/invalid-overlap-20261111/`).

## Multi-producer / multi-consumer stress (evening)

A second timer (TIM3, `common/stm32/tim3_stress_b.h`; base, enable bit and
IRQ from ST's cmsis-device-g0 `7c77b7cb`, -g4 `626ee412`, -h7 `81db1ec6`) lets
`rb-mp-stress` run on the three boards. 200 000 values per library, TIMER_PRESCALER 1
(`~/lab-runs/stm32-mp-first-20261111T194458Z`):

| Board | MPSC | SPMC |
|---|---|---|
| G0B1RE (M0+) | 0 errors, control caught | 0 errors, control caught |
| G474RE (M4) | 0 errors, control caught | 0 errors, control caught |
| H723ZG (M7) | 0 errors, control caught | 0 errors, control caught |

0 errors = pxq (MPSC/SPMC and MPMC), RIOT tsrb, wizard97 + PRIMASK macros.

The first G0B1 MPSC attempt failed because its `run.sh` was edited while it
ran; it was rerun cleanly.

## SAM D20 Xplained Pro (not working yet)

Board layer written (`common/samd20/`): 8 MHz OSC8M, 0 wait states, SysTick
timing, TC0/TC2 as the two stress timers, flash image only (32 KB RAM).
Register values from Zephyr hal_atmel `8f95c79f` (Microchip's headers).
probe-rs cannot drive the board, so `common/samd20/bin/probe-rs` stands in
with OpenOCD. Bench, stress and MP firmware build. On the board, SWD fails
with "stalled AP operation" (also before our firmware was ever flashed), and
a USB power cycle of its port did not clear it; it worked once after a
manual replug. `adapter serial` crashes OpenOCD 0.12.0 with this EDBG, so the
stand-in does not select the probe by serial. To check with the board in hand.

## Not done yet

- SAM D20: get SWD working (see above), then verify the clock and the
  SysTick timing on it.
- Pico 2: the Debug Probe needs firmware >= 2.2.0 for probe-rs; after an
  update attempt it does not enumerate (USB error -71), to be checked.
- Check the cycle-counter read overheads on the new cores.
- Overnight campaigns on the new boards; ST's own toolchain on the G0B1.
