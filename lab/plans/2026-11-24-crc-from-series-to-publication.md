# CRC: from the first series to a page

2026-11-24. The plan for the CRC kind
([`2026-11-24-crc-kind.md`](2026-11-24-crc-kind.md)) ends with the first
board series, which is running (commit 6301058, six boards, 20
configurations, two passes; `kinds/crc/README.md`, step 9). This plan is
what comes between the last run file and a published page. It is written
while the series runs and can be worked through without the owner; what
needs the owner's word is collected at the end and nothing of it is done
before.

Done means the same as for the ring buffers
([`2026-11-23-ring-buffers-finish.md`](2026-11-23-ring-buffers-finish.md)):
a number on the page can stand without us. A reader can see which code it
came from, build that code again, and measure one configuration again on
a board of their own.

Nothing is published, nobody is written to and no file of benchmark
version 2 is changed by this plan. The work is on branches from
`kind-crc`; a merge into `main` is the owner's.

## What the series leaves

Per board a directory of run files: 160 images (20 configurations at
eight placements), each run twice, 320 run files. A run file holds, for
the configuration and for the reference of its CRC (the baseline, in the
same image), 24 scenarios: lengths 1, 4, 16, 64, 256 and 1024 bytes, the
buffer at an 8-byte boundary and one byte after it, the cache off and on;
256 calls each, and a count of calls whose result was not the
reference's. From them: 20 records per board, 120 in all
(`records/crc/<board>/<adapter>.json`, schema `crc-bench/1`).

The files a record is held against (`CRC_TEST_SOURCES` in
`lab/tools/public-export.py`) are those of commit 6301058. A change to
one of them after the series stops the export of every CRC record, as the
kind has no ledger of rebuilds yet (step 5). Until step 5 is done, no
file under `kinds/crc` is changed but `README.md` and `proof/`, which are
not test sources.

## Steps

1. **The series is read before a record is made.** Per board, from the
   run files and logs, into a table of the report:
   - the runner's exit, the number of runs, runs without a file, flash
     writes (counted before the series: 26 for the six boards);
   - calls that disagreed with the reference (expected: none, in the
     configuration and in the baseline), runs marked invalid;
   - attempts and waits per run, so that a look at an unfinished run
     shows (on the Pico 2 the reason is known, README step 9);
   - the empty call per board: one value in every run;
   - pass 1 against pass 2: how many of the means agree within 1 % or
     0.05 cycles, and the largest difference, named.
   The record writer already refuses a configuration whose runs disagree
   on what they ran; it does not compare the means of the two passes, so
   that is done here, by a small program outside `kinds/crc`. A
   difference between the passes is written into the report as it is. A
   bundle is run again only if a run is missing or invalid, and the cost
   is counted first: no flash write if the bundle is the board's last
   one, else one write.

2. **Records, each one rebuilt.** `crcrecords.py --out records/crc` on the
   six directories; `crcverify.sh` on all 120 records (the record's commit
   builds its eight images again: bytes in flash, address, fixed part,
   boot stub, toolchain, layout). Expected: 120 of 120 `MATCH`. The time
   it takes is written down, for the instructions of step 6.
   `public-export.py --check` must say that the 120 records are of test
   sources that are those of HEAD. Committed on a branch from `kind-crc`.

3. **The numbers are checked before a sentence is written about them.**
   Each check ends in a line of the report, also where nothing is found:
   - *The noise floor.* The baseline is measured in every image. How far
     its means differ between the images of one board, and between the
     eight placements, is the size of a difference that says nothing
     about a library.
   - *Cost per byte.* (mean at 1024 bytes − mean at 256 bytes) / 768,
     per configuration and board, and what is left at length 0 by the
     same line. A value that does not fit its class (bitwise, table of
     16, table of 256, slicing by 4, braided words) is looked at in the
     image's disassembly before it is shown.
   - *The same class from several libraries.* For every class that two or
     more libraries offer (README step 2): are their loops the same
     instructions, and are their means the same within the noise floor?
     This answers the question of README step 4, whether a result is one
     per library or one per algorithm, with measurements.
   - *Aligned and one byte after.* Where the two offsets differ by more
     than the noise floor, and for which class.
   - *Cache off and on*, per board, and what "cache on" covers for a
     table read from flash
     ([`reports/2026-11-25-crc-first-series.md`](../../reports/2026-11-25-crc-first-series.md),
     "What "cache on" covers for a table read from flash"): the place where the open question
     of the table copied to RAM is answered or stays open.
   - *The table in RAM against the table in flash*, for the classes where
     the set has both (libcrc and CRC++ against the others).
   What cannot be explained is stated as not explained. A possible defect
   in a library goes into `lab/drafts` only and to the owner.

4. **What the page shows: a proposal on the numbers.** Written after
   step 3, with one example table filled in, for the owner to choose
   from. The starting point:
   - per CRC and board, one row per configuration: its class, where the
     table lies, bytes of flash and RAM, cycles for a short message
     (16 bytes) and per byte for a long one (from 256 and 1024 bytes),
     cache on, and the same as a factor of the baseline;
   - the convention of version 2's tables for which run is shown (one
     named placement, first pass), with the range over the eight
     placements beside it;
   - everything else (the other lengths, the offset, the cache off, both
     passes) stays in the records, with a link per row;
   - no ranking and no winner; what the numbers say is written as text
     under the tables, each sentence with the rows it rests on.
   The table is written by a program from the records
   (as `site/results_tables.py` for the ring buffers), under `site/`, so
   that it is not a test source and the page cannot drift from the
   records.

5. **The export rule for the kind, finished.** Two things the first
   publication needs, both changes to how the export decides and
   therefore the owner's (below):
   - *A ledger of rebuilds for CRC records*, as version 2 has
     (`lab/tools/image-ledger.py`, `records/rebuilt.json`): a record of
     another commit is exported if this tree builds its eight images
     byte for byte, and a change to the host side (runner, record writer)
     is taken only with a recorded fix (`records/host-fixes.json`).
     Without it, the first correction of `repeat.sh`, `crccompare.py` or
     the runner after the series takes every CRC record off the page
     until all six boards are run again.
   - *Its test*, in `lab/tools/test-public-export.sh`: a changed adapter
     stops its records and no others; a change that leaves every image
     the same stops none once the ledger is made; a change to the runner
     stops all without a recorded fix.
   Tried on the real records with a made-up change, without a board.

6. **The texts.** Each is facts with sources, and each is read against
   the records by the review before the owner sees it:
   - `kinds/crc/README.md`: a step for the series (what ran, when, the
     table of step 1) and the status line at its top;
   - a report of the series and its numbers (steps 1 and 3);
   - the results page of the kind (step 4) and a method page for it: what
     is measured, what the baseline is, what "the same as the reference"
     was checked for and how (host test, exhaustive runs, CBMC; and for
     which configuration a proof is by argument and not by machine), what
     is not measured (the boards' CRC hardware, slicing by 16, the table
     copied to RAM if that is still open);
   - `site/content/reproduce.md`: `kinds/crc/repeat.sh` and
     `crcverify.sh`, with the times of step 2;
   - `records/README.md`: the CRC records and their schema;
   - the front page, `README.md`, `PROJECT.md` and `RESULTS.md`: one line
     each that a second kind exists, with the link;
   - the MCP server's README: that its data are the ring buffers'
     (CRC is not in `site/data/libs.json` at the first publication).
   The site is built from an export (`site/build.py`,
   `site/check_links.py`), not from the private tree.

7. **Repetition from outside, tried.** An export into an empty directory;
   from that tree alone, following only the published instructions:
   `crcverify.sh` on every record, and `kinds/crc/repeat.sh --level quick`
   on the Pico 2, whose only bundle is on the board after the series (no
   flash write; three configurations, 48 runs, about 35 minutes).
   Expected: the same images and every mean within 1 %. Whatever the
   instructions lack is added; a correction to a test source goes
   through the ledger of step 5.
   Done 2026-11-25 (series report, "Repetition from outside"): 120 of 120
   `MATCH`; the first quick run made no records (the exported tree has no
   commit), `kinds/crc/repeat.sh` was corrected (it is not a test source)
   and the second run gave "same as ours". The check that this cannot come
   back unseen, without a board:
   [`lab/tools/test-crc-repeat-export.sh`](../tools/test-crc-repeat-export.sh)
   (about 30 s).

8. **A dry run of the whole publication**, after the owner's yes to the
   merge (`publish.sh --dry-run` wants a commit on `main`): the exported
   tree and the built pages in a directory, with a list of what differs
   from what is public today, and the search for embargoed words in all
   of it.

Order: 1 and 2 when the series ends; 3 before 4 and 6; 5 can be made
while the series runs, on a branch of its own, as it changes no file
under `kinds/crc`; 7 and 8 last. Each step is committed and pushed on its
own.

Flash writes expected: none beyond the series. Step 1 may cost one per
bundle that has to run again; step 7 none.

## Not in this plan

- The table copied to RAM (20 more flash writes, estimated in the
  proposal for the first series): decided after step 3, per board.
- More configurations (slicing by 16, the boards' CRC hardware, the
  libraries that need the Arduino core).
- CRC on the interactive comparison page and in the MCP data: after the
  first publication, by the section "Later" below.
- The next kind (fixed-block pools): its two checks on the host
  (`reports/2026-11-24-next-kind.md`, "Review and decision") are made
  apart from this plan.

## Later: CRC on the comparison page and in the MCP data

Not started before the static pages are public and the kind's method is
frozen by a tag, so that the data's shape follows pages that have been
read from outside.

1. **The data.** A file of its own, `site/data/crc.json`, written from
   `records/crc` by a program under `site/`: per board and configuration
   the numbers of the results page and the link to the record.
   `site/data/libs.json` keeps its shape, so that nothing that reads it
   today breaks.
2. **The comparison page.** A choice of kind; for CRC: the CRC, the
   board, the message length and the cache as choices, one row per
   configuration, the baseline as a row. Neutral defaults and no
   ranking, as for the ring buffers.
3. **The MCP server**, a new version: the kind as an argument of the
   existing queries or queries of its own (chosen when the data file
   exists), its README, and the test that the server and the page give
   the same numbers (`mcp-server/tests/test_parity.py`) for the new kind.
4. **Checks**: the site built from an export, every link, the tests of
   the server; a dry run of the publication for the owner.

For the owner then: the go for that publication.

## For the owner, when the steps are done

1. **What is shown first.** Decided 2026-11-24: static pages first (the
   results page, the method page, the records and the repeat), so that
   the kind can go live; CRC on the comparison page and in the MCP data
   follows by the section "Later" below.
2. **The ledger for CRC records** (step 5). Decided 2026-11-24: yes, the
   same-image rule of the ring buffers (DECISIONS 2026-11-22 and
   2026-11-23) applied to the second kind.
3. **`kind-crc` into `main`**, with the records, after the review.
4. **The publication** (`publish.sh --go`), after the dry run of step 8.
5. **The table copied to RAM**: a second series of 20 flash writes, or
   only the boards where step 3 shows that it matters, or not now.
   Decided 2026-11-25: after the first publication (below, item 7).
6. **What was left out by a note in `lab/drafts`**: whether anyone is
   told, and how.
7. **What the page shows** (step 4,
   [`2026-11-25-crc-page-proposal.md`](2026-11-25-crc-page-proposal.md)).
   Decided 2026-11-25, all five as the review recommended:
   - variant 1: the range over the eight placements, first pass, no placement picked;
   - cache off as a second table per board and CRC, with ranges;
   - the H723 as measured, with a sentence on its 7 wait states above its cache-off tables;
     the wait states a user would set: next version of the method;
   - the series with the tables in RAM after the first publication;
   - the median beside the mean: next version of the method.
