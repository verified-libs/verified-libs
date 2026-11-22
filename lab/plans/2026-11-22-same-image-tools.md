# Tools for the same-image rule: plan and state (2026-11-22)

The rule was decided on 2026-11-22 ([DECISIONS](../../DECISIONS.md),
[proposal](2026-11-22-same-image-rule.md)): a record may be shown if the
published tree builds, byte for byte, the image it was measured from, and
runs and judges it the same way. This is the plan for the tools. No test
changes. Every record shown today is made at the tree's sources, so it
meets the earlier, stricter rule too; the first mixed state comes with the
next library update, after steps 3 to 5.

## Step 1: rebuild a record from the tree at hand (done)

`VL_TREE=1 lab/tools/verify-build.sh RECORD.json ...` builds from the tree
at hand (what is committed at HEAD, or an exported tree as it is) with the
record's settings, whatever commit the record names, and compares the
checksum. For a stress record that differs it names the libraries whose
images differ.

Tried on four nRF5340 records of the run of 2026-11-19 (made at
`8d8880f4bf78`, before lwrb v3.4.0) against the tree of today:

| Record | Result |
|---|---|
| Benchmark, C and C++ single-producer set | differs (lwrb is in this image) |
| Benchmark, multi-producer set | match |
| Benchmark, Rust set | match |
| ISR stress, one image per library | differs: library 1 (lwrb) only; the other 39 match |

That is what the rule predicts. Four records took 70 seconds, so the 209
records with a checksum that are published today take about an hour, with
no board.

## Step 2: the export check (done, except the last point)

Tried in a copy of the repository with the four old records of step 1
added: the export took the two whose image the tree builds and refused the
other two, naming the library. A changed document under `firmware` changed
nothing; a changed adapter made the ledger stale, and a changed campaign
script refused every record. As planned, what has no image checksum of its
own (the code size records and the campaign summaries) is refused as soon
as the sources differ; the summaries wait for step 3.

- **Two kinds of test source.** Host side (run and judged with): every
  file under `firmware` that is not compiled or linked into an image (the
  run and campaign scripts, the judges, the serial host), `lab/boards.conf`
  and the two lab scripts. Image side: the C, C++, Rust and linker sources,
  makefiles and pins. Documentation under `firmware` is neither. The host
  side is kept as one set for all tests at first, which is stricter than
  the decision asks ("everything that test produces").
- **A ledger of rebuilds**, `records/rebuilt.json`, written by a new
  `lab/tools/image-ledger.sh`: for every published record whose commit does
  not have the tree's image sources, the result of step 1 at this tree
  (keyed by the checksum of the image sources, so a ledger of another tree
  is not taken).
- **`public-export.py`** accepts a record if its commit has the tree's
  sources (as today), or if the host side is the same and the ledger says
  the tree builds its image; for a stress record, for the libraries the
  page takes from it. Records without a checksum (code size, which needs no
  board) keep today's rule and are made again at every change.
- `verify-build.sh` and `repeat.sh` then build from the tree at hand by
  default, and the lists `EXPORTED_FROM` / `SAME_SOURCES` are no longer
  what a reader's check rests on.

## Step 3: the page data

`site/gen_libdata.py` and `site/collect_records.py`: per board and set the
newest record whose image the tree builds; per library the stress runs of
the campaigns that ran its current image; date and commit per row in
`libs.json`, on the comparison page and in the MCP server. The campaign
summaries (`records/campaign`) are put together from more than one
campaign by the site tools, not by a change to the test's own summary
script.

## Step 4: running only what changed

- Which images changed: the ledger of step 2 says it before any board is
  touched.
- Benchmark: `publication-rerun.sh` already takes the sets to run
  (`SETS=spsc`), and the code size takes no board.
- Two-interrupt stress: `run.sh` takes a list of libraries; whether the
  campaign script passes it on is to be checked.
- **ISR stress.** `overnight.sh` refuses a list of libraries
  ("campaigns run all libraries"), on purpose. Two ways:
  1. a wrapper outside the test sources that walks the campaign's rotation
     and calls `run.sh` for one library. No record is touched, but the
     rotation then exists twice and the two can drift apart unseen;
  2. let `overnight.sh` take the list. That changes a run script, so by the
     rule the ISR stress records are made once more by a full campaign.
     The first library update after today needs a full ISR campaign anyway
     as long as there is no way to run one library, so made together with
     that update the change costs no extra flash writes.
  Decided by the owner on 2026-11-22: the second, made together with the
  first library update ([DECISIONS](../../DECISIONS.md)).

## Step 5: the texts

`records/README.md`, the reproduce and method pages, `repeat.sh`'s own
text: say the new rule where they state the old one. Published with the
tools, not before.
