#!/usr/bin/env python3
"""Check every link of a built site (lab/tools/publish.sh runs this).

Usage: python3 site/check_links.py SITE_DIR TREE_DIR

A link to another page must name a page in SITE_DIR, and its anchor an id
on that page; a link to another file of the site (data/libs.json) must name
a file in SITE_DIR; a link into the repository (REPO_URL of site.conf) must name
a file in TREE_DIR, the tree that is published with the site. Links to
other sites are not fetched. Exit 1 if a link is broken.
"""
import glob
import os
import re
import sys

site, tree = sys.argv[1], sys.argv[2]
conf = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "site.conf")).read()
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
            if not page.endswith(".html") and "/" in page and ".." not in page and os.path.isfile(os.path.join(site, page)):
                continue   # a file served as it is
            if page not in pages:
                print(f"{name}: {href}: no such page"); bad += 1
            elif frag and frag not in ids[page]:
                print(f"{name}: {href}: no such anchor"); bad += 1
print(f"{links} links on {len(pages)} pages, {bad} broken")
sys.exit(1 if bad else 0)
