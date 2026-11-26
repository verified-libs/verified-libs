#!/usr/bin/env python3
"""The board queue (lab/tools/boardqueue.py) without a board: a fake runner
in place of run-crc.py and run-one.py, fake boards in a board table of the
test's own, a git worktree of its own, and its own queue and lock
directories. What it shows:

- a worker holds its board's lock (a second worker, or a run outside the
  queue, is refused) and its jobs get VL_BOARD_LOCKED=1;
- a job is stopped at its hard timeout, its whole process group with it;
- a job is stopped at its first flash write beyond the budget, and every
  write is in the ledger;
- a failure stops only its own board: the other board's worker goes on, and
  the failed board's next job waits;
- --expect and --refuse, and a worktree that is not a clean checkout of the
  job's commit (refused at add, and failed at start if it changed after);
- the Pico 2 writes alone: a Pico 2 job that may write does not overlap
  another board's job that may write; two other boards' do;
- a power switch waits for the jobs on the hub, and is never done on the
  nRF5340 DK;
- status.

    python3 -I lab/tools/test_boardqueue.py

The controls: VL_BOARDQUEUE_UNDER_TEST=a copy of boardqueue.py with one rule
taken out must make a test fail (test-boardqueue-controls.sh).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.environ.get("VL_BOARDQUEUE_UNDER_TEST") or os.path.join(HERE, "boardqueue.py")


def read(path):
    with open(path) as fh:
        return fh.read()
FAKE = r'''
import fcntl, os, sys, time
a = dict(zip(sys.argv[1::2], sys.argv[2::2]))
out = a.get("--mark")
def mark(s):
    if out:
        with open(out, "a") as fh:
            fh.write(f"{time.time():.3f} {s}\n")
mark("start")
print("VL_BOARD_LOCKED=" + os.environ.get("VL_BOARD_LOCKED", ""), flush=True)
lk = a.get("--try-lock")
if lk:
    fh = open(lk, "a")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB); print("board lock free", flush=True)
    except OSError:
        print("board lock held by the worker", flush=True)
if a.get("--child"):
    pid = os.fork()
    if pid == 0:
        time.sleep(60); os._exit(0)
    with open(a["--child"], "w") as fh:
        fh.write(str(pid))
for i in range(int(a.get("--writes", "0"))):
    time.sleep(float(a.get("--gap", "0.2")))
    print(f"12:00:0{i % 10} bundle {50 + i}: FLASH WRITE {i + 1} of this run, 125 units of 4096 bytes, 1 s: ok", flush=True)
    mark(f"write {i + 1}")
time.sleep(float(a.get("--sleep", "0")))
print(a.get("--print", "done: 2 runs, 0 without a file"), flush=True)
mark("end")
sys.exit(int(a.get("--exit", "0")))
'''


class Queue(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix="boardqueue-test-")
        self.q, self.locks = os.path.join(self.t, "queue"), os.path.join(self.t, "locks")
        self.conf = os.path.join(self.t, "boards.conf")
        with open(self.conf, "w") as fh:
            fh.write("# test boards: name hub port vid:pid serial\n"
                     "boarda   HUB1  1  0000:0001  A1  x\n"
                     "boardb   HUB2  1  0000:0002  B1  x\n"
                     "boardc   HUB2  2  0000:0003  C1  x\n"
                     "pico2    HUB1  3  0000:0004  P1  rp2350 separate-probe\n"
                     "nrf5340dk HUB2 3  0000:0005  N1  nrf5340\n")
        self.wt = os.path.join(self.t, "wt")
        os.makedirs(self.wt)
        g = lambda *a: subprocess.run(["git", "-C", self.wt] + list(a), check=True, capture_output=True)
        g("init", "-q"); g("config", "user.email", "t@example.invalid"); g("config", "user.name", "t")
        with open(os.path.join(self.wt, "fake.py"), "w") as fh:
            fh.write(FAKE)
        g("add", "fake.py"); g("commit", "-q", "-m", "fake runner")
        self.commit = subprocess.run(["git", "-C", self.wt, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        self.power = os.path.join(self.t, "power.sh")
        with open(self.power, "w") as fh:
            fh.write(f"echo \"power $1 $2\" >> {self.t}/power.log\n")
        self.env = dict(os.environ, VL_QUEUE=self.q, VL_LOCK_DIR=self.locks, BOARDS_CONF=self.conf,
                        VL_BOARDPOWER=self.power, VL_QUEUE_POLL="0.2")

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def bq(self, *args, wait=True, timeout=120):
        cmd = [sys.executable, "-I", QUEUE] + list(args)
        if not wait:
            return subprocess.Popen(cmd, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return subprocess.run(cmd, env=self.env, capture_output=True, text=True, timeout=timeout)

    def add(self, board, *fake, timeout=60, writes=0, extra=()):
        r = self.bq("add", board, "--worktree", self.wt, "--commit", self.commit[:12], "--timeout", str(timeout),
                    "--writes", str(writes), "--ok", "the test", *extra, "--", sys.executable, "-I", "fake.py", *fake)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def jobs(self, board, state):
        d = os.path.join(self.q, board, state)
        return sorted(f for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []

    def log(self, board, state, i=0):
        name = self.jobs(board, state)[i]
        return read(os.path.join(self.q, board, state, name[:-5] + ".log")), json.loads(read(os.path.join(self.q, board, state, name)))

    def ledger(self):
        p = os.path.join(self.q, "writes.tsv")
        return [l.split("\t") for l in read(p).splitlines()] if os.path.exists(p) else []

    def test_lock_and_env(self):
        self.add("boarda", "--try-lock", os.path.join(self.locks, "boarda.lock"))
        w = self.bq("worker", "boarda")
        self.assertEqual(w.returncode, 0, w.stdout + w.stderr)
        out, job = self.log("boarda", "done")
        self.assertIn("VL_BOARD_LOCKED=1", out)
        self.assertIn("board lock held by the worker", out)
        self.assertEqual(job["result"], "ok")
        # a second worker on the same board is refused while one runs
        self.add("boarda", "--sleep", "3")
        first = self.bq("worker", "boarda", wait=False)
        time.sleep(1)
        second = self.bq("worker", "boarda")
        self.assertEqual(second.returncode, 2)
        self.assertIn("busy", second.stderr)
        self.assertEqual(first.wait(timeout=60), 0)

    def test_timeout_kills_the_group(self):
        child = os.path.join(self.t, "child.pid")
        self.add("boarda", "--sleep", "60", "--child", child, timeout=2)
        t0 = time.time()
        w = self.bq("worker", "boarda")
        self.assertEqual(w.returncode, 1)
        self.assertLess(time.time() - t0, 20)
        _, job = self.log("boarda", "failed")
        self.assertIn("timeout after 2 s", job["result"])
        time.sleep(0.5)
        pid = int(read(child))
        gone = True
        try:
            os.kill(pid, 0)
            gone = read(f"/proc/{pid}/stat").split()[2] == "Z"
        except ProcessLookupError:
            pass
        self.assertTrue(gone, "the job's child process outlived the timeout")
        self.assertTrue(os.path.exists(os.path.join(self.q, "boarda", "STOPPED")))
        # a stopped board's worker does not start until STOPPED is removed
        self.add("boarda")
        self.assertEqual(self.bq("worker", "boarda").returncode, 2)
        os.remove(os.path.join(self.q, "boarda", "STOPPED"))
        self.assertEqual(self.bq("worker", "boarda").returncode, 0)

    def test_write_budget_and_ledger(self):
        mark = os.path.join(self.t, "marks")
        self.add("boarda", "--writes", "2", writes=2)
        self.add("boarda", "--writes", "4", "--gap", "0.5", "--mark", mark, writes=1)
        w = self.bq("worker", "boarda")
        self.assertEqual(w.returncode, 1, w.stdout)
        self.assertEqual(len(self.jobs("boarda", "done")), 1)
        out, job = self.log("boarda", "failed")
        self.assertIn("flash write 2 is over the budget of 1", job["result"])
        self.assertEqual(job["flash_writes"], 2)
        self.assertNotIn("write 3", read(mark), "the job went on writing after it was over budget")
        led = self.ledger()
        self.assertEqual(len(led), 4)
        self.assertEqual([x[1] for x in led], ["boarda"] * 4)
        self.assertEqual([x[2] for x in led], ["bundle 50", "bundle 51", "bundle 50", "bundle 51"])
        self.assertEqual({x[3] for x in led}, {"125"})
        st = self.bq("status")
        self.assertIn("boarda: worker none; waiting 0, done 1, failed 1; flash writes 4", st.stdout)
        self.assertIn("STOPPED", st.stdout)

    def test_failure_stops_only_its_own_board(self):
        self.add("boarda", "--exit", "3")
        self.add("boarda")
        self.add("boardb", "--sleep", "1")
        self.add("boardb", "--sleep", "1")
        wa, wb = self.bq("worker", "boarda", wait=False), self.bq("worker", "boardb", wait=False)
        self.assertEqual(wa.wait(timeout=60), 1)
        self.assertEqual(wb.wait(timeout=60), 0)
        self.assertEqual((len(self.jobs("boarda", "failed")), len(self.jobs("boarda", "todo"))), (1, 1))
        self.assertEqual(len(self.jobs("boardb", "done")), 2)
        self.assertIn("exit 3", self.log("boarda", "failed")[1]["result"])

    def test_expect_and_refuse(self):
        self.add("boarda", extra=("--expect", r"done: \d+ runs, 0 without a file", "--refuse", "errors [1-9]"))
        self.add("boarda", "--print", "done: 2 runs, 1 without a file", extra=("--expect", "0 without a file"))
        self.assertEqual(self.bq("worker", "boarda").returncode, 1)
        self.assertEqual(len(self.jobs("boarda", "done")), 1)
        self.assertIn("--expect", self.log("boarda", "failed")[1]["result"])
        self.add("boardb", "--print", "pass 1: errors 2", extra=("--refuse", "errors [1-9]"))
        self.assertEqual(self.bq("worker", "boardb").returncode, 1)
        self.assertIn("--refuse", self.log("boardb", "failed")[1]["result"])

    def test_worktree_must_be_clean_at_the_commit(self):
        r = self.bq("add", "boarda", "--worktree", self.wt, "--commit", "0123456789ab", "--timeout", "5", "--writes", "0",
                    "--ok", "t", "--", "true")
        self.assertEqual(r.returncode, 2)
        self.assertIn("not 0123456789ab", r.stderr)
        self.add("boarda")
        with open(os.path.join(self.wt, "fake.py"), "a") as fh:
            fh.write("# changed\n")
        self.assertEqual(self.bq("worker", "boarda").returncode, 1)
        self.assertIn("has changes", self.log("boarda", "failed")[1]["result"])
        r = self.bq("add", "boardb", "--worktree", self.wt, "--commit", self.commit[:12], "--timeout", "5", "--writes", "0",
                    "--ok", "t", "--", "true")
        self.assertEqual(r.returncode, 2)

    def test_pico_writes_alone(self):
        def spans(path):
            ev = [l.split() for l in read(path).splitlines()]
            return float(ev[0][0]), float(ev[-1][0])
        mp, mb, mc = (os.path.join(self.t, n) for n in ("mp", "mb", "mc"))
        # the Pico 2 and board B both may write: they must not overlap
        self.add("pico2", "--writes", "1", "--sleep", "2", "--mark", mp, writes=1)
        self.add("boardb", "--writes", "1", "--sleep", "2", "--mark", mb, writes=1)
        wp, wb = self.bq("worker", "pico2", wait=False), self.bq("worker", "boardb", wait=False)
        self.assertEqual((wp.wait(timeout=60), wb.wait(timeout=60)), (0, 0))
        (p0, p1), (b0, b1) = spans(mp), spans(mb)
        self.assertTrue(p1 <= b0 or b1 <= p0, f"the Pico 2's writing job overlapped another ({p0}-{p1}, {b0}-{b1})")
        # boards B and C both may write: they may overlap
        for f in (mb, mc):
            os.remove(f) if os.path.exists(f) else None
        self.add("boardb", "--writes", "1", "--sleep", "2", "--mark", mb, writes=1)
        self.add("boardc", "--writes", "1", "--sleep", "2", "--mark", mc, writes=1)
        wb, wc = self.bq("worker", "boardb", wait=False), self.bq("worker", "boardc", wait=False)
        self.assertEqual((wb.wait(timeout=60), wc.wait(timeout=60)), (0, 0))
        (b0, b1), (c0, c1) = spans(mb), spans(mc)
        self.assertTrue(b0 < c1 and c0 < b1, "two other boards' writing jobs did not overlap")

    def test_power(self):
        r = self.bq("power", "nrf5340dk", "cycle")
        self.assertEqual(r.returncode, 2)
        self.assertIn("never nrf5340dk", r.stderr)
        # a job runs on hub HUB2 (board B): board C's port is not switched; once it ends, it is
        self.add("boardb", "--sleep", "3")
        w = self.bq("worker", "boardb", wait=False)
        time.sleep(1)
        r = self.bq("power", "boardc", "cycle")
        self.assertEqual(r.returncode, 2)
        self.assertIn("a job runs on hub HUB2", r.stderr)
        r = self.bq("power", "boarda", "cycle")      # another hub: switched
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.bq("power", "boardc", "cycle", "--wait", "30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(w.wait(timeout=60), 0)
        self.assertEqual(read(os.path.join(self.t, "power.log")).split("\n")[:2], ["power cycle boarda", "power cycle boardc"])


if __name__ == "__main__":
    unittest.main()
