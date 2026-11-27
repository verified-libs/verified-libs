#!/usr/bin/env python3
"""The CRC kind's tables for the static pages (step 4 of
lab/plans/2026-11-24-crc-from-series-to-publication.md), written from the
records so that a page cannot drift from them. A proposal: the owner
chooses what the page shows.

Usage: python3 -I site/crc_tables.py [--records DIR] [--board B] [--crc C] [--variant 1|2] [--place N] [--cache on|off|both]
       python3 -I site/crc_tables.py --edges [--place N] [--cache on|off]   (count, see below)
       python3 -I site/crc_tables.py --write|--check site/content/results-crc.md   (the results page)

Reads the records (default records/crc, <board>/<adapter>.json, schema
crc-bench/1) and, for what a record does not hold, two files of the kind:
kinds/crc/configs.txt (the order of the configurations) and the tables of
kinds/crc/README.md: step 2 (class and where the table lies, row n is the
n-th configuration of configs.txt) and step 4 (bytes of table in flash, RAM
and code at -O2 for the board's core: the board images are built at -O2).

Per CRC and board one table, one row per configuration:
  class, table      README step 2
  flash, RAM        bytes: table in flash + code (-O2, the board's core), RAM
  16 B              cycles of one call on 16 bytes, offset 0
  per byte          (mean at 1024 - mean at 256) / 768, offset 0
Variant 1 (default): each number is the range over the eight placements,
min-max, first pass; no placement is picked. Variant 2: the number of one
named placement (--place, default 0), first pass, with the range over the
eight placements beside it in brackets. The 1-byte scenarios are not
used: at offset 0 with the cache on the 1-byte scenario is the first one
after the cache is switched on (kinds/crc/bench/main.c, run_all). No
factor of the baseline: the baseline is the bitwise reference at one
position, table methods come out below 1 against it, and it says nothing
a row does not say.
--edges: for every row of every table (board, CRC, configuration), whether
the named placement's 16-byte figure and per-byte figure are the lowest or
the highest of the eight, counted; a check on variant 2.
--write PAGE: replaces the text between <!-- table:crc --> and
<!-- /table:crc --> in PAGE with the tables of the results page: variant 1
(decided 2026-11-25), per board and CRC the cache-on and the cache-off
table, each configuration linked to its record, the footnotes once at the
end. --check PAGE: exit 1 if PAGE is not up to date.
--cache: on (default), off, or both (two tables); the spread over the
placements is largest with the cache off. Footnotes (NOTES) say what a
number counts where the code makes it less than plain. No ranking: the rows are in the order of configs.txt,
the board's CRC unit (on the boards that have one, labelled in its name cell) the last row of the same table.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import series_info   # noqa: E402  (the method version of a board's records, and the series archived before)
# Footnotes, from the code they name (checked 2026-11-24 at 6301058).
NOTES = {
    "adapter_crcany_crc32_byte": "crcany's generated crc32iso_hdlc.c defines `table_byte` as `table_word[0]` "
        "(`#define table_byte table_word[0]`, build/gen/src/crc32iso_hdlc.c line 29): the byte code reads the first row "
        "of the word table, so the whole word table (4 x 256 x 4 = 4096 bytes, one symbol `table_word` in the "
        "image) is linked in. The flash bytes count it.",
    "adapter_libcrc_crc32": "libcrc builds its table in RAM at its first call. The adapter's init() makes that call "
        "(kinds/crc/adapter_libcrc.c, lc32_init) and bench/main.c calls init() before the timed calls (line 156), so "
        "the 256 calls of a scenario find the table built; the building is not measured.",
    "adapter_libcrc_ccitt_ffff": "As libcrc crc_32: the table is built by init() (lc16_init) before the timed "
        "calls; the building is not measured.",
}
# The order of the boards on the page, as on the ring buffers' results page (RESULTS.md).
PAGE_ORDER = ["nRF5340 DK", "Raspberry Pi Pico 2 H", "NUCLEO-G474RE", "NUCLEO-H723ZG", "NUCLEO-G0B1RE", "SAM D20 Xplained Pro"]
# A sentence directly above a board's cache-off tables (decided 2026-11-25, DECISIONS.md), by the board
# and the clock its records were measured at (clock_hz), so that the page says what the records it shows
# carry: version 2's NUCLEO-H723ZG ran at the reset clock, method version 3's at 520 MHz.
BEFORE_OFF = {
    ("NUCLEO-H723ZG", 64000000): "The NUCLEO-H723ZG runs at 64 MHz with the 7 flash wait states it has after power-on: the "
        "board's 64 MHz build leaves `FLASH_ACR` as after reset (`firmware/common/stm32h723/board.h`). RM0468 "
        "(Table 16) allows 0 or 1 wait states at 64 MHz. The numbers with the cache off carry the 7 wait states; "
        "fewer were not measured.",
    ("NUCLEO-H723ZG", 520000000): "The NUCLEO-H723ZG runs at 520 MHz with 3 flash wait states (voltage scale 0), as "
        "ST's template for the board sets it (`firmware/common/stm32h723/board.h`, method version 3). RM0468 "
        "(Table 16) requires 3 wait states for its AXI clock of 260 MHz. The numbers with the cache off carry the 3 "
        "wait states.",
}


def method_of(records_dir, recs, link=False):
    """{method_version, archived, method_text} of one board's CRC records (site/series_info.py); link: the text in
    markdown, each archived series linked at its public commit."""
    vs = {series_info.method_version(r["schema"]) for r in recs}
    clocks = {r["clock_hz"] for r in recs}
    if len(vs) != 1 or len(clocks) != 1:
        sys.exit(f"records/crc/{records_dir}: records of more than one method version or clock ({sorted(vs)}, {sorted(clocks)})")
    prefix = f"crc/{records_dir}/"
    arch = series_info.archived_for(prefix, sorted({r["bench_commit"] for r in recs}))
    v, clock = vs.pop(), clocks.pop()
    return {"method_version": v, "archived": arch,
            "method_text": series_info.method_text(v, clock, arch, series_info.unchanged_under_3(prefix), link)}


# A sentence under a board's tables about its CRC unit, by the board and the clock its records were measured
# at, as BEFORE_OFF (decided 2026-11-26): the H723's unit at 520 MHz, against the archived series at 64 MHz.
# (text on the results page with its link, text on the comparison page and in the MCP notes)
HW_UNIT = {
    ("NUCLEO-H723ZG", 520000000): (
        "The board's CRC unit is reached over a bus that runs at half the core clock since method version 3, so its "
        "cycles per byte are 3.0 where the archived series at 64 MHz had 1.5; in time it is faster: 1024 bytes take "
        "3109 cycles at 520 MHz (6.0 µs) against 1567 at 64 MHz (24.5 µs)",
        " ([method](method-crc.md#the-nucleo-h723zg-at-520-mhz)).",
        " (method page, \"The NUCLEO-H723ZG at 520 MHz\")."),
}


def hw_unit_note(board, clock_hz, md=False):
    """The sentence about the board's CRC unit for records measured at clock_hz, or None."""
    t = HW_UNIT.get((board, clock_hz))
    return None if t is None else t[0] + (t[1] if md else t[2])


def before_off(board, clock_hz):
    """The sentence above a board's cache-off tables for records measured at clock_hz, or None."""
    return BEFORE_OFF.get((board, clock_hz))


CORE = {"Cortex-M0+": "M0+", "Cortex-M4": "M4", "Cortex-M4F": "M4", "Cortex-M7": "M7", "Cortex-M33": "M33"}


def kind_tables():
    ads = [l.split()[0] for l in open(os.path.join(ROOT, "kinds/crc/configs.txt"))
           if l.strip() and not l.startswith("#")]
    readme = open(os.path.join(ROOT, "kinds/crc/README.md")).read()
    cls = {}
    for m in re.finditer(r"^\| (\d+) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| .+\|$", readme, re.M):
        n = int(m.group(1))
        if 1 <= n <= len(ads):
            cls[ads[n - 1]] = (m.group(4), m.group(5))
    sizes = {}
    hdr = re.search(r"^\| Configuration \| Table in flash \| RAM \| Code -Os: (.+?) \| Code -O2: (.+?) \|$", readme, re.M)
    cores = [c.strip() for c in hdr.group(2).split("/")]
    for m in re.finditer(r"^\| (\w+) \| (\d+) \| (\d+) \| ([\d /]+) \| ([\d /]+) \|$", readme, re.M):
        o2 = [int(x) for x in m.group(5).split("/")]
        sizes["adapter_" + m.group(1)] = (int(m.group(2)), int(m.group(3)), dict(zip(cores, o2)))
    # The hardware rows (step 11): bytes per board, read from the board images; RAM and code per core.
    for m in re.finditer(r"^\| (hw_\w+) \| .+? \((M0\+|M4|M7|M33)\) \| (\d+) \| (\d+) \| (\d+) \|$", readme, re.M):
        t, ram, code = sizes.setdefault("adapter_" + m.group(1), (int(m.group(3)), {}, {}))
        ram[m.group(2)], code[m.group(2)] = int(m.group(4)), int(m.group(5))
    return ads, cls, sizes


HW_CLASS = "hardware unit"
HW_TEXT = "The board's CRC unit, driven by our code; not a library"
HW_LABEL = "the board's CRC unit, driven by our code; not a library"   # in the name cell of its row, every time


def is_hw(cls, ad):
    """A hardware row (step 11 of the kind's README): the board's CRC unit, not a library."""
    return cls.get(ad, ("", ""))[0] == HW_CLASS


def ram_of(ram, core):
    """RAM bytes: one number, or per core (the hardware rows)."""
    return ram.get(core) if isinstance(ram, dict) else ram


def per_place(rec):
    """placement -> first run (pass 1)"""
    out = {}
    for im in rec["images"]:
        r = sorted(im["runs"], key=lambda r: r["pass"])[0]
        out[im["place"]] = r
    return out


def span(vals, fmt):
    rest = [x for x in vals.values() if x is not None]
    if not rest:
        return "–"
    lo, hi = min(rest), max(rest)
    return f"{fmt(lo)}–{fmt(hi)}" if fmt(lo) != fmt(hi) else fmt(lo)


def cell(vals, place, fmt):
    v = vals.get(place)
    if v is None:
        return "–"
    rest = [x for x in vals.values() if x is not None]
    lo, hi = min(rest), max(rest)
    return f"{fmt(v)} ({fmt(lo)}–{fmt(hi)})" if fmt(lo) != fmt(hi) else fmt(v)


def edges(recs, ads, place, cache):
    n = e16 = epb = both = either = 0
    for (board, crc, ad), r in sorted(recs.items()):
        pp = per_place(r)
        b16, cpb = {}, {}
        for p, x in pp.items():
            res = x["results"]
            m16, m256, m1024 = (res.get(f"len{l}/offset0/cache_{cache}") for l in (16, 256, 1024))
            b16[p] = m16["mean"] if m16 else None
            cpb[p] = (m1024["mean"] - m256["mean"]) / 768 if m1024 and m256 else None
        def edge(v):
            vals = [x for x in v.values() if x is not None]
            return v.get(place) is not None and len(set(vals)) > 1 and v[place] in (min(vals), max(vals))
        a, b = edge(b16), edge(cpb)
        n += 1; e16 += a; epb += b; both += a and b; either += a or b
    print(f"cache {cache}, placement {place}: {n} rows; at an edge of the eight (and the eight not all equal): "
          f"16 B {e16}, per byte {epb}, both {both}, either {either}")


def main():
    if sys.argv[1:2] in (["--write"], ["--check"]) and len(sys.argv) == 3:
        return write_page(sys.argv[2], sys.argv[1] == "--check")
    if "--edges" in sys.argv:
        a = [x for x in sys.argv[1:] if x != "--edges"]
        place = int(a[a.index("--place") + 1]) if "--place" in a else 0
        cache = a[a.index("--cache") + 1] if "--cache" in a else "off"
        ads, _, _ = kind_tables()
        recs = {}
        for f in glob.glob(os.path.join(ROOT, "records/crc", "*", "*.json")):
            r = json.load(open(f))
            if r.get("schema") in ("crc-bench/1", "crc-bench/2"):
                recs[(r["board"], r["crc"], r["adapter"])] = r
        edges(recs, ads, place, cache)
        return 0
    a = sys.argv[1:]
    opt = {"--records": os.path.join(ROOT, "records/crc"), "--board": None, "--crc": None, "--place": "0", "--cache": "on",
           "--variant": "1"}
    while a:
        k = a.pop(0)
        if k not in opt or not a:
            sys.exit(__doc__)
        opt[k] = a.pop(0)
    place = int(opt["--place"])
    ads, cls, sizes = kind_tables()
    recs = {}
    for f in glob.glob(os.path.join(opt["--records"], "*", "*.json")):
        r = json.load(open(f))
        if r.get("schema") in ("crc-bench/1", "crc-bench/2"):
            recs[(r["board"], r["crc"], r["adapter"])] = r
    for board in sorted({k[0] for k in recs}):
        if opt["--board"] and opt["--board"] not in (board, os.path.basename(board)):
            continue
        for crc in sorted({k[1] for k in recs if k[0] == board}):
            if opt["--crc"] and opt["--crc"] != crc:
                continue
            rows = [recs[(board, crc, ad)] for ad in ads if (board, crc, ad) in recs]
            core = CORE.get(rows[0]["core"].split("(")[-1].rstrip(")"), rows[0]["core"])
            for cache in (("on", "off") if opt["--cache"] == "both" else (opt["--cache"],)):
                table(board, crc, rows, core, cls, sizes, place, cache, opt["--variant"])
    return 0


def table(board, crc, rows, core, cls, sizes, place, cache, variant, out=None, link=None, notes=True, short=False):
    """One table; printed, or appended to out (a list of lines). link(record) -> path of the
    record for the row's link, or None; notes=False leaves the footnotes to the caller."""
    def emit(line=""):
        (out.append(line) if out is not None else print(line))
    if short:   # the page: the board is the section's heading
        emit(f"### {crc}, {board}, cache {cache}\n")
    else:
        emit(f"### {crc} on the {board} ({rows[0]['core']}, {rows[0]['clock_hz'] // 1000000} MHz), cache {cache}\n")
    if cache == "off" and before_off(board, rows[0]["clock_hz"]):
        emit(before_off(board, rows[0]["clock_hz"]) + "\n")
    if variant == "2":
        emit(f"Cycles, cache {cache}, placement {place} of 8 (range over the eight placements in brackets), first pass.\n")
    else:
        emit(f"Cycles, cache {cache}: the range over the eight placements (min–max), first pass.\n")
    emit("| Configuration | Class | Table | Flash bytes | RAM bytes | 16 B | per byte |")
    emit("|---|---|---|---:|---:|---:|---:|")
    rows_of(rows_in_order(rows, cls), cls, sizes, core, place, cache, variant, emit, link)
    emit()
    if notes:
        for i, (k, text) in enumerate(NOTES.items()):
            if any(r["adapter"] == k for r in rows):
                emit(f"[{i + 1}] {text}")
        emit()


def rows_in_order(rows, cls):
    """The libraries in the order of configs.txt, then the board's CRC unit, the last row of the same table."""
    return [r for r in rows if not is_hw(cls, r["adapter"])] + [r for r in rows if is_hw(cls, r["adapter"])]


def rows_of(rows, cls, sizes, core, place, cache, variant, emit, link):
    for r in rows:
        pp = per_place(r)
        b16, cpb = {}, {}
        for p, x in pp.items():
            res = x["results"]
            m16 = res.get(f"len16/offset0/cache_{cache}"); m256 = res.get(f"len256/offset0/cache_{cache}")
            m1024 = res.get(f"len1024/offset0/cache_{cache}")
            b16[p] = m16["mean"] if m16 else None
            cpb[p] = (m1024["mean"] - m256["mean"]) / 768 if m1024 and m256 else None
        c, t = cls.get(r["adapter"], ("?", "?"))
        mark = "".join(f"[{i + 1}]" for i, k in enumerate(NOTES) if k == r["adapter"])
        tf, ram, code = sizes.get(r["adapter"], (None, None, {}))
        flash = tf + code[core] if tf is not None and core in code else None
        ram = ram_of(ram, core)
        f0, f1 = (lambda v: f"{v:.0f}"), (lambda v: f"{v:.1f}")
        if variant == "2":
            c16, cb = cell(b16, place, f0), cell(cpb, place, f1)
        else:
            c16, cb = span(b16, f0), span(cpb, f1)
        name = (f"[{r['name']}]({link(r)})" if link else r["name"]) + (f" ({HW_LABEL})" if is_hw(cls, r["adapter"]) else "")
        emit(f"| {name}{mark} | {c} | {t} | {flash if flash is not None else '?'} | {ram if ram is not None else '?'} | "
             f"{c16} | {cb} |")


def slug(text):
    """The anchor python-markdown's toc gives a heading of this text (ASCII), so that the fold-outs keep the
    anchors the board and table headings had."""
    t = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", t)


def numbers(r, cache):
    """(16-byte figures, per-byte figures) of a record over its eight placements, first pass, as on the page."""
    b16, cpb = [], []
    for x in per_place(r).values():
        res = x["results"]
        m16, m256, m1024 = (res.get(f"len{n}/offset0/cache_{cache}") for n in (16, 256, 1024))
        if m16:
            b16.append(m16["mean"])
        if m256 and m1024:
            cpb.append((m1024["mean"] - m256["mean"]) / 768)
    return b16, cpb


def span_text(vals, fmt):
    lo, hi = fmt(min(vals)), fmt(max(vals))
    return lo if lo == hi else f"{lo}–{hi}"


def fold(fid, summary, lines):
    """A fold-out (<details>, closed), its Markdown inside rendered (md_in_html; GitHub: the blank line after it)."""
    return [f'<details id="{fid}" markdown="1">', f"<summary>{summary}</summary>\n"] + lines + ["</details>\n"]


def page_block(rdir, rel):
    """The tables of the results page (site/content/results-crc.md): variant 1, per board a fold-out whose
    summary says the board, its clock and method version, how many configurations and the span of the 16-byte
    figure with the cache on; inside it the board's lines and one fold-out per CRC and cache setting with the
    table (crc_tables.table, unchanged), the cache on first; the footnotes once at the end, in a fold-out of
    their own. The fold-outs carry the anchors the headings had (slug). rel: the records directory as the
    page links it."""
    ads, cls, sizes = kind_tables()
    recs, where = {}, {}
    for f in sorted(glob.glob(os.path.join(rdir, "*", "*.json"))):
        r = json.load(open(f))
        if r.get("schema") in ("crc-bench/1", "crc-bench/2"):
            recs[(r["board"], r["crc"], r["adapter"])] = r
            where[id(r)] = f"{rel}/{os.path.basename(os.path.dirname(f))}/{os.path.basename(f)}"
    crcs = []
    for ad in ads:
        for k in recs:
            if k[2] == ad and k[1] not in crcs:
                crcs.append(k[1])
    boards = sorted({k[0] for k in recs}, key=lambda b: (PAGE_ORDER.index(b) if b in PAGE_ORDER else 99, b))
    out = []
    f0, f1 = (lambda v: f"{v:.0f}"), (lambda v: f"{v:.1f}")
    for board in boards:
        first = next(r for k, r in recs.items() if k[0] == board)
        mine = [r for k, r in recs.items() if k[0] == board]
        d = sorted({os.path.basename(os.path.dirname(f)) for f in glob.glob(os.path.join(rdir, "*", "*.json"))
                    if json.load(open(f)).get("board") == board})[0]
        version = method_of(d, mine)["method_version"]
        libs = {r["adapter"] for r in mine if not is_hw(cls, r["adapter"])}
        unit = any(is_hw(cls, r["adapter"]) for r in mine)
        on16 = [v for r in mine for v in numbers(r, "on")[0]]
        inner = [f"{first['board_decoded']}, {first['clock_hz'] / 1e6:.0f} MHz.\n", board_method_md(rdir, board, recs) + "\n"]
        for crc in crcs:
            rows = [recs[(board, crc, ad)] for ad in ads if (board, crc, ad) in recs]
            if not rows:
                continue
            core = CORE.get(rows[0]["core"].split("(")[-1].rstrip(")"), rows[0]["core"])
            for cache in ("on", "off"):
                t = []
                table(board, crc, rows, core, cls, sizes, 0, cache, "1", t, lambda r: where[id(r)], False, True)
                head = t.pop(0)   # "### <crc>, <board>, cache <on|off>": its text goes to the summary, its anchor to the fold-out
                title = head.lstrip("#").strip()
                b16 = [v for r in rows for v in numbers(r, cache)[0]]
                pb = [v for r in rows for v in numbers(r, cache)[1]]
                summ = (f"{crc}, cache {cache}: {len(rows)} rows, 16 bytes {span_text(b16, f0)} cycles, "
                        f"{span_text(pb, f1)} cycles per byte")
                inner += fold(slug(title), summ, t)
        hw = hw_unit_note(board, first["clock_hz"], md=True)
        if hw and unit:
            inner.append(hw + "\n")
        summ = (f"<strong>{board}</strong>, {first['clock_hz'] / 1e6:.0f} MHz, method version {version}: "
                f"{len(libs)} configurations" + (" and the board's CRC unit" if unit else "")
                + f", a call on 16 bytes {span_text(on16, f0)} cycles with the cache on")
        out += fold(slug(board), summ, inner)
    notes = [f"[{i + 1}] {text}\n" for i, (k, text) in enumerate(NOTES.items())]
    out += fold("notes-to-the-tables", f"Notes [1] to [{len(NOTES)}] to the tables", notes)
    return "\n".join(out).rstrip() + "\n"


def board_method_md(rdir, board, recs):
    """The method sentence of a board on the results page, each archived series linked at its public commit."""
    d = sorted({os.path.basename(os.path.dirname(f)) for f in glob.glob(os.path.join(rdir, "*", "*.json"))
                if json.load(open(f)).get("board") == board})[0]
    return method_of(d, [r for k, r in recs.items() if k[0] == board], link=True)["method_text"]


def write_page(path, check):
    """Replace the text between the markers of path with page_block(); check: exit 1 if it differs."""
    s = open(path).read()
    a, b = "<!-- table:crc -->\n", "<!-- /table:crc -->"
    i, j = s.index(a) + len(a), s.index(b)
    rel = os.path.relpath(os.path.join(ROOT, "records/crc"), os.path.dirname(os.path.abspath(path)))
    new = s[:i] + "\n" + page_block(os.path.join(ROOT, "records/crc"), rel) + "\n" + s[j:]
    if check:
        if new != s:
            print(f"{path}: not up to date (python3 -I site/crc_tables.py --write {path})")
            return 1
        print(f"{path}: up to date")
        return 0
    open(path, "w").write(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
