#!/usr/bin/env python3
"""The pools kind's tables for its results page (site/content/results-pools.md),
written from the records so that the page cannot drift from them, as
site/crc_tables.py does for the CRC kind.

Usage: python3 -I site/pools_tables.py --write|--check site/content/results-pools.md
       python3 -I site/pools_tables.py [--records DIR]      (print the block)

Reads the records (records/pools/<board>/<adapter>.json, schema pools-bench/1)
and, for what a record does not hold, three files of the kind:
kinds/pools/configs.txt (the order of the configurations), the table "The
set" of kinds/pools/README.md (library, pin, licence and the lock as built),
and kinds/pools/claims.tsv: what each library documents about use from
interrupts, the last column, documented, not tested (the series is one
context; a boxed note says so above the first fold-out and above each
board's table).

Per board a fold-out (<details>, closed by default; anchor: the board's
name as a heading's anchor) whose summary line says the board, its clock
and method version, how many configurations and the span of the pattern
SUMMARY's alloc with the cache on; inside it one table (bytes, init, the
pattern SUMMARY's alloc and free, cache on and off, the claims) and a nested
fold-out "Every pattern on this board" (anchor <board>-every-pattern) with
the table of bytes and init and one table per pattern. One row per
configuration in the order of configs.txt (not a ranking), our row with
interrupts off labelled in its name cell every time, and the reference free
list, the baseline timed in the same images, as the last row. Every cycle
figure is the range over the eight placements (min-max) of the mean of the
scenario's calls, first pass, the counter-read overhead subtracted. Two
rows differ only where their ranges do not overlap.

A record marked synthetic (site/pools_synthetic.py) is refused under
records/pools; --records DIR takes one, for a look at the pages, and the
block then says so in its first line.
--write PAGE: replaces the text between <!-- table:pools --> and
<!-- /table:pools --> with the block; --check PAGE: exit 1 if it differs.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import crc_tables   # noqa: E402  (the board order and the sentence above a board's cache-off numbers)

RECORDS = os.path.join(ROOT, "records/pools")
SCHEMAS = ("pools-bench/1",)
PAGE_ORDER = crc_tables.PAGE_ORDER
SCENARIOS = [   # (key, what is timed: one line each, from kinds/pools/README.md "The image")
    ("pair", "alloc, then free of the same block, 256 times, the pool almost empty"),
    ("pair_full", "the same with 31 of the 32 blocks held"),
    ("fill_drain_lifo", "8 times: 32 allocs, then 32 frees in reverse order"),
    ("fill_drain_fifo", "8 times: 32 allocs, then 32 frees in the order of the allocs"),
    ("mixed", "512 calls from a fixed seed, the pool between 25 % and 75 % full"),
    ("empty", "256 allocs on an exhausted pool, each of which must fail; no free"),
]
INIT_TEXT = "one call that creates the pool in the adapter's storage"
OPS = ("alloc", "free")
OURS_LABEL = "our reference free list with interrupts off; not a library"
BASE_NAME = "reference free list (ours)"
BASE_TEXT = "Reference free list (baseline), not a library"
BASE_LABEL = "reference free list (ours; the baseline, timed in the same images; not a library)"
# Footnotes, from kinds/pools/README.md (the set, and how each adapter fits the interface).
NOTES = {
    "adapter_memorypool": "MemoryPool is measured at its main branch, commit `5073178`, which is not a release. "
        "The project's only release, v0.1.0, spaces the blocks of `MemoryPool::Fixed` by the size of a pointer, so "
        "blocks of 32 bytes overlap, and it does not build for arm-none-eabi; the author fixed the spacing in pull "
        "request #4 (merged 2024-05-14) and made the mutex optional (2024-05-15), with no release since "
        "([kinds/pools/README.md](../../kinds/pools/README.md), \"MemoryPool: why the head, not the release\").",
    "adapter_heapless": "A heapless `Box` cannot be made from a raw pointer, so the adapter keeps the live boxes in a "
        "table indexed by the block's place: a few instructions per call, and 128 of the RAM bytes. heapless is not "
        "built for the Cortex-M0+ (its documentation).",
    "adapter_c_allocator": "C_Allocator treats an exhausted pool as a fault and calls `FaultHandler()`; the "
        "adapter's handler counts the call and returns, and `ALLOC_Alloc` then gives NULL (scenario empty).",
    "adapter_threadx": "ThreadX runs without its scheduler (`kinds/pools/tx_kernel_stubs.c`); the stubs are never "
        "reached with `TX_NO_WAIT`. Its RAM bytes include a pointer in front of every block.",
}
def sizes_of(rec):
    """(flash bytes, RAM bytes beyond the blocks and canaries) of a record (its "sizes": flash_bytes and
    ram_overhead_bytes, kinds/pools/README.md "Sizes: `sizes` in the record"), None where it holds none."""
    s = rec.get("sizes") or {}
    return s.get("flash_bytes"), s.get("ram_overhead_bytes")


def is_synthetic(rec):
    return bool(rec.get("synthetic")) or str(rec.get("board_decoded", "")).startswith("SYNTHETIC")


def load(rdir=None):
    """[(path, record)] of the records under rdir (default records/pools); a synthetic one there is refused.
    Returns (records, synthetic)."""
    rdir = rdir or RECORDS
    out, syn = [], False
    for f in sorted(glob.glob(os.path.join(rdir, "*", "*.json"))):
        r = json.load(open(f))
        if r.get("schema") not in SCHEMAS:
            continue
        if is_synthetic(r):
            if os.path.abspath(rdir) == os.path.abspath(RECORDS):
                sys.exit(f"refused: {os.path.relpath(f, ROOT)} is a synthetic record (site/pools_synthetic.py)")
            syn = True
        out.append((f, r))
    return out, syn


def kind_meta():
    """(adapters in the order of configs.txt, {adapter: {lang, name}}, {name: {library, pin, licence, lock}})."""
    ads, cfg = [], {}
    for line in open(os.path.join(ROOT, "kinds/pools/configs.txt")):
        f = line.split(None, 2)
        if f and not f[0].startswith("#") and len(f) == 3:
            ads.append(f[0])
            cfg[f[0]] = {"lang": f[1], "name": f[2].strip()}
    readme = open(os.path.join(ROOT, "kinds/pools/README.md")).read()
    sec = readme[readme.index("## The set"):]
    sec = sec[:sec.index("\n\n**Left out")]
    plain = lambda s: re.sub(r"\*\*|`", "", s).strip()   # noqa: E731
    sets = {}
    for m in re.finditer(r"^\| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$", sec, re.M):
        name = plain(m.group(1))
        if name in ("Configuration",) or set(name) <= set("-"):
            continue
        sets[name] = {"library": None if plain(m.group(2)) == "–" else plain(m.group(2)),
                      "pin": None if plain(m.group(3)) == "–" else plain(m.group(3)),
                      "licence": None if plain(m.group(4)) == "–" else plain(m.group(4)),
                      "lock": re.sub(r" \(below\)$", "", plain(m.group(5)))}
    return ads, cfg, sets


def role(adapter):
    """'library', or 'ours' for our reference free list with interrupts off (a configuration of ours, not a library)."""
    return "ours" if adapter == "adapter_ref_primask" else "library"


def per_place(rec):
    """placement -> first run (pass 1)"""
    return {im["place"]: sorted(im["runs"], key=lambda r: r["pass"])[0] for im in rec["images"]}


def keys():
    """The result keys of a record without the cache: 'init', then '<scenario>/<op>'."""
    return ["init"] + [f"{s}/{o}" for s, _ in SCENARIOS for o in OPS]


def ranges(results_by_place):
    """placement (or any key) -> results -> {cache: {key: [min, max] of the means, or None}}"""
    out = {}
    for cache in ("on", "off"):
        out[cache] = {}
        for k in keys():
            full = f"init/cache_{cache}" if k == "init" else f"{k}/cache_{cache}"
            vals = [res[full]["mean"] for res in results_by_place.values() if res.get(full)]
            out[cache][k] = [round(min(vals), 4), round(max(vals), 4)] if vals else None
    return out


def range_text(r):
    if not r:
        return "–"
    lo, hi = f"{r[0]:.0f}", f"{r[1]:.0f}"
    return lo if lo == hi else f"{lo}–{hi}"


def board_sections(recs):
    """[(board name, first record, [(path, rec) in configs.txt order], baseline ranges)]"""
    ads, _, _ = kind_meta()
    by = {}
    for f, r in recs:
        by.setdefault(r["board"], []).append((f, r))
    out = []
    for board in sorted(by, key=lambda b: (PAGE_ORDER.index(b) if b in PAGE_ORDER else 99, b)):
        rows = sorted(by[board], key=lambda x: ads.index(x[1]["adapter"]) if x[1]["adapter"] in ads else 99)
        base = {}
        for f, r in rows:   # the baseline over the libraries' images (as the CRC kind's), not our own row's
            if role(r["adapter"]) == "library":
                base.update({(r["adapter"], p): x["baseline"] for p, x in per_place(r).items()})
        out.append((board, rows[0][1], rows, ranges(base)))
    return out


ONE_CONTEXT_HTML = ('<div class="onectx"><strong>Measured in one context.</strong> Use from interrupts is not tested in '
                    'this series; the last column is what each library documents.</div>')
CLAIM_HEAD = "Documented use from interrupts (not tested)"
# With records of the concurrency series (site/pools_isr.py) the box says where the test is, and the claims
# column is what each library documents beside what was observed.
ISR_CONTEXT_HTML = ('<div class="onectx"><strong>Use from interrupts was tested</strong> in a series of its own, the '
                    'concurrency series: an interrupt at every cycle of a call, on every board, with controls that must '
                    'be caught (<a href="method-pools.html#use-from-interrupts">method</a>). What it observed is in each '
                    'board\'s fold-out "Use from interrupts"; a library used in a way it does not document is never '
                    'called failing. The numbers in the tables are of one context.</div>')
CLAIM_HEAD_ISR = "Documented use from interrupts"
SUMMARY = "pair"   # the one pattern of the results page: the plan's "common driver pattern"
CLAIMS = os.path.join(ROOT, "kinds/pools/claims.tsv")


def claims(path=None):
    """{adapter: {"who", "text", "source"}} from the kind's claims file (kinds/pools/claims.tsv: tab-separated,
    comments with #, a header row, then adapter, who (library or ours), documented, source), or {} without it."""
    path = path or CLAIMS
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8"):
        if not line.strip() or line.startswith("#"):
            continue
        f = line.rstrip("\n").split("\t")
        if f[0] == "adapter":   # the header row
            continue
        if len(f) != 4 or f[1] not in ("library", "ours"):
            sys.exit(f"{path}: not a row of adapter, who, documented, source: {line.strip()!r}")
        out[f[0]] = {"who": f[1], "text": f[2], "source": None if f[3] in ("", "–", "-") else f[3]}
    return out


def claim_cell(c):
    """The claims column as the pages write it: the library's words, then its source."""
    if not c:
        return "–"
    t = c["text"].replace("|", "\\|")
    return t + (f" (source: {c['source'].replace('|', '/')})" if c.get("source") else "")


def slug(text):
    """The anchor the site's markdown gives a heading (python-markdown's toc)."""
    t = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", t)


def fold(fid, summary, lines):
    """A fold-out (<details>, closed by default), its Markdown inside rendered (md_in_html; GitHub: the blank line)."""
    return [f'<details id="{fid}" markdown="1">', f"<summary>{summary}</summary>\n"] + lines + ["</details>\n"]


def span_of(rgs, key, cache="on"):
    """The span of a number over rows' ranges, as the tables write it ("17–212"), or "–"."""
    vals = [v for rg in rgs if rg[cache].get(key) for v in rg[cache][key]]
    return range_text([min(vals), max(vals)]) if vals else "–"


def isr_fold(board, bdir, data, isr, isr_rel, cl):
    """The nested fold-out of a board with what the concurrency series observed (site/pools_isr.py)."""
    import pools_isr
    lines = ["**Use from interrupts.** What the concurrency series observed with an interrupt at every cycle of "
             "the main context's alloc or free, cache off and on, in the classes of its method: within the "
             "library's documentation (passed, or a finding), ours, outside the library's documentation (only what "
             "was observed), and our controls, which must be caught. The longest wait of an interrupt is shown "
             "where the configuration takes interrupts off as built. Not part of any score.\n"
             + ("" if any(b == bdir for b, _ in isr) else "\n*The series has not run on this board yet.*\n")
             + (f"\n{pools_isr.BOARD_NOTE[bdir]}\n" if bdir in pools_isr.BOARD_NOTE and any(b == bdir for b, _ in isr) else ""),
             f"| Configuration | {CLAIM_HEAD_ISR} | Observed in the concurrency series | Trials | "
             "Instructions reached by an interrupt |",
             "|---|---|---|---:|---:|"]

    def row(name, adapter):
        k = (bdir, adapter)
        if k not in isr:
            return f"| {name} | {claim_cell(cl.get(adapter))} | – | – | – |"
        f, r = isr[k]
        sm = pools_isr.summary(bdir, f, r)
        cov = sm["coverage"]
        # linked to its record; synthetic records (a preview) lie outside the tree: no link
        link = f"[{pools_isr.cell(sm)}]({isr_rel}/{bdir}/{os.path.basename(f)})" if isr_rel else pools_isr.cell(sm)
        return (f"| {name} | {claim_cell(cl.get(adapter)) if adapter not in pools_isr.CONTROLS[1:] else '–'} | {link} | "
                f"{sm['trials']} | {'–' if not cov else f'{cov[0]} of {cov[1]}'} |")
    for name, r, _s, _rg in data:
        lines.append(row(name, r["adapter"]))
    lines.append(row(BASE_LABEL + "; the control without a lock", "adapter_ref"))
    for a in pools_isr.CONTROLS[1:]:
        lines.append(row(pools_isr.CONTROL_TEXT[a], a))
    lines.append("")
    return fold(slug(board) + "-use-from-interrupts", "Use from interrupts on this board (the concurrency series)", lines)


def page_block(recs, syn, rel, claims_path=None, isr=None, isr_syn=False, isr_rel=None):
    """The block of the results page: per board one fold-out, closed, whose summary says the board, its clock and
    method version, how many configurations and the span of the pair alloc with the cache on; inside it the table
    of the pattern SUMMARY, and a nested fold-out "Every pattern on this board" with the table of bytes and init and
    one table per pattern. The one-context note stays visible above the first fold-out, and stands above each
    board's table. The fold-outs carry the anchors <board> and <board>-every-pattern (slug)."""
    if not recs:
        return ("**The first board series of this kind is not published yet:** there are no records under "
                "[`records/pools`](../../records/README.md). The tables appear here, written from the records, "
                "when the series is published.\n")
    import crc_data   # the site's board ids, for the comparison page's address
    import series_info
    _, _, sets = kind_meta()
    cl = claims(claims_path)
    out = []
    if syn:
        out.append("**SYNTHETIC: every number below is made up (site/pools_synthetic.py); none is a measurement. "
                   "Not for publication.**\n")
    if isr_syn:
        out.append("**SYNTHETIC: every result of the concurrency series below is made up (site/pools_isr_synthetic.py); "
                   "none is a measurement. Not for publication.**\n")
    context = ISR_CONTEXT_HTML if isr else ONE_CONTEXT_HTML
    claim_head = CLAIM_HEAD_ISR if isr else CLAIM_HEAD
    commits = sorted({r["bench_commit"] for _, r in recs})
    boards = {r["board"] for _, r in recs}
    ads = {r["adapter"] for _, r in recs}
    libs = {r["adapter"] for _, r in recs if role(r["adapter"]) == "library"}
    out.append(f"{len(libs)} libraries and {len(ads) - len(libs)} configuration of ours on {len(boards)} boards, "
               f"{len(recs)} records; series at commit{'s' if len(commits) > 1 else ''} "
               + ", ".join(f"`{c}`" for c in commits) + ".\n")
    out.append(context + "\n")
    used = []
    for board, first, rows, base in board_sections(recs):
        bdir = os.path.basename(os.path.dirname(rows[0][0]))
        version = {series_info.method_version(r["schema"]) for _, r in rows}
        if len(version) != 1:
            sys.exit(f"records/pools/{bdir}: records of more than one method version")
        version = version.pop()
        data = []
        for f, r in rows:
            s = sets.get(r["name"], {})
            name = f"[{r['name']}]({rel}/{os.path.basename(os.path.dirname(f))}/{os.path.basename(f)})"
            if r["adapter"] in NOTES:
                if r["adapter"] not in used:
                    used.append(r["adapter"])
                name += f"[{list(NOTES).index(r['adapter']) + 1}]"
            if role(r["adapter"]) == "ours":
                name += f" ({OURS_LABEL})"
            data.append((name, r, s, ranges({p: x["results"] for p, x in per_place(r).items()})))
        note = crc_tables.before_off(board, first["clock_hz"])
        nlib = sum(1 for _, r, _, _ in data if role(r["adapter"]) == "library")
        inner = [f"{first['board_decoded']}, {first['clock_hz'] / 1e6:.0f} MHz. "
                 + series_info.method_text(version, first["clock_hz"], []) + "\n", context + "\n"]
        inner.append(f"Pattern `{SUMMARY}`: {dict(SCENARIOS)[SUMMARY]}. Cycles per call, and of the one call of init: "
                     "the range over the eight placements, first pass. Flash: code and constants; RAM: beyond the "
                     "blocks and their canaries.\n")
        inner.append(f"| Configuration · pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | "
                     f"alloc, cache on | free, cache on | alloc, cache off | free, cache off | {claim_head} |")
        inner.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for name, r, s, rg in data:
            fl, ram = sizes_of(r)
            inner.append(f"| {name}{' · ' + s['pin'] if s.get('pin') else ''} | {s.get('lock', '–')} | {'?' if fl is None else fl} | "
                         f"{'?' if ram is None else ram} | {range_text(rg['on']['init'])} | {range_text(rg['off']['init'])} | "
                         + " | ".join(range_text(rg[c][f'{SUMMARY}/{o}']) for c in ("on", "off") for o in OPS)
                         + f" | {claim_cell(cl.get(r['adapter']))} |")
        inner.append(f"| {BASE_LABEL} | none | – | – | {range_text(base['on']['init'])} | {range_text(base['off']['init'])} | "
                     + " | ".join(range_text(base[c][f'{SUMMARY}/{o}']) for c in ("on", "off") for o in OPS)
                     + f" | {claim_cell(cl.get('adapter_ref'))} |")
        inner.append("")
        inner.append(f"The same numbers with your own weights: the [comparison page for this board]"
                     f"(compare-pools.html#board={crc_data.SITE_ID.get(bdir, bdir)}&scen={SUMMARY}).\n")
        every = ["**Bytes and init.** Flash: the library's and the adapter's code and constants at `-O2`, measured in "
                 f"the board's images; RAM: beyond the 32 blocks of 32 bytes and the canaries. Init: cycles of {INIT_TEXT}, "
                 "the range over the eight placements, first pass.\n",
                 f"| Configuration | Library | Pin | Lock as built | Flash bytes | RAM bytes | Init, cache on | Init, cache off | {claim_head} |",
                 "|---|---|---|---|---:|---:|---:|---:|---|"]
        for name, r, s, rg in data:
            fl, ram = sizes_of(r)
            every.append(f"| {name} | {s.get('library') or '–'} | {s.get('pin') or '–'} | {s.get('lock', '–')} | "
                         f"{'?' if fl is None else fl} | {'?' if ram is None else ram} | "
                         f"{range_text(rg['on']['init'])} | {range_text(rg['off']['init'])} | {claim_cell(cl.get(r['adapter']))} |")
        every.append(f"| {BASE_LABEL} | – | – | none | – | – | "
                     f"{range_text(base['on']['init'])} | {range_text(base['off']['init'])} | {claim_cell(cl.get('adapter_ref'))} |")
        every.append("")
        for sc, text in SCENARIOS:
            every.append(f"**`{sc}`**: {text}. Cycles per call: the range over the eight placements, first pass.\n")
            every.append("| Configuration | alloc, cache on | free, cache on | alloc, cache off | free, cache off |")
            every.append("|---|---:|---:|---:|---:|")
            for name, r, s, rg in data + [(BASE_LABEL, None, None, base)]:
                every.append(f"| {name} | " + " | ".join(range_text(rg[c][f'{sc}/{o}']) for c in ("on", "off") for o in OPS) + " |")
            every.append("")
        if isr:
            inner += isr_fold(board, bdir, data, isr, isr_rel, cl)
        inner += fold(slug(board) + "-every-pattern", "Every pattern on this board: bytes and init, and "
                      + ", ".join(f"<code>{k}</code>" for k, _ in SCENARIOS), every)
        if note:
            inner.append(f"Cache off: {note}\n")
        summ = (f"<strong>{board}</strong>, {first['clock_hz'] / 1e6:.0f} MHz, method version {version}: "
                f"{nlib} configurations and a row of ours, <code>{SUMMARY}</code> alloc "
                f"{span_of([rg for _, _, _, rg in data], f'{SUMMARY}/alloc')} cycles with the cache on")
        out += fold(slug(board), summ, inner)
    notes = [f"[{i + 1}] {text}\n" for i, (k, text) in enumerate(NOTES.items()) if k in used]
    if notes:
        out += fold("notes-to-the-tables", "Notes to the tables: MemoryPool's pin, heapless, C_Allocator, ThreadX", notes)
    return "\n".join(out).rstrip() + "\n"


def block(rdir=None, page_dir=None, claims_path=None, isr_dir=None):
    import pools_isr
    recs, syn = load(rdir)
    rel = os.path.relpath(rdir or RECORDS, page_dir or os.path.join(ROOT, "site/content"))
    isr, isr_syn = pools_isr.load(isr_dir)
    isr_rel = os.path.relpath(isr_dir or pools_isr.RECORDS, page_dir or os.path.join(ROOT, "site/content")) \
        if not isr_syn else None
    return page_block(recs, syn, rel, claims_path, isr, isr_syn, isr_rel)


PAGES = {"results": "site/content/results-pools.md"}


def page_text(path, rdir=None, isr_dir=None):
    """(the page as it is, the page with the block written from the records between its markers)"""
    s = open(path).read()
    a, b = "<!-- table:pools -->\n", "<!-- /table:pools -->"
    i, j = s.index(a) + len(a), s.index(b)
    return s, s[:i] + "\n" + block(rdir, os.path.dirname(os.path.abspath(path)), isr_dir=isr_dir) + "\n" + s[j:]


def write_page(path, check, rdir=None, isr_dir=None):
    s, new = page_text(path, rdir, isr_dir)
    if check:
        if new != s:
            print(f"{path}: not up to date (python3 -I site/pools_tables.py --write {path})")
            return 1
        print(f"{path}: up to date")
        return 0
    open(path, "w").write(new)
    return 0


def main():
    a = sys.argv[1:]
    rdir = isr_dir = None
    if "--records" in a:
        i = a.index("--records")
        rdir, a = a[i + 1], a[:i] + a[i + 2:]
    if "--isr" in a:   # the concurrency series' records from another directory (synthetic ones: a preview)
        i = a.index("--isr")
        isr_dir, a = a[i + 1], a[:i] + a[i + 2:]
    if a[:1] in (["--write"], ["--check"]) and len(a) == 2:
        return write_page(a[1], a[0] == "--check", rdir, isr_dir)
    if a:
        sys.exit(__doc__)
    print(block(rdir), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
