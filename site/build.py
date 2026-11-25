#!/usr/bin/env python3
"""Build the static verified-libs site from the repository's markdown.

Usage: python3 site/build.py [--preview] [OUT_DIR]      (default: site/_build)

--preview: build even with embargoed material, for local viewing only; every
affected page gets a red banner. Without it the build refuses.

Pages: site/content/*.md, RESULTS.md, the reports in reports/, the
findings listed in PUBLISH_FINDINGS (site.conf), and the interactive
comparison (content/compare.html + compare.js + data/libs.json, which
site/gen_libdata.py writes from the records on the lab host). Links to repository files
become links to REPO_URL; the build fails if such a file is not in the tree.
The build also fails if any page contains a word from
site/embargo.txt, so nothing under embargo can be published by accident.
(The public tree has no such list: lab/tools/public-export.py made the same
check when it wrote the tree, and left the file EXPORTED_FROM. Only then is
a missing list accepted.)
Needs the python3-markdown package.
"""
import html
import json
import os
import re
import sys

import markdown

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embargo_strip import strip_embargo   # noqa: E402
import kinds_page   # noqa: E402
import crc_data   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")


def conf():
    c = {}
    for line in open(os.path.join(SITE, "site.conf")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            c[k.strip()] = v.strip()
    return c


def embargo_words():
    path = os.path.join(SITE, "embargo.txt")
    if not os.path.exists(path) and os.path.exists(os.path.join(ROOT, "EXPORTED_FROM")):
        return []   # an exported tree: the export has made this check
    return [w.strip().lower() for w in open(path)
            if w.strip() and not w.startswith("#")]


CSS = """
:root{--bg:#fdfdfc;--fg:#1d1d1b;--mute:#62625e;--line:#e2e1dc;--acc:#1f5f8b;--code:#f3f2ee;--bad:#a3261e}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#e8e7e3;--mute:#a3a29c;--line:#33332f;--acc:#7fb6dd;--code:#22221f;--bad:#f0877f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
header{border-bottom:1px solid var(--line)}nav,main{max-width:1060px;margin:0 auto;padding:0 16px}
nav{display:flex;gap:20px;align-items:baseline;padding:14px 16px;flex-wrap:wrap}
nav .brand{font-weight:650;margin-right:auto;color:var(--fg)}nav a{color:var(--mute);text-decoration:none}
nav a.on,nav a:hover{color:var(--acc)}main{padding:24px 16px 64px}
h1{font-size:1.9rem;line-height:1.25}h2{margin-top:2.2rem;border-bottom:1px solid var(--line);padding-bottom:4px}
a{color:var(--acc)}code{background:var(--code);padding:1px 4px;border-radius:4px;font-size:.92em}
pre{background:var(--code);padding:12px;overflow-x:auto;border-radius:6px}pre code{padding:0}
.tw{overflow-x:auto;margin:1rem 0}table{border-collapse:collapse;font-size:.92rem}
th,td{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
th{font-weight:600;white-space:nowrap}footer{max-width:1060px;margin:0 auto;padding:24px 16px;color:var(--mute);
font-size:.85rem;border-top:1px solid var(--line)}
form.cmp{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));margin:1rem 0}
form.cmp fieldset{border:1px solid var(--line);border-radius:6px;padding:8px 12px;margin:0;min-width:0}
form.cmp legend{font-weight:600;padding:0 4px}form.cmp label{display:block;margin:4px 0}
form.cmp label.w{display:grid;grid-template-columns:minmax(0,11rem) minmax(60px,1fr) 2ch;gap:8px;align-items:center}
form.cmp select,form.cmp button{font:inherit;color:inherit;background:var(--code);border:1px solid var(--line);
border-radius:4px;padding:2px 6px}form.cmp input[type=range]{width:100%;accent-color:var(--acc)}
form.cmp select{max-width:100%;display:block;margin-top:4px}form.cmp fieldset{align-self:start}
table.cmp{min-width:900px}table.cmp td.r{white-space:nowrap}
table.cmp td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
table.cmp th{white-space:normal;vertical-align:bottom;min-width:5rem}table.cmp td.score{font-weight:650}
.sortb{font:inherit;font-weight:600;color:inherit;background:none;border:0;padding:0;cursor:pointer;text-align:left}
.sortb:hover,.sortb:focus-visible{color:var(--acc)}.sub{color:var(--mute);font-size:.82rem;font-weight:400}
.tag{color:var(--mute);font-size:.82rem}.tag a{color:inherit}.warn{color:var(--bad)}.mute{color:var(--mute)}.bad{color:var(--bad);font-weight:600}
tr.sep td{background:var(--code);color:var(--mute);font-size:.85rem;font-weight:600}
p.kindsw{margin:0 0 .5rem;color:var(--mute)}p.kindsw strong{color:var(--fg)}
"""

NAV = [("index", "Home"), ("kinds", "Results"), ("compare", "Compare"), ("method", "Method"),
       ("reproduce", "Reproduce"), ("repeats", "Repeats"), ("findings", "Findings"), ("reports", "Reports")]


SITE_URL = ""   # from site.conf (main): the address the pages are served at, for search engines


def describe(md_text):
    """A page's description for search engines: its first paragraph of plain text."""
    for para in re.split(r"\n\s*\n", md_text):
        para = " ".join(para.split())
        if not para or para[0] in "#|-*`<>!" or para[:2].isdigit():
            continue
        para = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", para)
        para = re.sub(r"[`*]", "", para)   # not "_": it is part of the names (lwrb_write_byte)
        if len(para) > 160:
            para = para[:158].rsplit(" ", 1)[0].rstrip(",;:(") + " ..."
        return para
    return ""


# The icon a browser tab and a search result show next to the site's name.
FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="#1f5f8b"/>'
           '<path d="M8 17l5 5 11-12" fill="none" stroke="#fff" stroke-width="3.5" stroke-linecap="round" '
           'stroke-linejoin="round"/></svg>\n')


def page(slug, title, body, nav_on, desc="", listed=True):
    """One page. listed=False: a page that is not content (404.html): no address of its own, not for search engines."""
    links = "".join(f'<a href="{s}.html"{" class=on" if s == nav_on else ""}>{t}</a>' for s, t in NAV[1:])
    name = slug if slug.endswith(".html") else slug + ".html"
    full = title if title.startswith("verified-libs") else title + " - verified-libs"
    seo = (f'<meta name="description" content="{html.escape(desc)}">\n' if desc else "")
    if not listed:
        seo += '<meta name="robots" content="noindex">\n'
        if SITE_URL:   # served for any address that does not exist: the links must not depend on it
            seo += f'<base href="{SITE_URL}/">\n'
    elif SITE_URL:   # one address per page: the front page is the site's root
        url = f'{SITE_URL}/{"" if name == "index.html" else name}'
        seo += f'<link rel="canonical" href="{url}">\n'
        # What a link to the page shows where it is shared (Open Graph, read by most sites and chat programs).
        seo += (f'<meta property="og:site_name" content="verified-libs">\n'
                f'<meta property="og:type" content="{"website" if name == "index.html" else "article"}">\n'
                f'<meta property="og:title" content="{html.escape(full)}">\n'
                + (f'<meta property="og:description" content="{html.escape(desc)}">\n' if desc else "")
                + f'<meta property="og:url" content="{url}">\n<meta name="twitter:card" content="summary">\n')
        if name == "index.html":   # the site's name for search engines
            seo += ('<script type="application/ld+json">'
                    + json.dumps({"@context": "https://schema.org", "@type": "WebSite", "name": "verified-libs", "url": SITE_URL + "/"})
                    + '</script>\n')
    seo += '<link rel="icon" href="favicon.svg" type="image/svg+xml">\n'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{seo}<title>{html.escape(full)}</title><style>{CSS}</style></head>
<body><header><nav><a class="brand" href="index.html">verified-libs</a>{links}</nav></header>
<main>{body}</main>
<footer>verified-libs &middot; contact@verified-libs.org &middot; built from the repository; every number links back to its source. Code MIT, texts and results CC&nbsp;BY&nbsp;4.0.</footer>
</body></html>
"""


# The front page's heading is the project's name; its browser title says more.
# The project is a registry of more than one kind of library; ring buffers
# and CRC calculation in software are the kinds so far. Name the project first.
INDEX_TITLE = "verified-libs: libraries tested on real hardware: embedded ring buffers and CRC"
INDEX_DESC = ("An open registry of specialist libraries, measured, stress-tested and model-checked on real hardware. "
              "Two kinds so far: embedded ring buffer (FIFO) libraries and CRC calculation in software, for "
              "microcontrollers on six boards, every number with its record and source.")
# What a search engine shows under the page's title. Pages not named here
# (reports, findings) get their first paragraph (describe).
DESCRIPTIONS = {
    "index.html": INDEX_DESC,
    "kinds.html": "The kinds of library tested so far, embedded ring buffers and CRC calculation in software: "
                  "what is measured, how many libraries and boards, and where the results, method and records are.",
    "method.html": "How the ring buffer libraries are tested: cycle-counted benchmarks on six microcontroller boards, "
                   "interrupt stress tests with a known-bad control, model checks and contract checks.",
    "results.html": "Results for embedded ring buffer libraries on six microcontroller boards: cycles per push and pop, "
                    "code size, interrupt stress tests and model checks, each with its record.",
    "results-crc.html": "Results for CRC libraries in software on six microcontroller boards: cycles for a short "
                        "message and per byte, cache on and off, flash and RAM bytes, each with its record.",
    "method-crc.html": "How the CRC libraries are measured and checked: one image per configuration and placement, "
                       "every call compared with a reference, host tests and CBMC proofs.",
    "reproduce.html": "How to rebuild the firmware bit for bit and repeat the measurements: every number comes from a "
                      "record that names the commit, the toolchain, the flags and the pinned library versions.",
    "repeats.html": "Repeats of the tests by people outside the project, and how to send in your own.",
}

SITE_PAGES = {"reports.html", "findings.html"}   # pages with no markdown source
SITE_FILES = {"data/libs.json": "data/libs.json", "data/crc.json": "data/crc.json"}   # served as they are: output path -> file under site/
MISSING = []   # (page source, link target): links to files that are not in the tree


def render(md_text, src_rel, c, pagemap):
    """Markdown to HTML; rewrite links: known pages -> .html, repo files -> REPO_URL."""
    base = os.path.dirname(src_rel)

    def fix(m):
        text, target = m.group(1), m.group(2)
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            return m.group(0)
        path, _, frag = target.partition("#")
        full = os.path.normpath(os.path.join(base, path)) if path else src_rel
        if full in pagemap:
            return f"[{text}]({pagemap[full]}{'#' + frag if frag else ''})"
        if base == "site/content" and path in SITE_PAGES | set(pagemap.values()) | set(SITE_FILES):
            return m.group(0)   # a site page or file named as the site names it (results.html)
        if not os.path.exists(os.path.join(ROOT, full)):
            MISSING.append((src_rel, target))
        return f"[{text}]({c['REPO_URL']}/{full}{'#' + frag if frag else ''})"
    md_text = re.sub(r"\[([^\]]*)\]\(([^)\s]+)\)", fix, md_text)
    out = markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc"])
    return out.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")


def title_of(md_text, default):
    m = re.search(r"^# (.+)$", md_text, re.M)
    return m.group(1).strip() if m else default


def main():
    args = sys.argv[1:]
    preview = "--preview" in args
    args = [a for a in args if a != "--preview"]
    out = args[0] if args else os.path.join(SITE, "_build")
    os.makedirs(out, exist_ok=True)
    c = conf()
    global SITE_URL
    SITE_URL = c.get("SITE_URL", "").rstrip("/")
    findings = [f for f in c.get("PUBLISH_FINDINGS", "").split(",") if f.strip()]
    reports = sorted(f for f in os.listdir(os.path.join(ROOT, "reports")) if f.endswith(".md"))

    # source (repo-relative) -> output file
    pagemap = {"site/content/index.md": "index.html", "site/content/method.md": "method.html",
               "site/content/reproduce.md": "reproduce.html", "site/content/repeats.md": "repeats.html",
               "site/content/compare.html": "compare.html", "site/content/kinds.md": "kinds.html",
               "site/content/compare-crc.html": "compare-crc.html",
               "RESULTS.md": "results.html",
               # the CRC kind (DECISIONS 2026-11-24: static pages first)
               "site/content/results-crc.md": "results-crc.html", "site/content/method-crc.md": "method-crc.html"}
    for r in reports:
        pagemap[f"reports/{r}"] = "report-" + r[:-3] + ".html"
    for f in findings:
        pagemap[f"verify/findings/{f}/README.md"] = "finding-" + f + ".html"

    # The overview of the kinds ("Results" in the menu) is written from the data
    # by site/kinds_page.py; a page whose counts differ from the data is not built.
    if open(os.path.join(SITE, "content/kinds.md")).read() != kinds_page.markdown():
        sys.exit("build refused: site/content/kinds.md is not up to date (python3 -I site/kinds_page.py --write)")
    # The CRC kind's data (site/data/crc.json) is written from records/crc by site/crc_data.py.
    if open(os.path.join(SITE, "data/crc.json")).read() != crc_data.text():
        sys.exit("build refused: site/data/crc.json is not up to date (python3 -I site/crc_data.py --write)")
    pages = {}
    for src, dst in pagemap.items():
        if src.endswith(".html"):   # the comparison page is built below; in pagemap only as a link target
            continue
        text = strip_embargo(open(os.path.join(ROOT, src)).read())
        nav_on = {"index.html": "index", "method.html": "method", "results.html": "kinds", "kinds.html": "kinds",
                  "results-crc.html": "kinds", "method-crc.html": "method",
                  "reproduce.html": "reproduce", "repeats.html": "repeats"}.get(
            dst, "reports" if dst.startswith("report-") else "findings")
        title = INDEX_TITLE if dst == "index.html" else title_of(text, dst)
        pages[dst] = page(dst, title, render(text, src, c, pagemap), nav_on, DESCRIPTIONS.get(dst) or describe(text))

    rep = "".join(f'<li><a href="{pagemap["reports/" + r]}">{html.escape(title_of(open(os.path.join(ROOT, "reports", r)).read(), r))}</a> '
                  f'<span style="color:var(--mute)">({r[:10]})</span></li>' for r in reversed(reports))
    pages["reports.html"] = page("reports", "Reports", f"<h1>Reports</h1><ul>{rep}</ul>", "reports",
                                 "The reports behind the results: what was run, on which boards, at which commit, and what came out.")
    fin = "".join(f'<li><a href="{pagemap[f"verify/findings/{f}/README.md"]}">'
                  f'{html.escape(title_of(open(os.path.join(ROOT, "verify/findings", f, "README.md")).read(), f))}</a></li>'
                  for f in findings)
    pages["findings.html"] = page("findings", "Findings", (
        "<h1>Findings</h1><p>Defects found by the tests. Each was reported to the maintainer first; "
        "details are published after 90 days or when the maintainer agrees. Findings still under that "
        "notice period are not listed.</p>" + (f"<ul>{fin}</ul>" if fin else "<p>None published yet.</p>")),
        "findings", "Defects found by the tests, published after the maintainer was told and the notice period is over.")

    # Interactive comparison: static controls, the data of site/data/libs.json
    # (site/gen_libdata.py) and site/compare.js, all inline. The embargo check
    # below covers the data like any other page text.
    data = open(os.path.join(SITE, "data/libs.json")).read().replace("</", "<\\/")
    pages["compare.html"] = page("compare", "Compare embedded ring buffers", (
        open(os.path.join(SITE, "content/compare.html")).read()
        + f'<script type="application/json" id="libdata">{data}</script>'
        + f'<script>{open(os.path.join(SITE, "compare.js")).read()}</script>'), "compare",
        "Compare embedded ring buffer libraries by board: speed, code size, stress test and model check results, "
        "with filters and your own weights.")
    # The CRC kind's comparison: static controls, the data of site/data/crc.json (site/crc_data.py) and
    # site/compare-crc.js, all inline, as for the ring buffers.
    cdata = open(os.path.join(SITE, "data/crc.json")).read().replace("</", "<\\/")
    pages["compare-crc.html"] = page("compare-crc", "Compare CRC calculation in software", (
        open(os.path.join(SITE, "content/compare-crc.html")).read()
        + f'<script type="application/json" id="crcdata">{cdata}</script>'
        + f'<script>{open(os.path.join(SITE, "compare-crc.js")).read()}</script>'), "compare",
        "Compare CRC libraries in software by CRC, board and message: cycles per call and per byte as ranges over "
        "eight code placements, flash and RAM bytes, the reference as a row; no ranking.")

    # What the server shows for an address that does not exist (GitHub Pages serves 404.html).
    pages["404.html"] = page("404", "Page not found", (
        '<h1>Page not found</h1><p>There is no page at this address. The <a href="index.html">front page</a>, '
        'the <a href="compare.html">comparison</a>, the <a href="results.html">results</a> and the '
        '<a href="reports.html">reports</a> are where they were.</p>'), "", listed=False)

    if MISSING:
        for src, target in MISSING:
            print(f"BROKEN LINK: {src} links to {target}, which is not in the tree", file=sys.stderr)
        sys.exit("build refused: a page links to a file that does not exist")

    # Files served as they are (the data of the comparison, for scripts and AI
    # agents): through the same embargo check as the pages.
    files = {name: open(os.path.join(SITE, src)).read() for name, src in SITE_FILES.items()}
    files["favicon.svg"] = FAVICON
    # For search engines: every page by its address, and where the list is.
    if SITE_URL:
        urls = [SITE_URL + "/"] + [f"{SITE_URL}/{n}" for n in sorted(pages) if n not in ("index.html", "404.html")]
        files["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                + "".join(f"<url><loc>{html.escape(u)}</loc></url>\n" for u in urls) + "</urlset>\n")
        files["robots.txt"] = f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n"
    words = embargo_words()
    held = [(name, w) for name, body in files.items() for w in words if w in body.lower()]
    for name, w in held:
        print(f"EMBARGO: '{w}' appears in {name}", file=sys.stderr)
    if held:   # also in a preview: a data file cannot carry a banner
        sys.exit("build refused: embargoed material in a served file (see site/embargo.txt)")
    bad = [(name, w) for name, body in pages.items() for w in words if w in body.lower()]
    if bad:
        for name, w in bad:
            print(f"EMBARGO: '{w}' appears in {name}", file=sys.stderr)
        if not preview:
            sys.exit("build refused: embargoed material on a page (see site/embargo.txt)")
        banner = ('<div style="background:#b3261e;color:#fff;padding:10px 16px;font-weight:600">'
                  'PREVIEW - contains embargoed material, not for publication</div>')
        for name in {n for n, _ in bad}:
            pages[name] = pages[name].replace("<header>", banner + "<header>", 1)
    for name, body in {**pages, **files}.items():
        os.makedirs(os.path.dirname(os.path.join(out, name)), exist_ok=True)
        open(os.path.join(out, name), "w").write(body)
    print(f"{len(pages)} pages and {len(files)} other file{'s' if len(files) != 1 else ''} written to {out}")


if __name__ == "__main__":
    main()
