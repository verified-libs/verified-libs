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
import os
import re
import sys

import markdown

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embargo_strip import strip_embargo   # noqa: E402

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
"""

NAV = [("index", "Home"), ("results", "Results"), ("compare", "Compare"), ("method", "Method"),
       ("reproduce", "Reproduce"), ("repeats", "Repeats"), ("findings", "Findings"), ("reports", "Reports")]


def page(slug, title, body, nav_on):
    links = "".join(f'<a href="{s}.html"{" class=on" if s == nav_on else ""}>{t}</a>' for s, t in NAV[1:])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title if title.startswith("verified-libs") else title + " - verified-libs")}</title><style>{CSS}</style></head>
<body><header><nav><a class="brand" href="index.html">verified-libs</a>{links}</nav></header>
<main>{body}</main>
<footer>verified-libs &middot; contact@verified-libs.org &middot; built from the repository; every number links back to its source. Code MIT, texts and results CC&nbsp;BY&nbsp;4.0.</footer>
</body></html>
"""


# The front page's heading is the project's name; its browser title says more.
INDEX_TITLE = "verified-libs: embedded ring buffer libraries, measured and tested on real hardware"

SITE_PAGES = {"reports.html", "findings.html"}   # pages with no markdown source
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
        if base == "site/content" and path in SITE_PAGES | set(pagemap.values()):
            return m.group(0)   # a site page named as the site names it (results.html)
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
    findings = [f for f in c.get("PUBLISH_FINDINGS", "").split(",") if f.strip()]
    reports = sorted(f for f in os.listdir(os.path.join(ROOT, "reports")) if f.endswith(".md"))

    # source (repo-relative) -> output file
    pagemap = {"site/content/index.md": "index.html", "site/content/method.md": "method.html",
               "site/content/reproduce.md": "reproduce.html", "site/content/repeats.md": "repeats.html",
               "site/content/compare.html": "compare.html",
               "RESULTS.md": "results.html"}
    for r in reports:
        pagemap[f"reports/{r}"] = "report-" + r[:-3] + ".html"
    for f in findings:
        pagemap[f"verify/findings/{f}/README.md"] = "finding-" + f + ".html"

    pages = {}
    for src, dst in pagemap.items():
        if src.endswith(".html"):   # the comparison page is built below; in pagemap only as a link target
            continue
        text = strip_embargo(open(os.path.join(ROOT, src)).read())
        nav_on = {"index.html": "index", "method.html": "method", "results.html": "results",
                  "reproduce.html": "reproduce", "repeats.html": "repeats"}.get(
            dst, "reports" if dst.startswith("report-") else "findings")
        title = INDEX_TITLE if dst == "index.html" else title_of(text, dst)
        pages[dst] = page(dst, title, render(text, src, c, pagemap), nav_on)

    rep = "".join(f'<li><a href="{pagemap["reports/" + r]}">{html.escape(title_of(open(os.path.join(ROOT, "reports", r)).read(), r))}</a> '
                  f'<span style="color:var(--mute)">({r[:10]})</span></li>' for r in reversed(reports))
    pages["reports.html"] = page("reports", "Reports", f"<h1>Reports</h1><ul>{rep}</ul>", "reports")
    fin = "".join(f'<li><a href="{pagemap[f"verify/findings/{f}/README.md"]}">'
                  f'{html.escape(title_of(open(os.path.join(ROOT, "verify/findings", f, "README.md")).read(), f))}</a></li>'
                  for f in findings)
    pages["findings.html"] = page("findings", "Findings", (
        "<h1>Findings</h1><p>Defects found by the tests. Each was reported to the maintainer first; "
        "details are published after 90 days or when the maintainer agrees. Findings still under that "
        "notice period are not listed.</p>" + (f"<ul>{fin}</ul>" if fin else "<p>None published yet.</p>")),
        "findings")

    # Interactive comparison: static controls, the data of site/data/libs.json
    # (site/gen_libdata.py) and site/compare.js, all inline. The embargo check
    # below covers the data like any other page text.
    data = open(os.path.join(SITE, "data/libs.json")).read().replace("</", "<\\/")
    pages["compare.html"] = page("compare", "Compare embedded ring buffers", (
        open(os.path.join(SITE, "content/compare.html")).read()
        + f'<script type="application/json" id="libdata">{data}</script>'
        + f'<script>{open(os.path.join(SITE, "compare.js")).read()}</script>'), "compare")

    if MISSING:
        for src, target in MISSING:
            print(f"BROKEN LINK: {src} links to {target}, which is not in the tree", file=sys.stderr)
        sys.exit("build refused: a page links to a file that does not exist")

    words = embargo_words()
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
    for name, body in pages.items():
        open(os.path.join(out, name), "w").write(body)
    print(f"{len(pages)} pages written to {out}")


if __name__ == "__main__":
    main()
