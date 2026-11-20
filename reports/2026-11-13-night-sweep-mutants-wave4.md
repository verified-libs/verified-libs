# Night campaign with the interrupt sweep, mutants and wave 4 (2026-11-12/13)

Stress campaign on all six boards (`lab/tools/night-all.sh`, each board with
its own copy of the repository at commit `25c64d2`), 18:45 to about 07:00 UTC
(the nRF5340 until 08:45: it was waiting in a run that was too slow, see
below). New since the campaign of 2026-11-11/12:

- the **interrupt sweep** (modes `sweep`, `sweep-block`, `sweep-dma`): one
  interrupt per call, at every delay from the start of the call, from five
  fill levels and 256 start positions; 6 of the 17 rotation entries;
- the **count check**: after every sweep the buffer is drained and the number
  of bytes compared with what went in and out (bytes lost and bytes too many
  are reported);
- four **mutants** (`mutants.c`): ring buffers with one deliberate defect
  each, to show which test modes can find which kind of defect. They do not
  decide whether a run is valid; the negative control does, as before;
- **wave 4**: NuttX circbuf, Arduino RingBufferN as shipped (ArduinoCore-API
  issue 195 says it is not interrupt-safe; reported, not counted) and
  Arduino SafeRingBufferN. 28 libraries and variants, plus the control and
  the mutants.

**No errors in any real library in any valid run, on any board**: 422 valid
runs of 427. The errors are where they are expected: the two variants their
own projects call unsafe (wizard97 as shipped, Arduino RingBufferN as
shipped), on every board and in every mode, and on the Pico 2 in SMP mode the
single-core designs whose interrupt lock does nothing against the other core
(ETL queue_spsc_isr and queue_spsc_locked, wizard97 with PRIMASK macros,
Arduino SafeRingBufferN).

## Per board

| Board | Runs | Valid | Invalid (control) | Did not finish | Too slow (time limit) | Build failed | Retries | Power cycles | Errors in real libraries |
|---|---|---|---|---|---|---|---|---|---|
| nrf5340dk | 30 | 26 | 0 | 4 | 0 | 0 | 2 | 2 | 0 |
| nucleo-g0b1re | 38 | 38 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| nucleo-g474re | 113 | 113 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| nucleo-h723zg | 62 | 62 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| sam-d20-xpro | 24 | 23 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| pico2 | 160 | 160 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

The four nRF5340 runs under 'Did not finish' were too slow, not hung (see
below); the campaign's `run.sh` could not yet tell the two apart.

## Valid runs per configuration (valid / started)

| Configuration | nrf5340dk | nucleo-g0b1re | nucleo-g474re | nucleo-h723zg | sam-d20-xpro | pico2 |
|---|---|---|---|---|---|---|
| single p0 cache on flash | 2/2 | 3/3 | 7/7 | 4/4 | 2/2 | 5/5 |
| block p0 cache on flash | 2/2 | 3/3 | 7/7 | 4/4 | 3/3 | 5/5 |
| single p2 cache on flash | 2/2 | 3/3 | 7/7 | 4/4 | 3/3 | 10/10 |
| sweep cache off flash | 2/2 | 3/3 | 7/7 | 4/4 | 2/2 | - |
| sweep cache on flash | 2/2 | 2/2 | 7/7 | 4/4 | 2/2 | 20/20 |
| block p1 cache on flash | 2/2 | 2/2 | 7/7 | 4/4 | 3/3 | 5/5 |
| single p2 cache off flash | 2/2 | 2/2 | 7/7 | 4/4 | 2/2 | - |
| sweep-block cache on flash | 2/2 | 2/2 | 7/7 | 4/4 | 2/2 | 18/18 |
| single p2 cache on sram | 2/2 | 2/2 | 7/7 | 4/4 | - | 5/5 |
| block p0 cache on sram | 2/2 | 2/2 | 7/7 | 4/4 | - | 5/5 |
| sweep-block cache off flash | **0/4** | 2/2 | 7/7 | 4/4 | 1/1 | - |
| block p1 cache on sram | 1/1 | 2/2 | 6/6 | 3/3 | - | 5/5 |
| dma p0 cache on flash | 1/1 | 2/2 | 6/6 | 3/3 | **0/1** | 9/9 |
| dma p2 cache on flash | 1/1 | 2/2 | 6/6 | 3/3 | 1/1 | 9/9 |
| dma p1 cache on sram | 1/1 | 2/2 | 6/6 | 3/3 | - | 9/9 |
| sweep-dma cache on flash | 1/1 | 2/2 | 6/6 | 3/3 | 1/1 | 9/9 |
| sweep-block cache on sram | 1/1 | 2/2 | 6/6 | 3/3 | - | 9/9 |
| dma p1 cache on flash | - | - | - | - | 1/1 | - |
| smp p0 cache on flash | - | - | - | - | - | 5/5 |
| smp-block p0 cache on flash | - | - | - | - | - | 5/5 |
| smp p2 cache on flash | - | - | - | - | - | 10/10 |
| smp-block p1 cache on flash | - | - | - | - | - | 5/5 |
| smp p2 cache on sram | - | - | - | - | - | 4/4 |
| smp-block p0 cache on sram | - | - | - | - | - | 4/4 |
| smp-block p1 cache on sram | - | - | - | - | - | 4/4 |

Bold: at least one run of that configuration was invalid or did not finish.

## Errors per library (valid runs)

| Library | nrf5340dk | nucleo-g0b1re | nucleo-g474re | nucleo-h723zg | sam-d20-xpro | pico2 |
|---|---|---|---|---|---|---|
| Arduino RingBufferN as shipped (C++) *(not claimed ISR-safe)* | 46,353 | 60,644 | 194,811 | 138,764 | 40,211 | 152,281 |
| Arduino RingBufferN as shipped (C++) [SMP, single-core design] *(not claimed ISR-safe)* | 0 | 0 | 0 | 0 | 0 | 90,294 |
| Arduino RingBufferN as shipped (C++) [sweep] *(not claimed ISR-safe)* | 471,808 | 1,550,967 | 3,980,265 | 1,715,698 | 771,130 | 3,534,429 |
| Arduino SafeRingBufferN (C++) [SMP, single-core design] | 0 | 0 | 0 | 0 | 0 | 81,765 |
| ETL queue_spsc_isr (C++) [SMP, single-core design] | 0 | 0 | 0 | 0 | 0 | 102,031 |
| ETL queue_spsc_locked (C++) [SMP, single-core design] | 0 | 0 | 0 | 0 | 0 | 90,123 |
| wizard97 + PRIMASK macros (C++) [SMP, single-core design] | 0 | 0 | 0 | 0 | 0 | 840,538 |
| wizard97 as shipped (C++) *(not claimed ISR-safe)* | 217,944 | 348,946 | 580,807 | 139,256 | 297,213 | 209,253 |
| wizard97 as shipped (C++) [SMP, single-core design] *(not claimed ISR-safe)* | 0 | 0 | 0 | 0 | 0 | 1,378,431 |
| wizard97 as shipped (C++) [sweep] *(not claimed ISR-safe)* | 474,486 | 1,457,091 | 2,821,526 | 940,085 | 812,417 | 2,868,307 |

Rows without a tag count as errors in real libraries, except 'single-core design' rows (SMP runs of interrupt-only designs).

## Interrupt sweep (valid sweep runs)

| Board | Runs | Trials | Interrupt inside the call | Library functions with instructions not interrupted |
|---|---|---|---|---|
| nrf5340dk | 8 | 222,648,964 | 77.6% | 260 |
| nucleo-g0b1re | 13 | 454,578,120 | 73.9% | 138 |
| nucleo-g474re | 40 | 1,247,266,170 | 72.7% | 304 |
| nucleo-h723zg | 22 | 524,629,714 | 73.8% | 349 |
| sam-d20-xpro | 8 | 249,306,478 | 75.9% | 125 |
| pico2 | 56 | 982,911,563 | 70.0% | 321 |

'Not interrupted' includes paths the sweep never executes (see README, Interrupt sweep); the per-run lists are in each record under sweep.functions.

## Mutants: which mode finds which defect

Valid runs in which each mutant was caught, interrupt→main / main→interrupt
direction, all boards together.

| Mutant | block | single | smp | smp-block | sweep | sweep-block |
|---|---|---|---|---|---|---|
| drain re-reads head | 81 / 0 of 84 | 39 / 0 of 89 | 16 / 19 of 19 | 18 / 18 of 18 | 55 / 0 of 55 | 70 / 0 of 70 |
| full test misses the wrap | 84 / 67 of 84 | 89 / 88 of 89 | 19 / 19 of 19 | 18 / 18 of 18 | 55 / 55 of 55 | 70 / 70 of 70 |
| shared count, no lock | 84 / 84 of 84 | 89 / 89 of 89 | 19 / 19 of 19 | 18 / 18 of 18 | 55 / 55 of 55 | 70 / 70 of 70 |
| shared count, pop without lock | 84 / 0 of 84 | 89 / 0 of 89 | 19 / 19 of 19 | 18 / 18 of 18 | 55 / 0 of 55 | 70 / 0 of 70 |

- **The sweep finds every mutant in every run** in the directions where the
  defect can show (55 of 55 and 70 of 70), where the random modes sometimes
  miss: "drain re-reads head" is caught in 39 of 89 random single-byte runs,
  "full test misses the wrap" in 67 of 84 random block runs in the
  main→interrupt direction.
- Two mutants cannot fail in the main→interrupt direction on one core (the
  defective call then runs in the interrupt and is not interrupted itself);
  on two cores (Pico 2, SMP) they are caught in both directions ("drain
  re-reads head" in 16 of 19 random single-byte SMP runs one way, in every run
  otherwise).

## Runs that did not count

- **nRF5340 DK, 4 runs: `sweep-block` with the cache off was too slow, not
  hung.** At 256 start positions it needs about 1.7 hours on this board;
  `run.sh` gave up after about 1.5 hours, the campaign power-cycled the board
  and tried once more, twice (about 6 hours of the night). Checked afterwards:
  the same build and seeds finish with 16 start positions (0 errors, control
  caught). `run.sh` now tells a slow run from a hung one (two reads of the
  result block; exit 4, no power cycle, no retry). The same configuration
  took 95 minutes on the G0B1 and 94 on the H723, close to the limit.
- **SAM D20, first campaign of the night stopped by hand**: run 0 (single
  bytes, prescaler 0, 300 000 bytes) passed the same time limit with the
  larger library list. Restarted at 20:39 UTC with a 2-hour limit; the table
  shows that campaign. That run took 83 minutes.
- **SAM D20, 1 run invalid** (`dma`, prescaler 0): the negative control was
  caught in one direction only (9 950 errors interrupt→main, 0 main→interrupt
  with 298 interrupts in the measured part: the main loop was starved). 0
  errors in the real libraries; the run is not counted.

## Time per run

`sweep-block` at 256 start positions is by far the longest entry of the
rotation: 10 to 14 minutes on the fast boards, 38 to 88 on the slow ones
(cache on, flash; up to 95 with the cache off), against 2 to 18 for a random block run. The slow boards
got 23 to 38 runs in the night, the fast ones 62 to 160. Open: fewer start
positions for `sweep-block`, on all boards alike.

## After the campaign: board check of the work since `25c64d2`

Short runs on all six boards at `76c9581` (20 000 bytes or 16 start
positions; records in `~/lab-runs/val-20261113/`): the six stress modes, the
benchmark, and the multi-producer/multi-consumer stress (MPSC and SPMC), plus
the SMP modes on the Pico 2. All 61 runs valid, no errors in real libraries in their documented mode.
Records name their source commit.

- **Rest of wave 4** (first board runs): RT-Thread rt_ringbuffer with
  interrupts off per call, Mbed CE CircularBuffer and moodycamel
  ReaderWriterQueue: 0 errors on one core on every board. RT-Thread as
  shipped, without a lock (no claim; reported, not counted): 76 errors.
  With the other side on core 1, the two interrupt-lock designs fail as
  expected (RT-Thread with interrupt lock, Mbed CE); moodycamel, which is
  documented for two threads, has 0 errors.
- **SMP sweep, first board run: it found nothing it should have found.**
  Single-byte `sweep-smp` reported 0 errors for wizard97 as shipped, Arduino
  RingBufferN as shipped and three of the four mutants. Cause: core 1 has to
  notice the start flag first, so its call always came after the first
  instructions of core 0's call, and it moved in steps of its polling loop.
  Fixed (a fixed lead on core 0, delay steps of about one cycle on core 1):
  every mutant, every single-core design and both unsafe variants are now
  caught in both directions in `sweep-smp` and `sweep-smp-block`; the
  multicore-documented libraries stay at 0 errors. This is what the mutants
  are for: the run was "valid" by the negative control alone.

## How many start positions: 16 to 256 (NUCLEO-G474RE, `sweep-block`)

Question: the sweep runs with 256 start positions take up to 1.7 h on the
slowest board; would fewer do? Measured on one board at `4e8e856`: 16, 32,
64, 128 and 256 start positions, three seed pairs each, cache on, code in
flash, `-O2` (15 runs, all valid, 0 errors in the real libraries; records in
`~/lab-runs/reps-20261113/nucleo-g474re`).

| Start positions | Time per run | Mutants, wizard97 as shipped, Arduino RingBufferN as shipped | RT-Thread rt_ringbuffer, no lock: errors isr→main in the three runs |
|---|---|---|---|
| 16 | 2.4 min | caught in 3 of 3 | 3 / 3 / 6 |
| 32 | 2.4 min | caught in 3 of 3 | 0 / 0 / 0 |
| 64 | 3.1 min | caught in 3 of 3 | 6 / 0 / 0 |
| 128 | 5.9 min | caught in 3 of 3 | 39 / 42 / 63 |
| 256 | 11.2 min | caught in 3 of 3 | 84 / 75 / 78 |

- The mutants and the two unsafe variants do not distinguish the settings:
  their error counts grow linearly with the number of start positions, and
  the weakest ("full test misses the wrap") still has 85 to 101 errors per
  direction at 16. "Pop without lock" and "drain re-reads head" are caught
  isr→main only at every setting, as in the campaign.
- The rarest real finding does: RT-Thread without a lock, isr→main, is
  missed in all three runs at 32 and in two of three at 64, and found in
  every run from 128 up. main→isr was found in all 15 runs (2 to 4 errors at
  16, 42 to 82 at 256). From 64 to 128 the isr→main count grows far more
  than twofold; why has not been examined.
- The times at 16 and 32 are bounded below by `run.sh`'s fixed first wait of
  120 s.

Decision (owner, 2026-11-13): 256 start positions stay, the same on every
board; the default time limit of `run.sh` goes from 300 to 600 polls (at
least 2.5 h), so the slowest configuration (about 1.7 h) fits.
