# First overnight stress campaign, 2026-11-06/07

nRF5340 DK application core, 20 adapters (19 library configurations + the
negative control), [`overnight.sh`](../firmware/nrf5340-rb-stress/overnight.sh)
for 8 hours, 21:52–05:55 UTC. **Harness development, not published
results.** ⚠ pxq RingBuffer_PackedState is the project owner's library
(principle 6). Raw report: [`2026-11-07-overnight-campaign-raw.md`](2026-11-07-overnight-campaign-raw.md);
the JSON records stay on lib-lab1 in `~/lab-runs/overnight-20261106T215245Z/`.

## Result
- **32 runs: 24 valid, 5 invalid (control not caught), 3 did not finish.**
- **0 errors in every real library across all 24 valid runs.** Per library
  about 10.2 million bytes moved under 49–93 million interrupts, with new
  random seeds in every run, single bytes and blocks, interrupt periods
  from 160 to 10 688 cycles, cache on and off, code in flash and SRAM.
- **wizard97 as shipped:** 219 737 errors, as its own header warns; with
  the PRIMASK macros its README asks for: 0.
- **Coverage:** every library found the buffer full and empty in both
  directions in most runs; the "full in main → ISR" gap from the first
  stress runs is closed (16–23 of 24 valid runs per library).

## The 8 runs that do not count
**5 invalid runs:** all block mode at the slowest interrupt rate (prescaler 4,
an interrupt every 2 560–10 688 cycles). At that rate the buffer stayed
empty in ISR → main and full in main → ISR, so the control's bugs never had
a chance to show (0 control errors). The validity rule did its job: these
runs show nothing either way and were not counted.

**3 unfinished runs:** all single bytes, fastest interrupts (160–668
cycles), instruction cache off. Re-running that setting and reading the
progress after 2 and 4 minutes showed starvation, not a hang in a library:
e.g. lwrb ISR → main had moved 30 820 bytes under 3.35 million interrupts,
with the buffer found full 3.32 million times: with the cache off its
interrupt handler takes about as long as the interrupt period, leaving the
main loop almost no CPU time. Not a library defect: a test setting with
more than 100 % interrupt load.

## Changes made after this campaign
- Rotation: no prescaler 4 in block mode (replaced by prescaler 1, every
  320–1 336 cycles) and no cache-off with prescaler 0 (replaced by
  prescaler 2).
- Firmware: a starvation cap (60 interrupts per byte) ends a starved
  library/direction instead of hanging the run; it is reported as
  "starved", never as a pass.

## Limits
One core (interrupt vs main loop), one compiler (arm-none-eabi-gcc 14.2.1,
`-O2`), one board. 0 errors over many runs makes hidden ordering bugs of
this kind unlikely for these configurations; it does not prove their
absence. GenMC found the diffstorm defects that this test cannot see
(see [`../verify/findings`](../verify/findings/)).
