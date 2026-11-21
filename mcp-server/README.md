# MCP server: the ring buffer comparison for AI agents

An AI agent asked to "pick a ring buffer for this Cortex-M0+ project" usually
answers from memory: the library it has seen most often. This server gives it
measurements instead: the comparison a person gets on
<https://verified-libs.org/compare.html>, as tools an agent can call.

It is a small [Model Context Protocol](https://modelcontextprotocol.io)
server over stdio. It reads one file, [`site/data/libs.json`](../site/data/libs.json)
of this checkout (the file the website's comparison is built from), and
nothing else: no network, no other files, no writing. Python 3.9 or newer
(tested with 3.14), standard library only; nothing to install.

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
```

The data is the one in your checkout: `git pull` to get new results. Every
answer carries the SHA-256 of the data file it was computed from.

## Tools

| Tool | What it gives |
|---|---|
| `about` | What is measured and how to read it: the tests, the boards and their records, the limits, the conflict of interest, the licence. |
| `list_ring_buffers` | The tested configurations by name, with language, licence, documented producer/consumer modes and their group in the interrupt stress test. |
| `compare_ring_buffers` | The comparison table for one board: filters for hard requirements, optional weights for a speed ranking. Each answer links to the same view on the website. |
| `get_ring_buffer` | One configuration on every board and in every mode. |

All four are read-only and take a fraction of a second. A full comparison
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

What follows from that:

- **No ranking by us.** Without weights the order is alphabetical, and the
  answer says that it is not a ranking. With weights the score is the page's:
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
- The notes per library and the published findings on the
  [results page](https://verified-libs.org/results.html#notes-per-library)
  are not in `libs.json`, so the tools do not have them; `about` links there.
- The stress results of the multi-producer and multi-consumer modes are on
  the results page, not in this data (as on the comparison page).
- stdio only: the server runs on your machine, from your checkout. There is
  no hosted server.
- Tested against the protocol's specification (versions 2025-11-25,
  2025-06-18, 2025-03-26 and 2024-11-05) with our own client test, not yet
  with a range of real clients. If yours does not get along with it, write
  to contact@verified-libs.org.

## Tests

```sh
python3 -m unittest discover -s mcp-server/tests
```

`test_server.py` starts the server and talks to it as a client would.
`test_parity.py` needs `gjs` to run the website's script and is skipped
without it. When `site/compare.js` changes, `vlquery.py` changes with it, and
the parity test says where they differ.
