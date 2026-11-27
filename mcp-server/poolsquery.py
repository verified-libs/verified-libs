#!/usr/bin/env python3
"""The pools comparison of verified-libs.org/compare-pools.html, in Python: a
port of the page's own script (site/compare-pools.js), tested against it
(tests/test_parity_pools.py), over the same data (site/data/pools.json,
written by site/pools_data.py from records/pools). The MCP server's pools
tools use it.

No ranking of ours: without weights the rows are in the order of the
configuration list (or sorted by name or an exact column, flash or RAM
bytes); with the reader's weights they are ordered by a score that is a
range. The cycles are ranges over eight placements of the code; two rows
differ only where their ranges do not overlap (compared as the page shows
the numbers). Our reference free list with interrupts off (role "ours": not
a library) is a row of the same table, labelled in its name cell every
time; with weights it is scored like any row, and the filter on the kind of
row leaves it out. What each library documents about use from interrupts is
shown as documented, not tested, and used in no filter and no score. The
reference free list, the baseline, stays apart, last.

Python 3.9 or newer, standard library only.
"""
import functools
import hashlib
import json
import math
import os
import re
import urllib.parse

import vlquery as q

REPO = "https://github.com/verified-libs/verified-libs/blob/main/"
SCENS = ["pair", "pair_full", "fill_drain_lifo", "fill_drain_fifo", "mixed", "empty"]
SORTS = ["name", "flash", "ram"]
SORT_TEXT = {"name": "name", "flash": "flash bytes", "ram": "RAM bytes"}
LANGS = ["C", "C++", "Rust"]
KINDS = ["library", "ours"]
WEIGHTS = [("alloc", "Cycles, one alloc"), ("free", "Cycles, one free"), ("bytes", "Bytes, flash + RAM")]
WEIGHT_IDS = [m for m, _ in WEIGHTS]
ABOVE_TEXT = "overlaps above"
OURS_LABEL = "our reference free list with interrupts off; not a library"
BASE_TEXT = "Reference free list (baseline), not a library"
BASE_NAME = "reference free list (ours)"
NOT_PUBLISHED = ("The first board series of this kind is not published yet: there are no records, so there is nothing "
                 "to compare.")
CLAIM_HEADER = "Documented use from interrupts (not tested)"


def default_data_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site", "data", "pools.json")


def load(path=None):
    """Read pools.json. Returns (data, provenance)."""
    path = path or default_data_path()
    with open(path, "rb") as fh:
        raw = fh.read()
    data = json.loads(raw.decode("utf-8"))
    if data.get("schema") != "pools-data/1":
        raise ValueError(f"{path}: not the pools data of site/pools_data.py (schema pools-data/1)")
    prov = {"file": os.path.basename(path), "sha256": hashlib.sha256(raw).hexdigest()}
    marker = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(path)))), "EXPORTED_FROM")
    if os.path.isfile(marker):
        with open(marker) as fh:
            prov["exported_from_commit"] = fh.read().strip()[:40]
    return data, prov


# --- The page's formatting ----------------------------------------------------

def range_text(r, f):
    if not r:
        return "–"
    a, b = f(r[0]), f(r[1])
    return a if a == b else a + "–" + b


def shown_cycles(r):
    return [math.floor(r[0] + 0.5), math.floor(r[1] + 0.5)] if r else None


def overlap(a, b):
    return bool(a) and bool(b) and a[0] <= b[1] and b[0] <= a[1]


def score_overlap(a, b):
    """The score's marks are judged on the score before rounding (closed ranges), as compare-pools.js."""
    return overlap(a, b)


def score_text(r):
    return range_text(r, q.dec1) if r else "–"


# --- State and address ----------------------------------------------------------

def default_state(P):
    return {"board": P["boards"][0]["id"] if P["boards"] else "", "scen": "pair", "cache": "on", "lang": "", "kind": "",
            "sort": "", "dir": 1, "row": "", "w": {m: 0 for m in WEIGHT_IDS}}


def is_ours(c):
    return c.get("role") == "ours"


def _dec(v):
    """decodeURIComponent, or None where it would throw."""
    if re.search(r"%(?![0-9A-Fa-f]{2})", v):
        return None
    try:
        return urllib.parse.unquote(v, errors="strict")
    except UnicodeDecodeError:
        return None


def _enc(v):
    """encodeURIComponent."""
    return urllib.parse.quote(v, safe="-_.!~*'()")


def tidy(P, st):
    """What the page drops: a chosen configuration that is not measured on the chosen board."""
    if not row_of(P, st["board"], st["row"]):
        st["row"] = ""
    return st


def state_from_hash(P, fragment):
    st = default_state(P)
    frag = fragment[1:] if fragment.startswith("#") else fragment
    for kv in frag.split("&"):
        p = kv.split("=")
        k, v = p[0], _dec(p[1] if len(p) > 1 else "")
        if v is None:
            continue
        if k == "board" and any(b["id"] == v for b in P["boards"]):
            st["board"] = v
        elif k == "scen" and v in SCENS:
            st["scen"] = v
        elif k == "cache" and v in ("on", "off"):
            st["cache"] = v
        elif k == "lang" and v in LANGS:
            st["lang"] = v
        elif k == "kind" and v in KINDS:
            st["kind"] = v
        elif k == "sort":
            s = v[1:] if v.startswith("-") else v
            if s in SORTS:
                st["sort"], st["dir"] = s, (-1 if v.startswith("-") else 1)
        elif k == "row":
            st["row"] = v
        elif k == "w":
            for i, x in enumerate(v.split(",")):
                if i < len(WEIGHT_IDS):
                    st["w"][WEIGHT_IDS[i]] = max(0, min(10, q._parse_int(x)))
    return tidy(P, st)


def hash_of(st):
    parts = ["board=" + st["board"], "scen=" + st["scen"], "cache=" + st["cache"]]
    if weighted(st):
        parts.append("w=" + ",".join(str(st["w"][m]) for m in WEIGHT_IDS))
    if st["lang"]:
        parts.append("lang=" + _enc(st["lang"]))
    if st["kind"]:
        parts.append("kind=" + st["kind"])
    if st["sort"]:
        parts.append("sort=" + ("-" if st["dir"] < 0 else "") + st["sort"])
    if st["row"]:
        parts.append("row=" + _enc(st["row"]))
    return "#" + "&".join(parts)


def view_url(st):
    return q.SITE_URL + "/compare-pools.html" + hash_of(st)


# --- Rows -------------------------------------------------------------------------

def row_of(P, board, adapter):
    for r in P["rows"]:
        if r["board"] == board and r["adapter"] == adapter:
            return r
    return None


def baseline_of(P, st):
    for b in P["baseline"]:
        if b["board"] == st["board"]:
            return b
    return None


def board_of(P, st):
    return next(b for b in P["boards"] if b["id"] == st["board"])


def cyc(st, r, op):
    return r["cycles"][st["cache"]]["init" if op == "init" else st["scen"] + "/" + op]


def weighted(st):
    return any(st["w"][m] > 0 for m in WEIGHT_IDS)


def bytes_of(r):
    return None if r["flash_bytes"] is None or r["ram_bytes"] is None else r["flash_bytes"] + r["ram_bytes"]


def values_of(st, r):
    b = bytes_of(r)
    return {"alloc": cyc(st, r, "alloc"), "free": cyc(st, r, "free"), "bytes": None if b is None else [b, b]}


def score(st, xs):
    """The score as on the other comparison pages, as a range (compare-pools.js, score): x["score"] = [lowest, highest]."""
    wsum = sum(st["w"][m] for m in WEIGHT_IDS)
    best = {}
    for m in WEIGHT_IDS:
        for x in xs:
            v = values_of(st, x["r"])[m]
            if v and v[0] > 0 and (best.get(m) is None or v[0] < best[m]):
                best[m] = v[0]
    for x in xs:
        lo = hi = 0
        v = values_of(st, x["r"])
        for m in WEIGHT_IDS:
            if not st["w"][m] or not v[m] or not v[m][0] > 0:
                continue
            lo += st["w"][m] * best[m] / v[m][1]
            hi += st["w"][m] * best[m] / v[m][0]
        x["score"] = [100 * lo / wsum, 100 * hi / wsum]


def shown(P, st):
    """(all, rows): the configurations measured on the chosen board, and those the filters keep, in list order or
    sorted. Each item: {"c": configuration, "r": row, "i": list index}."""
    every = []
    for i, c in enumerate(P["configurations"]):
        r = row_of(P, st["board"], c["adapter"])
        if r:
            every.append({"c": c, "r": r, "i": i})
    out = [x for x in every if not (st["lang"] and x["c"]["lang"] != st["lang"])
           and not (st["kind"] and x["c"].get("role") != st["kind"])]
    if weighted(st):
        score(st, out)
    if not st["sort"] and weighted(st):
        def by_score(a, b):
            c = b["score"][1] - a["score"][1]
            return (c > 0) - (c < 0) or a["i"] - b["i"]
        out = sorted(out, key=functools.cmp_to_key(by_score))
    if st["sort"]:
        def cmp(a, b):
            if st["sort"] == "name":
                c = st["dir"] * q.locale_compare(a["c"]["name"], b["c"]["name"])
            else:
                k = "flash_bytes" if st["sort"] == "flash" else "ram_bytes"
                x, y = a["r"][k], b["r"][k]
                if x is None and y is None:
                    c = 0
                elif x is None:
                    return 1
                elif y is None:
                    return -1
                else:
                    c = st["dir"] * (x - y)
                    c = (c > 0) - (c < 0)
            return c or a["i"] - b["i"]
        out = sorted(out, key=functools.cmp_to_key(cmp))
    return every, out


def chosen_of(st, rs):
    for x in rs:
        if x["c"]["adapter"] == st["row"]:
            return x
    return None


def overlaps(st, rs, base, x):
    """Per column (init, alloc, free), the names of the other rows (the baseline included) whose range overlaps x's,
    as shown; with weights also the rows whose score overlaps x's (the baseline has no score)."""
    out = {"init": [], "alloc": [], "free": []}
    if weighted(st) and "score" in x:
        out["score"] = [y["c"]["name"] for y in rs if y is not x and score_overlap(x["score"], y["score"])]
    others = [(y["c"]["name"], y["r"]) for y in rs if y is not x] + ([(BASE_NAME, base)] if base else [])
    for op in ("init", "alloc", "free"):
        mine = shown_cycles(cyc(st, x["r"], op))
        out[op] = [name for name, r in others if overlap(mine, shown_cycles(cyc(st, r, op)))]
    return out


def header(st):
    def h(key, text):
        return text + (" ↓" if st["dir"] < 0 else " ↑") if st["sort"] == key else text
    return ([h("name", "Configuration")] + (["Score (your weights)"] if weighted(st) else [])
            + ["Library", "Version", "Lang.", "Lock as built", h("flash", "Flash bytes"), h("ram", "RAM bytes"),
               "Cycles, init", "Cycles, alloc (" + st["scen"] + ")", "Cycles, free (" + st["scen"] + ")", CLAIM_HEADER])


def _nb(v):
    return "–" if v is None else q.num(v)


def claim_cell(c):
    d = c.get("documented_interrupts")
    return [d["text"] if d else "–"] + (["source: " + d["source"]] if d and d.get("source") else [])


def scenario_text(P, st):
    return next(s["text"] for s in P["scenarios"] if s["key"] == st["scen"])


def page_view(P, st):
    """What the page shows: header, rows (cell texts), separators, count, note, source."""
    if not P["published"]:
        return {"header": [], "rows": [], "seps": [], "count": NOT_PUBLISHED, "note": "", "src": ""}
    every, rs = shown(P, st)
    base = baseline_of(P, st)
    ch = chosen_of(st, rs)
    wd = weighted(st)
    cs = ch["score"] if ch and wd else None
    by_score = wd and not st["sort"]

    def numbers(r, is_chosen):
        out = []
        for op in ("init", "alloc", "free"):
            cell = [range_text(cyc(st, r, op), q.num)]
            if ch and not is_chosen and overlap(shown_cycles(cyc(st, ch["r"], op)), shown_cycles(cyc(st, r, op))):
                cell.append("overlaps")
            out.append(cell)
        return out

    rows, seps = [], []
    for j, x in enumerate(rs):
        c, r = x["c"], x["r"]
        first = [c["name"], "record"] + ([OURS_LABEL] if is_ours(c) else []) + (["chosen"] if x is ch else [])
        sc = []
        if wd:
            sc = [score_text(x["score"])]
            if by_score and j > 0 and score_overlap(rs[j - 1]["score"], x["score"]):
                sc.append(ABOVE_TEXT)
            if cs and x is not ch and score_overlap(cs, x["score"]):
                sc.append("overlaps")
        rows.append([first] + ([sc] if wd else [])
                    + [["–" if c["library"] is None else c["library"]], ["–" if c["pin"] is None else c["pin"]], [c["lang"]],
                       ["–" if c["lock"] is None else c["lock"]], [_nb(r["flash_bytes"])], [_nb(r["ram_bytes"])]]
                    + numbers(r, x is ch) + [claim_cell(c)])
    if base:
        seps.append([len(rows), BASE_TEXT])
        rows.append([[s] for s in (BASE_NAME,) + (("–",) if wd else ()) + ("–", "–", "C", "none", "–", "–")]
                    + numbers(base, False) + [claim_cell({"documented_interrupts": P.get("baseline_documented")})])
    count = (f"{len(rs)} of {len(every)} rows shown, "
             + ("sorted by " + SORT_TEXT[st["sort"]] + (", descending" if st["dir"] < 0 else "") if st["sort"]
                else "ordered by the score of your weights, its highest end first; a score marked “overlaps above” "
                     "is not told apart from the row above by this series" if wd
                else "in the order of the configuration list; this is not a ranking")
             + (". The chosen configuration is not shown: nothing is marked" if st["row"] and not ch else "") + ".")
    bd = board_of(P, st)
    note = " ".join(t for t in ("SYNTHETIC: " + P["SYNTHETIC"] + "." if P.get("SYNTHETIC") else "",
                                st["scen"] + ": " + scenario_text(P, st) + ".",
                                "No block is freed in this scenario." if st["scen"] == "empty" else "",
                                bd["note_cache_off"] if st["cache"] == "off" and bd.get("note_cache_off") else "") if t)
    src = (f"{bd['name']} ({bd['core']}, {math.floor(bd['clock_hz'] / 1e6 + 0.5)} MHz). Records: {P['source']['records']}, "
           f"series at commit {', '.join(P['source']['commits'])}, toolchain {', '.join(P['source']['toolchain_image'])}. "
           "Each number is the mean of the scenario's calls, the first included, in cycles less the counter-read overhead, "
           "as min–max over the eight placements, first pass; init is one call.")
    return {"header": header(st), "rows": rows, "seps": seps, "count": count, "note": note, "src": src}
