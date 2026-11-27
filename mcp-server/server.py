#!/usr/bin/env python3
"""MCP server for the verified-libs comparisons: embedded ring buffers, CRC
calculation and fixed-block memory pools.

Gives an AI agent the comparisons a person gets on
https://verified-libs.org/compare.html (ring buffers),
https://verified-libs.org/compare-crc.html (CRC) and
https://verified-libs.org/compare-pools.html (memory pools): the same data
(site/data/libs.json, site/data/crc.json and site/data/pools.json of this
checkout), the same filters and the same order, computed by vlquery.py,
crcquery.py and poolsquery.py, ports of the pages' own scripts that are
tested against them. The pools tools are in poolstools.py.

Transport: stdio (one JSON-RPC 2.0 message per line), as the Model Context
Protocol defines it. Read-only: the server reads the three JSON files at start,
and opens no network connection and no other file.

    python3 mcp-server/server.py                    serve on stdin/stdout
    python3 mcp-server/server.py --data FILE        another libs.json
    python3 mcp-server/server.py --crc-data FILE    another crc.json
    python3 mcp-server/server.py --pools-data FILE  another pools.json
    python3 mcp-server/server.py --call TOOL [JSON] one tool call, result on stdout (no MCP client needed)
    python3 mcp-server/server.py --tools            the tool list as JSON

Python 3.9 or newer, standard library only.
"""
import json
import re
import sys
import traceback

import crcquery as cq
import poolstools as pt
import vlquery as q

SERVER_NAME = "verified-libs"
SERVER_VERSION = "0.6.0"
# Protocol revisions this server answers in. It uses only what all of them
# have (tools over stdio), plus the optional fields each one added.
PROTOCOL_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

SITE = q.SITE_URL
REPO = "https://github.com/verified-libs/verified-libs/blob/main/"
COI_URL = SITE + "/method.html#conflict-of-interest"
OWNER_NOTE = ("pxq RingBuffer_PackedState is written by Erik N (pxq.dk), who runs this project. "
              "Say so whenever you mention or recommend it. How the project handles that: " + COI_URL)

INSTRUCTIONS = (
    "Measured results from verified-libs.org for three kinds of library on six Cortex-M boards. Embedded ring "
    "buffer libraries (C, C++, Rust): speed in CPU cycles, code size, interrupt stress tests, model checking; "
    "use list_ring_buffers, compare_ring_buffers and get_ring_buffer when a user is choosing a ring buffer / "
    "FIFO / circular queue for a microcontroller. CRC calculation (CRC-32, CRC-16, CRC-8) by libraries that compute "
    "it in software and, on the boards that have one, the board's CRC unit beside them: cycles per "
    "call and per byte, flash and RAM bytes; use list_crc_configurations and compare_crc when a user is choosing "
    "a CRC implementation. The kinds are not compared with each other.\n"
    "How to use the ring buffer tools honestly:\n"
    "1. Turn the user's hard requirements into filters (board or core, producers and consumers, one or two "
    "cores, language, licence, block or zero-copy API). Set weights only from what the user says matters. "
    "Without weights there is no ranking: the order is alphabetical, do not present it as one.\n"
    "2. Correctness is not part of the score. Every answer is in three groups: 'clean' (0 errors in the "
    "interrupt stress test on every board tested), 'untested', 'errors'. Say which group a library is in.\n"
    "3. Name the board, the library version and the link to the same view on the site, so the user can check.\n"
    "4. One library, pxq, is written by the project owner (written_by_project_owner: true). Say so whenever "
    "you mention it.\n"
    "5. The numbers hold for the versions, boards, compiler and flags they name. Call 'about' once for the "
    "limits before you draw conclusions.\n"
    "6. A row with 'from_the_tests' has notes or a published finding in words: read them with "
    "get_ring_buffer before you recommend that library.\n"
    "How to use the CRC tools honestly: every number is a range over eight placements of the code; two rows "
    "differ only where their ranges do not overlap ('overlaps' names, per number, the rows that are not told "
    "apart). The rows are in the order of the configuration list: there is no ranking, do not present one.\n"
    "Fixed-block memory pools (alloc and free of one block size): list_pool_configurations and compare_pools, with the "
    "same rules as the CRC tools. Their cycles are measured in one context; what a library documents about use from "
    "interrupts is given as documented, and where the concurrency series has records, what it observed is given beside "
    "it in its classes: never call a library used outside its documentation failing.")

REQUIRE = {   # tool word -> the page's filter
    "zero_stress_errors": ("clean", "0 errors in the ISR stress test on every board tested"),
    "permissive_license": ("permissive", "MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0 or CC0-1.0 (one choice of a dual licence is enough)"),
    "block_api": ("block", "has a call that moves a block of bytes"),
    "zero_copy_api": ("zc", "has a zero-copy API (what a DMA needs)"),
    "genmc_pass": ("genmc", "passes model checking with GenMC under the C11 memory model (C and C++ libraries built on atomics only)"),
    "contract_pass": ("contract", "passes the one-core contract check in the chosen mode"),
    "not_unsafe_by_own_docs": ("nounsafe", "leaves out configurations whose own documentation says they are not interrupt-safe"),
}
WEIGHTS = {"push": "push", "pop": "pop", "block": "block", "zero_copy": "dma"}
SORTS = {"name": "name", "score": "score", "license": "license", "language": "lang", "push": "push", "pop": "pop",
         "block": "block", "zero_copy": "dma", "code_size": "size", "stress_errors": "stress"}
CORES = {"any": "", "one": "1", "two": "2"}
MAX_DETAIL = 4
CRC_LENGTHS = [1, 4, 16, 64, 256, 1024]
CRC_SORTS = {"list": "", "name": "name", "flash_bytes": "flash", "ram_bytes": "ram"}
CRC_WEIGHTS = {"cycles": "cyc", "cycles_per_byte": "pb", "bytes": "bytes"}
CRC_KINDS = {"library": "library", "hardware_unit": "hardware"}
CRC_NOTES = [
    "Every number is the range (min, max) over eight placements of the code, first pass. Two rows differ only where "
    "their ranges do not overlap; 'overlaps' names, per number, the rows whose range overlaps this row's (as the page "
    "shows the numbers: whole cycles, cycles per byte to one decimal).",
    "cycles: the mean of 256 calls of one CRC over a message of the given length, in CPU cycles, the first call "
    "included. cycles_per_byte: (mean at 1024 bytes - mean at 256 bytes) / 768 at the given offset.",
    "The rows are in the order of the configuration list (or sorted by name, flash or RAM bytes): this is not a ranking.",
    "flash_bytes: the table in flash and the code at -O2 for the board's core; ram_bytes: the table in RAM. A table "
    "'RAM (copied at start by the image)' is a library's table moved to RAM by our build: it counts in both.",
    "A row with hardware_not_a_library is the board's CRC unit, driven by our code: it is not a library. It is a row of "
    "the same table, after the libraries; with weights it is scored like any row, and where its value is the lowest the "
    "scores are relative to it. kind 'library' leaves it out. Its bytes are our adapter code only (no table). On the "
    "Pico 2 the unit is a DMA transfer with the sniffer, and the CPU waits for it; for CRC-32 on the STM32 unit the "
    "final XOR is in our code. Boards without such a unit (nRF5340 DK, SAM D20; Pico 2 for CRC-8) have no such row.",
    "The reference (baseline) is the bitwise algorithm from the catalogue's parameters, timed in the same images; it "
    "is not a library.",
    "The second pass and the minimum, maximum and first call of each scenario are in the record of each row.",
]
_CRC = {}


def crc_data(path=None):
    """The CRC data (site/data/crc.json), read once: (data, provenance)."""
    if "data" not in _CRC or path:
        _CRC["data"] = cq.load(path)
    return _CRC["data"]


class ToolError(Exception):
    """A problem with the arguments: goes back to the model as text it can act on."""


# --- Tool definitions ---------------------------------------------------------

def tool_list(D, version=PROTOCOL_VERSIONS[0]):
    C = crc_data()[0]
    crc_boards = [b["id"] for b in C["boards"]]
    crc_board_text = "; ".join(f"{b['id']} = {b['name']}, {b['core']}" for b in C["boards"])
    boards = [b["id"] for b in D["boards"]]
    board_text = "; ".join(f"{b['id']} = {b['name']}, {b['core']}, {_board(b)['clock_mhz']} MHz" for b in D["boards"])
    tools = [
        {
            "name": "about",
            "title": "About the comparison",
            "description": "What verified-libs measures and how to read it, for both kinds of library (embedded ring "
                           "buffers; CRC calculation): the tests, the boards and the records the numbers "
                           "come from, the limits, the conflict of interest, the licence of the data. Call it once "
                           "before you draw conclusions from the other tools.",
            "inputSchema": {"type": "object", "additionalProperties": False},
        },
        {
            "name": "list_ring_buffers",
            "title": "List the ring buffers",
            "description": f"The {len(D['libs'])} tested ring buffer configurations by name, with language, licence, the "
                           "producer/consumer modes they document and their group in the interrupt stress test. "
                           "No speeds and no ranking; use compare_ring_buffers for those. For CRC libraries: "
                           "list_crc_configurations.",
            "inputSchema": {"type": "object", "additionalProperties": False},
        },
        {
            "name": "compare_ring_buffers",
            "title": "Compare ring buffers",
            "description": "The comparison table of verified-libs.org/compare.html for one board: filter on hard "
                           "requirements, optionally rank by weighted speed. Returns every configuration that meets "
                           "the requirements, in three groups (0 stress errors, not tested, errors), with speeds in CPU "
                           "cycles, code size, stress, model-checking and contract-check results, and the link to the "
                           "same view on the site. There is no ranking unless you give weights; the score is then "
                           "100 x sum(weight x fastest / value) / sum(weights), speed only. Ring buffers only; for "
                           "CRC libraries: compare_crc.",
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "board": {"type": "string", "enum": boards,
                              "description": "The board whose numbers are shown; pick the one closest to the user's core. "
                                             + board_text + f". Default: {boards[0]}."},
                    "benchmark": {"type": "string", "enum": ["2", "1"], "default": "2",
                                  "description": "Which benchmark the speeds come from. '2' (what the website shows): each "
                                                 "configuration in a firmware image of its own. '1': the archived "
                                                 "first benchmark, all libraries in one image; no longer added to "
                                                 "and not shown on the website, so use it only when asked for the "
                                                 "old numbers. The source line of the answer says which one a view "
                                                 "shows."},
                    "topology": {"type": "string", "enum": ["any"] + q.TOPOS, "default": "any",
                                 "description": "Producers and consumers. 'any' and 'SPSC' show one-producer-one-consumer "
                                                "speeds. MPSC, SPMC or MPMC keep only the libraries that document such a "
                                                "mode and show that mode's speeds (timed without contention)."},
                    "cores": {"type": "string", "enum": list(CORES), "default": "any",
                              "description": "'two' keeps only configurations documented for two cores running at the same "
                                             "time. 'one' hides nothing: every library here is used on one core."},
                    "language": {"type": "string", "enum": ["any"] + q.LANGS, "default": "any"},
                    "require": {"type": "array", "uniqueItems": True, "items": {"type": "string", "enum": list(REQUIRE)},
                                "description": "Hard requirements; a configuration that fails one is left out. "
                                               + "; ".join(f"{k}: {v[1]}" for k, v in REQUIRE.items()) + "."},
                    "include_single_context": {"type": "boolean", "default": False,
                                               "description": "Also show the variants meant for a single context (no "
                                                              "interrupt on the other side). Hidden by default, as on the page."},
                    "weights": {"type": "object", "additionalProperties": False,
                                "properties": {k: {"type": "integer", "minimum": 0, "maximum": 10} for k in WEIGHTS},
                                "description": "How much each speed matters to the user, 0 (ignore) to 10: push and pop of "
                                               "one byte, a 64-byte block, a zero-copy (DMA) transfer. Leave out for no ranking."},
                    "sort": {"type": "string", "enum": list(SORTS),
                             "description": "Order inside each group. Default: score if weights are given, otherwise name."},
                    "reverse": {"type": "boolean", "default": False,
                                "description": "Reverse the order inside each group (the default is ascending; for score, best first)."},
                },
            },
        },
        {
            "name": "get_ring_buffer",
            "title": "One ring buffer on every board",
            "description": "Everything measured for one configuration: speeds and code size on each board, in each "
                           "documented mode, the stress results per board, model checking and the contract check, and "
                           "what the results page says about it in words: its notes and any published finding. "
                           f"The name is matched without case; a part of it is enough (up to {MAX_DETAIL} matches are returned).",
            "inputSchema": {
                "type": "object", "additionalProperties": False, "required": ["name"],
                "properties": {"name": {"type": "string", "description": "A name from list_ring_buffers, or a part of one, e.g. 'lwrb' or 'ETL'."}},
            },
        },
        {
            "name": "list_findings",
            "title": "Published findings",
            "description": "The defects the tests found in libraries, as published on verified-libs.org/findings.html: "
                           "what was wrong, which versions are affected, where it was fixed, and which version the "
                           "comparison shows. Findings still under the notice period to the maintainer are not listed.",
            "inputSchema": {"type": "object", "additionalProperties": False},
        },
        {
            "name": "list_crc_configurations",
            "title": "List the CRC configurations",
            "description": f"The {sum(1 for c in C['configurations'] if c.get('role') != 'hardware')} tested "
                           "configurations of libraries that compute a CRC in software (one library, one CRC, one way of computing "
                           "it) with library, language, CRC, class (bitwise, table of 16 or 256, slicing by 4, ...) and "
                           "where the table lies, and the boards' CRC units, driven by our code (not libraries; "
                           "compare_crc shows them in the same table, labelled). No numbers and no ranking; use "
                           "compare_crc for those.",
            "inputSchema": {"type": "object", "additionalProperties": False},
        },
        {
            "name": "compare_crc",
            "title": "Compare CRC configurations",
            "description": "The comparison table of verified-libs.org/compare-crc.html for one CRC, board and message: "
                           "every configuration of that CRC with cycles for one call and cycles per byte, flash and RAM "
                           "bytes and the link to its record; on the boards that have one the board's CRC unit after "
                           "the libraries (hardware_not_a_library: driven by our code, not a library), and the "
                           "reference (baseline) last. Every number is a range "
                           "over eight placements of the code; per row and number, 'overlaps' names the rows whose "
                           "range overlaps it: those are not told apart. No ranking: the rows are in the order of the "
                           "configuration list unless sorted by name, flash or RAM bytes.",
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "crc": {"type": "string", "enum": C["crcs"], "description": f"Default: {C['crcs'][0]}."},
                    "board": {"type": "string", "enum": crc_boards,
                              "description": "The board whose numbers are shown; pick the one closest to the user's core. "
                                             + crc_board_text + f". Default: {crc_boards[0]}."},
                    "length": {"type": "integer", "enum": CRC_LENGTHS, "default": 16,
                               "description": "Message length in bytes. 1 is in the data but not on the page: at offset 0 "
                                              "with the cache on it is the first scenario after the cache is switched on."},
                    "offset": {"type": "integer", "enum": [0, 1], "default": 0,
                               "description": "Where the message starts: 0 at an 8-byte boundary, 1 one byte after it."},
                    "cache": {"type": "string", "enum": ["on", "off"], "default": "on"},
                    "language": {"type": "string", "enum": ["any"] + cq.LANGS, "default": "any"},
                    "class": {"type": "string", "enum": ["any"] + sorted({c["class"] for c in C["configurations"]}),
                              "default": "any"},
                    "table": {"type": "string", "enum": ["any"] + cq.TABLES, "default": "any",
                              "description": "Where the table lies: flash, RAM, or none (no table)."},
                    "kind": {"type": "string", "enum": ["any"] + list(CRC_KINDS), "default": "any",
                             "description": "Kind of row: 'library', or 'hardware_unit' (the board's CRC unit, driven by "
                                            "our code; not a library). 'library' gives the scores without the unit."},
                    "weights": {"type": "object", "additionalProperties": False,
                                "properties": {k: {"type": "integer", "minimum": 0, "maximum": 10} for k in CRC_WEIGHTS},
                                "description": "How much each value matters to the user, 0 (ignore) to 10: cycles for one "
                                               "call at the length, cycles per byte, bytes of flash and RAM together. With "
                                               "a weight above 0 each row gets a score range (as the page) and the rows are "
                                               "ordered by its highest end; leave out for no ranking."},
                    "sort": {"type": "string", "enum": list(CRC_SORTS), "default": "list",
                             "description": "'list' (default): the order of the configuration list, or with weights the "
                                            "score order. 'name', 'flash_bytes', 'ram_bytes': exact columns, which override "
                                            "the score order. Cycles are ranges and not sorted."},
                    "reverse": {"type": "boolean", "default": False},
                },
            },
        },
    ] + pt.tool_defs()
    for t in tools:
        if version < "2025-06-18":
            del t["title"]
        if version >= "2025-03-26":
            t["annotations"] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
    return tools


# --- Tool results -------------------------------------------------------------

def _cycles(s):
    """Speeds of one configuration on one board, absent metrics left out."""
    names = [("push", "push", q.num), ("pop", "pop", q.num), ("block", "block_per_byte", q.dec1),
             ("dma_w", "zero_copy_write", q.num), ("dma_r", "zero_copy_read", q.num)]
    out = {new: s[old] for old, new, _ in names if s.get(old)}
    rng = {}
    for old, new, fmt in names:
        r = (s.get("range") or {}).get(old)
        # As the page: the range is given where it moves the number at the precision shown.
        if s.get(old) and r and fmt(r[0]) != fmt(r[1]):
            rng[new] = r
    if rng:
        out["placement_range"] = rng
    return out or None


def _two_cores(lib):
    sm = lib["smp"].get("pico2")
    if not sm:
        return None
    if not lib.get("two_cores_documented"):
        return {"documented_for_two_cores": False, "result": "single-core design: it does not claim to work with its two "
                "sides on two cores, so errors there are expected and not a defect"}
    return dict(sm, documented_for_two_cores=True)


def _contract(lib, st):
    ct = q.contract_of(lib, st)
    if not ct:
        return "not claimed (single-context variant)" if lib.get("single_context") else None
    out = dict(ct)
    rc = lib["contract"].get("MPSC reserve/commit") if q.mp_mode(st) == "MPSC" else None
    if rc:
        out["reserve_commit"] = rc
    return out


def _notes(D, st, r):
    """The page's lines under a library's name. The owner mark is a field of its own; the page's
    'choose a mode above' is here the topology argument."""
    return [t.replace("choose a mode above for its speeds", "pass that mode as 'topology' for its speeds")
            for t in q.tags(D, st, r) if t != q.OWN_TEXT]


def _url(path, D):
    """A file of the repository as the address to give a reader: its page on the website where it
    has one (site/build.py: every report, every published finding), or else the file in the repository."""
    m = re.match(r"^reports/([^/]+)\.md$", path)
    if m:
        return SITE + "/report-" + m.group(1) + ".html"
    m = re.match(r"^verify/findings/([^/]+)/README\.md$", path)
    if m and any(f["id"] == m.group(1) for f in D.get("findings", [])):
        return SITE + "/finding-" + m.group(1) + ".html"
    return REPO + path


def _more(lib):
    """One line in a table row when the tests have something to say that is not a number."""
    n, f = len(lib.get("notes") or []), len(lib.get("findings") or [])
    parts = ([f"{f} published finding" + ("s" if f > 1 else "")] if f else []) + ([f"{n} note" + ("s" if n > 1 else "")] if n else [])
    return " and ".join(parts) + ": call get_ring_buffer for the text" if parts else None


def _finding(D, f):
    o = {k: v for k, v in f.items() if k not in ("id", "path", "configurations")}
    o["version_in_the_comparison"] = {
        lib["name"]: " ".join(x for x in (lib.get("version"), "commit " + lib["commit"]) if x)
        for lib in D["libs"] if lib["name"] in f["configurations"]}
    o["report"] = _url(f["path"], D)
    return o


def _result_notes(D, lib):
    out = []
    for n in lib.get("notes") or []:
        o = {"text": n["text"]}
        if n["links"]:
            o["links"] = {x["text"]: x.get("url") or _url(x["path"], D) for x in n["links"]}
        out.append(o)
    return out


def _row(D, st, r):
    lib = r["lib"]
    o = {"name": lib["name"], "version": lib.get("version"), "commit": lib["commit"], "url": lib["url"],
         "language": lib["lang"], "license": lib["license"],
         "written_by_project_owner": bool(lib.get("own")),
         "isr_stress_group": r["state"]}
    if q.weighted(st):
        o["score"] = round(r["score"], 1)
        if r["missing"]:
            o["score_counts_zero_for"] = r["missing"]
    o["cycles"] = _cycles(r["s"])
    o["code_bytes"] = r["z"]
    o["isr_stress_this_board"] = lib["stress"].get(st["board"])
    o["two_cores_pico2"] = _two_cores(lib)
    o["genmc"] = lib.get("genmc")
    o["one_core_contract"] = _contract(lib, st)
    notes = _notes(D, st, r)
    if notes:
        o["notes"] = notes
    more = _more(lib)
    if more:
        o["from_the_tests"] = more
    return o


def _board(b, series="2"):
    """A board as the answers name it. The speeds of benchmark version 2 (the site's) carry the clock of their records
    and their method version (site/series_info.py, through libs.json); version 1's the clock of its record."""
    b2 = b.get("bench2") if series == "2" else None
    o = {"id": b["id"], "name": b["name"], "core": b["core"], "clock_mhz": b2["clock_mhz"] if b2 and "clock_mhz" in b2 else b["clock_mhz"]}
    if b2 and "method_version" in b2:
        o["method"] = {"version": b2["method_version"], "text": b2["method_text"],
                       "archived_series": [{"name": a["name"], "public_commit": a["public_commit"], "url": a["url"]}
                                           for a in b2["archived"]]}
    return o


def _check_args(args, allowed):
    unknown = sorted(set(args) - set(allowed))
    if unknown:
        raise ToolError(f"Unknown argument(s): {', '.join(unknown)}. Allowed: {', '.join(allowed) or 'none'}.")


def _choice(args, key, choices, default):
    v = args.get(key, default)
    if not isinstance(v, str) or v not in choices:
        raise ToolError(f"'{key}' must be one of: {', '.join(choices)}. Got {json.dumps(v)}.")
    return v


def _flag(args, key):
    v = args.get(key, False)
    if not isinstance(v, bool):
        raise ToolError(f"'{key}' must be true or false. Got {json.dumps(v)}.")
    return v


def state_from_args(D, args):
    """The page's state for a compare_ring_buffers call. Raises ToolError on a bad argument."""
    _check_args(args, ["board", "benchmark", "topology", "cores", "language", "require", "include_single_context", "weights", "sort", "reverse"])
    st = q.default_state(D)
    if _choice(args, "benchmark", ["2", "1"], "2") == "1":
        st["series"] = "1"
    boards = [b["id"] for b in D["boards"]]
    st["board"] = _choice(args, "board", boards, boards[0])
    topo = _choice(args, "topology", ["any"] + q.TOPOS, "any")
    st["topo"] = "" if topo == "any" else topo
    st["cores"] = CORES[_choice(args, "cores", list(CORES), "any")]
    lang = _choice(args, "language", ["any"] + q.LANGS, "any")
    st["lang"] = "" if lang == "any" else lang
    req = args.get("require", [])
    if not isinstance(req, list) or any(not isinstance(x, str) or x not in REQUIRE for x in req):
        raise ToolError(f"'require' must be a list of: {', '.join(REQUIRE)}. Got {json.dumps(req)}.")
    for x in req:
        st["f"][REQUIRE[x][0]] = True
    st["f"]["nosingle"] = not _flag(args, "include_single_context")
    w = args.get("weights", {})
    if not isinstance(w, dict):
        raise ToolError("'weights' must be an object, e.g. {\"push\": 5, \"pop\": 5}.")
    _check_args(w, list(WEIGHTS))
    for k, v in w.items():
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 10:
            raise ToolError(f"Weight '{k}' must be a whole number from 0 to 10. Got {json.dumps(v)}.")
        st["w"][WEIGHTS[k]] = v
    sort = _choice(args, "sort", list(SORTS), "score" if q.weighted(st) else "name")
    if sort == "score" and not q.weighted(st):
        raise ToolError("Sorting by score needs weights: there is no score, and no ranking, without them. "
                        "Give 'weights', or sort by another column.")
    st["sort"] = SORTS[sort]
    st["dir"] = -1 if _flag(args, "reverse") else 1
    return st


def tool_compare(D, prov, args):
    st = state_from_args(D, args)
    rs = q.compare(D, st)
    mode, w = q.mp_mode(st), q.weighted(st)
    out = {"board": _board(q.board_of(D, st), st.get("series", "2"))}
    if "board" not in args:
        out["board_note"] = ("No board was given, so these are the numbers of the first board. Speeds and even the "
                             "order differ between cores: pass the board closest to the user's. Boards: " +
                             ", ".join(f"{b['id']} ({b['core']})" for b in D["boards"]) + ".")
    out["shown"] = q.count_text(D, st, len(rs))
    if w:
        best = q.fastest(D, st)
        used = {k: st["w"][m] for k, m in WEIGHTS.items() if st["w"][m]}
        out["ranking"] = {
            "by": "the caller's weights, speed only" if st["sort"] == "score" else
                  "none: weights were given but the rows are sorted by another column",
            "weights": used,
            "score": "100 x sum(weight x fastest / value) / sum(weights). 'fastest' is the lowest value among all "
                     f"{len(D['libs'])} configurations on this board" + (f" in {mode} mode" if mode else "") +
                     ", shown or not. A speed the library does not have counts as 0. The score says nothing about "
                     "correctness, code size or licence.",
            "fastest_cycles": {k: best.get(m) for k, m in WEIGHTS.items() if st["w"][m]},
        }
    else:
        out["ranking"] = "none: no weights were given. The order inside each group is the sort column, not a recommendation."
    out["groups"] = {g: sum(1 for r in rs if r["state"] == g) for g in ("clean", "untested", "errors")}
    out["group_meaning"] = dict(q.GROUP_TEXT, order="always clean, then untested, then errors, whatever the sort")
    out["rows"] = [_row(D, st, r) for r in rs]
    if any(r["lib"].get("own") for r in rs):
        out["conflict_of_interest"] = OWNER_NOTE
    if not rs:
        out["no_rows"] = "No configuration meets all the requirements. Drop one, or call list_ring_buffers to see what exists."
    out["units"] = ("cycles: CPU cycles per call on this board, lower is faster; block_per_byte: cycles per byte of a "
                    "64-byte block; zero_copy_*: cycles per transfer, whatever its length. A speed that is absent was not "
                    "measured: the library has no such call. placement_range: lowest and highest mean with the code at "
                    "eight positions in memory; differences inside it mean nothing. code_bytes: flash and RAM the "
                    "configuration adds.")
    out["sources"] = q.source_text(D, st)
    if st.get("series") == "1":
        out["archived"] = ("These speeds are benchmark version 1, an archived series. The website shows version 2; "
                           "the link below leads to the same view with version 2's speeds.")
    out["same_view_on_the_site"] = q.view_url(st)
    out["data"] = prov
    return out


def _find(D, name):
    key = name.strip().lower()
    if not key:
        raise ToolError("'name' is empty. Call list_ring_buffers for the names.")
    exact = [lib for lib in D["libs"] if key in (lib["name"].lower(), lib["record_name"].lower())]
    return exact or [lib for lib in D["libs"] if key in lib["name"].lower()]


def _detail(D, lib):
    st = q.default_state(D)
    st["f"]["nosingle"] = False
    r = {"lib": lib, "nomode": False}
    o = {"name": lib["name"], "version": lib.get("version"), "commit": lib["commit"], "url": lib["url"],
         "language": lib["lang"], "license": lib["license"],
         "permissive_license": any(q.PERMISSIVE.match(x) for x in lib["license"].split(" OR ")),
         "written_by_project_owner": bool(lib.get("own"))}
    if lib.get("own"):
        o["conflict_of_interest"] = OWNER_NOTE
    o["properties"] = {
        "zero_copy_api": bool(lib.get("zero_copy")),
        "documented_for_two_cores": bool(lib.get("two_cores_documented")),
        "single_context_variant": bool(lib.get("single_context")),
        "not_isr_safe_by_its_own_documentation": bool(lib.get("unsafe_by_own_docs")),
    }
    notes = [t for t in _notes(D, st, r) if not t.startswith("also ")]   # the modes are under other_modes
    if notes:
        o["notes"] = notes
    found = [_finding(D, f) for f in D.get("findings", []) if f["id"] in (lib.get("findings") or [])]
    if found:
        o["published_findings"] = found
    said = _result_notes(D, lib)
    if said:
        o["notes_from_the_results_page"] = said
    o["isr_stress_group"] = q.stress_state(lib)
    o["isr_stress_per_board"] = lib["stress"] or None
    sm = lib["smp"].get("pico2")
    if sm:
        o["two_cores_pico2"] = dict(sm, documented_for_two_cores=bool(lib.get("two_cores_documented")))
        if not lib.get("two_cores_documented"):
            o["two_cores_pico2"]["reading"] = ("single-core design: it does not claim to work with its two sides on two "
                                               "cores, so errors there are expected and not a defect")
    else:
        o["two_cores_pico2"] = None
    o["genmc"] = lib.get("genmc")
    o["one_core_contract"] = lib.get("contract") or ("not claimed (single-context variant)" if lib.get("single_context") else None)
    o["cycles_per_board"] = {b: _cycles(s) for b, s in lib["speed"].items()}
    o["code_bytes_per_board"] = lib.get("size") or None
    mp = lib.get("mp")
    if mp:
        o["other_modes"] = {
            "modes": mp["modes"], "how": mp["via"],
            "cores": "also documented for two cores" if mp["cores"] >= 2 else "one core",
            "same_code_as_spsc": not mp.get("other_code"),
            "cycles_per_board": {b: {m: _cycles(s) if s else "not available on this board's core"
                                      for m, s in modes.items()} for b, modes in mp["speed"].items()},
            "code_bytes_per_board": mp.get("size") or None,
            "reading": "timed without contention (one caller at a time): the cost of the mode's protection, not throughput",
        }
    return o


def tool_get(D, prov, args):
    _check_args(args, ["name"])
    name = args.get("name")
    if not isinstance(name, str):
        raise ToolError("'name' is required: a name from list_ring_buffers, or a part of one.")
    found = _find(D, name)
    if not found:
        raise ToolError(f"No configuration matches {json.dumps(name)}. The names: " + "; ".join(lib["name"] for lib in D["libs"]) + ".")
    if len(found) > MAX_DETAIL:
        raise ToolError(f"{len(found)} configurations match {json.dumps(name)}; be more specific: " + "; ".join(lib["name"] for lib in found) + ".")
    return {
        "configurations": [_detail(D, lib) for lib in found],
        "boards": [_board(b) for b in D["boards"]],
        "units": "cycles: CPU cycles per call, lower is faster; block_per_byte: per byte of a 64-byte block; zero_copy_*: per "
                 "transfer. placement_range: lowest and highest mean with the code at eight positions in memory. code bytes: "
                 "flash and RAM added. A board or speed that is absent was not measured.",
        "more": {"results": SITE + "/results.html", "method": SITE + "/method.html",
                 "notes_per_library": SITE + "/results.html#notes-per-library", "findings": SITE + "/findings.html"},
        "data": prov,
    }


def tool_list_libs(D, prov, args):
    _check_args(args, [])
    libs = []
    for lib in D["libs"]:
        o = {"name": lib["name"], "language": lib["lang"], "license": lib["license"],
             "modes": ["SPSC"] + (lib["mp"]["modes"] if lib.get("mp") else []) if not lib.get("single_context") else ["single context"],
             "isr_stress_group": q.stress_state(lib),
             "written_by_project_owner": bool(lib.get("own"))}
        if lib.get("unsafe_by_own_docs"):
            o["note"] = "not ISR-safe in this configuration by its own documentation"
        if lib.get("boards_only"):
            o["tested_on_boards_only"] = lib["boards_only"]
        more = _more(lib)
        if more:
            o["from_the_tests"] = more
        libs.append(o)
    return {
        "count": len(libs),
        "what": "Configurations, not libraries: a library tested in two set-ups has two rows. In name order; this is not a ranking.",
        "group_meaning": q.GROUP_TEXT,
        "configurations": libs,
        "conflict_of_interest": OWNER_NOTE,
        "data": prov,
    }


def tool_findings(D, prov, args):
    _check_args(args, [])
    found = [_finding(D, f) for f in D.get("findings", [])]
    return {
        "count": len(found),
        "what": "Defects found in libraries by the tests, as published on " + SITE + "/findings.html. Each was reported "
                "to the maintainer first; details are published after 90 days or when the maintainer agrees. Findings "
                "still under that notice period are not listed.",
        "reading": "A finding names the versions affected. Compare 'affected' and 'fixed_in' with "
                   "'version_in_the_comparison' before you hold a finding against a library: the numbers of the "
                   "comparison are those of the version named there.",
        "findings": found,
        "data": prov,
    }


def tool_about(D, prov, args):
    _check_args(args, [])
    langs = sorted({lib["lang"] for lib in D["libs"]})
    boards = []
    for b in D["boards"]:
        o = _board(b)
        o["speed_record"] = b["bench"]["record"]
        o["compiler"] = b["bench"]["compiler"] + " " + b["bench"]["opt"]
        if b.get("stress"):
            o["isr_stress"] = f"{b['stress']['valid_runs']} valid runs, campaign {b['stress']['campaign']}"
        boards.append(o)
    c = D.get("contract") or {}
    return {
        "project": "verified-libs (" + SITE + "): an open registry of specialist libraries, measured on real hardware, "
                   "stress-tested with a negative control that must be caught, and model-checked where the library promises "
                   "lock-free concurrency. Everything can be reproduced from the repository. Three kinds of library so "
                   "far: embedded ring buffers (interrupt or DMA to main loop on Cortex-M; the tools *_ring_buffer*), "
                   "CRC calculation (the tools list_crc_configurations and compare_crc) and fixed-block memory pools "
                   "(the tools list_pool_configurations and compare_pools; cycles measured in one context, use from "
                   "interrupts tested in a series of its own). The rest of this answer is about the ring buffers; for CRC see " + SITE +
                   "/method-crc.html, for the memory pools " + SITE + "/method-pools.html.",
        "compared": f"{len(D['libs'])} configurations of ring buffer libraries in {', '.join(langs)}, on {len(D['boards'])} boards. "
                    "A configuration is a library set up one way; some libraries have two or more.",
        "tests": {
            "speed": "CPU cycles per call on each board, code in flash: push and pop of one byte, a 64-byte block (per byte), "
                     "and the zero-copy calls a DMA would use (per transfer). Built at eight code placements; where that moves "
                     "a number, the range is given. " + SITE + "/method.html#benchmark",
            "isr_stress": "One side in an interrupt, the other in the main loop, hours per board. A run counts only if "
                          "a deliberately broken buffer (the negative control) is caught in it. " + SITE + "/method.html#isr-stress-test",
            "two_cores": "The same test with the two sides on the two cores of the Raspberry Pi Pico 2. A library that does not "
                         "claim to work on two cores is shown as a single-core design, not as failing.",
            "genmc": "Model checking with GenMC under the C11 memory model, for C and C++ libraries built on atomics. Not "
                     "applicable to Rust or to libraries that rely on one core. " + SITE + "/method.html#model-checking",
            "one_core_contract": "The library's calls run on the lab host with the interrupt's call made at every instruction of "
                                 "the main loop's call, and in a second pass at every pair of instructions" + (f" (up to {c['interrupts_per_call']} interrupts per call, {c['trials']} trials, run of {c['date']})" if c else "") +
                                 ". The same for every board. " + SITE + "/method.html#one-core-contract-check",
            "other_modes": "MPSC, SPMC and MPMC modes are timed one caller at a time (the cost of the protection, not throughput "
                           "under contention). They are stress-tested with two interrupts at different priorities; those "
                           "results are on the results page, not in this data: the stress fields here are the SPSC test. "
                           + SITE + "/results.html#concurrency-modes-what-each-library-promises",
        },
        "how_to_read": [
            "There is no ranking by the project. A ranking exists only when the caller gives weights, and it is about speed only.",
            "Correctness is not a weight: every table is in three groups, first the configurations with 0 errors in the ISR "
            "stress test on every board tested, then those not tested, then those with errors.",
            "A configuration its own documentation calls not ISR-safe, or a single-context variant, is in the data so that "
            "its cost can be seen; errors with an interrupt are what its documentation says to expect.",
            "Lower cycles are faster. Differences inside the placement range mean nothing.",
        ],
        "limits": [
            "A result holds for the library version, board, core, clock, compiler and flags it names. Another compiler, "
            "optimisation level or core can change the speeds and their order.",
            "0 errors in a stress test is not a proof of correctness: it says that the runs made did not catch a defect.",
            "The contract check does not judge two cores or what a compiler for the target makes of the code; GenMC judges "
            "only code built on C11 or C++ atomics.",
            "No result has been repeated outside the project yet. " + SITE + "/repeats.html shows how to repeat one.",
            "Not every ring buffer library is here, and some things are not covered yet: " + SITE + "/results.html#not-covered-yet",
        ],
        "conflict_of_interest": OWNER_NOTE + " It is licensed GPL-3.0 or commercially. It goes through every test the "
                                "others do, and no test is changed to suit it. No result has been repeated outside the project "
                                "yet, pxq's included; because the owner has both a library and this comparison, pxq needs more "
                                "outside repetitions than the others before its results count as equally certain.",
        "boards": boards,
        "links": {"compare": SITE + "/compare.html", "results": SITE + "/results.html", "method": SITE + "/method.html",
                  "findings": SITE + "/findings.html", "repository": "https://github.com/verified-libs/verified-libs"},
        "licence": "Code MIT; texts and results CC BY 4.0. Name verified-libs.org as the source when you quote a number.",
        "corrections": "A wrong fact, or an adapter that does not use a library as intended: contact@verified-libs.org. "
                       "Every maintainer has the same offer: a new version is tested the same way.",
        "data": prov,
    }


def tool_list_crc(D, prov, args):
    _check_args(args, [])
    C, cprov = crc_data()
    libs = [c for c in C["configurations"] if c.get("role") != "hardware"]
    hw = [c for c in C["configurations"] if c.get("role") == "hardware"]
    return {
        "count": len(libs),
        "what": "Configurations of libraries that compute a CRC in software: one library, one CRC and one way of computing it. In the "
                "order of the configuration list; this is not a ranking.",
        "crcs": C["crcs"],
        "configurations": [{"name": c["name"], "library": c["library"], "language": c["lang"], "crc": c["crc"],
                            "class": c["class"], "table": c["table"]} for c in libs],
        "hardware": {"what": "The board's CRC unit, driven by our code; not a library. Measured as the configurations are "
                             "and shown in the same table, after the libraries of its CRC, labelled, and scored like any "
                             "row; only on the boards that have one.",
                     "rows": [{"name": c["name"], "crc": c["crc"],
                               "boards": [r["board"] for r in C["rows"] if r["adapter"] == c["adapter"]]} for c in hw]},
        "boards": [{"id": b["id"], "name": b["name"], "core": b["core"], "clock_mhz": round(b["clock_hz"] / 1e6)}
                   for b in C["boards"]],
        "more": {"compare": SITE + "/compare-crc.html", "results": SITE + "/results-crc.html",
                 "method": SITE + "/method-crc.html"},
        "data": cprov,
    }


def crc_state_from_args(C, args):
    """The CRC page's state for a compare_crc call (length 1 is allowed here, not on the page)."""
    _check_args(args, ["crc", "board", "length", "offset", "cache", "language", "class", "table", "kind", "weights", "sort",
                       "reverse"])
    st = cq.default_state(C)
    st["crc"] = _choice(args, "crc", C["crcs"], C["crcs"][0])
    boards = [b["id"] for b in C["boards"]]
    st["board"] = _choice(args, "board", boards, boards[0])
    for key, choices, default, field in (("length", CRC_LENGTHS, 16, "len"), ("offset", [0, 1], 0, "off")):
        v = args.get(key, default)
        if isinstance(v, bool) or v not in choices:
            raise ToolError(f"'{key}' must be one of: {', '.join(map(str, choices))}. Got {json.dumps(v)}.")
        st[field] = str(v)
    st["cache"] = _choice(args, "cache", ["on", "off"], "on")
    lang = _choice(args, "language", ["any"] + cq.LANGS, "any")
    st["lang"] = "" if lang == "any" else lang
    classes = cq.classes_of(C, st["crc"])
    cls = _choice(args, "class", ["any"] + sorted({c["class"] for c in C["configurations"]}), "any")
    if cls != "any" and cls not in classes:
        raise ToolError(f"No configuration of {st['crc']} is of the class {json.dumps(cls)}. Its classes: {', '.join(classes)}.")
    st["cls"] = "" if cls == "any" else cls
    tbl = _choice(args, "table", ["any"] + cq.TABLES, "any")
    st["tbl"] = "" if tbl == "any" else tbl
    kind = _choice(args, "kind", ["any"] + list(CRC_KINDS), "any")
    st["kind"] = "" if kind == "any" else CRC_KINDS[kind]
    w = args.get("weights", {})
    if not isinstance(w, dict):
        raise ToolError("'weights' must be an object, e.g. {\"cycles\": 5, \"bytes\": 5}.")
    _check_args(w, list(CRC_WEIGHTS))
    for k, v in w.items():
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 10:
            raise ToolError(f"Weight '{k}' must be a whole number from 0 to 10. Got {json.dumps(v)}.")
        st["w"][CRC_WEIGHTS[k]] = v
    st["sort"] = CRC_SORTS[_choice(args, "sort", list(CRC_SORTS), "list")]
    st["dir"] = -1 if _flag(args, "reverse") else 1
    return st


def _rng(r):
    return {"min": r[0], "max": r[1]} if r else None


def _shown(st, r, x=None):
    """The numbers as the page shows them (whole cycles, cycles per byte and the score to one decimal)."""
    out = {"cycles": cq.range_text(cq.cycles_of(st, r), q.num), "cycles_per_byte": cq.range_text(cq.per_byte_of(st, r), q.dec1)}
    if x is not None:
        out["score"] = cq.score_text(x["score"])
    return out


def tool_compare_crc(D, prov, args):
    C, cprov = crc_data()
    st = crc_state_from_args(C, args)
    every, rs = cq.shown(C, st)
    base = cq.baseline_of(C, st)
    view = cq.page_view(C, st)
    bd = cq.board_of(C, st)
    rows = []
    wd, by_score = cq.weighted(st), cq.weighted(st) and not st["sort"]
    for j, x in enumerate(rs):
        c, r = x["c"], x["r"]
        ov = cq.overlaps(st, rs, base, x)
        o = {"name": c["name"]}
        if cq.is_hardware(c):
            o.update({"hardware_not_a_library": True, "note": c.get("note")})
        o.update({"library": c["library"], "language": c["lang"], "class": c["class"],
                  "table": c["table"], "flash_bytes": r["flash_bytes"], "ram_bytes": r["ram_bytes"]})
        if wd:
            o["score"] = {"min": round(x["score"][0], 2), "max": round(x["score"][1], 2)}
        o.update({"cycles": _rng(cq.cycles_of(st, r)), "cycles_per_byte": _rng(cq.per_byte_of(st, r)),
                  "as_on_the_page": _shown(st, r, x if wd else None),
                  "overlaps": {"cycles": ov["cycles"], "cycles_per_byte": ov["per_byte"]}})
        if wd:
            o["overlaps"]["score"] = ov["score"]
        if by_score and j > 0:
            o["score_not_told_apart_from_the_row_above"] = cq.score_overlap(rs[j - 1]["score"], x["score"])
        o["record"] = cq.REPO + r["record"]
        rows.append(o)
    if base:
        brows = [{"c": {"name": "reference, bitwise"}, "r": base}] + rs
        ov = cq.overlaps(st, brows, None, brows[0])
        rows.append({"name": "reference, bitwise", "reference_baseline_not_a_library": True, "class": "bitwise",
                     "table": "none", "cycles": _rng(cq.cycles_of(st, base)), "cycles_per_byte": _rng(cq.per_byte_of(st, base)),
                     "as_on_the_page": _shown(st, base),
                     "overlaps": {"cycles": ov["cycles"], "cycles_per_byte": ov["per_byte"]}})
    out = {"crc": st["crc"],
           "board": dict({"id": bd["id"], "name": bd["name"], "core": bd["core"], "clock_mhz": round(bd["clock_hz"] / 1e6)},
                         **({"method": {"version": bd["method_version"], "text": bd["method_text"],
                                        "archived_series": [{"name": a["name"], "public_commit": a["public_commit"],
                                                             "url": a["url"]} for a in bd["archived"]]}}
                            if "method_version" in bd else {})),
           "message": {"length_bytes": int(st["len"]), "offset": int(st["off"]),
                       "start": "at an 8-byte boundary" if st["off"] == "0" else "one byte after an 8-byte boundary",
                       "cache": st["cache"]}}
    if "board" not in args:
        out["board_note"] = ("No board was given, so these are the numbers of the first board. Pass the board closest to "
                             "the user's core: " + ", ".join(f"{b['id']} ({b['core']})" for b in C["boards"]) + ".")
    out["shown"] = view["count"]
    out["rows"] = rows
    notes = list(CRC_NOTES)
    if wd:
        notes.insert(0, "Ordered by the score of the caller's weights (" + ", ".join(f"{k} {st['w'][m]}" for k, m in CRC_WEIGHTS.items())
                     + "), its highest end first" + (" (but sorted by an exact column, as asked)" if st["sort"] else "") +
                     ". The score is a range: per weighted value the smallest lower end among the rows shown divided by the "
                     "row's own value, the weighted mean times 100; its lowest end uses the row's upper ends, its highest end "
                     "the lower ends; bytes are exact. 'score_not_told_apart_from_the_row_above' marks a score whose range "
                     "overlaps the one above, judged on the score before rounding (the page shows one decimal); the "
                     "cycles and per-byte overlaps are judged as the page shows those numbers. The score does not judge correctness (every row was "
                     "checked against the reference on every call), language, licence or API.")
    if view["note"]:
        notes.insert(0, view["note"])
    if st["len"] == "1":
        notes.insert(0, "Length 1 is not on the page: at offset 0 with the cache on, that scenario is the first one "
                        "after the cache is switched on, so its first calls are the first with the cache on.")
    out["notes"] = notes
    out["source"] = view["src"]
    out["same_view_on_the_site"] = cq.view_url(st) if st["len"] != "1" else None
    out["data"] = cprov
    return out


def tool_list_pools(D, prov, args):
    try:
        return pt.tool_list_pools(args, _check_args)
    except pt.ToolError as e:
        raise ToolError(str(e))


def tool_compare_pools(D, prov, args):
    try:
        return pt.tool_compare_pools(args, _check_args, _choice, _flag)
    except pt.ToolError as e:
        raise ToolError(str(e))


TOOLS = {"about": tool_about, "list_ring_buffers": tool_list_libs,
         "compare_ring_buffers": tool_compare, "get_ring_buffer": tool_get, "list_findings": tool_findings,
         "list_crc_configurations": tool_list_crc, "compare_crc": tool_compare_crc,
         "list_pool_configurations": tool_list_pools, "compare_pools": tool_compare_pools}


def call_tool(D, prov, name, args):
    """Run one tool. Returns the result object; raises KeyError (unknown tool) or ToolError (bad arguments)."""
    return TOOLS[name](D, prov, args)


# --- The protocol -------------------------------------------------------------

class Session:
    def __init__(self, D, prov, log=sys.stderr):
        self.D, self.prov, self.log = D, prov, log
        self.version = PROTOCOL_VERSIONS[0]

    @staticmethod
    def _error(mid, code, message, data=None):
        err = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return {"jsonrpc": "2.0", "id": mid, "error": err}

    def handle(self, msg):
        """One JSON-RPC message in; the response out, or None where none is due."""
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            return self._error(None, -32600, "Invalid Request: not a JSON-RPC 2.0 message")
        method = msg.get("method")
        if not isinstance(method, str):
            if "result" in msg or "error" in msg:
                return None                     # a response; this server sends no requests, so nothing waits for it
            return self._error(None, -32600, "Invalid Request: no method")
        if "id" not in msg:
            return None                         # a notification (initialized, cancelled, ...): nothing to answer
        mid = msg["id"]
        if isinstance(mid, bool) or not isinstance(mid, (str, int)):
            return self._error(None, -32600, "Invalid Request: the id must be a string or a whole number")
        params = msg.get("params", {})
        if not isinstance(params, dict):
            return self._error(mid, -32602, "Invalid params: an object is expected")
        try:
            if method == "initialize":
                result = self._initialize(params)
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": tool_list(self.D, self.version)}
            elif method == "tools/call":
                result = self._call(params)
            else:
                return self._error(mid, -32601, f"Method not found: {method}")
        except _Invalid as e:
            return self._error(mid, -32602, str(e))
        except Exception:                       # a defect in this server: say so, keep serving
            traceback.print_exc(file=self.log)
            return self._error(mid, -32603, "Internal error")
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def _initialize(self, params):
        asked = params.get("protocolVersion")
        if not isinstance(asked, str):
            raise _Invalid("Invalid params: protocolVersion is missing")
        # The version asked for if this server has it, otherwise the latest it has (the client decides whether to go on).
        self.version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        info = {"name": SERVER_NAME, "version": SERVER_VERSION}
        if self.version >= "2025-06-18":
            info["title"] = "verified-libs: embedded ring buffers and CRC, measured"
        if self.version >= "2025-11-25":
            info["websiteUrl"] = SITE
        return {"protocolVersion": self.version, "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": info, "instructions": INSTRUCTIONS}

    def _call(self, params):
        name, args = params.get("name"), params.get("arguments", {})
        if not isinstance(name, str) or name not in TOOLS:
            raise _Invalid(f"Unknown tool: {name}")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise _Invalid("Invalid params: arguments must be an object")
        try:
            out = call_tool(self.D, self.prov, name, args)
        except ToolError as e:
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}
        result = {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}], "isError": False}
        if self.version >= "2025-06-18":
            result["structuredContent"] = out
        return result


class _Invalid(Exception):
    """A request this server cannot act on: JSON-RPC error -32602."""


def serve(session, fin, fout):
    """Read messages line by line until the input closes. Only protocol messages go to fout."""
    def send(obj):
        fout.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
        fout.flush()

    for raw in fin:
        if not raw.strip():
            continue
        try:
            msg = json.loads(raw.decode("utf-8"))
        except ValueError:                       # includes text that is not UTF-8
            send(Session._error(None, -32700, "Parse error"))
            continue
        if isinstance(msg, list):                # a batch (protocol 2025-03-26 had them)
            out = [r for r in (session.handle(m) for m in msg) if r is not None] if msg else \
                  Session._error(None, -32600, "Invalid Request: empty batch")
            if out:
                send(out)
        else:
            r = session.handle(msg)
            if r is not None:
                send(r)


def main(argv):
    data_path, crc_path, pools_path, call, show_tools = None, None, None, None, False
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--data" and args:
            data_path = args.pop(0)
        elif a == "--crc-data" and args:
            crc_path = args.pop(0)
        elif a == "--pools-data" and args:
            pools_path = args.pop(0)
        elif a == "--call" and args:
            call = (args.pop(0), args.pop(0) if args and not args[0].startswith("--") else "{}")
        elif a == "--tools":
            show_tools = True
        else:
            print(__doc__.strip(), file=sys.stderr)
            return 2
    try:
        D, prov = q.load(data_path)
        C, cprov = crc_data(crc_path)
        P, pprov = pt.pools_data(pools_path)
    except (OSError, ValueError) as e:
        print(f"verified-libs MCP server: cannot read the data: {e}", file=sys.stderr)
        return 1
    if show_tools:
        print(json.dumps(tool_list(D), ensure_ascii=False, indent=1))
        return 0
    if call:
        try:
            out = call_tool(D, prov, call[0], json.loads(call[1]))
        except KeyError:
            print(f"Unknown tool: {call[0]}. Tools: {', '.join(TOOLS)}.", file=sys.stderr)
            return 2
        except (ToolError, ValueError) as e:
            print(e, file=sys.stderr)
            return 2
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    print(f"verified-libs MCP server {SERVER_VERSION}: ring buffers {len(D['libs'])} configurations, {len(D['boards'])} boards, "
          f"data sha256 {prov['sha256'][:12]}; CRC {len(C['configurations'])} configurations, {len(C['boards'])} boards, "
          f"data sha256 {cprov['sha256'][:12]}; pools {len(P['configurations'])} configurations, {len(P['boards'])} boards, "
          f"data sha256 {pprov['sha256'][:12]}; waiting for an MCP client on stdin", file=sys.stderr)
    try:
        serve(Session(D, prov), sys.stdin.buffer, sys.stdout.buffer)
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
