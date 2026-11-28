#!/usr/bin/env python3
"""A test of the lists on the pages (site/build.py nest_lists):
  - the sources are CommonMark, as GitHub renders them: a nested item is
    indented to its parent's text (2 spaces under "- ", 3 under "1. "), and a
    list may follow a paragraph with no blank line between them. Small cases
    of each are rendered as the build renders a page, and must give nested
    lists;
  - the whole site is built, and no page may have a literal list mark ("- ",
    "* ", "+ " or "1. " at the start of a line) in the text of a paragraph
    or a list item, outside code: that is a list python-markdown did not
    see.
Usage: python3 -I site/test_lists.py [DIR]      exit 0: as expected
  DIR: check the pages of a site built there, instead of building one
"""
import html.parser
import os
import re
import subprocess
import sys
import tempfile

import markdown

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build   # noqa: E402

fails = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


def md(text):
    out = markdown.markdown(build.nest_lists(text), extensions=["tables", "fenced_code", "toc", "md_in_html"])
    return re.sub(r"\s+", " ", out).replace("> <", "><").strip()


CASES = [
    ("two spaces under -", "- a\n  - b\n  - c\n- d\n",
     "<ul><li>a<ul><li>b</li><li>c</li></ul></li><li>d</li></ul>"),
    ("three levels", "- a\n  - b\n    - c\n",
     "<ul><li>a<ul><li>b<ul><li>c</li></ul></li></ul></li></ul>"),
    ("three spaces under 1.", "1. a\n   - b\n2. c\n",
     "<ol><li>a<ul><li>b</li></ul></li><li>c</li></ol>"),
    ("four spaces stay one level", "- a\n    - b\n",
     "<ul><li>a<ul><li>b</li></ul></li></ul>"),
    ("a continuation line", "- a\n  more\n  - b\n",
     "<ul><li>a more<ul><li>b</li></ul></li></ul>"),
    ("a list after a paragraph", "**Title.**\n- a\n- b\n",
     "<p><strong>Title.</strong></p><ul><li>a</li><li>b</li></ul>"),
    ("an item after a paragraph inside an item",
     "- a\n  - b\n\n  More of a.\n- c\n  - d\n",
     "<ul><li><p>a</p><ul><li>b</li></ul><p>More of a.</p></li><li><p>c</p><ul><li>d</li></ul></li></ul>"),
    ("a fence outside a list is kept", "```\n- a\n  - b\n```\n",
     "<pre><code>- a - b </code></pre>"),
    ("an indented code block outside a list is kept", "Text.\n\n    - a\n",
     "<p>Text.</p><pre><code>- a </code></pre>"),
]
for name, src, want in CASES:
    got = md(src)
    check(got == want, f"{name}: {got}" if got != want else name)


class Text(html.parser.HTMLParser):
    """The literal list marks in the text of paragraphs and list items, outside code."""
    def __init__(self):
        super().__init__()
        self.open, self.code, self.found = [], 0, []   # found: the lines that begin with a mark

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "li"):
            self.open.append(tag)
        elif tag in ("code", "pre"):
            self.code += 1

    def handle_endtag(self, tag):
        if tag in ("p", "li") and self.open:
            self.open.pop()
        elif tag in ("code", "pre"):
            self.code -= 1

    def handle_data(self, data):
        # a mark at the start of a source line: the line begins inside this piece of text (after a tag such as
        # <strong>, a mark is followed by the end of the piece)
        if self.open and not self.code:
            m = re.search(r"\n[ \t]*(?:[-*+]|\d+\.)(?: +|$)[^\n]*", data)
            if m:
                self.found.append(m.group(0).strip()[:90])


def pages_check(t):
    pages = sorted(f for f in os.listdir(t) if f.endswith(".html"))
    check(len(pages) > 10, f"{len(pages)} pages")
    for f in pages:
        x = Text()
        x.feed(open(os.path.join(t, f)).read())
        x.close()
        check(not x.found, f"{f}: no literal list mark" + "".join("\n       " + s for s in x.found[:3]))


if len(sys.argv) > 1:
    pages_check(sys.argv[1])
else:
    with tempfile.TemporaryDirectory() as t:
        p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "build.py"), t], capture_output=True, text=True)
        check(p.returncode == 0, "the site builds" + ("" if p.returncode == 0 else ": " + p.stderr[-300:]))
        pages_check(t)

if fails:
    print(f"{len(fails)} failed")
    sys.exit(1)
print("all as expected")
