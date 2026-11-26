#!/usr/bin/env python3
"""A queue and a worker per board, so that boards can run at the same time
(lab/plans/2026-11-25-parallel-board-runs.md, section 3; DECISIONS
2026-11-25). The runners are wrapped as they are (kinds/crc/bench/run-crc.py,
firmware/nrf5340-rb-bench/run-one.py); nothing frozen is changed.

Until the proof of the plan's section 4 has passed and has been read, the
rule stays one board at a time: start one worker at a time.

Usage:
  boardqueue.py add BOARD --worktree DIR --commit HASH --timeout SECONDS --writes N --ok WHO
                [--cwd SUBDIR] [--expect REGEX]... [--refuse REGEX]... [--note TEXT] -- COMMAND...
  boardqueue.py worker BOARD [--follow]
  boardqueue.py status
  boardqueue.py power BOARD on|off|cycle [--wait SECONDS]

BOARD is a board's name in lab/boards.conf (e.g. nucleo-g474re).

add: puts a job in BOARD's queue. Enqueuing a job is the OK for that board's
  run: --ok names who gave it. The worktree must be a clean checkout of the
  commit (its build made before; a job never builds). COMMAND runs in
  DIR/SUBDIR. --writes is the job's flash write budget, --timeout its hard
  limit. --expect: a line of the output must match (each); --refuse: no line
  may match.
worker: runs BOARD's jobs in order, holding the board's lock
  (~/vl-dev/<board>.lock) for as long as it runs; each job gets
  VL_BOARD_LOCKED=1 (the runners then do not take the lock themselves).
  Per job it checks the worktree (clean, at the commit), holds its hub's lock
  shared, and takes the write lock if the job may write (below). It stops
  the job at its timeout or at its first flash write beyond the budget, and
  a job fails if the command exits non-zero, a --expect line is missing or a
  --refuse line is there. At the first failure it moves the job to failed/,
  writes STOPPED in the board's queue and stops: that board waits for a
  person, the other workers go on. Without --follow it ends when the queue is
  empty; with --follow it waits for new jobs. A STOPPED board's worker does
  not start until STOPPED is removed.
status: per board the worker, the job running, the jobs waiting, done and
  failed, and the board's flash writes from the ledger.
power: switches a board's port through lab/tools/boardpower.sh, only while
  no job runs on that board's hub (the hub's lock, exclusive). Never the
  nRF5340 DK: after a power-on our boot stub leaves its debug port locked
  (lab/drafts/2026-11-25-nrf5340-approtect-recovery.md).

Flash writes are counted in one place, the ledger writes.tsv in the queue
directory: one line per write (UTC, board, what was written, units, job),
from the runners' "FLASH WRITE" lines. A runner prints that line after the
write, so a job over budget is stopped after that write, before any more.

The Pico 2 writes alone (DECISIONS 2026-11-25): a job that may write takes
the write lock, exclusive on the Pico 2 and shared on the other boards, for
the whole job. So no other board writes while a Pico 2 job that may write
runs, and boards other than the Pico 2 write at the same time as each other.

Files: the queue directory (VL_QUEUE, default ~/vl-queue) has one directory
per board with todo/, running/, done/, failed/ (a job is a JSON file, its
output beside it as .log), worker.pid and STOPPED, and writes.tsv. Locks are
in VL_LOCK_DIR (default ~/vl-dev): <board>.lock, hub-<serial>.lock,
usb-write.lock. The board table is lab/boards.conf (BOARDS_CONF);
boardpower.sh can be replaced by VL_BOARDPOWER (the test does).

Python 3, standard library only.
"""
import datetime
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QROOT = os.environ.get("VL_QUEUE") or os.path.expanduser("~/vl-queue")
LOCKS = os.environ.get("VL_LOCK_DIR") or os.path.expanduser("~/vl-dev")
CONF = os.environ.get("BOARDS_CONF") or os.path.join(ROOT, "lab/boards.conf")
BOARDPOWER = os.environ.get("VL_BOARDPOWER") or os.path.join(ROOT, "lab/tools/boardpower.sh")
PICO = "pico2"
NO_POWER = {"nrf5340dk": "after a power-on our boot stub leaves its debug port locked "
                         "(lab/drafts/2026-11-25-nrf5340-approtect-recovery.md)"}
WRITE = re.compile(r"(?:^|\s)([^:\s][^:]*?): FLASH WRITE (\d+) of this run, (\d+) units")
POLL = float(os.environ.get("VL_QUEUE_POLL", "10"))


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def die(msg, code=2):
    print(f"boardqueue: {msg}", file=sys.stderr)
    sys.exit(code)


def boards():
    """name -> hub serial, from the board table."""
    out = {}
    for line in open(CONF):
        f = line.split()
        if len(f) >= 5 and not f[0].startswith("#"):
            out[f[0]] = f[1]
    return out


def qdir(board, *sub):
    return os.path.join(QROOT, board, *sub)


def ensure(board):
    for sub in ("todo", "running", "done", "failed"):
        os.makedirs(qdir(board, sub), exist_ok=True)


def lock(path, exclusive=True, wait=0.0):
    """Open and flock path; wait up to `wait` seconds. Returns the file, or None if not got."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fh = open(path, "a")
    end = time.time() + wait
    while True:
        try:
            fcntl.flock(fh, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            return fh
        except OSError:
            if time.time() >= end:
                fh.close()
                return None
            time.sleep(min(1.0, max(0.05, end - time.time())))


def git(wt, *args):
    return subprocess.run(["git", "-C", wt] + list(args), capture_output=True, text=True)


def worktree_problem(wt, commit):
    """None if wt is a clean checkout of commit, else what is wrong."""
    if not os.path.isdir(wt):
        return f"worktree {wt} does not exist"
    head = git(wt, "rev-parse", "HEAD")
    if head.returncode != 0:
        return f"{wt} is not a git checkout"
    if not head.stdout.strip().startswith(commit):
        return f"{wt} is at {head.stdout.strip()[:12]}, not {commit}"
    dirty = git(wt, "status", "--porcelain", "--untracked-files=no")
    if dirty.stdout.strip():
        return f"{wt} has changes: {dirty.stdout.strip().splitlines()[0]}"
    return None


# --- add ---------------------------------------------------------------------------

def cmd_add(argv):
    if "--" not in argv:
        die("add: the command goes after --")
    i = argv.index("--")
    opts, command = argv[:i], argv[i + 1:]
    if not opts or not command:
        die("add: BOARD and a command are needed")
    board, opts = opts[0], opts[1:]
    if board not in boards():
        die(f"add: {board} is not in {CONF}")
    job = {"board": board, "cwd": ".", "expect": [], "refuse": [], "note": ""}
    keys = {"--worktree": "worktree", "--commit": "commit", "--timeout": "timeout_s", "--writes": "write_budget",
            "--ok": "ok_by", "--cwd": "cwd", "--note": "note"}
    while opts:
        k = opts.pop(0)
        if not opts:
            die(f"add: {k} needs a value")
        v = opts.pop(0)
        if k in ("--expect", "--refuse"):
            re.compile(v)
            job[k[2:]].append(v)
        elif k in keys:
            job[keys[k]] = v
        else:
            die(f"add: unknown option {k}")
    for k in ("worktree", "commit", "timeout_s", "write_budget", "ok_by"):
        if k not in job:
            die(f"add: --{ {'timeout_s': 'timeout', 'write_budget': 'writes', 'ok_by': 'ok'}.get(k, k)} is needed")
    job["worktree"] = os.path.abspath(job["worktree"])
    if not re.fullmatch(r"[0-9a-f]{7,40}", job["commit"]):
        die("add: --commit must be a hash")
    try:
        job["timeout_s"], job["write_budget"] = int(job["timeout_s"]), int(job["write_budget"])
    except ValueError:
        die("add: --timeout and --writes must be whole numbers")
    if job["timeout_s"] <= 0 or job["write_budget"] < 0:
        die("add: --timeout must be above 0, --writes 0 or more")
    bad = worktree_problem(job["worktree"], job["commit"])
    if bad:
        die(f"add: {bad}")
    if not os.path.isdir(os.path.join(job["worktree"], job["cwd"])):
        die(f"add: {job['cwd']} is not a directory of the worktree")
    job["command"] = command
    job["enqueued"] = now()
    ensure(board)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    job["id"] = f"{stamp}-{board}"
    tmp = qdir(board, "todo", "." + job["id"] + ".json")
    with open(tmp, "w") as fh:
        json.dump(job, fh, indent=1)
    os.rename(tmp, qdir(board, "todo", job["id"] + ".json"))
    print(f"{board}: job {job['id']} enqueued ({job['write_budget']} writes at most, {job['timeout_s']} s at most)")
    return 0


# --- worker --------------------------------------------------------------------------

def ledger_add(board, what, units, job_id):
    with open(os.path.join(QROOT, "writes.tsv"), "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.write(f"{now()}\t{board}\t{what}\t{units}\t{job_id}\n")


def run_job(board, hub, job, log):
    """Run one job. Returns (ok, reason, writes)."""
    bad = worktree_problem(job["worktree"], job["commit"])
    if bad:
        return False, bad, 0
    held = [lock(os.path.join(LOCKS, f"hub-{hub}.lock"), exclusive=False, wait=job["timeout_s"])]
    if held[0] is None:
        return False, f"the hub {hub} stayed busy (a power switch)", 0
    if job["write_budget"] > 0:
        log.write(f"{now()} waiting for the write lock\n"); log.flush()
        w = lock(os.path.join(LOCKS, "usb-write.lock"), exclusive=(board == PICO), wait=job["timeout_s"])
        if w is None:
            return False, "the write lock stayed busy", 0
        held.append(w)
    try:
        env = dict(os.environ, VL_BOARD_LOCKED="1")
        log.write(f"{now()} start: {' '.join(job['command'])}\n"); log.flush()
        p = subprocess.Popen(job["command"], cwd=os.path.join(job["worktree"], job["cwd"]), env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        state = {"writes": 0, "over": False, "seen": [], "lines": 0}

        def read():
            for line in p.stdout:
                log.write(line); log.flush()
                state["lines"] += 1
                state["seen"].append(line.rstrip("\n"))
                m = WRITE.search(line)
                if m:
                    state["writes"] += 1
                    ledger_add(board, m.group(1).strip(), m.group(3), job["id"])
                    if state["writes"] > job["write_budget"] and not state["over"]:
                        state["over"] = True
                        stop(p)
        t = threading.Thread(target=read, daemon=True)
        t.start()
        try:
            rc = p.wait(timeout=job["timeout_s"])
            timed_out = False
        except subprocess.TimeoutExpired:
            stop(p)
            rc, timed_out = p.wait(), True
        t.join(timeout=30)
        log.write(f"{now()} end: exit {rc}, {state['writes']} flash writes\n"); log.flush()
        if timed_out:
            return False, f"timeout after {job['timeout_s']} s", state["writes"]
        if state["over"]:
            return False, f"flash write {state['writes']} is over the budget of {job['write_budget']}: stopped", state["writes"]
        if rc != 0:
            return False, f"exit {rc}", state["writes"]
        for rx in job.get("expect", []):
            if not any(re.search(rx, s) for s in state["seen"]):
                return False, f"no line matches --expect {rx!r}", state["writes"]
        for rx in job.get("refuse", []):
            hit = next((s for s in state["seen"] if re.search(rx, s)), None)
            if hit is not None:
                return False, f"a line matches --refuse {rx!r}: {hit[:120]}", state["writes"]
        return True, "ok", state["writes"]
    finally:
        for fh in held:
            fh.close()


def stop(p):
    """End the job's whole process group: TERM, then KILL after 10 s."""
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(100):
        if p.poll() is not None:
            break
        time.sleep(0.1)
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def cmd_worker(argv):
    follow = "--follow" in argv
    rest = [a for a in argv if a != "--follow"]
    if len(rest) != 1:
        die("worker BOARD [--follow]")
    board = rest[0]
    hubs = boards()
    if board not in hubs:
        die(f"worker: {board} is not in {CONF}")
    ensure(board)
    if os.path.exists(qdir(board, "STOPPED")):
        die(f"worker: {board} is stopped ({open(qdir(board, 'STOPPED')).read().strip()}); remove {qdir(board, 'STOPPED')} first")
    held = lock(os.path.join(LOCKS, board + ".lock"))
    if held is None:
        die(f"worker: {board} is busy ({os.path.join(LOCKS, board + '.lock')} is held)")
    with open(qdir(board, "worker.pid"), "w") as fh:
        fh.write(f"{os.getpid()}\n")
    print(f"{now()} {board}: worker {os.getpid()} started")
    try:
        while True:
            todo = sorted(f for f in os.listdir(qdir(board, "todo")) if f.endswith(".json") and not f.startswith("."))
            if not todo:
                if not follow:
                    print(f"{now()} {board}: queue empty, worker ends")
                    return 0
                time.sleep(POLL)
                continue
            name = todo[0]
            os.rename(qdir(board, "todo", name), qdir(board, "running", name))
            job = json.load(open(qdir(board, "running", name)))
            job["started"] = now()
            print(f"{now()} {board}: job {job['id']} starts")
            with open(qdir(board, "running", name[:-5] + ".log"), "w") as log:
                ok, why, writes = run_job(board, hubs[board], job, log)
            job.update(ended=now(), result=why, flash_writes=writes)
            dest = "done" if ok else "failed"
            with open(qdir(board, dest, name), "w") as fh:
                json.dump(job, fh, indent=1)
            os.rename(qdir(board, "running", name[:-5] + ".log"), qdir(board, dest, name[:-5] + ".log"))
            os.remove(qdir(board, "running", name))
            print(f"{now()} {board}: job {job['id']} {dest}: {why} ({writes} flash writes)")
            if not ok:
                with open(qdir(board, "STOPPED"), "w") as fh:
                    fh.write(f"{now()} job {job['id']}: {why}\n")
                print(f"{now()} {board}: STOPPED; the other boards go on")
                return 1
    finally:
        try:
            os.remove(qdir(board, "worker.pid"))
        except FileNotFoundError:
            pass
        held.close()


# --- status --------------------------------------------------------------------------

def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def cmd_status(argv):
    led = []
    path = os.path.join(QROOT, "writes.tsv")
    if os.path.exists(path):
        led = [l.rstrip("\n").split("\t") for l in open(path) if l.strip()]
    print(f"queue {QROOT}; flash writes in the ledger: {len(led)}")
    for board in sorted(boards()):
        if not os.path.isdir(qdir(board)):
            continue
        n = {s: len([f for f in os.listdir(qdir(board, s)) if f.endswith(".json") and not f.startswith(".")])
             for s in ("todo", "running", "done", "failed")}
        w = "none"
        if os.path.exists(qdir(board, "worker.pid")):
            pid = int(open(qdir(board, "worker.pid")).read().split()[0])
            w = f"{pid} ({'running' if alive(pid) else 'gone'})"
        line = (f"{board}: worker {w}; waiting {n['todo']}, done {n['done']}, failed {n['failed']}; "
                f"flash writes {sum(1 for x in led if x[1] == board)}")
        for f in os.listdir(qdir(board, "running")):
            if f.endswith(".json"):
                j = json.load(open(qdir(board, "running", f)))
                line += f"; running {j['id']} (at most {j['timeout_s']} s, {j['write_budget']} writes)"
        if os.path.exists(qdir(board, "STOPPED")):
            line += "; STOPPED: " + open(qdir(board, "STOPPED")).read().strip()
        print(line)
    return 0


# --- power ---------------------------------------------------------------------------

def cmd_power(argv):
    wait = 0.0
    if "--wait" in argv:
        i = argv.index("--wait")
        wait = float(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 2 or argv[1] not in ("on", "off", "cycle"):
        die("power BOARD on|off|cycle [--wait SECONDS]")
    board, action = argv
    hubs = boards()
    if board not in hubs:
        die(f"power: {board} is not in {CONF}")
    if board in NO_POWER:
        die(f"power: never {board}: {NO_POWER[board]}")
    h = lock(os.path.join(LOCKS, f"hub-{hubs[board]}.lock"), exclusive=True, wait=wait)
    if h is None:
        die(f"power: a job runs on hub {hubs[board]}; not switched")
    try:
        return subprocess.run(["bash", BOARDPOWER, action, board]).returncode
    finally:
        h.close()


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("add", "worker", "status", "power"):
        sys.exit(__doc__)
    return {"add": cmd_add, "worker": cmd_worker, "status": cmd_status, "power": cmd_power}[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
