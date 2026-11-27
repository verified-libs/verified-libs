#!/usr/bin/env python3
"""The MCP server's tools for the fixed-block memory pools kind:
list_pool_configurations and compare_pools, over site/data/pools.json
(site/pools_data.py), with poolsquery.py, the port of the comparison page's
own script (site/compare-pools.js, tested against it). server.py registers
them; the other tools do not change.

The cycles are measured in one context: what a library documents about use
from interrupts is given as documented and used in no score. Where the data
holds records of the concurrency series, what it observed is given beside
it, with a filter on it (never a score), and the notes say so. Until the first board series is published the data holds no
records, and both tools say so.

Python 3.9 or newer, standard library only.
"""
import poolsquery as pq
import vlquery as q

SITE = q.SITE_URL
SORTS = {"list": "", "name": "name", "flash_bytes": "flash", "ram_bytes": "ram"}
WEIGHTS = {"alloc": "alloc", "free": "free", "bytes": "bytes"}
KINDS = {"library": "library", "ours": "ours"}
ONE_CONTEXT = ("Measured in one context. Use from interrupts is not tested in this series; "
               "documented_use_from_interrupts is what each library documents, with its source: NOT tested here, and used "
               "in no filter and no score; do not present it as a result.")
# With records of the concurrency series (site/pools_isr.py, the data's "isr"): the first note says so instead.
ISR_CONTEXT = ("Use from interrupts was tested in a series of its own, the concurrency series (an interrupt at every cycle "
               "of a call, every board, with controls that must be caught; " + q.SITE_URL + "/method-pools.html"
               "#use-from-interrupts). use_from_interrupts_observed says what it observed, in its classes: 'within' the "
               "library's documentation (passed, or a finding), 'ours', 'outside' its documentation (the library was used "
               "in a way it does not document: only what was observed, never call it failing), and 'control' (our "
               "control, which must be caught). It is part of no score; use_from_interrupts 'passed' keeps the rows that "
               "passed within their documentation (and ours). documented_use_from_interrupts is each library's own words. "
               "The cycles are of one context.")
NOTES = [
    ONE_CONTEXT,
    "Every number is the range (min, max) over eight placements of the code, first pass. Two rows differ only where "
    "their ranges do not overlap; 'overlaps' names, per number, the rows whose range overlaps this row's (as the page "
    "shows the numbers: whole cycles).",
    "cycles: the mean of the scenario's calls (the first included) in CPU cycles, less the counter-read overhead; init "
    "is one call. One pool shape: 32 blocks of 32 bytes.",
    "The rows are in the order of the configuration list (or sorted by name, flash or RAM bytes): this is not a ranking.",
    "flash_bytes: the library's and the adapter's code and constant data at -O2, measured in the board's images; "
    "ram_bytes: what the pool needs beyond the 32 blocks of 32 bytes and their canaries.",
    "A row with ours_not_a_library is our reference free list with interrupts off around each call: the price of the "
    "simplest lock on the core, not a library. It is scored like any row; kind 'library' leaves it out.",
    "The reference free list (baseline) is our free list without a lock, timed in the same images; it is not a library.",
    "Every call was checked on the board (a block given exactly when one is free, in the pool, aligned, not given "
    "twice, its contents and the pool's canaries intact), so correctness is not a weight.",
    "The second pass and the minimum, maximum and first call of each scenario are in the record of each row.",
]
NOT_PUBLISHED = ("The first board series of the fixed-block memory pools is not published yet: there are no records, "
                 "so there are no numbers. The method is at " + SITE + "/method-pools.html.")
_P = {}


class ToolError(Exception):
    """A problem with the arguments (server.py turns it into its own ToolError)."""


def pools_data(path=None):
    """The pools data (site/data/pools.json), read once: (data, provenance)."""
    if "data" not in _P or path:
        _P["data"] = pq.load(path)
    return _P["data"]


def tool_defs():
    P = pools_data()[0]
    isr_arg = {"use_from_interrupts": {
        "type": "string", "enum": ["any", "passed"], "default": "any",
        "description": "'passed': only the rows that passed the concurrency series within their documentation (and our "
                       "row). A filter, never a score."}} if pq.has_isr(P) else {}
    boards = [b["id"] for b in P["boards"]]
    board = {"type": "string", "description": "The board whose numbers are shown; pick the one closest to the user's core. "
             + ("; ".join(f"{b['id']} = {b['name']}, {b['core']}" for b in P["boards"]) + f". Default: {boards[0]}."
                if boards else "No board yet: the first series is not published.")}
    if boards:
        board["enum"] = boards
    return [
        {
            "name": "list_pool_configurations",
            "title": "List the fixed-block memory pool configurations",
            "description": "The tested configurations of fixed-block memory pool libraries (one pool of one block size: "
                           "alloc and free), with library, version, language, licence, the lock as built and what each "
                           "library documents about use from interrupts (documented; what the concurrency series "
                           "observed is in compare_pools), and our reference free list with interrupts off (not a library). No numbers and no "
                           "ranking; use compare_pools for those.",
            "inputSchema": {"type": "object", "additionalProperties": False},
        },
        {
            "name": "compare_pools",
            "title": "Compare fixed-block memory pool configurations",
            "description": "The comparison table of verified-libs.org/compare-pools.html for one board, scenario and "
                           "cache: every configuration with cycles of init, alloc and free as ranges over eight code "
                           "placements, flash and RAM bytes, the lock as built, what the library documents about "
                           "interrupts and, where the concurrency series has records, what it observed (never a score), "
                           "and the link to its record; our row with interrupts off labelled; the reference free list "
                           "(baseline) last. Cycles measured in one context. Overlaps name the rows not "
                           "told apart. Optional weights give a score range; without them there is no ranking.",
            "inputSchema": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "board": board,
                    "scenario": {"type": "string", "enum": pq.SCENS, "default": "pair",
                                 "description": "pair: alloc then free, the pool almost empty; pair_full: the same with 31 "
                                                "of 32 blocks held; fill_drain_lifo / fill_drain_fifo: 32 allocs, then 32 "
                                                "frees in reverse / the same order; mixed: a fixed-seed sequence, 25-75 % "
                                                "full; empty: alloc on an exhausted pool (no free)."},
                    "cache": {"type": "string", "enum": ["on", "off"], "default": "on"},
                    "language": {"type": "string", "enum": ["any"] + pq.LANGS, "default": "any"},
                    "kind": {"type": "string", "enum": ["any"] + list(KINDS), "default": "any",
                             "description": "Kind of row: 'library', or 'ours' (our reference free list with interrupts "
                                            "off; not a library). 'library' gives the scores without our row."},
                    "weights": {"type": "object", "additionalProperties": False,
                                "properties": {k: {"type": "integer", "minimum": 0, "maximum": 10} for k in WEIGHTS},
                                "description": "How much each value matters to the user, 0 (ignore) to 10: cycles of one "
                                               "alloc and of one free in the scenario, bytes of flash and RAM together. "
                                               "With a weight above 0 each row gets a score range (as the page) and the "
                                               "rows are ordered by its highest end; leave out for no ranking."},
                    "sort": {"type": "string", "enum": list(SORTS), "default": "list",
                             "description": "'list' (default): the order of the configuration list, or with weights the "
                                            "score order. 'name', 'flash_bytes', 'ram_bytes': exact columns, which override "
                                            "the score order. Cycles are ranges and not sorted."},
                    "reverse": {"type": "boolean", "default": False},
                    **isr_arg,
                },
            },
        },
    ]


def _observed(s):
    """A row's result of the concurrency series as the tool gives it, or None (no record of the row)."""
    if not s:
        return None
    out = {"class": s["class"], "as_on_the_page": s["text"], "trials": s["trials"], "observed": s["observed"],
           "record": pq.REPO + s["record"]}
    if s.get("irq_wait_cycles"):
        out["longest_wait_of_an_interrupt_cycles"] = s["irq_wait_cycles"]
    return out


def _documented(c):
    d = c.get("documented_interrupts")
    return {"text": d["text"], "source": d["source"], "tested": False} if d else None


def tool_list_pools(args, check_args):
    check_args(args, [])
    P, prov = pools_data()
    out = {"published": P["published"]}
    if not P["published"]:
        out.update({"count": 0, "what": NOT_PUBLISHED, "data": prov})
        return out
    libs = [c for c in P["configurations"] if c["role"] == "library"]
    ours = [c for c in P["configurations"] if c["role"] == "ours"]
    out.update({
        "count": len(libs),
        "what": "Configurations of fixed-block memory pool libraries: one pool of 32 blocks of 32 bytes each, behind "
                "alloc and free. In the order of the configuration list; this is not a ranking.",
        "one_context": ISR_CONTEXT if pq.has_isr(P) else ONE_CONTEXT,
        "configurations": [{"name": c["name"], "library": c["library"], "language": c["lang"], "version": c["pin"],
                            "licence": c["licence"], "lock_as_built": c["lock"],
                            "documented_use_from_interrupts": _documented(c)} for c in libs],
        "ours": {"what": "Our reference free list with interrupts off around each call; not a library. Measured as the "
                         "configurations are, and shown in the same table, labelled, and scored like any row.",
                 "rows": [{"name": c["name"], "lock_as_built": c["lock"]} for c in ours]},
        "boards": [{"id": b["id"], "name": b["name"], "core": b["core"], "clock_mhz": round(b["clock_hz"] / 1e6)}
                   for b in P["boards"]],
        "more": {"compare": SITE + "/compare-pools.html", "results": SITE + "/results-pools.html",
                 "method": SITE + "/method-pools.html"},
        "data": prov})
    return out


def _arg_names(P):
    return ["board", "scenario", "cache", "language", "kind", "weights", "sort", "reverse"] + (
        ["use_from_interrupts"] if pq.has_isr(P) else [])


def state_from_args(P, args, check_args, choice, flag):
    """The page's state for a compare_pools call. Raises the server's ToolError on a bad argument."""
    check_args(args, _arg_names(P))
    st = pq.default_state(P)
    boards = [b["id"] for b in P["boards"]]
    st["board"] = choice(args, "board", boards, boards[0])
    st["scen"] = choice(args, "scenario", pq.SCENS, "pair")
    st["cache"] = choice(args, "cache", ["on", "off"], "on")
    lang = choice(args, "language", ["any"] + pq.LANGS, "any")
    st["lang"] = "" if lang == "any" else lang
    kind = choice(args, "kind", ["any"] + list(KINDS), "any")
    st["kind"] = "" if kind == "any" else KINDS[kind]
    w = args.get("weights", {})
    if not isinstance(w, dict):
        raise ToolError("'weights' must be an object, e.g. {\"alloc\": 5, \"free\": 5}.")
    check_args(w, list(WEIGHTS))
    for k, v in w.items():
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 10:
            raise ToolError(f"Weight '{k}' must be a whole number from 0 to 10. Got {v!r}.")
        st["w"][WEIGHTS[k]] = v
    if pq.has_isr(P):
        st["isr"] = "" if choice(args, "use_from_interrupts", ["any", "passed"], "any") == "any" else "passed"
    st["sort"] = SORTS[choice(args, "sort", list(SORTS), "list")]
    st["dir"] = -1 if flag(args, "reverse") else 1
    return st


def _rng(r):
    return {"min": r[0], "max": r[1]} if r else None


def tool_compare_pools(args, check_args, choice, flag):
    P, prov = pools_data()
    if not P["published"]:
        check_args(args, _arg_names(P))
        return {"published": False, "what": NOT_PUBLISHED, "rows": [], "data": prov}
    st = state_from_args(P, args, check_args, choice, flag)
    every, rs = pq.shown(P, st)
    base = pq.baseline_of(P, st)
    view = pq.page_view(P, st)
    bd = pq.board_of(P, st)
    wd, by_score = pq.weighted(st), pq.weighted(st) and not st["sort"]
    rows = []

    def numbers(r):
        return {op: _rng(pq.cyc(st, r, op)) for op in ("init", "alloc", "free")}

    def shown_text(r, x=None):
        out = {op: pq.range_text(pq.cyc(st, r, op), q.num) for op in ("init", "alloc", "free")}
        if x is not None:
            out["score"] = pq.score_text(x["score"])
        return out
    for j, x in enumerate(rs):
        c, r = x["c"], x["r"]
        ov = pq.overlaps(st, rs, base, x)
        o = {"name": c["name"]}
        if pq.is_ours(c):
            o.update({"ours_not_a_library": True, "note": c.get("note")})
        o.update({"library": c["library"], "version": c["pin"], "language": c["lang"], "licence": c["licence"],
                  "lock_as_built": c["lock"], "flash_bytes": r["flash_bytes"], "ram_bytes": r["ram_bytes"]})
        if wd:
            o["score"] = {"min": round(x["score"][0], 2), "max": round(x["score"][1], 2)}
        o.update({"cycles": numbers(r), "as_on_the_page": shown_text(r, x if wd else None),
                  "overlaps": {op: ov[op] for op in ("init", "alloc", "free")}})
        if wd:
            o["overlaps"]["score"] = ov["score"]
        if by_score and j > 0:
            o["score_not_told_apart_from_the_row_above"] = pq.score_overlap(rs[j - 1]["score"], x["score"])
        o["documented_use_from_interrupts"] = _documented(c)
        if pq.has_isr(P):
            o["use_from_interrupts_observed"] = _observed(r.get("isr"))
        o["record"] = pq.REPO + r["record"]
        rows.append(o)
    if base:
        brows = [{"c": {"name": pq.BASE_NAME}, "r": base}] + rs
        ov = pq.overlaps(st, brows, None, brows[0])
        rows.append({"name": pq.BASE_NAME, "reference_baseline_not_a_library": True, "lock_as_built": "none",
                     "cycles": numbers(base), "as_on_the_page": shown_text(base),
                     "overlaps": {op: ov[op] for op in ("init", "alloc", "free")}})
        if pq.has_isr(P):
            bi = next((x for x in P.get("baseline_isr", []) if x["board"] == st["board"]), None)
            rows[-1]["use_from_interrupts_observed"] = _observed(bi)
    out = {"published": True,
           "board": {"id": bd["id"], "name": bd["name"], "core": bd["core"], "clock_mhz": round(bd["clock_hz"] / 1e6)},
           "scenario": {"name": st["scen"], "what": pq.scenario_text(P, st)}, "cache": st["cache"]}
    if "board" not in args:
        out["board_note"] = ("No board was given, so these are the numbers of the first board. Pass the board closest to "
                             "the user's core: " + ", ".join(f"{b['id']} ({b['core']})" for b in P["boards"]) + ".")
    out["shown"] = view["count"]
    out["rows"] = rows
    notes = list(NOTES)
    if pq.has_isr(P):
        notes[0] = ISR_CONTEXT
        bn = (P["isr_source"].get("board_notes") or {}).get(bd["id"])
        if bn:
            notes.insert(1, bn)
    if wd:
        notes.insert(1, "Ordered by the score of the caller's weights (" + ", ".join(f"{k} {st['w'][m]}" for k, m in WEIGHTS.items())
                     + "), its highest end first" + (" (but sorted by an exact column, as asked)" if st["sort"] else "") +
                     ". The score is a range: per weighted value the smallest lower end among the rows shown divided by the "
                     "row's own value, the weighted mean times 100; its lowest end uses the row's upper ends, its highest end "
                     "the lower ends; bytes are exact; a value a row does not have (no free in 'empty') counts 0. "
                     "'score_not_told_apart_from_the_row_above' marks a score whose range overlaps the one above, judged "
                     "on the score before rounding (the page shows one decimal). The score does not judge correctness, "
                     "what a library documents about interrupts, language, licence, the lock or the API.")
    if view["note"]:
        notes.insert(1, view["note"])
    out["notes"] = notes
    out["source"] = view["src"]
    out["same_view_on_the_site"] = pq.view_url(st)
    out["data"] = prov
    return out
