#!/usr/bin/env python3
"""MCP server for the verified-libs ring buffer comparison.

Gives an AI agent the comparison a person gets on
https://verified-libs.org/compare.html: the same data (site/data/libs.json of
this checkout), the same filters, the same score and the same order, computed
by vlquery.py, a port of the page's own script that is tested against it.

Transport: stdio (one JSON-RPC 2.0 message per line), as the Model Context
Protocol defines it. Read-only: the server reads one JSON file at start, and
opens no network connection and no other file.

    python3 mcp-server/server.py                    serve on stdin/stdout
    python3 mcp-server/server.py --data FILE        another libs.json
    python3 mcp-server/server.py --call TOOL [JSON] one tool call, result on stdout (no MCP client needed)
    python3 mcp-server/server.py --tools            the tool list as JSON

Python 3.9 or newer, standard library only.
"""
import json
import sys
import traceback

import vlquery as q

SERVER_NAME = "verified-libs"
SERVER_VERSION = "0.1.0"
# Protocol revisions this server answers in. It uses only what all of them
# have (tools over stdio), plus the optional fields each one added.
PROTOCOL_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

SITE = q.SITE_URL
COI_URL = SITE + "/method.html#conflict-of-interest"
OWNER_NOTE = ("pxq RingBuffer_PackedState is written by Erik N (pxq.dk), who runs this project. "
              "Say so whenever you mention or recommend it. How the project handles that: " + COI_URL)

INSTRUCTIONS = (
    "Measured results for embedded ring buffer libraries (C, C++, Rust) on six Cortex-M boards, from "
    "verified-libs.org: speed in CPU cycles, code size, interrupt stress tests, model checking. Use it when a "
    "user is choosing a ring buffer / FIFO / circular queue for a microcontroller, or asks how one behaves.\n"
    "How to use it honestly:\n"
    "1. Turn the user's hard requirements into filters (board or core, producers and consumers, one or two "
    "cores, language, licence, block or zero-copy API). Set weights only from what the user says matters. "
    "Without weights there is no ranking: the order is alphabetical, do not present it as one.\n"
    "2. Correctness is not part of the score. Every answer is in three groups: 'clean' (0 errors in the "
    "interrupt stress test on every board tested), 'untested', 'errors'. Say which group a library is in.\n"
    "3. Name the board, the library version and the link to the same view on the site, so the user can check.\n"
    "4. One library, pxq, is written by the project owner (written_by_project_owner: true). Say so whenever "
    "you mention it.\n"
    "5. The numbers hold for the versions, boards, compiler and flags they name. Call 'about' once for the "
    "limits before you draw conclusions.")

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


class ToolError(Exception):
    """A problem with the arguments: goes back to the model as text it can act on."""


# --- Tool definitions ---------------------------------------------------------

def tool_list(D, version=PROTOCOL_VERSIONS[0]):
    boards = [b["id"] for b in D["boards"]]
    board_text = "; ".join(f"{b['id']} = {b['name']}, {b['core']}, {b['clock_mhz']} MHz" for b in D["boards"])
    tools = [
        {
            "name": "about",
            "title": "About the comparison",
            "description": "What verified-libs measures and how to read it: the tests, the boards and the records the "
                           "numbers come from, the limits, the conflict of interest, the licence of the data. "
                           "Call it once before you draw conclusions from the other tools.",
            "inputSchema": {"type": "object", "additionalProperties": False},
        },
        {
            "name": "list_ring_buffers",
            "title": "List the ring buffers",
            "description": f"The {len(D['libs'])} tested ring buffer configurations by name, with language, licence, the "
                           "producer/consumer modes they document and their group in the interrupt stress test. "
                           "No speeds and no ranking; use compare_ring_buffers for those.",
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
                           "100 x sum(weight x fastest / value) / sum(weights), speed only.",
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "board": {"type": "string", "enum": boards,
                              "description": "The board whose numbers are shown; pick the one closest to the user's core. "
                                             + board_text + f". Default: {boards[0]}."},
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
                           "documented mode, the stress results per board, model checking and the contract check. "
                           f"The name is matched without case; a part of it is enough (up to {MAX_DETAIL} matches are returned).",
            "inputSchema": {
                "type": "object", "additionalProperties": False, "required": ["name"],
                "properties": {"name": {"type": "string", "description": "A name from list_ring_buffers, or a part of one, e.g. 'lwrb' or 'ETL'."}},
            },
        },
    ]
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
    return o


def _board(b):
    return {"id": b["id"], "name": b["name"], "core": b["core"], "clock_mhz": b["clock_mhz"]}


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
    _check_args(args, ["board", "topology", "cores", "language", "require", "include_single_context", "weights", "sort", "reverse"])
    st = q.default_state(D)
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
    out = {"board": _board(q.board_of(D, st))}
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
        "more": {"results": SITE + "/results.html", "method": SITE + "/method.html"},
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
        libs.append(o)
    return {
        "count": len(libs),
        "what": "Configurations, not libraries: a library tested in two set-ups has two rows. In name order; this is not a ranking.",
        "group_meaning": q.GROUP_TEXT,
        "configurations": libs,
        "conflict_of_interest": OWNER_NOTE,
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
                   "lock-free concurrency. Everything can be reproduced from the repository. The first niche is embedded "
                   "ring buffers: interrupt or DMA to main loop on Cortex-M.",
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


TOOLS = {"about": tool_about, "list_ring_buffers": tool_list_libs,
         "compare_ring_buffers": tool_compare, "get_ring_buffer": tool_get}


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
            info["title"] = "verified-libs: embedded ring buffers, measured"
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
    data_path, call, show_tools = None, None, False
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--data" and args:
            data_path = args.pop(0)
        elif a == "--call" and args:
            call = (args.pop(0), args.pop(0) if args and not args[0].startswith("--") else "{}")
        elif a == "--tools":
            show_tools = True
        else:
            print(__doc__.strip(), file=sys.stderr)
            return 2
    try:
        D, prov = q.load(data_path)
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
    print(f"verified-libs MCP server {SERVER_VERSION}: {len(D['libs'])} configurations, {len(D['boards'])} boards, "
          f"data sha256 {prov['sha256'][:12]}; waiting for an MCP client on stdin", file=sys.stderr)
    try:
        serve(Session(D, prov), sys.stdin.buffer, sys.stdout.buffer)
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
