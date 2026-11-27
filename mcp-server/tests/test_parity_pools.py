#!/usr/bin/env python3
"""The Python port (poolsquery.py) against the pools page's own script
(site/compare-pools.js), as test_parity_crc.py does for the CRC kind.

site/compare-pools.js is run as it is, under gjs with the same stand-in for
the page (page_harness.js), for every board, scenario, cache and sort, with
filters, weights and a chosen configuration, and views drawn with a fixed
seed. For each view the port must give the same header, the same rows in the
same order with the same text in every cell (the overlap marks included), the
same separators, count line, note, source line and address.

Two data files: the committed site/data/pools.json (until the first series is
published it holds no records, and the page says so), and SYNTHETIC data made
in a temporary directory by site/pools_synthetic.py and site/pools_data.py
(made-up numbers, never written into the tree), so that the views with rows
are tested before the series exists. VL_PARITY_POOLS_DATA names another file
instead of the synthetic one.

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
import poolsquery as pq   # noqa: E402

COMPARE_JS = os.path.join(ROOT, "site", "compare-pools.js")
# A claims file for the synthetic data (the columns of kinds/pools/claims.tsv): one row with a source, one
# without, one missing, so that every form of the cell is drawn.
CLAIMS = ("# a test file of the columns of kinds/pools/claims.tsv\nadapter\twho\tdocumented\tsource\n"
          "adapter_ref\tours\tthe baseline (test text)\tkinds/pools/adapter_ref.c\n"
          "adapter_threadx\tlibrary\tfrom ISRs with TX_NO_WAIT (test text)\ttest source, chapter 4\n"
          "adapter_etl\tlibrary\tnothing about interrupts or threads (test text)\t–\n")


def synthetic(tmp, isr=False):
    """Make synthetic records and their pools.json in tmp; return the path of the file. isr: with synthetic records
    of the concurrency series too (site/pools_isr_synthetic.py)."""
    subprocess.run([sys.executable, "-I", os.path.join(ROOT, "site", "pools_synthetic.py"), os.path.join(tmp, "syn")],
                   check=True, capture_output=True)
    with open(os.path.join(tmp, "claims.tsv"), "w") as fh:
        fh.write(CLAIMS)
    out = os.path.join(tmp, "pools-synthetic.json")
    extra = []
    if isr:
        subprocess.run([sys.executable, "-I", os.path.join(ROOT, "site", "pools_isr_synthetic.py"), os.path.join(tmp, "isr")],
                       check=True, capture_output=True)
        extra = ["--isr", os.path.join(tmp, "isr")]
    subprocess.run([sys.executable, "-I", os.path.join(ROOT, "site", "pools_data.py"), "--records",
                    os.path.join(tmp, "syn", "records"), "--out", out, "--claims", os.path.join(tmp, "claims.tsv")] + extra,
                   check=True, capture_output=True)
    return out


def fragments(P, seed=20261126, random_views=1500):
    """The views to compare: the corner cases by hand, every plain view, the rest drawn."""
    boards = [b["id"] for b in P["boards"]]
    ads = [c["adapter"] for c in P["configurations"]]
    enc = pq._enc
    out = ["", "#", "#board=nosuchboard", "#scen=init", "#scen=nosuch", "#cache=maybe", "#sort=score", "#sort=-flash",
           "#sort=-", "#lang=Ada", "#kind=hardware", "#row=nosuch", "#row=%E0%A4%A", "#board=%",
           "#board=pico2&board=nucleo-h723zg", "#unknown=1&cache=off", "#w=12,-3,x", "#w=0,0,0", "#w=3", "#w=1,2,3,4,5",
           "#w=%203,4.5,+2", "#w=0,0,7&sort=name", "#w=5,5,5&sort=-ram", "#w=0,10,0&scen=empty", "#w=10,0,0&lang=Rust",
           "#kind=ours", "#kind=library&w=10,0,0", "#kind=ours&w=3,3,3&row=adapter_ref_primask",
           "#row=adapter_heapless&board=nucleo-g0b1re", "#board=sam-d20-xpro&row=adapter_heapless",
           "#scen=empty&row=adapter_etl&cache=off", "#board=nucleo-h723zg&cache=off&w=10,0,0"]
    weights = ["10,0,0", "0,10,0", "0,0,10", "5,5,0", "3,3,3", "10,10,1", "1,0,10"]
    for b in boards:
        for s in pq.SCENS:
            for cache in ("on", "off"):
                out.append(f"#board={b}&scen={s}&cache={cache}")
        base = f"#board={b}"
        out += [base + "&sort=" + d + k for k in pq.SORTS for d in ("", "-")]
        out += [base + "&cache=off&row=" + enc(a) for a in ads]
        out += [base + "&scen=pair_full&row=" + enc(a) for a in ads]
        out += [base + "&lang=" + enc(x) for x in pq.LANGS] + [base + "&kind=" + k for k in pq.KINDS]
        out += [base + "&kind=" + k + "&w=3,3,3" for k in pq.KINDS]
        for w in weights:
            out += [base + "&w=" + w, base + "&w=" + w + "&cache=off&scen=mixed", base + "&w=" + w + "&scen=empty",
                    base + "&w=" + w + "&row=" + enc(ads[len(w) % len(ads)]) if ads else base,
                    base + "&w=" + w + "&sort=-flash"]
    if pq.has_isr(P):   # the filter on the concurrency series, alone and with the others
        out += ["#isr=passed", "#isr=nosuch", "#isr=passed&kind=library", "#isr=passed&w=3,3,3",
                "#isr=passed&sort=-flash", "#isr=passed&row=adapter_etl"]
        out += [f"#board={b}&isr=passed" + x for b in boards for x in ("", "&cache=off", "&w=10,0,0", "&kind=ours")]
    rnd = random.Random(seed)
    for _ in range(random_views if boards else 50):
        parts = ["board=" + (rnd.choice(boards) if boards else "x")]
        for key, vals, p in (("scen", pq.SCENS, 0.7), ("cache", ["on", "off"], 0.5), ("lang", pq.LANGS, 0.2),
                             ("kind", pq.KINDS, 0.2), ("row", ads or ["adapter_etl"], 0.5),
                             ("sort", [d + k for k in pq.SORTS for d in ("", "-")], 0.3),
                             ("w", [",".join(str(rnd.choice([0, 0, 1, 3, 5, 10])) for _ in range(3)) for _ in range(4)], 0.6),
                             ("isr", ["passed"], 0.3 if pq.has_isr(P) else 0)):
            if rnd.random() < p:
                parts.append(key + "=" + enc(rnd.choice(vals)))
        rnd.shuffle(parts)
        out.append("#" + "&".join(parts))
    return out


def port_view(P, frag):
    st = pq.state_from_hash(P, frag)
    v = pq.page_view(P, st)
    v.update(hash=frag, written=pq.hash_of(st))
    return v


def page_views(data_path, frags):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "fragments.txt")
        with open(path, "w") as fh:
            fh.write("\n".join(frags) + "\n")
        env = dict(os.environ, LC_ALL="C.UTF-8", LANG="C.UTF-8")
        p = subprocess.run(["gjs", os.path.join(HERE, "page_harness.js"), COMPARE_JS, data_path, path],
                           capture_output=True, text=True, timeout=600, env=env)
    if p.returncode != 0:
        raise RuntimeError("page_harness.js failed:\n" + p.stderr[-2000:])
    return [json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")][1:]


class _Parity:
    data_path = None

    @classmethod
    def setUpClass(cls):
        cls.P, _ = pq.load(cls.data_path)
        cls.frags = fragments(cls.P)
        cls.page = page_views(cls.data_path, cls.frags)

    def compare_all(self):
        frags = [f for f in self.frags if f != ""]
        self.assertEqual(len(self.page), len(frags))
        stats = {"shown": set(), "marked": 0, "chosen": 0, "above": 0, "scored": 0, "claims": 0}
        for frag, page in zip(frags, self.page):
            port = port_view(self.P, frag)
            for key in ("written", "header", "seps", "count", "note", "src"):
                self.assertEqual(port[key], page[key], f"{key} differs for {frag}")
            self.assertEqual([r[0][0] for r in port["rows"]], [r[0][0] for r in page["rows"]], f"row order differs for {frag}")
            self.assertEqual(port["rows"], page["rows"], f"a cell differs for {frag}")
            stats["shown"].update(r[0][0] for r in port["rows"])
            stats["marked"] += sum(1 for r in port["rows"] for c in r if "overlaps" in c)
            stats["chosen"] += any("chosen" in r[0] for r in port["rows"])
            stats["above"] += sum(1 for r in port["rows"] for c in r if pq.ABOVE_TEXT in c)
            stats["scored"] += "Score (your weights)" in port["header"]
            # the claims cell: the last, or before the concurrency series' two cells where the data has them
            stats["claims"] += sum(1 for r in port["rows"]
                                   if any(isinstance(c, list) and any(str(x).startswith("source: ") for x in c) for c in r))
        return stats

    def test_address_round_trip(self):
        for page in self.page:
            st = pq.state_from_hash(self.P, page["written"])
            self.assertEqual(pq.hash_of(st), page["written"])
            self.assertEqual(st, pq.state_from_hash(self.P, page["hash"]), page["hash"])


@unittest.skipUnless(shutil.which("gjs"), "gjs is not installed: the website's script cannot be run here")
class ParityPoolsCommitted(_Parity, unittest.TestCase):
    """The committed data: before the first series, no rows and the page's line that says so."""
    data_path = pq.default_data_path()

    def test_every_view_is_the_same(self):
        stats = self.compare_all()
        if not self.P["published"]:
            self.assertEqual(stats["shown"], set())
            self.assertTrue(all(p["count"] == pq.NOT_PUBLISHED for p in self.page))


@unittest.skipUnless(shutil.which("gjs"), "gjs is not installed: the website's script cannot be run here")
class ParityPoolsSynthetic(_Parity, unittest.TestCase):
    """SYNTHETIC data (made-up numbers): every view with rows, marks, scores and claims."""
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.data_path = os.environ.get("VL_PARITY_POOLS_DATA") or synthetic(cls._tmp.name)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_every_view_is_the_same(self):
        stats = self.compare_all()
        # the views together must have shown every configuration and the reference, and marked overlaps
        self.assertEqual(stats["shown"], {c["name"] for c in self.P["configurations"]} | {pq.BASE_NAME})
        self.assertGreater(stats["chosen"], 100)
        self.assertGreater(stats["marked"], 100)
        self.assertGreater(stats["scored"], 300)
        self.assertGreater(stats["above"], 100)
        if not os.environ.get("VL_PARITY_POOLS_DATA"):
            self.assertGreater(stats["claims"], 50)

    def test_ours_and_claims(self):
        """Our row is labelled in every row it has and scored like any row; 'library' leaves it out and gives the
        scores of the data without it. The claims are in no filter and no score: the same views without any claim
        give the same order and scores."""
        P = self.P
        ours = {c["adapter"] for c in P["configurations"] if c["role"] == "ours"}
        self.assertEqual(ours, {"adapter_ref_primask"})
        P2 = dict(P, configurations=[c for c in P["configurations"] if c["adapter"] not in ours])
        P3 = dict(P, configurations=[dict(c, documented_interrupts=None) for c in P["configurations"]])
        for frag in fragments(P, random_views=300):
            st = pq.state_from_hash(P, frag)
            _, rs = pq.shown(P, st)
            v = pq.page_view(P, st)
            for x, row in zip(rs, v["rows"]):
                self.assertEqual(pq.OURS_LABEL in row[0], x["c"]["adapter"] in ours, frag)
            self.assertEqual([t for _, t in v["seps"]], [pq.BASE_TEXT] if pq.baseline_of(P, st) else [], frag)
            _, c3 = pq.shown(P3, st)
            self.assertEqual([(x["c"]["adapter"], x.get("score")) for x in rs],
                             [(x["c"]["adapter"], x.get("score")) for x in c3], frag)
            if pq.weighted(st):
                _, a = pq.shown(P, dict(st, kind="library"))
                _, b = pq.shown(P2, dict(st, kind=""))
                self.assertEqual([(x["c"]["adapter"], x["score"]) for x in a], [(x["c"]["adapter"], x["score"]) for x in b],
                                 frag)
        # heapless is not on the two Cortex-M0+ boards, and a chosen heapless row is dropped there
        for b in ("nucleo-g0b1re", "sam-d20-xpro"):
            st = pq.state_from_hash(P, f"#board={b}&row=adapter_heapless")
            self.assertEqual(st["row"], "")
            self.assertFalse(any(x["c"]["adapter"] == "adapter_heapless" for x in pq.shown(P, st)[0]))

    def test_rounded_marks_differ(self):
        """The score's marks are judged before rounding: judged on the shown text, the port must differ from the page
        somewhere (so the parity test would catch that change)."""
        raw = pq.score_overlap

        def rounded(a, b):
            t = lambda r: [float(pq.q.to_fixed(r[0], 1)), float(pq.q.to_fixed(r[1], 1))]   # noqa: E731
            return pq.overlap(t(a), t(b))
        differ = 0
        try:
            for frag in fragments(self.P):
                st = pq.state_from_hash(self.P, frag)
                if not pq.weighted(st):
                    continue
                want = pq.page_view(self.P, st)["rows"]
                pq.score_overlap = rounded
                got = pq.page_view(self.P, st)["rows"]
                pq.score_overlap = raw
                differ += want != got
        finally:
            pq.score_overlap = raw
        self.assertGreater(differ, 0)


@unittest.skipUnless(shutil.which("gjs"), "gjs is not installed: the website's script cannot be run here")
class ParityPoolsIsrSynthetic(_Parity, unittest.TestCase):
    """SYNTHETIC data with SYNTHETIC records of the concurrency series: the second column, the baseline's control,
    the filter, and that the series' results are in no score."""
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.data_path = synthetic(cls._tmp.name, isr=True)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_every_view_is_the_same(self):
        self.assertTrue(pq.has_isr(self.P))
        stats = self.compare_all()
        self.assertEqual(stats["shown"], {c["name"] for c in self.P["configurations"]} | {pq.BASE_NAME})

    def test_isr_column_filter_and_no_score(self):
        P = self.P
        P0 = dict(P, rows=[{k: v for k, v in r.items() if k != "isr"} for r in P["rows"]])
        for frag in fragments(P, random_views=300):
            st = pq.state_from_hash(P, frag)
            v = pq.page_view(P, st)
            self.assertEqual(v["header"][-2:], pq.ISR_HEADERS, frag)
            _, rs = pq.shown(P, st)
            if st["isr"]:
                self.assertTrue(all(x["r"]["isr"]["passed"] for x in rs), frag)
                self.assertTrue(all(x["r"]["isr"]["class"] in ("within", "ours") for x in rs), frag)
            else:   # without the filter the series changes nothing of the order or the scores
                _, r0 = pq.shown(P0, st)
                self.assertEqual([(x["c"]["adapter"], x.get("score")) for x in rs],
                                 [(x["c"]["adapter"], x.get("score")) for x in r0], frag)
        outside = [r["isr"]["text"] for r in P["rows"] if r.get("isr") and r["isr"]["class"] == "outside"]
        self.assertTrue(outside)
        self.assertFalse([t for t in outside if any(w in t for w in ("pass", "FAIL", "fail", "caught"))])


if __name__ == "__main__":
    unittest.main()
