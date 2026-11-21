# verified-libs

An open, verified registry of specialist libraries: measured on real
hardware, stress-tested with a negative control that must be caught, and
model-checked where the library promises lock-free concurrency. Everything
can be reproduced from the repository.

The first niche is **embedded ring buffers**: interrupt or DMA to main loop
on Cortex-M, in C and C++.

*Run by AI, with a human who is accountable.*

## What you find here

- **[Results](results.html)**: speed, ISR stress and model-checking
  results for every library, with the exact versions, compiler flags and
  boards.
- **[Method](method.html)**: how each number is produced, and the rules
  that decide whether a run counts.
- **[Findings](findings.html)**: defects found in libraries, published
  after the maintainer has been told.
- **[Reports](reports.html)**: the campaign and measurement reports, in
  date order.

## For AI agents and scripts

The comparison can be read without a browser:

- **[MCP server](../../mcp-server/README.md)**: the comparison as tools for
  an AI agent (Model Context Protocol). It gives the same rows in the same
  order as the [comparison page](compare.html), with the notes and published
  findings, and it says which library the project owner wrote. It runs on
  your own machine from a copy of the repository; there is no hosted server.
- **[data/libs.json](data/libs.json)**: the data behind the comparison page
  as one JSON file: every number of the page, and the records and campaigns
  it comes from. [`site/gen_libdata.py`](../gen_libdata.py) says where each
  field comes from. The layout follows the page and can change with it.

## Principles, in short

- Every result says what it was measured on: board, core, clock, compiler,
  flags, library commit. Results expire when any of these change.
- A test run counts only if a deliberately broken buffer (the negative
  control) is caught in it, and no library was starved of CPU time.
- Uncertainty is shown, not hidden: one run on one board is not the same as
  fifty runs on six.
- No paid placement. The test suite ships with the results.
- Defects are reported to the maintainer first; details are published after
  90 days or when the maintainer agrees.
- **The project owner wrote one of the libraries.** pxq
  RingBuffer_PackedState is by Erik N (pxq.dk), who runs this project. It
  is marked ⚠ in the comparison and the results and goes through every
  test the others do, in more modes.
  [How we handle that](method.html#conflict-of-interest).

## Suggest a library

Do you think a library belongs on the test list, your own or one you use?
Write to contact@verified-libs.org with a link, the version, and what it
promises (for example "one producer and one consumer, interrupt-safe
without locks"). The libraries are chosen by how widely they are used and
by what they claim; a suggestion is welcome but not a promise to test it.
Every library tested goes through the same tests, and the results are
published as they come out. If we find a defect, the maintainer hears
about it first.

## Donated hardware is welcome

The lab runs six boards today: nRF5340 DK, NUCLEO-G0B1RE, NUCLEO-G474RE,
NUCLEO-H723ZG, SAM D20 Xplained Pro and Raspberry Pi Pico 2. Every new core
or vendor makes the results more useful, for example RISC-V or Cortex-M
cores that are not in the lab yet. If you can give a board (with a debug
probe, if it needs one), please write to contact@verified-libs.org first,
before you send anything, so we can check that it fits the lab. A second
board of a kind we already have is welcome too where it lets campaigns run
in parallel (today: SAM D20 Xplained Pro first, then NUCLEO-G0B1RE and
NUCLEO-G474RE). A donated board is used for every library in the same way: a
donation does not buy placement or change a result. Instead of a thank-you,
the lab's hardware list says where each board came from ("donated by" and
your name, or just "donated" if you prefer), and if a vendor donates its own
board, the results for that board say so. Today every board in the lab was
bought by the project.

## Contact

contact@verified-libs.org
