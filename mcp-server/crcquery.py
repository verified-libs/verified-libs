#!/usr/bin/env python3
"""The CRC comparison of verified-libs.org/compare-crc.html, in Python: a port
of the page's own script (site/compare-crc.js), tested against it
(tests/test_parity_crc.py), over the same data (site/data/crc.json, written by
site/crc_data.py from records/crc). The MCP server's CRC tools use it.

No ranking of ours: without weights the rows are in the order of the
configuration list (or sorted by name or an exact column, flash or RAM bytes);
with the reader's weights they are ordered by a score that is a range. The
cycles are ranges over eight placements of the code; two rows differ only
where their ranges do not overlap (compared as the page shows the numbers).
The board's CRC unit (role "hardware": driven by our code, not a library) is a
row of the same table, after the libraries of its CRC, labelled in its name cell
every time; with weights it is scored like any row, and the filter on the kind
of row leaves it out (decided 2026-11-26). Nothing on a board without one, and a
line that says so. The reference stays apart, last.

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
LENS = ["4", "16", "64", "256", "1024"]
SORTS = ["name", "flash", "ram"]
SORT_TEXT = {"name": "name", "flash": "flash bytes", "ram": "RAM bytes"}
LANGS = ["C", "C++", "Rust"]
TABLES = ["flash", "RAM", "none"]
KINDS = ["library", "hardware"]
WEIGHTS = [("cyc", "Cycles, one call"), ("pb", "Cycles per byte"), ("bytes", "Bytes, flash + RAM")]
WEIGHT_IDS = [m for m, _ in WEIGHTS]
ABOVE_TEXT = "overlaps above"
BASELINE_TEXT = "Reference (baseline), not a library"
HW_LABEL = "the board\u2019s CRC unit, driven by our code; not a library"


def default_data_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site", "data", "crc.json")


def load(path=None):
    """Read crc.json. Returns (data, provenance)."""
    path = path or default_data_path()
    with open(path, "rb") as fh:
        raw = fh.read()
    data = json.loads(raw.decode("utf-8"))
    if data.get("schema") != "crc-data/2":
        raise ValueError(f"{path}: not the CRC data of site/crc_data.py (schema crc-data/2)")
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


def shown_per_byte(r):
    return [float(q.to_fixed(r[0], 1)), float(q.to_fixed(r[1], 1))] if r else None


def overlap(a, b):
    return bool(a) and bool(b) and a[0] <= b[1] and b[0] <= a[1]


def score_overlap(a, b):
    """The score's marks are judged on the score before rounding (closed ranges), so that a mark never says
    "not told apart" where the series tells the rows apart (compare-crc.js, scoreOverlap)."""
    return overlap(a, b)


def score_text(r):
    return range_text(r, q.dec1) if r else "–"


def table_where(t):
    return "RAM" if t.startswith("RAM") else "none" if t == "none" else "flash"


# --- State and address ----------------------------------------------------------

def default_state(C):
    return {"crc": C["crcs"][0], "board": C["boards"][0]["id"], "len": "16", "off": "0", "cache": "on",
            "lang": "", "cls": "", "tbl": "", "kind": "", "sort": "", "dir": 1, "row": "", "w": {m: 0 for m in WEIGHT_IDS}}


def configs_of(C, crc):
    """The rows of a CRC: its libraries in list order, then the board's CRC unit (crc.json holds them in that order)."""
    return [c for c in C["configurations"] if c["crc"] == crc]


def is_hardware(c):
    return c.get("role") == "hardware"


def classes_of(C, crc):
    out = []
    for c in configs_of(C, crc):
        if c["class"] not in out:
            out.append(c["class"])
    return out


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


def tidy(C, st):
    """What the page drops: a class or a chosen configuration that is not of the chosen CRC."""
    if st["cls"] not in classes_of(C, st["crc"]):
        st["cls"] = ""
    if not any(c["adapter"] == st["row"] for c in configs_of(C, st["crc"])):
        st["row"] = ""
    return st


def state_from_hash(C, fragment):
    st = default_state(C)
    frag = fragment[1:] if fragment.startswith("#") else fragment
    for kv in frag.split("&"):
        p = kv.split("=")
        k, v = p[0], _dec(p[1] if len(p) > 1 else "")
        if v is None:
            continue
        if k == "crc" and v in C["crcs"]:
            st["crc"] = v
        elif k == "board" and any(b["id"] == v for b in C["boards"]):
            st["board"] = v
        elif k == "len" and v in LENS:
            st["len"] = v
        elif k == "off" and v in ("0", "1"):
            st["off"] = v
        elif k == "cache" and v in ("on", "off"):
            st["cache"] = v
        elif k == "lang" and v in LANGS:
            st["lang"] = v
        elif k == "class":
            st["cls"] = v
        elif k == "table" and v in TABLES:
            st["tbl"] = v
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
    return tidy(C, st)


def hash_of(st):
    parts = ["crc=" + _enc(st["crc"]), "board=" + st["board"], "len=" + st["len"], "off=" + st["off"], "cache=" + st["cache"]]
    if weighted(st):
        parts.append("w=" + ",".join(str(st["w"][m]) for m in WEIGHT_IDS))
    if st["lang"]:
        parts.append("lang=" + _enc(st["lang"]))
    if st["cls"]:
        parts.append("class=" + _enc(st["cls"]))
    if st["tbl"]:
        parts.append("table=" + st["tbl"])
    if st["kind"]:
        parts.append("kind=" + st["kind"])
    if st["sort"]:
        parts.append("sort=" + ("-" if st["dir"] < 0 else "") + st["sort"])
    if st["row"]:
        parts.append("row=" + _enc(st["row"]))
    return "#" + "&".join(parts)


def view_url(st):
    return q.SITE_URL + "/compare-crc.html" + hash_of(st)


# --- Rows -------------------------------------------------------------------------

def row_of(C, board, adapter):
    for r in C["rows"]:
        if r["board"] == board and r["adapter"] == adapter:
            return r
    return None


def baseline_of(C, st):
    for b in C["baseline"]:
        if b["board"] == st["board"] and b["crc"] == st["crc"]:
            return b
    return None


def board_of(C, st):
    return next(b for b in C["boards"] if b["id"] == st["board"])


def cycles_of(st, r, length=None):
    return r["cycles"][st["cache"]][st["off"]][length or st["len"]]


def per_byte_of(st, r):
    return r["per_byte"][st["cache"]][st["off"]]


def weighted(st):
    return any(st["w"][m] > 0 for m in WEIGHT_IDS)


def bytes_of(r):
    return None if r["flash_bytes"] is None or r["ram_bytes"] is None else r["flash_bytes"] + r["ram_bytes"]


def values_of(st, r):
    b = bytes_of(r)
    return {"cyc": cycles_of(st, r), "pb": per_byte_of(st, r), "bytes": None if b is None else [b, b]}


def score(st, xs):
    """The score as on the ring buffers' page, as a range (compare-crc.js, score): x["score"] = [lowest, highest]."""
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


def shown(C, st):
    """(all, rows): the configurations of the chosen CRC measured on the chosen board, and those the
    filters keep, in list order or sorted. Each item: {"c": configuration, "r": row, "i": list index}."""
    every = []
    for i, c in enumerate(configs_of(C, st["crc"])):
        r = row_of(C, st["board"], c["adapter"])
        if r:
            every.append({"c": c, "r": r, "i": i})
    out = [x for x in every if not (st["lang"] and x["c"]["lang"] != st["lang"])
           and not (st["cls"] and x["c"]["class"] != st["cls"])
           and not (st["tbl"] and table_where(x["c"]["table"]) != st["tbl"])
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
    """Per metric, the names of the other rows (the baseline included) whose range overlaps x's, as shown;
    with weights also the rows whose score overlaps x's (the baseline has no score)."""
    out = {"cycles": [], "per_byte": []}
    if weighted(st) and "score" in x:
        out["score"] = [y["c"]["name"] for y in rs if y is not x and score_overlap(x["score"], y["score"])]
    xc, xp = shown_cycles(cycles_of(st, x["r"])), shown_per_byte(per_byte_of(st, x["r"]))
    others = ([(y["c"]["name"], y["r"]) for y in rs if y is not x]
              + ([("reference, bitwise", base)] if base else []))
    for name, r in others:
        if overlap(xc, shown_cycles(cycles_of(st, r))):
            out["cycles"].append(name)
        if overlap(xp, shown_per_byte(per_byte_of(st, r))):
            out["per_byte"].append(name)
    return out


def has_unit(every):
    """Whether the board has the CRC unit for the chosen CRC (before the filters)."""
    return any(is_hardware(x["c"]) for x in every)


def no_unit_text(bd, st):
    return f"No CRC unit of the {bd['name']} was measured for {st['crc']}: the table holds libraries only."


def header(st):
    def h(key, text):
        return text + (" ↓" if st["dir"] < 0 else " ↑") if st["sort"] == key else text
    return ([h("name", "Configuration")] + (["Score (your weights)"] if weighted(st) else [])
            + ["Library", "Lang.", "Class", "Table", h("flash", "Flash bytes"), h("ram", "RAM bytes"),
               "Cycles, " + st["len"] + " bytes", "Cycles per byte"])


def _nb(v):
    return "–" if v is None else q.num(v).replace(" ", " ")


def page_view(C, st):
    """What the page shows: header, rows (cell texts), separators, count, note, source."""
    every, rs = shown(C, st)
    base = baseline_of(C, st)
    ch = chosen_of(st, rs)
    cc = shown_cycles(cycles_of(st, ch["r"])) if ch else None
    cp = shown_per_byte(per_byte_of(st, ch["r"])) if ch else None
    wd = weighted(st)
    cs = ch["score"] if ch and wd else None
    by_score = wd and not st["sort"]

    def numbers(r, is_chosen):
        c1 = [range_text(cycles_of(st, r), q.num)]
        c2 = [range_text(per_byte_of(st, r), q.dec1)]
        if ch and not is_chosen and overlap(cc, shown_cycles(cycles_of(st, r))):
            c1.append("overlaps")
        if ch and not is_chosen and overlap(cp, shown_per_byte(per_byte_of(st, r))):
            c2.append("overlaps")
        return [c1, c2]

    rows, seps = [], []
    for j, x in enumerate(rs):
        c, r = x["c"], x["r"]
        first = [c["name"], "record"] + ([HW_LABEL] if is_hardware(c) else []) + (["chosen"] if x is ch else [])
        sc = []
        if wd:
            sc = [score_text(x["score"])]
            if by_score and j > 0 and score_overlap(rs[j - 1]["score"], x["score"]):
                sc.append(ABOVE_TEXT)
            if cs and x is not ch and score_overlap(cs, x["score"]):
                sc.append("overlaps")
        rows.append([first] + ([sc] if wd else []) + [["–" if c["library"] is None else c["library"]], [c["lang"]], [c["class"]], [c["table"]],
                     [_nb(r["flash_bytes"])], [_nb(r["ram_bytes"])]] + numbers(r, x is ch))
    if base:
        seps.append([len(rows), BASELINE_TEXT])
        rows.append([[s] for s in ("reference, bitwise",) + (("–",) if wd else ()) + ("–", "C", "bitwise", "none", "–", "–")]
                    + numbers(base, False))
    count = (f"{len(rs)} of {len(every)} rows of {st['crc']} shown, "
             + ("sorted by " + SORT_TEXT[st["sort"]] + (", descending" if st["dir"] < 0 else "") if st["sort"]
                else "ordered by the score of your weights, its highest end first; a score marked \u201coverlaps above\u201d "
                     "is not told apart from the row above by this series" if wd
                else "in the order of the configuration list; this is not a ranking")
             + (". The chosen configuration is not shown: nothing is marked" if st["row"] and not ch else "") + ".")
    bd = board_of(C, st)
    unit_shown = any(is_hardware(x["c"]) for x in rs)
    note = " ".join(t for t in (bd["note_cache_off"] if st["cache"] == "off" and bd.get("note_cache_off") else "",
                                bd["note_hw_unit"] if unit_shown and bd.get("note_hw_unit") else "",
                                "" if has_unit(every) else no_unit_text(bd, st)) if t)
    src = (f"{bd['name']} ({bd['core']}, {math.floor(bd['clock_hz'] / 1e6 + 0.5)} MHz). "
           + (bd["method_text"] + " " if bd.get("method_text") else "") + f"Records: {C['source']['records']}, "
           f"series at commit {', '.join(C['source']['commits'])}, toolchain {', '.join(C['source']['toolchain_image'])}. "
           "Each number is the mean of the scenario's 256 calls, the first included, as min–max over the eight placements, "
           "first pass; per byte from the means at 256 and 1024 bytes, at the chosen start.")
    return {"header": header(st), "rows": rows, "seps": seps, "count": count, "note": note, "src": src}
