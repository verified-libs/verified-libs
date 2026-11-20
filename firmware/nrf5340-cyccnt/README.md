# nrf5340-cyccnt

First cycle-count measurement on the nRF5340 DK application core
(Cortex-M33), bare metal in C, no SDK. It proves the measurement chain:
toolchain image → probe-rs → DWT `CYCCNT` → results read back from RAM.

## Run
On lib-lab1, with the nRF5340 DK on J2:
```sh
bash run.sh
```
`run.sh` builds in the pinned toolchain image, flashes, resets, and reads
the result block at `0x20000000` with probe-rs. No UART is involved, so the
measured code is not disturbed by I/O.

## How it works
- **Debug access after reset:** an erased nRF5340 locks its debug port
  (APPROTECT) at every reset. On first boot the firmware writes
  `UICR.APPROTECT` and `UICR.SECUREAPPROTECT` = `0x50FA50FA` and resets;
  every boot then copies them into the CTRL-AP software branch, as Nordic's
  SystemInit does. (probe-rs 0.32 cannot program the UICR page itself:
  `program_page` fails with code 104.)
- **Application core only:** the probe-rs target `nRF5340_xxAA_APPONLY`
  ignores the blank, locked network core. The stock `nRF5340_xxAA` target
  would erase the whole chip on every attach.
- **Clock:** `HFCLKCTRL` = Div2, so the core runs at 64 MHz.
- **Register addresses:** nrfx MDK v4.7.0, cross-checked against the
  nRF5340 Product Specification (OPS v0.5.1).

## Results (2026-11-06, nRF5340 DK, 64 MHz, 1000 runs each)
| Measurement | min | max | mean |
|---|---|---|---|
| Back-to-back `CYCCNT` reads (overhead) | 1 | 1 | 1.000 |
| 100 × NOP from flash, cache off | 141 | 141 | 141.000 |
| 100 × NOP from flash, cache on | 51 | 105 | 51.054 |

What this shows:
- **The instruction cache is off after reset** (`CACHE.ENABLE` = 0). Every
  result must record the cache state; it changes the numbers by almost 3×.
- **Cache off is fully deterministic:** 141 cycles in every one of 1000
  runs. Fetching from flash is the bottleneck (200 bytes of code).
- **Cache on:** 51 cycles, i.e. 50 for 100 NOPs. The Cortex-M33 can
  dual-issue pairs of 16-bit instructions, so 100 NOPs take 50 cycles once
  the code is in the cache. The single 105-cycle run is the first, cold one
  (51.054 × 1000 = 999 × 51 + 105).
- **Measurement overhead is 1 cycle.** It is subtracted in real benchmarks.

So for ring buffer benchmarks on the nRF5340 we report both cache states,
with cache on as the primary number: that is how firmware normally runs
(Zephyr enables the cache). The first, cold run is reported separately.
