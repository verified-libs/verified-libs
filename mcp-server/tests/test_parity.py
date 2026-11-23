#!/usr/bin/env python3
"""The Python port (vlquery.py) against the website's own script (site/compare.js).

site/compare.js is run as it is, under gjs with a stand-in for the page
(page_harness.js), for a few thousand views: every board, every producer/
consumer mode, with filters, weights and sort orders drawn with a fixed seed.
For each view the port must give the same rows in the same order, the same
text in every cell, the same three groups, the same count line, the same
source line and the same address.

Skipped if gjs is not installed (gjs is what the lab host has; another
JavaScript engine needs only another way to read a file in page_harness.js).

    python3 -m unittest discover -s mcp-server/tests
"""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
import vlquery as q   # noqa: E402

COMPARE_JS = os.path.join(ROOT, "site", "compare.js")
# VL_PARITY_DATA: another libs.json to run the comparison on (e.g. one with benchmark version 2 in it)
DATA = os.environ.get("VL_PARITY_DATA") or q.default_data_path()
FLAG_WORDS = [f for f in q.FLAGS if f != "nosingle"] + ["single", "two"]


def fragments(D, seed=20261121, random_views=2500):
    """The views to compare: the corner cases by hand, the rest drawn."""
    boards = [b["id"] for b in D["boards"]]
    out = ["", "#", "#board=nosuchboard", "#w=12,-3,x,5,7", "#w=0,0,0,0", "#w=3", "#f=two", "#f=nosingle,single",
           "#f=single,nosingle", "#sort=score", "#sort=-score", "#w=1,1,1,1&sort=-score", "#sort=-name",
           "#lang=C%2B%2B", "#lang=Rust&topo=MPMC&cores=2", "#topo=SPSC&cores=2", "#unknown=1&board=pico2",
           "#board=pico2&board=nucleo-h723zg", "#w=5,5,0,0", "#w=0,0,0,10&f=zc", "#cores=1", "#topo=XYZ&cores=3&lang=Ada"]
    for b in boards:                       # every board in every mode, plain and ranked
        for topo in [""] + q.TOPOS:
            base = "#board=" + b + ("&topo=" + topo if topo else "")
            out += [base, base + "&f=single", base + "&w=10,10,10,10", base + "&w=1,2,3,4&f=single"]
            out += [base + "&sort=" + d + k for k in q.SORT_KEYS for d in ("", "-")]
            out += [base + "&w=7,0,3,0&sort=" + d + k for k in q.SORT_KEYS for d in ("", "-")]
    rnd = random.Random(seed)
    for _ in range(random_views):
        parts = ["board=" + rnd.choice(boards)]
        if rnd.random() < 0.6:
            parts.append("w=" + ",".join(str(rnd.choice([0, 0, 1, 3, 5, 10])) for _ in range(4)))
        fl = [f for f in FLAG_WORDS if rnd.random() < 0.2]
        if fl:
            parts.append("f=" + ",".join(fl))
        if rnd.random() < 0.5:
            parts.append("topo=" + rnd.choice(q.TOPOS))
        if rnd.random() < 0.3:
            parts.append("cores=" + rnd.choice(["1", "2"]))
        if rnd.random() < 0.3:
            parts.append("series=" + rnd.choice(["1", "1", "2", "3"]))
        if rnd.random() < 0.3:
            parts.append("lang=" + rnd.choice(["C", "C%2B%2B", "Rust"]))
        if rnd.random() < 0.6:
            parts.append("sort=" + rnd.choice(["", "-"]) + rnd.choice(q.SORT_KEYS))
        rnd.shuffle(parts)
        out.append("#" + "&".join(parts))
    return out


def port_view(D, frag):
    st = q.state_from_hash(D, frag)
    rs = q.compare(D, st)
    seps, prev = [], None
    for i, r in enumerate(rs):
        if r["state"] != prev:
            seps.append([i, q.GROUP_TEXT[r["state"]]])
        prev = r["state"]
    return {"hash": frag, "written": q.hash_of(st), "header": q.header(st),
            "rows": [q.page_cells(D, st, r) for r in rs], "seps": seps,
            "count": q.count_text(D, st, len(rs)), "src": q.source_text(D, st)}


@unittest.skipUnless(shutil.which("gjs"), "gjs is not installed: the website's script cannot be run here")
class Parity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.D, _ = q.load(DATA)
        cls.frags = fragments(cls.D)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fragments.txt")
            with open(path, "w") as fh:
                fh.write("\n".join(cls.frags) + "\n")
            # The root collation, so that the order does not depend on the host's language.
            env = dict(os.environ, LC_ALL="C.UTF-8", LANG="C.UTF-8")
            p = subprocess.run(["gjs", os.path.join(HERE, "page_harness.js"), COMPARE_JS, DATA, path],
                               capture_output=True, text=True, timeout=600, env=env)
        if p.returncode != 0:
            raise RuntimeError("page_harness.js failed:\n" + p.stderr[-2000:])
        lines = [json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")]
        cls.engine = lines[0]
        cls.page = lines[1:]

    def test_every_view_is_the_same(self):
        # The first fragment is the empty line, which the harness skips: the page with no fragment is "#".
        frags = [f for f in self.frags if f != ""]
        self.assertEqual(len(self.page), len(frags))
        shown = set()
        for frag, page in zip(frags, self.page):
            port = port_view(self.D, frag)
            for key in ("written", "header", "seps", "count", "src"):
                self.assertEqual(port[key], page[key], f"{key} differs for {frag}")
            self.assertEqual([r[0][0] for r in port["rows"]], [r[0][0] for r in page["rows"]], f"row order differs for {frag}")
            self.assertEqual(port["rows"], page["rows"], f"a cell differs for {frag}")
            shown.update(r[0][0] for r in port["rows"])
        # The views together must have shown every configuration, or the test proves less than it says.
        self.assertEqual(shown, {lib["name"] for lib in self.D["libs"]})

    def test_address_round_trip(self):
        for page in self.page:
            st = q.state_from_hash(self.D, page["written"])
            self.assertEqual(q.hash_of(st), page["written"])
            self.assertEqual(st, q.state_from_hash(self.D, page["hash"]), page["hash"])

    def test_character_order(self):
        """The port's order of ASCII is the engine's (lower case before upper at the last level)."""
        chars = sorted((chr(c) for c in range(32, 127)), key=lambda ch: q._coll_key(ch))
        self.assertEqual("".join(chars), self.engine["ascii_order"])

    def test_sorted_fields_are_ascii(self):
        """Outside ASCII the port's order is only an approximation: say so when the data gets there."""
        for lib in self.D["libs"]:
            for k in ("name", "license", "lang"):
                self.assertTrue(lib[k].isascii(), f"{lib['name']}: {k} is not ASCII; check locale_compare")


if __name__ == "__main__":
    unittest.main()
