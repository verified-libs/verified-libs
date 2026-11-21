#!/usr/bin/env python3
"""The server as an MCP client meets it: a process, JSON lines in, JSON lines out.

    python3 -m unittest discover -s mcp-server/tests
"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(os.path.dirname(HERE), "server.py")
sys.path.insert(0, os.path.dirname(HERE))
import server   # noqa: E402
import vlquery as q   # noqa: E402


def talk(lines, timeout=60):
    """Start the server, send the lines, close its input. Returns (answers, stderr, exit code)."""
    data = b"".join((l if isinstance(l, bytes) else json.dumps(l).encode()) + b"\n" for l in lines)
    p = subprocess.run([sys.executable, SERVER], input=data, capture_output=True, timeout=timeout)
    out = p.stdout.decode("utf-8")
    # Every line the server writes to stdout must be one JSON-RPC message, with no line break inside.
    answers = [json.loads(line) for line in out.split("\n") if line]
    assert out == "" or out.endswith("\n")
    return answers, p.stderr.decode(), p.returncode


def init(version="2025-11-25", mid=1):
    return {"jsonrpc": "2.0", "id": mid, "method": "initialize",
            "params": {"protocolVersion": version, "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}}


INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def call(mid, name, args=None):
    params = {"name": name}
    if args is not None:
        params["arguments"] = args
    return {"jsonrpc": "2.0", "id": mid, "method": "tools/call", "params": params}


class Protocol(unittest.TestCase):
    def test_initialize_each_version(self):
        for v in server.PROTOCOL_VERSIONS:
            ans, _, rc = talk([init(v), INITIALIZED, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}])
            self.assertEqual(rc, 0)
            self.assertEqual(len(ans), 2, "a notification gets no answer")
            r = ans[0]["result"]
            self.assertEqual(r["protocolVersion"], v)
            self.assertEqual(r["capabilities"], {"tools": {"listChanged": False}})
            self.assertEqual(r["serverInfo"]["name"], "verified-libs")
            self.assertIn("written by the project owner", r["instructions"])
            tools = ans[1]["result"]["tools"]
            self.assertEqual([t["name"] for t in tools], list(server.TOOLS))
            for t in tools:
                self.assertEqual(t["inputSchema"]["type"], "object")
                self.assertEqual("title" in t, v >= "2025-06-18")
                self.assertEqual("annotations" in t, v >= "2025-03-26")

    def test_unknown_version_gets_the_latest(self):
        ans, _, _ = talk([init("2099-01-01")])
        self.assertEqual(ans[0]["result"]["protocolVersion"], server.PROTOCOL_VERSIONS[0])

    def test_ping_and_ids(self):
        ans, _, _ = talk([init(), {"jsonrpc": "2.0", "id": "abc", "method": "ping"}, {"jsonrpc": "2.0", "id": 0, "method": "ping"}])
        self.assertEqual(ans[1], {"jsonrpc": "2.0", "id": "abc", "result": {}})
        self.assertEqual(ans[2], {"jsonrpc": "2.0", "id": 0, "result": {}})

    def test_errors(self):
        ans, err, rc = talk([
            init(),
            b"this is not json",
            b"\xff\xfe",
            {"jsonrpc": "2.0", "id": 2, "method": "resources/list"},
            call(3, "no_such_tool"),
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "about", "arguments": [1]}},
            {"id": 5, "method": "ping"},
            {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": [1]},
            {"jsonrpc": "2.0", "id": 7, "result": {}},
            {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 3}},
            {"jsonrpc": "2.0", "id": 8, "method": "ping"},
        ])
        self.assertEqual(rc, 0)
        codes = [(a.get("id"), a["error"]["code"] if "error" in a else None) for a in ans]
        self.assertEqual(codes, [(1, None), (None, -32700), (None, -32700), (2, -32601), (3, -32602), (4, -32602),
                                 (None, -32600), (6, -32602), (8, None)])
        self.assertIn("Unknown tool: no_such_tool", ans[4]["error"]["message"])
        self.assertNotIn("Traceback", err)

    def test_batch(self):
        ans, _, _ = talk([init("2025-03-26"), [{"jsonrpc": "2.0", "id": 2, "method": "ping"}, INITIALIZED,
                                               {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}], []])
        self.assertEqual([a["id"] for a in ans[1]], [2, 3])
        self.assertEqual(ans[2]["error"]["code"], -32600)

    def test_bad_arguments_come_back_as_tool_errors(self):
        bad = [("compare_ring_buffers", {"board": "stm32"}), ("compare_ring_buffers", {"bord": "pico2"}),
               ("compare_ring_buffers", {"weights": {"push": 11}}), ("compare_ring_buffers", {"weights": {"push": True}}),
               ("compare_ring_buffers", {"weights": {"speed": 1}}), ("compare_ring_buffers", {"sort": "score"}),
               ("compare_ring_buffers", {"require": ["fast"]}), ("compare_ring_buffers", {"require": "block_api"}),
               ("compare_ring_buffers", {"reverse": "yes"}), ("compare_ring_buffers", {"topology": "spsc"}),
               ("get_ring_buffer", {}), ("get_ring_buffer", {"name": "no such library"}), ("get_ring_buffer", {"name": "r"}),
               ("get_ring_buffer", {"name": ""}), ("about", {"x": 1}), ("list_ring_buffers", {"x": 1})]
        ans, _, _ = talk([init()] + [call(i + 2, n, a) for i, (n, a) in enumerate(bad)])
        for (n, a), r in zip(bad, ans[1:]):
            self.assertTrue(r["result"]["isError"], (n, a))
            self.assertNotIn("structuredContent", r["result"])
            self.assertTrue(r["result"]["content"][0]["text"])
        self.assertIn("nrf5340dk", ans[1]["result"]["content"][0]["text"], "the error names the valid values")

    def test_structured_content_by_version(self):
        for v in server.PROTOCOL_VERSIONS:
            ans, _, _ = talk([init(v), call(2, "list_ring_buffers"), call(3, "about", {})])
            for a in ans[1:]:
                r = a["result"]
                self.assertFalse(r["isError"])
                self.assertEqual("structuredContent" in r, v >= "2025-06-18")
                if "structuredContent" in r:    # the text block is the same object, serialised
                    self.assertEqual(json.loads(r["content"][0]["text"]), r["structuredContent"])


class Answers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.D, cls.prov = q.load()

    def tool(self, name, args=None):
        return server.call_tool(self.D, self.prov, name, args or {})

    def test_compare_is_the_page(self):
        """The rows of a tool call are the rows of the page at the address the answer gives."""
        cases = [{}, {"board": "pico2", "topology": "MPSC", "include_single_context": True},
                 {"board": "nucleo-g0b1re", "weights": {"push": 5, "pop": 5, "zero_copy": 2}, "require": ["zero_stress_errors"]},
                 {"board": "nucleo-h723zg", "cores": "two", "sort": "code_size", "reverse": True},
                 {"language": "C++", "require": ["permissive_license", "contract_pass", "genmc_pass"]},
                 {"language": "Rust", "weights": {"block": 10}, "sort": "name"},
                 {"board": "sam-d20-xpro", "topology": "MPMC", "weights": {"push": 1}, "require": ["not_unsafe_by_own_docs", "block_api", "zero_copy_api"]}]
        for args in cases:
            out = self.tool("compare_ring_buffers", args)
            url = out["same_view_on_the_site"]
            self.assertTrue(url.startswith(q.SITE_URL + "/compare.html#"))
            st = q.state_from_hash(self.D, url.split("#", 1)[1])
            self.assertEqual(st, server.state_from_args(self.D, args), args)
            page = q.compare(self.D, st)
            self.assertEqual([r["name"] for r in out["rows"]], [r["lib"]["name"] for r in page], args)
            self.assertEqual(out["shown"], q.count_text(self.D, st, len(page)))
            self.assertEqual(sum(out["groups"].values()), len(out["rows"]))
            order = [q.GROUP[r["isr_stress_group"]] for r in out["rows"]]
            self.assertEqual(order, sorted(order), "the three groups come in their order, whatever the sort")
            for r in out["rows"]:
                self.assertEqual("score" in r, "weights" in args)

    def test_no_ranking_without_weights(self):
        out = self.tool("compare_ring_buffers", {"board": "pico2"})
        self.assertTrue(out["ranking"].startswith("none"))
        self.assertTrue(all("score" not in r for r in out["rows"]))
        self.assertNotIn("board_note", out)
        self.assertIn("board_note", self.tool("compare_ring_buffers"))

    def test_owner_is_labelled_everywhere(self):
        """Principle 6: wherever the owner's library appears, the answer says whose it is."""
        own = {lib["name"] for lib in self.D["libs"] if lib.get("own")}
        self.assertTrue(own)
        for args in ({}, {"include_single_context": True}, {"topology": "MPSC"}, {"weights": {"push": 1}}):
            out = self.tool("compare_ring_buffers", args)
            shown = {r["name"] for r in out["rows"]}
            for r in out["rows"]:
                self.assertEqual(r["written_by_project_owner"], r["name"] in own)
            self.assertEqual("conflict_of_interest" in out, bool(shown & own), args)
        # a view without it carries no such note
        out = self.tool("compare_ring_buffers", {"language": "C"})
        self.assertFalse({r["name"] for r in out["rows"]} & own)
        self.assertNotIn("conflict_of_interest", out)
        lst = self.tool("list_ring_buffers")
        self.assertEqual({c["name"] for c in lst["configurations"] if c["written_by_project_owner"]}, own)
        self.assertIn("conflict_of_interest", lst)
        self.assertIn("Erik N (pxq.dk)", self.tool("about")["conflict_of_interest"])
        for name in own:
            cfg = self.tool("get_ring_buffer", {"name": name})["configurations"]
            self.assertEqual(len(cfg), 1)
            self.assertTrue(cfg[0]["written_by_project_owner"])
            self.assertIn(server.COI_URL, cfg[0]["conflict_of_interest"])
        other = self.tool("get_ring_buffer", {"name": "lwrb"})["configurations"][0]
        self.assertFalse(other["written_by_project_owner"])
        self.assertNotIn("conflict_of_interest", other)

    def test_every_configuration_can_be_fetched(self):
        for lib in self.D["libs"]:
            cfg = self.tool("get_ring_buffer", {"name": lib["name"].upper()})["configurations"]
            self.assertEqual([c["name"] for c in cfg], [lib["name"]])
            self.assertEqual(cfg[0]["commit"], lib["commit"])
        self.assertEqual(self.tool("list_ring_buffers")["count"], len(self.D["libs"]))

    def test_answers_name_their_data(self):
        for name, args in (("about", {}), ("list_ring_buffers", {}), ("compare_ring_buffers", {}), ("get_ring_buffer", {"name": "lwrb"})):
            self.assertEqual(len(self.tool(name, args)["data"]["sha256"]), 64)

    def test_command_line_call(self):
        p = subprocess.run([sys.executable, SERVER, "--call", "compare_ring_buffers", '{"board": "pico2"}'],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(json.loads(p.stdout), self.tool("compare_ring_buffers", {"board": "pico2"}))
        p = subprocess.run([sys.executable, SERVER, "--call", "compare_ring_buffers", '{"board": "x"}'],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual((p.returncode, p.stdout), (2, ""))


if __name__ == "__main__":
    unittest.main()
