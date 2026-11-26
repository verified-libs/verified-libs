#!/usr/bin/env python3
"""The Python port (crcquery.py) against the CRC page's own script
(site/compare-crc.js), as test_parity.py does for the ring buffers.

site/compare-crc.js is run as it is, under gjs with the same stand-in for the
page (page_harness.js), for every CRC, board, length, start, cache and sort,
with filters and a chosen configuration, and views drawn with a fixed seed.
For each view the port must give the same header, the same rows in the same
order with the same text in every cell (the overlap marks included), the same
separators, count line, note, source line and address.

Skipped if gjs is not installed.

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
import crcquery as cq   # noqa: E402

COMPARE_JS = os.path.join(ROOT, "site", "compare-crc.js")
DATA = os.environ.get("VL_PARITY_CRC_DATA") or cq.default_data_path()


def fragments(C, seed=20261125, random_views=1500):
    """The views to compare: the corner cases by hand, every plain view, the rest drawn."""
    boards = [b["id"] for b in C["boards"]]
    enc = cq._enc
    out = ["", "#", "#crc=nosuch", "#board=nosuchboard", "#len=1", "#len=17", "#off=2", "#cache=maybe",
           "#sort=score", "#sort=-flash", "#sort=-", "#lang=Ada", "#table=ROM", "#class=nosuch", "#row=nosuch",
           "#class=%E0%A4%A", "#crc=%", "#row=adapter_etl_crc8_t256", "#board=pico2&board=nucleo-h723zg",
           "#unknown=1&cache=off", "#crc=" + enc(C["crcs"][2]) + "&row=adapter_etl_crc32_t256",
           "#w=12,-3,x", "#w=0,0,0", "#w=3", "#w=1,2,3,4,5", "#w=%203,4.5,+2", "#w=0,0,7&sort=name", "#w=5,5,5&sort=-ram",
           "#w=10,0,0&table=RAM", "#w=0,0,10&lang=Rust",
           # the board's CRC unit: a row of the table, chosen, filtered by class and kind, scored; none on some boards
           "#row=adapter_hw_crc32", "#board=nucleo-g474re&crc=" + enc(C["crcs"][2]) + "&row=adapter_hw_crc8",
           "#board=pico2&crc=" + enc(C["crcs"][2]), "#board=nucleo-g0b1re&class=" + enc("hardware unit"),
           "#board=nucleo-g474re&kind=hardware", "#board=nucleo-g474re&kind=library&w=10,0,0", "#kind=unit",
           "#board=nucleo-h723zg&kind=hardware&w=3,3,3&row=adapter_hw_crc32", "#board=nrf5340dk&kind=hardware",
           "#board=nucleo-h723zg&cache=off&w=10,0,0", "#board=pico2&crc=" + enc(C["crcs"][2]) + "&cache=off",
           "#board=nucleo-h723zg&w=10,10,10&row=adapter_etl_crc32_t256_ram",
           "#board=pico2&cache=off&len=1024&row=adapter_crcany_crc32_word_ram"]
    weights = ["10,0,0", "0,10,0", "0,0,10", "5,5,0", "3,3,3", "10,10,1", "1,0,10"]
    for crc in C["crcs"]:
        cfgs = cq.configs_of(C, crc)
        for b in boards:
            for length in cq.LENS:
                for off in ("0", "1"):
                    for cache in ("on", "off"):
                        out.append(f"#crc={enc(crc)}&board={b}&len={length}&off={off}&cache={cache}")
            base = f"#crc={enc(crc)}&board={b}"
            out += [base + "&sort=" + d + k for k in cq.SORTS for d in ("", "-")]
            out += [base + "&cache=off&row=" + enc(c["adapter"]) for c in cfgs]
            out += [base + "&row=" + enc(c["adapter"]) + "&len=1024" for c in cfgs]
            out += [base + "&class=" + enc(k) for k in cq.classes_of(C, crc)]
            out += [base + "&table=" + t for t in cq.TABLES] + [base + "&lang=" + enc(x) for x in cq.LANGS]
            out += [base + "&kind=" + k for k in cq.KINDS] + [base + "&kind=" + k + "&w=3,3,3" for k in cq.KINDS]
            for w in weights:                 # every board and CRC with weights: plain, cache off, a row chosen, sorted
                out += [base + "&w=" + w, base + "&w=" + w + "&cache=off&len=1024",
                        base + "&w=" + w + "&row=" + enc(cfgs[len(w) % len(cfgs)]["adapter"]),
                        base + "&w=" + w + "&sort=-flash"]
    rnd = random.Random(seed)
    for _ in range(random_views):
        crc = rnd.choice(C["crcs"])
        cfgs = cq.configs_of(C, crc)
        parts = ["crc=" + enc(crc), "board=" + rnd.choice(boards)]
        for key, vals, p in (("len", cq.LENS, 0.7), ("off", ["0", "1"], 0.5), ("cache", ["on", "off"], 0.5),
                             ("lang", cq.LANGS, 0.2), ("table", cq.TABLES, 0.2), ("kind", cq.KINDS, 0.2),
                             ("class", cq.classes_of(C, crc), 0.2), ("row", [c["adapter"] for c in cfgs], 0.5),
                             ("sort", [d + k for k in cq.SORTS for d in ("", "-")], 0.3),
                             ("w", [",".join(str(rnd.choice([0, 0, 1, 3, 5, 10])) for _ in range(3)) for _ in range(4)], 0.6)):
            if rnd.random() < p:
                parts.append(key + "=" + enc(rnd.choice(vals)))
        rnd.shuffle(parts)
        out.append("#" + "&".join(parts))
    return out


def port_view(C, frag):
    st = cq.state_from_hash(C, frag)
    v = cq.page_view(C, st)
    v.update(hash=frag, written=cq.hash_of(st))
    return v


@unittest.skipUnless(shutil.which("gjs"), "gjs is not installed: the website's script cannot be run here")
class ParityCRC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.C, _ = cq.load(DATA)
        cls.frags = fragments(cls.C)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fragments.txt")
            with open(path, "w") as fh:
                fh.write("\n".join(cls.frags) + "\n")
            env = dict(os.environ, LC_ALL="C.UTF-8", LANG="C.UTF-8")
            p = subprocess.run(["gjs", os.path.join(HERE, "page_harness.js"), COMPARE_JS, DATA, path],
                               capture_output=True, text=True, timeout=600, env=env)
        if p.returncode != 0:
            raise RuntimeError("page_harness.js failed:\n" + p.stderr[-2000:])
        cls.page = [json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")][1:]

    def test_every_view_is_the_same(self):
        frags = [f for f in self.frags if f != ""]
        self.assertEqual(len(self.page), len(frags))
        shown, marked, chosen, above, scored = set(), 0, 0, 0, 0
        for frag, page in zip(frags, self.page):
            port = port_view(self.C, frag)
            for key in ("written", "header", "seps", "count", "note", "src"):
                self.assertEqual(port[key], page[key], f"{key} differs for {frag}")
            self.assertEqual([r[0][0] for r in port["rows"]], [r[0][0] for r in page["rows"]], f"row order differs for {frag}")
            self.assertEqual(port["rows"], page["rows"], f"a cell differs for {frag}")
            shown.update(r[0][0] for r in port["rows"])
            marked += sum(1 for r in port["rows"] for c in r if "overlaps" in c)
            chosen += any("chosen" in r[0] for r in port["rows"])
            above += sum(1 for r in port["rows"] for c in r if cq.ABOVE_TEXT in c)
            scored += "Score (your weights)" in port["header"]
        # The views together must have shown every configuration and the reference, and marked overlaps.
        self.assertEqual(shown, {c["name"] for c in self.C["configurations"]} | {"reference, bitwise"})
        self.assertGreater(chosen, 100)
        self.assertGreater(marked, 100)
        self.assertGreater(scored, 500)
        self.assertGreater(above, 100)

    def test_address_round_trip(self):
        for page in self.page:
            st = cq.state_from_hash(self.C, page["written"])
            self.assertEqual(cq.hash_of(st), page["written"])
            self.assertEqual(st, cq.state_from_hash(self.C, page["hash"]), page["hash"])


class HardwareInTheTable(unittest.TestCase):
    """The board's CRC unit is a row of the same table (decided 2026-11-26): after the libraries, labelled in its
    name cell, scored like any row. With the kind filter on 'library' the scores are exactly those of the data
    without the unit; with it shown, the unit is in the order. Nothing on a board without one, and a line says so."""
    def test_hardware_in_the_table(self):
        C, _ = cq.load(DATA)
        hw = {c["adapter"] for c in C["configurations"] if c.get("role") == "hardware"}
        self.assertEqual(len(hw), 3)
        D2 = dict(C, configurations=[c for c in C["configurations"] if c["adapter"] not in hw])
        seen = scored_with = moved = 0
        for frag in fragments(C, random_views=300):
            st = cq.state_from_hash(C, frag)
            every, rs = cq.shown(C, st)
            v = cq.page_view(C, st)
            has = [x for x in every if x["c"]["adapter"] in hw]
            seen += bool(has)
            # the unit after the libraries in the list order; labelled in every row it has; no separator of its own
            idx = [x["c"]["adapter"] in hw for x in every]
            self.assertEqual(idx, sorted(idx), frag)
            for x, row in zip(rs, v["rows"]):
                self.assertEqual(cq.HW_LABEL in row[0], x["c"]["adapter"] in hw, frag)
            self.assertEqual([t for _, t in v["seps"]], [cq.BASELINE_TEXT] if cq.baseline_of(C, st) else [], frag)
            self.assertEqual("libraries only" in v["note"], not has, frag)
            if cq.weighted(st) and rs:
                lib = dict(st, kind="library")
                _, a = cq.shown(C, lib)
                _, b = cq.shown(D2, dict(st, kind=""))
                self.assertEqual([(x["c"]["adapter"], x["score"]) for x in a],
                                 [(x["c"]["adapter"], x["score"]) for x in b], frag)
                if any(x["c"]["adapter"] in hw for x in rs):
                    scored_with += 1
                    self.assertTrue(all(len(x["score"]) == 2 for x in rs), frag)
                    if not st["sort"]:
                        order = [x["score"][1] for x in rs]
                        self.assertEqual(order, sorted(order, reverse=True), frag)
                    libs_only = {x["c"]["adapter"]: x["score"] for x in a}
                    moved += any(libs_only.get(x["c"]["adapter"]) not in (None, x["score"]) for x in rs)
        self.assertGreater(seen, 100)
        self.assertGreater(scored_with, 50)
        self.assertGreater(moved, 10)   # where the unit is lowest, the libraries' scores are relative to it
        # nothing on a board without the unit: the nRF5340 and the SAM D20 have none, the Pico 2 no CRC-8
        for b, crcs in (("nrf5340dk", C["crcs"]), ("sam-d20-xpro", C["crcs"]), ("pico2", ["CRC-8/SMBUS"])):
            for crc in crcs:
                st = dict(cq.default_state(C), board=b, crc=crc)
                every, _ = cq.shown(C, st)
                self.assertFalse(any(x["c"]["adapter"] in hw for x in every), (b, crc))
                self.assertIn("libraries only", cq.page_view(C, st)["note"], (b, crc))


class ScoreMarkControl(unittest.TestCase):
    """The score's marks are judged on the score before rounding: judged on the shown text, the port must
    differ from the page somewhere (so the parity test would catch that change)."""
    def test_rounded_marks_differ(self):
        C, _ = cq.load(DATA)
        raw = cq.score_overlap
        def rounded(a, b):
            t = lambda r: [float(q) for q in (cq.q.to_fixed(r[0], 1), cq.q.to_fixed(r[1], 1))]
            return cq.overlap(t(a), t(b))
        differ = 0
        try:
            for frag in fragments(C):
                st = cq.state_from_hash(C, frag)
                if not cq.weighted(st):
                    continue
                want = cq.page_view(C, st)["rows"]
                cq.score_overlap = rounded
                got = cq.page_view(C, st)["rows"]
                cq.score_overlap = raw
                differ += want != got
        finally:
            cq.score_overlap = raw
        self.assertGreater(differ, 0)


if __name__ == "__main__":
    unittest.main()
