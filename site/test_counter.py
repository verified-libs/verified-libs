#!/usr/bin/env python3
"""A test of the visit counter switch (GOATCOUNTER_CODE in site/site.conf,
site/build.py counter()), in both states, and of how check_links.py treats
its script:
  - empty: a page has no script from elsewhere and no sentence about
    counting;
  - set: every listed page has GoatCounter's tag, exactly, at the end of its
    body, and the sentence in its footer; 404.html has neither;
  - a setting that is not a site code (letters, digits, hyphens) stops the
    build, so nothing else from it reaches a page;
  - check_links.py: the counter's script is not a link; it passes where the
    setting names it, and is reported as broken where the setting is empty,
    on 404.html, or for any other script from elsewhere.
Usage: python3 -I site/test_counter.py      exit 0: as expected
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build   # noqa: E402

fails = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


TAG = '<script data-goatcounter="https://verified-libs.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'
build.GOATCOUNTER = ""
off, off404 = build.page("kinds", "Results", "<p>x</p>", "kinds"), build.page("404", "Not found", "<p>x</p>", "", listed=False)
check("<script" not in off.split("</main>")[1] and "goatcounter" not in off.lower() and "src=" not in off,
      "empty: no script from elsewhere, no counting sentence")
build.GOATCOUNTER = build.counter_code("verified-libs")
on, on404 = build.page("kinds", "Results", "<p>x</p>", "kinds"), build.page("404", "Not found", "<p>x</p>", "", listed=False)
check(on.endswith(TAG + "\n</body></html>\n"), "set: the tag, exactly, at the end of the body")
check("Visits are counted with" in on.split("<footer>")[1] and "https://www.goatcounter.com/help/privacy" in on,
      "set: the sentence in the footer, with the link to GoatCounter's privacy page")
check("goatcounter" not in on404.lower() and "src=" not in on404, "set: nothing on 404.html")
check(on.replace(" Visits are counted with", "").count("<script") == off.count("<script") + 1, "set: one script more, no other")
for bad in ('verified"-libs', "x.goatcounter.com", "a b", "<script>", "code/count"):
    try:
        build.counter_code(bad)
        check(False, f"refused: {bad!r}")
    except SystemExit:
        check(True, f"refused: {bad!r}")
build.GOATCOUNTER = ""

with tempfile.TemporaryDirectory() as t:
    site, tree = os.path.join(t, "site"), os.path.join(t, "tree")
    os.makedirs(site)
    os.makedirs(tree)
    conf_on, conf_off = os.path.join(t, "on.conf"), os.path.join(t, "off.conf")
    base = "REPO_URL=https://github.com/verified-libs/verified-libs/blob/main\n"
    open(conf_on, "w").write(base + "GOATCOUNTER_CODE=verified-libs\n")
    open(conf_off, "w").write(base + "GOATCOUNTER_CODE=\n")

    def links(pages, conf):
        for f in os.listdir(site):
            os.remove(os.path.join(site, f))
        for n, body in pages.items():
            open(os.path.join(site, n), "w").write(body)
        p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "check_links.py"), site, tree, conf], capture_output=True, text=True)
        return p.returncode, p.stdout
    page = '<html><body><a href="index.html">x</a>' + TAG + "</body></html>"
    rc, out = links({"index.html": page}, conf_on)
    check(rc == 0 and "the visit counter's script on 1 pages" in out, "check_links: the counter passes where the setting names it")
    rc, out = links({"index.html": page}, conf_off)
    check(rc == 1 and "not the visit counter" in out, "check_links: the counter is broken where the setting is empty")
    rc, out = links({"index.html": '<html><body><a href="index.html">x</a></body></html>', "404.html": page}, conf_on)
    check(rc == 1 and "404.html" in out, "check_links: the counter on 404.html is broken")
    rc, out = links({"index.html": '<html><body><script src="https://example.org/x.js"></script></body></html>'}, conf_on)
    check(rc == 1, "check_links: another script from elsewhere is broken")
print(f"{len(fails)} failed")
sys.exit(1 if fails else 0)
