# CRC on the comparison page and in the MCP server: a proposal (part B)

2026-11-25. The section "Later" of
[`2026-11-24-crc-from-series-to-publication.md`](2026-11-24-crc-from-series-to-publication.md),
part B, for review before it is built. Part A made the data:
[`site/data/crc.json`](../../site/data/crc.json), written from
`records/crc` by [`site/crc_data.py`](../../site/crc_data.py) (ranges over
the eight placements, first pass; every length and both offsets),
checked against the results page by `site/test_crc_data.py`.

## The page

**A second page, `compare-crc.html`**, not a choice of kind on
`compare.html`. The two kinds share no column: ring buffers have
producers and consumers, stress results and weights; CRC has a CRC, a
message length, an offset and the cache. One page with a choice would put
two different forms and tables behind one switch in `compare.js`, and
every change for CRC would touch the code the ring-buffer page and its
parity test run. With two pages `compare.html`, `compare.js` and
`site/data/libs.json` do not change. The menu's "Compare" stays one entry,
"on" for both pages; each page links to the other at its top. Its own
script `site/compare-crc.js`, its data inline as for the ring buffers.

**Choices**, each a select, kept in the address so a view can be linked:
CRC (3), board (6), message length (4, 16, 64, 256, 1024 bytes), offset
(an 8-byte boundary, or one byte after), cache (on, off). Defaults:
CRC-32/ISO-HDLC, the first board in the order of the results page, 16
bytes, offset 0, cache on: the results page's first table. The 1-byte
length is left out, for the reason the results page gives (at offset 0
with the cache on it is the first scenario after the cache is switched
on); it stays in the data and the MCP server, with that note.

**Columns**: configuration (linked to its record), library, language,
class, table (where it lies), flash bytes, RAM bytes, cycles for one call
at the chosen length, cycles per byte (from 256 and 1024 bytes, at the
chosen offset). The board's sentence of the results page goes above the
table where there is one (the NUCLEO-H723ZG with the cache off).

**The baseline** (the bitwise reference of the chosen CRC, timed in the
same images) as the last row, set apart and labelled "reference (baseline),
not a library".

**A range in a cell**: `257–258` (min–max over the eight placements),
one number where all eight agree, as on the results page. A line under
the table: "A range is min–max over eight placements of the code. Two rows
differ only where their ranges do not overlap."

**No sorting by cycles.** The rows stay in the order of
`kinds/crc/configs.txt`. A sort by a range has no order that is true where
ranges overlap, and marking overlap in a sorted list still reads as a
ranking. Sorting is offered only by the exact columns: name, flash bytes,
RAM bytes. Filters, no weights: language, class, table in flash or RAM.

## The MCP server

**Version 0.3.0.** Tools of its own for the kind, so that the existing
tools and their arguments and answers do not change:
`list_crc_configurations` (the configurations, with library, language,
CRC, class, table) and `compare_crc` (arguments as the page's choices; the
same rows in the same order as `compare-crc.html`, the baseline last). The
server reads `site/data/crc.json` beside `libs.json`; `about` names both
kinds.

**A range for an agent**: `{"min": 257.0, "max": 258.0}` per number, plus
`"overlaps": [names]` per row: the rows whose range of the chosen column
overlaps this one's. The agent then does not have to work out what may be
compared.

**Texts an agent reads**, in every `compare_crc` answer: a mean includes
the first call of 256; a range is over eight placements of the code; rows
whose ranges overlap are not different; the order is the configuration
list, not a ranking; the NUCLEO-H723ZG's cache-off numbers carry 7 flash
wait states. The 1-byte length is given with its note.

**Parity**: a Python port of `compare-crc.js` in the server, tested against
the page's script under gjs as `test_parity.py` does for the ring buffers:
every CRC, board, length, offset, cache and sort, with filters; the same
rows, cells and address.

## What stays out

The second pass, and the minimum, maximum and first call of each scenario:
in the records (linked per row). The comparison of the two kinds with each
other. Weights and a score.

## Checks for part B

The site built from an export (`site/build.py`, `site/check_links.py`),
the MCP tests (both kinds), `site/test_crc_data.py`,
`public-export.py --check`.

## Weights (added 2026-11-25)

The owner asked on 2026-11-25 for weight sliders as on the ring buffers'
comparison. They are kept within the ranges rule (DECISIONS 2026-11-25): the
score is a range (the smallest lower end among the rows shown over the
row's upper ends for its lowest score, over its lower ends for its highest;
bytes, flash and RAM together, are exact), the rows are ordered by the
highest end, and a score that overlaps the one above it is marked
"overlaps above": not told apart by this series. All weights 0: list
order, no score column, as before.
