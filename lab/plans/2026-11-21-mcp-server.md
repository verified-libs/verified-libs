# MCP server over the comparison data (2026-11-21)

PROJECT.md: "The same query for people (website) and AIs." Version 1 gave
agents the data as a JSON file; this is the step after it (plan of
2026-11-18): tools an agent can call, so that a choice of ring buffer rests
on measurements and not on which name the model has seen most.

## Decisions

1. **A port of the page, not a second comparison.** `mcp-server/vlquery.py`
   follows `site/compare.js` function by function. Two implementations of one
   comparison drift apart unless something holds them together, so
   `tests/test_parity.py` runs `compare.js` itself (gjs, a stand-in for the
   page) for 3841 views and compares rows, order, every cell's text, the
   groups, the count line, the source line and the address.
   Found on the way: the page's thousands separator is U+202F; the page's
   name order depends on the reader's language only for upper against lower
   case (no visible effect: no two names differ only in case).
2. **No ranking of ours here either.** No weights, no score; the answer says
   that the order is not a ranking. Sorting by score without weights is an
   error, not a silent fallback. The three correctness groups are in every
   answer, in their order.
3. **The owner's library is labelled in the answers** (principle 6): a field
   per row, a note on every answer that shows it, and a line in the server's
   instructions. Tested for every tool.
4. **Standard library only, stdio only.** Nothing to install, nothing to
   trust but one Python file and the data in the checkout. The server opens
   no network connection. Protocol versions 2025-11-25 back to 2024-11-05.
5. **Arguments in the agent's words** (`require: ["zero_stress_errors"]`,
   `cores: "two"`), translated to the page's state; each answer gives the
   page's address for the same view, and the test checks that the address
   leads back to the same state.
6. **A default board is named as a default.** The page starts on the first
   board; so does the tool, but the answer then says that no board was given
   and that numbers differ between cores.

## Done

- `mcp-server/server.py`, `vlquery.py`, `tests/` (17 tests), `README.md`.
- Tools: `about`, `list_ring_buffers`, `compare_ring_buffers`,
  `get_ring_buffer`; `--call` for agents with a shell and no MCP set-up.

## Open

- A test with real clients (so far: our own client test against the
  specification).
- The notes per library and the findings are not in `libs.json`; a tool for
  them needs the data generator to carry them.
- The JSON data as files on the website, for agents without a checkout.
- A hosted server (HTTP transport): a question of who runs it and where,
  not of code.
- A line about the server on the website.
