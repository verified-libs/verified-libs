# Proposal: keep the records of images that did not change (2026-11-22)

A proposal for the owner to accept, change or turn down. Nothing in the
rules or the tools has changed. The owner's question, after the re-run for
lwrb v3.4.0 was started: when one library changes, can we measure only
what changed?

## The rule today

A record may be shown only if the test sources at its commit (`firmware`,
`lab/boards.conf` and two lab scripts) are byte for byte those of the
published tree (DECISIONS 2026-11-16; `lab/tools/public-export.py` refuses
the export otherwise). The reason holds: the public repository has no
history, so a reader can check a record only against the tree they have.

A library's pin and its adapter lie under `firmware`. So one new version
of one library makes every record of every library unshowable, and
everything is measured again: 184 flash writes and 13 hours on the six
boards for lwrb v3.4.0
([report](../../reports/2026-11-22-lwrb-v3.4.0-rerun.md)).

## What that run showed

- **Almost nothing that ran had changed.** By the checksums in the
  records: of the 24 or 25 benchmark images per board, 8 changed (the C
  and C++ single-producer set at its eight placements); of the ISR test's
  40 library images per code location, 1 changed (lwrb's); of the
  two-interrupt test's images, none.
- **The same image gave the same numbers.** 787 of the 791 speed numbers
  from unchanged benchmark images are identical to the last digit, and
  the other four are within 0.03 %. The stress tests gave the same run
  counts, the same valid runs and no errors, with new seeds.
- **A changed image moves every number in it.** The C and C++
  single-producer libraries share one benchmark image. lwrb's code grew
  by about 120 bytes, and 29 of the 666 means of the other libraries in
  that image left the placement range shown before (26 of them on the
  nRF5340, by up to 5 %; one block number on the Pico 2 by 57 %).

So the unit that decides whether a number still stands is the image, not
the library and not the commit.

## The proposed rule

A record may be shown if both hold:

1. **The image is the same.** The published tree builds, byte for byte,
   the image the record was measured from. The records already carry the
   checksums (`fw_sha256` for a benchmark, `images.libs[].sha256` for each
   library of a stress run), and the build is reproducible (the unchanged
   images of this run were built at two commits and compared).
2. **The way it is run and judged is the same.** The host-side test
   sources (the run and campaign scripts, the judges, `lab/boards.conf`)
   at the record's commit are those of the published tree, as today.

For the reader this is a plainer promise than today's: "the tree you have
builds exactly the image this was measured from, and runs it the same
way". `verify-build.sh` and `repeat.sh` would check the checksum instead
of looking the commit up in a list.

What follows from it, with no further rule needed:

| What changes | What is measured again |
|---|---|
| A C or C++ single-producer library | The whole shared benchmark set (8 images per board), that library's code size, that library's ISR stress image |
| A Rust library | The Rust benchmark set, that library's stress image |
| A multi-producer library | The multi-producer benchmark set, that library's two-interrupt and ISR images |
| A test's firmware, a run script, a judge | Everything that test produces |
| The compiler or another tool that changes the images | Everything whose image changed |

Each row of the comparison page would carry the date and commit of its
own records, because they would no longer be the same for every library.

## What it would have cost for lwrb v3.4.0

| Board | Flash writes, full re-run | Under the proposal |
|---|---|---|
| nRF5340 DK | 28 | 9 |
| NUCLEO-G0B1RE | 27 | 9 |
| NUCLEO-G474RE | 29 | 11 |
| NUCLEO-H723ZG | 28 | 10 |
| SAM D20 Xplained Pro | 41 | 9 |
| Pico 2 | 31 | 13 |
| All | 184 | about 61 |

Eight benchmark images per board, plus the ISR bundles that hold lwrb's
image (counted as this run switched between them; on the SAM D20 lwrb is
in one of the two bundles, so the board is written once instead of 16
times). The time falls more than the writes: the eight images take
roughly 10 to 35 minutes per board (a third of this run's benchmark
step), and the stress run of one library is a fraction of the five hours
all of them take.

## What it does not solve

- **The shared benchmark image.** A change in one C or C++ library still
  moves the others' numbers, and still costs eight writes per board. One
  benchmark image per library, selected at run time from a bundle as the
  stress tests do it, would end both. That is a change to the benchmark
  firmware and so to the frozen method: a step for the version after 1,
  with a full re-run when it comes.
- **What a checksum does not see.** The boards, the probes and their
  firmware, the room. The identical numbers two days apart say the cycle
  counts do not depend on them, but that is one run. A full re-run at
  every method version, or at least twice a year, would keep that
  checked.
- **Stress runs on different nights.** A library stressed alone has other
  seeds and another date than its neighbours in the table. The seeds
  differ between any two runs already; the date would be shown.

## What would change in the tools (after a yes)

- `lab/tools/public-export.py`: the check above in place of "the record's
  commit has the tree's test sources", and the split of the test sources
  into what goes into images and what runs and judges them.
- `site/collect_records.py`, `site/gen_libdata.py`: records from more
  than one run, the newest per image; date and commit per library in
  `libs.json`, shown on the page and by the MCP server.
- `lab/tools/publication-rerun.sh` and the two campaign scripts: a way to
  run only the sets and libraries whose images changed.
- `verify-build.sh`, `repeat.sh`: rebuild and compare checksums.
- DECISIONS: a new entry that replaces the rule of 2026-11-16.

No test changes: what is measured, how, and how it is judged stay as
frozen.

## For the owner to decide

1. **The rule itself**: yes, no, or with changes.
2. **How long a changed library is stressed alone.** Proposed: the same
   rotation entries the last full campaign reached on that board, so that
   its row rests on the same runs as its neighbours' (not five hours
   alone, which would give it many more runs than the others).
3. **How often everything runs again regardless.** Proposed: at every
   method version, and otherwise twice a year.
4. **One benchmark image per library** on the list for the version
   after 1: yes or no.
5. **Collecting updates.** Proposed: new library versions are collected
   and run together, at most once a month, unless a maintainer asks for a
   test of a release.
