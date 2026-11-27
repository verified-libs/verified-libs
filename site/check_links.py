#!/usr/bin/env python3
"""Check every link of a built site (lab/tools/publish.sh runs this).

Usage: python3 site/check_links.py SITE_DIR TREE_DIR [SITE_CONF]   (default: site/site.conf)

A link to another page must name a page in SITE_DIR, and its anchor an id
on that page (on a comparison page the anchor may instead be the address of a
view, key=value pairs, which its script reads); a link to another file of the site (data/libs.json, favicon.svg) must name
a file in SITE_DIR; a link into the repository (REPO_URL of site.conf) must name
a file in TREE_DIR, the tree that is published with the site. Links to
other sites are not fetched. Exit 1 if a link is broken.

Scripts: a <script src="..."> is not a link and is not followed. The only
one a page may have is the visit counter's (GoatCounter, when
GOATCOUNTER_CODE is set in site.conf: //gc.zgo.at/count.js, with
data-goatcounter naming https://<code>.goatcounter.com/count), and never on
404.html; any other script with a src, or the counter where the setting is
empty, is reported and counts as broken.
"""
import glob
import os
import re
import sys

site, tree = sys.argv[1], sys.argv[2]
conf = open(sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "site.conf")).read()
repo = re.search(r"^REPO_URL=(\S+)", conf, re.M).group(1).rstrip("/") + "/"
pages = {os.path.basename(f): open(f).read() for f in glob.glob(os.path.join(site, "*.html"))}
ids = {n: set(re.findall(r'\bid="([^"]+)"', body)) for n, body in pages.items()}
bad = links = 0
for name, body in sorted(pages.items()):
    for href in sorted(set(re.findall(r'href="([^"]+)"', body))):
        links += 1
        if href.startswith(repo):
            if not os.path.exists(os.path.join(tree, href[len(repo):].split("#")[0])):
                print(f"{name}: {href}: not in the published tree"); bad += 1
        elif not re.match(r"^[a-z]+:", href):
            page, _, frag = href.partition("#")
            page = page or name
            if not page.endswith(".html") and ".." not in page and os.path.isfile(os.path.join(site, page)):
                continue   # a file served as it is
            if page not in pages:
                print(f"{name}: {href}: no such page"); bad += 1
            elif frag and frag not in ids[page] and not (page.startswith("compare") and re.fullmatch(r"[a-z]+=[^&]*(&[a-z]+=[^&]*)*", frag.replace("&amp;", "&"))):
                # a comparison page's address of a view (#board=...&scen=...) is read by its script, not an anchor
                print(f"{name}: {href}: no such anchor"); bad += 1
code = (re.search(r"^GOATCOUNTER_CODE=(\S*)", conf, re.M) or [None, ""])[1]
counter = (f'<script data-goatcounter="https://{code}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'
           if code else None)
scripts = 0
for name, body in sorted(pages.items()):
    for tag in re.findall(r"<script\b[^>]*\bsrc=[^>]*>(?:</script>)?", body):
        scripts += 1
        if tag != counter or name == "404.html":
            print(f"{name}: a script from elsewhere that is not the visit counter of site.conf: {tag[:120]}"); bad += 1
print(f"{links} links on {len(pages)} pages, {bad} broken" + (f"; the visit counter's script on {scripts} pages" if scripts else
                                                                 "; no script from elsewhere"))
sys.exit(1 if bad else 0)
