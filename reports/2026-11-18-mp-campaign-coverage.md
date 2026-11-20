# MP stress campaign with coverage, all six boards (night 2026-11-17/18)

13 hours per board, rb-mp-stress at commit 515fc3e, one library per reset,
1,000,000 values per library and run. Prescaler 1-4 in rotation; at
prescaler 3 and 4 half the runs use aimed interrupts and every run records
where its interrupts landed (method:
[2026-11-17-mp-coverage-prototype.md](2026-11-17-mp-coverage-prototype.md)).
The first campaign of this kind, and the last long one before version 1
(DECISIONS 2026-11-18).

## Result

**No errors in any library in its documented mode, in any run on any
board.** A run is valid when the control (an SPSC buffer used by two
producers or two consumers) was caught in it.

| Board | Runs | Valid | Control caught, random interrupts | Control caught, aimed |
|---|---|---|---|---|
| nRF5340 DK | 64 | 53 | 37 of 48 | 16 of 16 |
| NUCLEO-G0B1RE | 116 | 105 | 77 of 88 | 28 of 28 |
| NUCLEO-G474RE | 218 | 206 | 152 of 164 | 54 of 54 |
| NUCLEO-H723ZG | 143 | 143 | 107 of 107 | 36 of 36 |
| SAM D20 Xplained Pro | 74 | 66 | 48 of 56 | 18 of 18 |
| Pico 2 | 235 | 177 | 119 of 177 | 58 of 58 |
| All | 850 | 750 | 540 of 640 | 210 of 210 |

No run failed (probe, serial port or build). Every run where the control
was not caught had random interrupts at prescaler 2, 3 or 4. On the Pico 2
no random run at prescaler 3 or 4 caught it (0 of 58); at prescaler 1 and
2 all 119 did.

## Coverage (prescaler 3 and 4, valid runs, the control left out)

Per library and mode: the share of interrupts that landed in the library's
code, the median number of interrupts per instruction boundary where one
can land, and how many of those boundaries were interrupted at least 10
times in the weakest run. Range over the libraries:

| Board | Interrupts | In library code | Median per boundary | Boundaries >= 10x, weakest run | Rows with every boundary >= 10x |
|---|---|---|---|---|---|
| nRF5340 DK | random | 2.0-8.7 % | 8-3,014 | 47-88 % | 0 of 13 |
| | aimed | 8.7-32.3 % | 2,880-9,790 | 63-100 % | 1 of 13 |
| NUCLEO-G0B1RE | random | 6.2-14.5 % | 33-2,744 | 55-89 % | 0 of 11 |
| | aimed | 14.3-42.9 % | 704-15,730 | 84-100 % | 8 of 11 |
| NUCLEO-G474RE | random | 2.3-11.1 % | 83-3,383 | 40-80 % | 0 of 13 |
| | aimed | 4.2-27.8 % | 2,188-18,481 | 68-100 % | 4 of 13 |
| NUCLEO-H723ZG | random | 8.8-20.0 % | 8-518 | 42-75 % | 0 of 13 |
| | aimed | 9.0-26.1 % | 52-5,590 | 50-100 % | 1 of 13 |
| SAM D20 Xplained Pro | random | 9.1-21.0 % | 96-6,530 | 50-91 % | 0 of 11 |
| | aimed | 18.2-53.6 % | 433-12,289 | 85-100 % | 8 of 11 |
| Pico 2 | random | no valid run | | | |
| | aimed | 1.9-24.5 % | 1,712-7,970 | 61-100 % | 2 of 13 |

Per-library tables: `report.md` in each campaign directory
(`~/lab-runs/mp-campaign-20261117T1736*Z/` on lib-lab1), boundary lists in
`coverage.txt`.

## Reading

- The aimed runs are the ones that test: they caught the control in every
  run on every board. With them the lowest median per boundary is 52
  (heapless on the H723); on the other boards it is 433 or more. With
  random interrupts no library on any board had all its
  boundaries interrupted 10 times in every run.
- Random runs at the slow rates add little. On the Pico 2 they are never
  valid, so half of its prescaler 3/4 time (58 runs of about 3 minutes)
  gave nothing.
- The aim window is one value (160 cycles) for every library and board. The
  H723 gains least from aiming (not examined why), and the long lock-free
  operations (heapless,
  reserve/commit) keep boundaries below 10 on most boards. A window per
  library would close that; it is a method change and waits until after
  version 1.
- Boundaries in blocks that were never interrupted (heapless: about 90
  boundaries on the Cortex-M4/M33/M7 boards, 41 on the Cortex-M0+ ones) are paths the test does not take, likely
  retries after a real collision. An interrupt test on one core does not
  reach them; model checking does.

## For the publication re-run

No change is made here. A proposal for the owner, since it changes what a
campaign covers: at prescaler 3 and 4 run aimed interrupts only (random
runs there are often invalid and never on the Pico 2), and keep random
interrupts at prescaler 1 and 2, where the control is caught reliably.
