#!/usr/bin/env python3
"""The pools tools of the MCP server (poolstools.py): list_pool_configurations
and compare_pools.

- On the committed data (no records until the first series is published) both
  tools say the series is not published, and still check their arguments.
- On SYNTHETIC data made in a temporary directory (site/pools_synthetic.py and
  site/pools_data.py; made-up numbers, never written into the tree): the rows
  are the page's (poolsquery.py, tested against site/compare-pools.js), our
  row is labelled, the claims are given as not tested, the baseline is last,
  and bad arguments are refused.
- The other tools: their definitions are those of the server without the pools
  tools, and the pools tools come last.

    python3 -m unittest discover -s mcp-server/tests
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import server   # noqa: E402
import poolsquery as pq   # noqa: E402
import poolstools as pt   # noqa: E402
import vlquery as q   # noqa: E402
from test_parity_pools import synthetic   # noqa: E402


class PoolsUnpublished(unittest.TestCase):
    def setUp(self):
        pt.pools_data(pq.default_data_path())
        self.D, self.prov = q.load()
        self.P = pt.pools_data()[0]

    def test_not_published(self):
        if self.P["published"]:
            self.skipTest("the committed data has records")
        lst = server.call_tool(self.D, self.prov, "list_pool_configurations", {})
        self.assertEqual((lst["published"], lst["count"]), (False, 0))
        self.assertIn("not published yet", lst["what"])
        out = server.call_tool(self.D, self.prov, "compare_pools", {"scenario": "pair"})
        self.assertEqual((out["published"], out["rows"]), (False, []))
        with self.assertRaises(server.ToolError):
            server.call_tool(self.D, self.prov, "compare_pools", {"nosuch": 1})
        names = [t["name"] for t in server.tool_list(self.D)]
        self.assertEqual(names[-2:], ["list_pool_configurations", "compare_pools"])
        self.assertNotIn("enum", [t for t in server.tool_list(self.D) if t["name"] == "compare_pools"][0]
                         ["inputSchema"]["properties"]["board"])

    def test_about_names_the_pools_tools(self):
        about = server.call_tool(self.D, self.prov, "about", {})["project"]
        self.assertIn("Three kinds", about)
        for t in ("list_pool_configurations", "compare_pools", "method-pools.html", "compare_crc"):
            self.assertIn(t, about)

    def test_other_tools_unchanged(self):
        """The tool list is the other tools' definitions, unchanged, then the two pools tools."""
        keep = pt.tool_defs
        try:
            pt.tool_defs = lambda: []
            without = server.tool_list(self.D)
        finally:
            pt.tool_defs = keep
        with_pools = server.tool_list(self.D)
        self.assertEqual(with_pools[:len(without)], without)
        self.assertEqual(len(with_pools), len(without) + 2)


class PoolsSynthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.path = synthetic(cls._tmp.name)
        cls.D, cls.prov = q.load()

    @classmethod
    def tearDownClass(cls):
        pt.pools_data(pq.default_data_path())
        cls._tmp.cleanup()

    def setUp(self):
        self.P = pt.pools_data(self.path)[0]

    def tool(self, name, args=None):
        return server.call_tool(self.D, self.prov, name, args or {})

    def test_compare_pools_is_the_page(self):
        cases = [{}, {"board": "nucleo-h723zg", "cache": "off"}, {"board": "pico2", "scenario": "pair_full"},
                 {"board": "sam-d20-xpro", "language": "C++", "sort": "flash_bytes", "reverse": True},
                 {"scenario": "empty", "weights": {"free": 10}}, {"weights": {"alloc": 5, "bytes": 5}},
                 {"board": "nrf5340dk", "cache": "off", "weights": {"alloc": 3, "free": 3, "bytes": 3}},
                 {"kind": "library", "weights": {"alloc": 10}}, {"kind": "ours"}, {"scenario": "mixed", "sort": "name"}]
        for args in cases:
            out = self.tool("compare_pools", args)
            url = out["same_view_on_the_site"]
            self.assertTrue(url.startswith(q.SITE_URL + "/compare-pools.html#"), url)
            st = pq.state_from_hash(self.P, url.split("#", 1)[1])
            self.assertEqual(st, pt.state_from_args(self.P, args, server._check_args, server._choice, server._flag), args)
            view = pq.page_view(self.P, st)
            self.assertEqual([r["name"] for r in out["rows"]], [r[0][0] for r in view["rows"]], args)
            self.assertEqual(out["shown"], view["count"])
            wd = "weights" in args
            for j, (r, cells) in enumerate(zip(out["rows"], view["rows"])):
                want = {"init": cells[7 + wd][0], "alloc": cells[8 + wd][0], "free": cells[9 + wd][0]}
                if wd and "score" in r:
                    want["score"] = cells[1][0]
                    if not st["sort"] and j > 0:
                        self.assertEqual(r["score_not_told_apart_from_the_row_above"], pq.ABOVE_TEXT in cells[1], args)
                self.assertEqual(r["as_on_the_page"], want, args)
                self.assertEqual(bool(r.get("ours_not_a_library")), pq.OURS_LABEL in cells[0], args)
                if "documented_use_from_interrupts" in r and r["documented_use_from_interrupts"]:
                    self.assertIs(r["documented_use_from_interrupts"]["tested"], False)
            self.assertTrue(out["rows"][-1]["reference_baseline_not_a_library"])
            self.assertTrue(all(r["record"].startswith(server.REPO + "records/pools/") for r in out["rows"][:-1]))
            self.assertIn("one context", out["notes"][0])
            if args.get("scenario") == "empty":
                self.assertTrue(all(r["cycles"]["free"] is None for r in out["rows"]))

    def test_list(self):
        lst = self.tool("list_pool_configurations")
        self.assertTrue(lst["published"])
        self.assertEqual(lst["count"], 10)
        self.assertEqual([r["name"] for r in lst["ours"]["rows"]], ["reference free list, interrupts off (ours)"])
        mp = next(c for c in lst["configurations"] if c["library"] == "bertmelis/MemoryPool")
        self.assertIn("unreleased", mp["version"])
        self.assertEqual(len(lst["boards"]), 6)

    def test_bad_arguments(self):
        for bad in ({"board": "nosuch"}, {"scenario": "init"}, {"cache": True}, {"kind": "hardware_unit"},
                    {"weights": {"cycles": 3}}, {"weights": {"alloc": 11}}, {"weights": {"alloc": True}},
                    {"sort": "score"}, {"reverse": "yes"}, {"language": "Ada"}, {"length": 16}):
            with self.assertRaises(server.ToolError, msg=bad):
                self.tool("compare_pools", bad)
        with self.assertRaises(server.ToolError):
            self.tool("list_pool_configurations", {"board": "pico2"})

    def test_ours_scored_and_left_out(self):
        args = {"board": "nucleo-g474re", "weights": {"alloc": 10}}
        every = self.tool("compare_pools", args)
        libs = self.tool("compare_pools", dict(args, kind="library"))
        self.assertIn("reference free list, interrupts off (ours)", [r["name"] for r in every["rows"]])
        self.assertNotIn("reference free list, interrupts off (ours)", [r["name"] for r in libs["rows"]])
        self.assertTrue(all("score" in r for r in every["rows"][:-1]))


if __name__ == "__main__":
    unittest.main()
