#!/usr/bin/env python3
"""The comparison of site/compare.js as a Python module.

The website's comparison page (compare.html) and the MCP server must give the
same answer to the same question (PROJECT.md: "the same query for people and
AIs"). This module is therefore a line-by-line port of site/compare.js, not a
second design: the same filters, the same score, the same three groups, the
same order, and the same address of the view. tests/test_parity.py runs
site/compare.js itself and compares every cell of the table with this port.

When site/compare.js changes, this file changes with it, and the parity test
says where they differ.

Standard library only.
"""
import functools
import hashlib
import json
import math
import os
import re
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import quote, unquote

SITE_URL = "https://verified-libs.org"

# (id, label, as in compare.js)
METRICS = [("push", "1-byte push"), ("pop", "1-byte pop"), ("block", "64-byte block"),
           ("dma", "Zero-copy (DMA) transfer")]
METRIC_IDS = [m for m, _ in METRICS]
PERMISSIVE = re.compile(r"^(MIT|BSD-2-Clause|BSD-3-Clause|Apache-2\.0|CC0-1\.0)$")
FLAGS = ["clean", "permissive", "block", "zc", "genmc", "contract", "nounsafe", "nosingle"]
TOPOS = ["SPSC", "MPSC", "SPMC", "MPMC"]
LANGS = ["C", "C++", "Rust"]
# The sort keys the page's columns offer.
SORT_KEYS = ["name", "score", "license", "lang", "push", "pop", "block", "dma", "size", "stress"]
GROUP = {"clean": 0, "untested": 1, "errors": 2}
GROUP_TEXT = {
    "clean": "0 errors in the ISR stress test, on every board tested",
    "untested": "Not in the ISR stress campaign shown here",
    "errors": "Errors in the ISR stress test, on this or another board (listed after the rows above, whatever the order)",
}
COLS = [("name", "Library"), ("license", "License"), ("lang", "Lang."), ("push", "1 byte push"), ("pop", "1 byte pop"),
        ("block", "64-byte block, cycles/byte"), ("dma", "Zero-copy write / read, cycles"), ("size", "Code / RAM, bytes"),
        ("stress", "ISR stress errors, this board"), (None, "Two cores (Pico 2)"), (None, "GenMC (C11)"),
        (None, "One-core contract, every instruction")]
OWN_TEXT = "⚠ written by the project owner"


def default_data_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site", "data", "libs.json")


def load(path=None):
    """Read libs.json. Returns (data, provenance)."""
    path = path or default_data_path()
    with open(path, "rb") as fh:
        raw = fh.read()
    data = json.loads(raw.decode("utf-8"))
    for key in ("boards", "libs"):
        if not isinstance(data.get(key), list) or not data[key]:
            raise ValueError(f"{path}: no '{key}' list; not the comparison data of site/gen_libdata.py")
    prov = {"file": os.path.basename(path), "sha256": hashlib.sha256(raw).hexdigest()}
    # The public tree names the commit it was exported from (lab/tools/public-export.py).
    marker = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(path)))), "EXPORTED_FROM")
    if os.path.isfile(marker):
        with open(marker) as fh:
            prov["exported_from_commit"] = fh.read().strip()[:40]
    return data, prov


# --- JavaScript's formatting and ordering, reproduced -------------------------

def js_str(v):
    """String(v) for the values that occur in the data."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def to_fixed(n, digits):
    """Number.prototype.toFixed: the exact value, halves rounded up."""
    return str(Decimal(n).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def num(n):
    """Rounded to a whole number, thousands separated by a narrow no-break space (U+202F), as on the page."""
    return f"{math.floor(n + 0.5):,}".replace(",", "\u202f")


def dec1(n):
    return to_fixed(n, 1)


# The order of the printable ASCII characters in the root collation that
# String.prototype.localeCompare uses (CLDR root; checked against the engine in
# tests/test_parity.py). Letters follow, case-insensitive at the first level.
_PUNCT = " _-,;:!?.'\"()[]{}@*/\\&#%`^+<=>|~$0123456789"


def _coll_key(s):
    prim, case = [], []
    for ch in s:
        lo = ch.lower()
        if ch in _PUNCT:
            prim.append((0, _PUNCT.index(ch)))
            case.append(0)
        elif len(lo) == 1 and "a" <= lo <= "z":
            prim.append((1, ord(lo)))
            case.append(0 if ch == lo else 1)   # lower case first
        else:
            prim.append((2, ord(ch)))           # outside ASCII: by code point (none in the data today)
            case.append(0)
    return prim, case


def locale_compare(a, b):
    ka, kb = _coll_key(a), _coll_key(b)
    return (ka > kb) - (ka < kb)


def _parse_int(x):
    m = re.match(r"\s*([+-]?\d+)", x)
    return int(m.group(1)) if m else 0


# --- State: what the page keeps in the address --------------------------------

def has2(D):
    """Does the data hold benchmark version 2 (one image per configuration) for some board?"""
    return any(b.get("bench2") for b in D["boards"])


def default_state(D):
    return {"series": "2" if has2(D) else "1", "has2": has2(D),
            "boards2": [b["id"] for b in D["boards"] if b.get("bench2")], "board": D["boards"][0]["id"], "w": {m: 0 for m in METRIC_IDS}, "f": {"nosingle": True},
            "lang": "", "topo": "", "cores": "", "sort": "name", "dir": 1}


def weighted(st):
    return any(st["w"][m] > 0 for m in METRIC_IDS)


def state_from_hash(D, fragment):
    """The state the page is in after loading this address fragment (load() and readHash())."""
    st = default_state(D)
    st["sort"] = None
    for kv in re.sub(r"^#", "", fragment).split("&"):
        p = kv.split("=")
        k, v = p[0], unquote(p[1] if len(p) > 1 else "", errors="strict")
        if k == "board" and any(b["id"] == v for b in D["boards"]):
            st["board"] = v
        elif k == "w":
            for i, x in enumerate(v.split(",")):
                if i < len(METRIC_IDS):
                    st["w"][METRIC_IDS[i]] = max(0, min(10, _parse_int(x)))
        elif k == "f":
            for x in v.split(","):
                if x in FLAGS:
                    st["f"][x] = True
                elif x == "two":
                    st["cores"] = "2"
                elif x == "single":
                    st["f"]["nosingle"] = False
        elif k == "topo" and v in TOPOS:
            st["topo"] = v
        elif k == "cores" and v in ("1", "2"):
            st["cores"] = v
        elif k == "lang" and v in LANGS:
            st["lang"] = v
        elif k == "sort":
            st["sort"] = re.sub(r"^-", "", v)
            st["dir"] = -1 if v[:1] == "-" else 1
    if st["sort"] is None:      # an address with weights and no sort key is ranked by them
        st["sort"] = "score" if weighted(st) else "name"
        st["dir"] = 1
    if st["sort"] == "score" and not weighted(st):
        st["sort"] = "name"
    return st


def hash_of(st):
    """The address fragment the page writes for this state (writeHash())."""
    parts = ["board=" + st["board"]]
    w = [st["w"][m] for m in METRIC_IDS]
    if any(w):
        parts.append("w=" + ",".join(str(x) for x in w))
    f = [x for x in FLAGS if x != "nosingle" and st["f"].get(x)]
    if not st["f"].get("nosingle"):
        f.append("single")
    if f:
        parts.append("f=" + ",".join(f))
    if st["topo"]:
        parts.append("topo=" + st["topo"])
    if st["cores"]:
        parts.append("cores=" + st["cores"])
    if st["lang"]:
        parts.append("lang=" + quote(st["lang"], safe="-_.!~*'()"))
    if weighted(st) or st["sort"] != "name" or st["dir"] != 1:
        parts.append("sort=" + ("-" if st["dir"] < 0 else "") + st["sort"])
    return "#" + "&".join(parts)


def view_url(st):
    return SITE_URL + "/compare.html" + hash_of(st)


# --- The comparison ------------------------------------------------------------

def stress_state(lib):
    """Stress result over all boards: "clean", "errors" or "untested"."""
    runs = sum(s["runs"] for s in lib["stress"].values())
    errs = sum(s["errors"] for s in lib["stress"].values())
    return "errors" if errs else "clean" if runs else "untested"


def mp_mode(st):
    return st["topo"] if st["topo"] and st["topo"] != "SPSC" else ""


def contract_of(lib, st):
    c = lib.get("contract")
    return c.get(mp_mode(st) or "SPSC") if c else None


def two(st):
    """Is the view one of benchmark version 2? The page shows it for every board that has it; version 1
    (archived) is shown for a board without it, and where the server's `benchmark` argument asks for it
    (st["series"] == "1", which the page's address cannot say)."""
    return st.get("series") != "1" and st["board"] in st.get("boards2", ())


def speed_of(lib, st):
    """The speeds that apply to the chosen use: those of the mode, or the SPSC ones."""
    mode, key = mp_mode(st), "speed2" if two(st) else "speed"
    if not mode:
        return (lib.get(key) or {}).get(st["board"]) or None
    mp = lib.get("mp")
    if not mp or mode not in mp["modes"]:
        return None
    return ((mp.get(key) or {}).get(st["board"]) or {}).get(mode) or None


def size_of(lib, st):
    mode = mp_mode(st)
    if not mode:
        return (lib.get("size") or {}).get(st["board"]) or None
    mp = lib.get("mp")
    if not mp or not mp.get("size") or mode not in mp["modes"]:
        return None
    return (mp["size"].get(st["board"]) or {}).get(mode) or None


def metric(s, m):
    if m == "dma":
        w, r = s.get("dma_w"), s.get("dma_r")
        return (w + r) / 2 if w and r else None
    return s.get(m)


def fastest(D, st):
    """Per metric, the lowest value among ALL configurations on the board (in the chosen mode)."""
    best = {}
    for m in METRIC_IDS:
        for lib in D["libs"]:
            s = speed_of(lib, st)
            v = metric(s, m) if s else None
            if v and (not best.get(m) or v < best[m]):
                best[m] = v
    return best


def _keep(lib, st):
    mode = mp_mode(st)
    f = st["f"]
    s = speed_of(lib, st) or {}
    if lib.get("boards_only") and st["board"] not in lib["boards_only"]:
        return False     # tested on these boards only (its licence)
    if f.get("clean") and stress_state(lib) != "clean":
        return False
    if f.get("permissive") and not any(PERMISSIVE.match(x) for x in lib["license"].split(" OR ")):
        return False     # a dual licence counts if one choice is permissive
    if f.get("block") and not s.get("block"):
        return False
    if f.get("zc") and (not s.get("dma_w") if mode else not lib.get("zero_copy")):
        return False     # zero-copy is not timed in the MP modes
    if st["topo"] == "SPSC" or not st["topo"]:
        if st["topo"] and lib.get("single_context"):
            return False
        if st["cores"] == "2" and not lib.get("two_cores_documented"):
            return False
    else:
        if not lib.get("mp") or st["topo"] not in lib["mp"]["modes"]:
            return False
        if st["cores"] == "2" and lib["mp"]["cores"] < 2:
            return False
    if f.get("genmc") and not lib.get("genmc"):
        return False
    if f.get("contract") and not ((contract_of(lib, st) or {}).get("verdict") == "pass"):
        return False
    if f.get("nounsafe") and lib.get("unsafe_by_own_docs"):
        return False
    if f.get("nosingle") and lib.get("single_context"):
        return False
    if st["lang"] and lib["lang"] != st["lang"]:
        return False
    return True


def rows(D, st):
    """The rows of the table, filtered and scored, in the order of the data (not sorted yet)."""
    best = fastest(D, st)
    wsum = sum(st["w"][m] for m in METRIC_IDS)
    out = []
    for lib in D["libs"]:
        if not _keep(lib, st):
            continue
        s = speed_of(lib, st) or {}
        r = {"lib": lib, "s": s, "state": stress_state(lib), "score": None, "missing": [],
             "nomode": bool(mp_mode(st) and not speed_of(lib, st))}
        for m in METRIC_IDS:
            r[m] = metric(s, m)
        r["z"] = size_of(lib, st)
        r["size"] = r["z"]["flash"] if r["z"] else None
        if wsum:
            acc = 0
            for m, label in METRICS:
                if not st["w"][m]:
                    continue
                if r[m]:
                    acc += st["w"][m] * best[m] / r[m]
                else:
                    r["missing"].append(label)
            r["score"] = 100 * acc / wsum
        out.append(r)
    return out


def sort_rows(st, rs):
    k, d, w = st["sort"], st["dir"], weighted(st)

    def by_name(a, b):
        return locale_compare(a["lib"]["name"], b["lib"]["name"])

    def cmp(a, b):
        # Whatever the order, the table is in three groups: error-free, not tested, with errors.
        if GROUP[a["state"]] != GROUP[b["state"]]:
            return GROUP[a["state"]] - GROUP[b["state"]]
        if k == "score" and w:
            c = d * (b["score"] - a["score"])
            return (c > 0) - (c < 0) or by_name(a, b)
        if k in ("name", "license", "lang"):
            return d * locale_compare(a["lib"][k].lower(), b["lib"][k].lower()) or by_name(a, b)
        if k == "stress":
            x = (a["lib"]["stress"].get(st["board"]) or {}).get("errors")
            y = (b["lib"]["stress"].get(st["board"]) or {}).get("errors")
        elif k in ("push", "pop", "block", "dma", "size"):
            x, y = a[k], b[k]
        else:
            x = y = None
        if x is None and y is None:
            return by_name(a, b)
        if x is None:
            return 1            # no value: always last
        if y is None:
            return -1
        c = d * (x - y)
        return (c > 0) - (c < 0) or by_name(a, b)

    return sorted(rs, key=functools.cmp_to_key(cmp))


def compare(D, st):
    """Filtered, scored and sorted rows for a state."""
    return sort_rows(st, rows(D, st))


def board_of(D, st):
    return next(b for b in D["boards"] if b["id"] == st["board"])


# --- The texts of the page -------------------------------------------------------

def tags(D, st, r):
    """The lines under a library's name, as the page words them."""
    lib, mode, out = r["lib"], mp_mode(st), []
    if lib.get("own"):
        out.append(OWN_TEXT)
    if lib.get("stress_tested_commits"):
        out.append("ISR stress column: campaign tested an earlier commit (" +
                   ", ".join(lib["stress_tested_commits"]) + "), not " + js_str(lib["commit"]))
    if lib.get("boards_only"):
        names = [next((b["name"] for b in D["boards"] if b["id"] == i), i) for i in lib["boards_only"]]
        out.append("tested on " + ", ".join(names) + " only: " + js_str(lib.get("boards_only_why")))
    if lib.get("unsafe_by_own_docs"):
        out.append("not ISR-safe in this configuration by its own documentation")
    if lib.get("single_context"):
        out.append("single-context variant (no ISR safety claimed)")
    mp = lib.get("mp")
    if mp:
        if mode:
            tail = ("; not available on this board's core" if r["nomode"] else
                    "; speeds shown are for " + mode + ("" if mp.get("other_code") else " (the same code as SPSC)"))
        else:
            tail = "; speeds shown are for SPSC, choose a mode above for its speeds" if mp.get("other_code") else ""
        out.append("also " + ", ".join(mp["modes"]) + ": " + mp["via"] +
                   ("; one core" if mp["cores"] < 2 else "; also two cores") + tail)
    return out


def _speed_cell(v, rng, fmt):
    cell = [fmt(v) if v else "–"]
    if v and rng and fmt(rng[0]) != fmt(rng[1]):
        cell.append(fmt(rng[0]) + "–" + fmt(rng[1]))
    return cell


def _runs(n):
    return js_str(n) + (" runs" if n > 1 else " run")


def page_cells(D, st, r):
    """The texts of one table row, cell by cell, exactly as compare.html shows them."""
    lib, s = r["lib"], r["s"]
    cells = [[lib["name"], (lib["version"] + ", " if lib.get("version") else "") + js_str(lib["commit"])] + tags(D, st, r)]
    if weighted(st):
        c = [to_fixed(r["score"], 0)]
        if r["missing"]:
            c.append("no " + ", no ".join(r["missing"]))
        cells.append(c)
    cells.append([lib["license"]])
    cells.append([lib["lang"]])
    rg = s.get("range") or {}
    cells.append(_speed_cell(r["push"], rg.get("push"), num))
    cells.append(_speed_cell(r["pop"], rg.get("pop"), num))
    cells.append(_speed_cell(r["block"], rg.get("block"), dec1))
    c = [num(s["dma_w"]) + " / " + num(s["dma_r"]) if r["dma"] else "–"]
    w, rd = rg.get("dma_w"), rg.get("dma_r")
    if r["dma"] and w and rd and (num(w[0]) != num(w[1]) or num(rd[0]) != num(rd[1])):
        c.append(num(w[0]) + "–" + num(w[1]) + " / " + num(rd[0]) + "–" + num(rd[1]))
    cells.append(c)
    z = r["z"]
    c = [num(z["flash"]) + " / " + num(z["ram"]) if z else "–"]
    if z and z.get("heap"):
        c.append("+ heap")
    cells.append(c)
    sb = lib["stress"].get(st["board"])
    if not sb:
        c = ["not tested"]
    elif sb["errors"]:
        c = [num(sb["errors"]) + " in " + js_str(sb["runs_with_errors"]) + " of " + js_str(sb["runs"]) + " runs"]
    else:
        c = ["0", " in " + js_str(sb["runs"]) + " runs"]
        if r["state"] == "errors":
            c.append("errors on another board")
    if sb and sb.get("not_counted"):
        c.append(_runs(sb["not_counted"]) + " not counted: starved by the interrupt load")
    cells.append(c)
    sm = lib["smp"].get("pico2")
    if not sm:
        c = ["–"]
    elif not lib.get("two_cores_documented"):
        c = ["single-core design"]
    elif sm["errors"]:
        c = [num(sm["errors"]) + " in " + js_str(sm["runs_with_errors"]) + " of " + js_str(sm["runs"]) + " runs"]
    else:
        c = ["0", " in " + js_str(sm["runs"]) + " runs"]
    if sm and lib.get("two_cores_documented") and sm.get("not_counted"):
        c.append(_runs(sm["not_counted"]) + " not counted: starved")
    cells.append(c)
    cells.append([lib.get("genmc") or "–"])
    ct = contract_of(lib, st)
    if ct:
        c = [ct["verdict"], num(ct["trials"]) + " trials"]
        rc = lib["contract"].get("MPSC reserve/commit") if mp_mode(st) == "MPSC" else None
        if rc:
            c.append("reserve/commit: " + rc["verdict"] + ", " + num(rc["trials"]) + " trials")
    else:
        c = ["not claimed" if lib.get("single_context") else "–"]
    cells.append(c)
    return cells


def header(st):
    cols = [COLS[0], ("score", "Score (your weights)")] + COLS[1:] if weighted(st) else COLS
    return [label + ((" ▲" if st["dir"] > 0 else " ▼") if key and st["sort"] == key else "") for key, label in cols]


def count_text(D, st, n):
    mode, w = mp_mode(st), weighted(st)
    return (f"{n} of {len(D['libs'])} configurations shown" +
            ("" if w else "; no weights set, so there is no ranking: the order is the column you sort by") +
            ((". Speeds" + (" and scores" if w else "") + " are those of each library's " + mode +
              " mode, timed without contention (one caller at a time), and compared among these libraries only; "
              "the ISR stress columns are still the SPSC test") if mode else ""))


def source_text(D, st):
    """Which records the numbers of this view come from (the line under the table)."""
    b, mode = board_of(D, st), mp_mode(st)
    bench, rust = b["bench"], b.get("rust_bench")
    if two(st):
        b2 = b["bench2"]
        t = (b["name"] + " (" + b["core"] + ", " + js_str(b["clock_mhz"]) + " MHz). Speed: " +
             "benchmark version 2, each configuration in an image of its own (" + js_str(b2["records"]) + ", commit " +
             b2["commit"] + ", " + js_str(b2["passes"]) + " passes), " + b2["compiler"] + " " + b2["opt"] + " (Rust: " + b2["rustc"] +
             ", same opt-level), code in flash" + (", library code that is not inlined at least " + js_str(b2["far_bytes"]) +
             " bytes from its caller" if b2.get("far_bytes") else "") + "; small numbers: lowest and highest mean " +
             "with the image at " + str(len(b2["placements"])) + " placements. No other library's code is in the image, " +
             "so with a cache this is the best case")
        return _source_tail(D, b, t)
    if mode:
        speed = b["mp_bench"]["record"] if b.get("mp_bench") else "no record of the modes on this board"
    else:
        speed = (bench["record"] + (" and, for the Rust libraries, " + rust["record"] if rust else "") +
                 ("; for Nordic's nrf_ringbuf, " + b["nordic_bench"]["record"] if b.get("nordic_bench") else ""))
    t = (b["name"] + " (" + b["core"] + ", " + js_str(b["clock_mhz"]) + " MHz). Speed: " + speed + ", " +
         bench["compiler"] + " " + bench["opt"] +
         (" (Rust: " + rust["rustc"].split(" (")[0] + ", same opt-level)" if rust and rust.get("rustc") else "") +
         ", code in flash")
    pl = bench.get("placement")
    if not mode and pl:
        t += ("; small numbers: lowest and highest mean with the library code at " + str(len(pl["shifts"])) +
              " placements (moved by " + js_str(pl["shifts"][0]) + " to " + js_str(pl["shifts"][-1]) + " bytes)")
    return _source_tail(D, b, t)


def _source_tail(D, b, t):
    if b.get("size"):
        t += ". Code and RAM: " + b["size"]["record"]
    t += ". ISR stress: "
    t += (js_str(b["stress"]["valid_runs"]) + " valid runs, campaign " + b["stress"]["campaign"]) if b.get("stress") else "no campaign"
    t += "."
    c = D.get("contract")
    if c:
        t += (" One-core contract check (same for every board): run of " + c["date"] + " at commit " + c["commit"] +
              ", up to " + js_str(c["interrupts_per_call"]) + " interrupts per call, " + num(c["trials"]) + " trials.")
    return t
