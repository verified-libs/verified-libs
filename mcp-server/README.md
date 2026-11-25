# MCP server: the comparisons for AI agents

An AI agent asked to "pick a ring buffer for this Cortex-M0+ project" usually
answers from memory: the library it has seen most often. This server gives it
measurements instead: the comparisons a person gets on
<https://verified-libs.org/compare.html> (embedded ring buffers) and
<https://verified-libs.org/compare-crc.html> (CRC calculation in software),
as tools an agent can call.

It is a small [Model Context Protocol](https://modelcontextprotocol.io)
server over stdio, version 0.3.0. It reads two files of this checkout,
[`site/data/libs.json`](../site/data/libs.json) and
[`site/data/crc.json`](../site/data/crc.json) (the files the website's
comparisons are built from), and nothing else: no network, no other files,
no writing. Python 3.9 or newer (tested with 3.14), standard library only;
nothing to install.

## Use it

Clone the repository, then tell your client to start
`python3 mcp-server/server.py` (on Windows: `python`).

Claude Code:

```sh
claude mcp add verified-libs -- python3 /path/to/verified-libs/mcp-server/server.py
```

Clients with a JSON configuration (Claude Desktop, Cursor and others):

```json
{
  "mcpServers": {
    "verified-libs": {
      "command": "python3",
      "args": ["/path/to/verified-libs/mcp-server/server.py"]
    }
  }
}
```

An agent with a shell and no MCP configuration can call a tool directly:

```sh
python3 mcp-server/server.py --tools
python3 mcp-server/server.py --call compare_ring_buffers \
    '{"board": "nucleo-g0b1re", "require": ["zero_stress_errors", "permissive_license"], "weights": {"push": 5, "pop": 5}}'
python3 mcp-server/server.py --call compare_crc '{"crc": "CRC-16/IBM-3740", "board": "nucleo-g0b1re", "length": 64}'
```

The data is the one in your checkout: `git pull` to get new results. Every
answer carries the SHA-256 of the data file it was computed from.
`--data FILE` and `--crc-data FILE` take another file of the same kind.

## Tools

| Tool | What it gives |
|---|---|
| `about` | What is measured and how to read it: the tests, the boards and their records, the limits, the conflict of interest, the licence. |
| `list_ring_buffers` | The tested configurations by name, with language, licence, documented producer/consumer modes and their group in the interrupt stress test. |
| `compare_ring_buffers` | The comparison table for one board: filters for hard requirements, optional weights for a speed ranking. Each answer links to the same view on the website. The speeds are those of benchmark version 2 (each configuration in an image of its own), as on the website; `"benchmark": "1"` gives the archived first benchmark instead, and the answer says so. |
| `get_ring_buffer` | One configuration on every board and in every mode, with what the results page says about it in words: its notes and any published finding. |
| `list_findings` | The published findings: what was wrong, the versions affected, where it was fixed, and the version the comparison shows. |
| `list_crc_configurations` | The CRC configurations (one library, one CRC, one way of computing it) with library, language, CRC, class and where the table lies. No numbers. |
| `compare_crc` | The CRC comparison table for one CRC, board, message length, start and cache: per configuration the cycles for one call and per byte as `{min, max}` over eight placements of the code, the same as the page shows them, flash and RAM bytes, the link to its record, and per number `overlaps`: the rows whose range overlaps this one's, which this series does not tell apart. The reference (baseline) is the last row. In the order of the configuration list, or sorted by name, flash or RAM bytes; cycles are not sorted. Optional weights (cycles, cycles per byte, bytes) give each row a score range as on the page, order the rows by its highest end and mark a score that overlaps the one above (`score_not_told_apart_from_the_row_above`). Length 1 is in the data, not on the page, and the answer says why. |

All seven are read-only and take a fraction of a second. A full comparison
(all configurations) is about 30 000 characters; filters make it shorter.

## The same answer as the website

The project's rule is one query for people and for AIs. The server therefore
does not have a comparison of its own: [`vlquery.py`](vlquery.py) is a port of
the page's script, [`site/compare.js`](../site/compare.js), and
[`tests/test_parity.py`](tests/test_parity.py) runs that script itself (under
gjs, with a stand-in for the page) and compares it with the port for 3841
views: every board in every producer/consumer mode, plain, ranked and sorted
by every column in both directions, and 2500 views drawn with a fixed seed.
For each view the rows, their order, the text of every cell, the three
groups, the count line, the source line and the address must be the same.
The same for CRC: [`crcquery.py`](crcquery.py) is a port of
[`site/compare-crc.js`](../site/compare-crc.js), and
[`tests/test_parity_crc.py`](tests/test_parity_crc.py) compares them for
2909 views (every CRC, board, length, start and cache; every sort; every
configuration chosen, with its overlap marks; filters; seven sets of weights
on every board and CRC, with the score marks; 1500 views drawn with a fixed
seed).

What follows from that:

- **No ranking by us.** Without weights the order is alphabetical, and the
  answer says that it is not a ranking. For CRC every number is a range, and
  so is the score of the caller's weights; a score that overlaps the one
  above it is marked as not told apart. With weights the score is the page's:
  `100 × Σ(weight × fastest / value) / Σ weights`, speed only.
- **Correctness is not a weight.** Every answer is in three groups: 0 errors
  in the ISR stress test on every board tested, not tested, errors. No weight
  moves a library from one group to another.
- **The owner's library is labelled.** pxq RingBuffer_PackedState is written
  by the project owner. Every row has `written_by_project_owner`, an answer
  that shows it carries a conflict-of-interest note, and the server's
  instructions tell the agent to say so
  ([how the project handles it](https://verified-libs.org/method.html#conflict-of-interest)).
  [`tests/test_server.py`](tests/test_server.py) checks this for every tool.
- **Every number names its source**: the board, the library version and
  commit, the records, and the link to the same view on the site.

## Limits

- The server tells an agent what was measured, on which boards and versions.
  It cannot make an agent read it carefully. The reading rules are in the
  server's instructions and in `about`; the link to the site in each answer
  lets a person check what the agent says.
- Of the notes per library on the
  [results page](https://verified-libs.org/results.html#notes-per-library),
  the tools have those that say something about the version shown
  (`site/data/libs-meta.json` names them); notes about earlier versions and
  earlier campaigns are on the results page only. Findings still under the
  notice period to the maintainer are not in the data.
- The stress results of the multi-producer and multi-consumer modes are on
  the results page, not in this data (as on the comparison page).
- stdio only: the server runs on your machine, from your checkout. There is
  no hosted server.
- Tested against the protocol's specification (versions 2025-11-25,
  2025-06-18, 2025-03-26 and 2024-11-05) with our own client test, and tried
  with one real client (Claude Code), not yet with a range of them. If yours
  does not get along with it, write to contact@verified-libs.org.

## Tests

```sh
python3 -m unittest discover -s mcp-server/tests
```

`test_server.py` starts the server and talks to it as a client would.
`test_parity.py` and `test_parity_crc.py` need `gjs` to run the website's
scripts and are skipped without it. When `site/compare.js` or
`site/compare-crc.js` changes, its port changes with it, and the parity test
says where they differ.
