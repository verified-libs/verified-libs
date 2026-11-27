#!/usr/bin/env python3
"""Run the pools concurrency series' images on a board, one image per reset,
and write one JSON file per run (lab/plans/2026-11-27-pools-concurrency.md,
3.2). As the first series' runner, whose pieces are imported and not
changed (kinds/pools/bench/run-pools.py: the probe calls, board table, lock
and lab table of firmware/nrf5340-rb-bench/run-one.py, the Pico 2's writes
in parts and its XIP cache before a reset); only the result block (decode.py)
and the run file are this series'. The images and the bundle are built first,
without a board: bash onebuild.sh BOARD.

Usage (on lib-lab1, through the queue):
  run-isr.py BOARD OUTDIR [--flash] [--adapter A[,A...]] [--wait S] [--poll S] [--stall N] [--grace S]
             [--max-wait S] [--from DIR]

  --flash     the bundle is written if it is not on the board (one flash
              write, counted in run.log). Without --flash nothing is written:
              the bundle must be on the board already, which is checked by
              comparing the flash with it.
  --adapter   these configurations only (default: every image of the bundle)
  --wait      seconds after the reset before the first look (default 10)
  --poll      seconds between looks (default 10). Each look reads the head of
              the result block over the debug port, without a halt and
              without a write: done, and the trial counters of both cache
              states. A run is judged when done is set, however long it
              takes while the counters move (a line in run.log every 10
              minutes says how far it is);
  --stall     looks without a change of the trial counters after which the
              run has stopped (default 3, i.e. 30 s). Before the first trial
              (the calibration) it has stopped only after --grace seconds
              (default 900). A stopped run is read without a write: the
              result block, the fault registers (ICSR; CFSR, HFSR, MMFAR,
              BFAR but on the Cortex-M0+, which has none), main.c's phase,
              fired and fired_phase (their addresses from the image's
              nm.txt), and the stack below the image's initial stack pointer,
              where the board layer's fault handler (`b .`) leaves the
              exception frame; its PC and LR are named from nm.txt. The run is
              started once more; the run file holds both starts' trial
              numbers and is judged by decode.py (stop(), the host check's
              crash text). It is not repeated further: a run that stops,
              stops where it stops.
  --max-wait  a guard (default 14400 s): a run still moving after it gives no
              file.
  --from      where the bundle is (default build/v1/BOARD)

A run: the host writes the selection words (magic, image address, ~address,
a random run number), clears done and clock_hz, and resets the chip (the
Pico 2: XIP cache on first, as run-pools.py); the boot stub starts that
image, which sweeps its configuration with the cache off and on and writes
the result block at the start of RAM. A run file is written only if the
block is whole, done, and of this start (image address and run number);
otherwise the run is logged as giving no file. The verdict is decode.py's,
by the plan's classes; a control that is not caught, or a configuration
within its documentation or ours that fails, is said in run.log.

OUTDIR gets run.log, build.json and bundle<N>.json (what was built and
flashed) and <adapter>.json for each run (schema "pools-isr-run/1").
Environment: PROBE, VL_BOARD_LOCKED as run-one.py.
Exit: 0 every run gave a file, 1 not, 2 the probe or the board failed.
"""
import fcntl
import importlib.util
import json
import os
import random
import re
import socket
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode   # noqa: E402

_spec = importlib.util.spec_from_file_location("run_pools", os.path.join(HERE, "..", "pools", "bench", "run-pools.py"))
rp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rp)   # v2 (run-one.py), write_parts, read_words, XIP_CTRL_*, PART_UNITS, BOARD_IDS
v2 = rp.v2

SCHEMA = "pools-isr-run/1"
NWORDS = decode.words_needed()


def main():
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in v2.BOARD or args[1].startswith("-"):
        sys.exit(__doc__)
    board, outdir, args = args[0], args[1], args[2:]
    flash, wait, max_wait, adapters = False, 10.0, 14400.0, None
    poll, stall, grace = 10.0, 3, 900.0
    src = os.path.join(HERE, "build/v1", board)
    while args:
        a = args.pop(0)
        if a == "--flash":
            flash = True
        elif a == "--adapter" and args:
            adapters = set(args.pop(0).split(","))
        elif a == "--wait" and args:
            wait = float(args.pop(0))
        elif a == "--max-wait" and args:
            max_wait = float(args.pop(0))
        elif a == "--poll" and args:
            poll = float(args.pop(0))
        elif a == "--stall" and args:
            stall = int(args.pop(0))
        elif a == "--grace" and args:
            grace = float(args.pop(0))
        elif a == "--from" and args:
            src = args.pop(0)
        else:
            sys.exit(__doc__)
    names = [f for f in os.listdir(src) if re.fullmatch(r"bundle\d+\.json", f)]
    if len(names) != 1:
        sys.exit(f"{src}: {len(names)} bundles, one expected")
    man = json.load(open(os.path.join(src, names[0])))
    built = json.load(open(os.path.join(src, "build.json")))
    if man["board"] != board or man.get("kind") != "pools-isr" or built["board"] != board:
        sys.exit(f"{src}: no pools-isr bundle of {board}")
    if man["result_bytes"] != 4 * NWORDS:
        sys.exit(f"{src}: the images' result block is not the {4 * NWORDS} bytes decode.py reads")
    if adapters and adapters - {im["adapter"] for im in man["images"]}:
        sys.exit(f"not in the bundle: {sorted(adapters - {im['adapter'] for im in man['images']})}")
    if board == "samd20":   # OpenOCD stand-in for probe-rs, as run-one.py
        os.environ["PATH"] = os.path.join(rp.RB, "../common/samd20/bin") + os.pathsep + os.environ["PATH"]
    lab_name, lab_probe = v2.lab_board(board)
    sel_probe = os.environ.get("PROBE") or lab_probe
    lock_dir = os.path.expanduser("~/vl-dev")
    if lab_name and os.path.isdir(lock_dir) and os.environ.get("VL_BOARD_LOCKED") != "1":
        lock = open(os.path.join(lock_dir, lab_name + ".lock"), "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print(f"{board}: busy ({lock.name} is held by another run)", file=sys.stderr)
            sys.exit(2)
    pr = ["--chip", v2.BOARD[board][0]] + (["--probe", sel_probe] if sel_probe else [])
    os.makedirs(outdir, exist_ok=True)
    log = open(os.path.join(outdir, "run.log"), "a")

    def say(msg):
        line = time.strftime("%H:%M:%S ", time.gmtime()) + msg
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    probe_rs = v2.subprocess.run(["probe-rs", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    with open(os.path.join(outdir, "build.json"), "w") as fh:
        json.dump(built, fh, indent=1)
    state = {"wait": wait, "max_wait": max_wait, "poll": poll, "stall": stall, "grace": grace, "src": src,
             "bad": 0, "runs": 0, "writes": 0, "unexpected": 0, "stopped": 0}
    images = [im for im in man["images"] if adapters is None or im["adapter"] in adapters]
    name = f"bundle {man['bundle']}"
    say(f"{board}: pools-isr {name} from {src} ({built['bench_commit']}), {len(images)} images, {probe_rs}")
    try:
        elf = os.path.join(src, os.path.basename(man["bundle_elf"]))
        t0 = time.time()
        rc, out = v2.probe(["verify"] + pr + [elf], limit=600)
        if rc == 0 and "Verification successful" in out:
            say(f"{name}: on the board ({time.time() - t0:.0f} s to compare), nothing written")
        elif not flash:
            raise v2.ProbeError(f"{name} is not on the board (or could not be compared; --flash writes it): {out.strip()[-200:]}")
        else:
            t0 = time.time()
            if board == "rp2350" and man["flash_pages_written"] > rp.PART_UNITS:
                rp.write_parts(elf, pr, outdir, name, say)
                rc, out = v2.probe(["verify"] + pr + [elf], limit=600)
                if rc != 0 or "Verification successful" not in out:
                    raise v2.ProbeError(f"{name}: written in parts, but the flash is not the bundle: {out.strip()[-200:]}")
            else:
                out = v2.must(["download"] + pr + ["--preverify", elf], f"{name}: flash write", limit=900)
            state["writes"] += 1
            say(f"{name}: FLASH WRITE {state['writes']} of this run, {man['flash_pages_written']} units of {man['unit']} bytes, "
                f"{time.time() - t0:.0f} s: {(out.strip().splitlines() or [''])[-1]}")
            if board == "rp2350":
                for _ in range(30):
                    if v2.probe(["read"] + pr + ["b32", f"{v2.RESULTS:#x}", "1"], limit=20)[0] == 0:
                        break
                    time.sleep(5)
        with open(os.path.join(outdir, f"bundle{man['bundle']}.json"), "w") as fh:
            json.dump(man, fh, indent=1)
        for im in images:
            run(board, pr, man, built, im, outdir, state, say, probe_rs)
    except v2.ProbeError as e:
        say(f"STOPPED: {e}")
        say(f"{state['runs']} runs, {state['bad']} without a file, {state['writes']} flash writes")
        return 2
    say(f"done: {state['runs']} runs, {state['bad']} without a file, {state['writes']} flash writes, "
        f"{state['unexpected']} verdicts not as expected, {state['stopped']} stopped before done")
    return 1 if state["bad"] else 0


EXPECTED = {"control": ("caught",), "ours": ("pass",), "within": ("pass",)}


def start(board, pr, man, im, nonce, what):
    sel, base = int(man["select_addr"], 16), int(im["base"], 16)
    res_addr = int(man["results_addr"], 16)
    v2.must(["write"] + pr + ["b32", f"{sel:#x}", f"{v2.SELECT_MAGIC:#x}", f"{base:#x}", f"{~base & 0xFFFFFFFF:#x}", f"{nonce:#x}"],
            f"{what}: selection", limit=30, tries=3)
    v2.must(["write"] + pr + ["b32", f"{res_addr + 8:#x}", "0", "0"], f"{what}: clearing the results", limit=30, tries=3)
    if board == "rp2350":   # as run-pools.py: every start with the XIP cache on, the reset through AIRCR
        v2.must(["write"] + pr + ["b32", rp.XIP_CTRL_SET, rp.XIP_CTRL_EN], f"{what}: XIP cache on", limit=30, tries=3)
        v2.probe(["write"] + pr + ["b32", "0xE000ED0C", "0x05FA0004"], limit=20)
    else:
        v2.must(["reset"] + pr, f"{what}: reset", limit=60, tries=3)


def read(pr, addr, n, what):
    """N words at ADDR over the debug port (no halt, no write); [] if the read failed"""
    rc, out = v2.probe(["read"] + pr + ["b32", f"{addr:#x}", str(n)], limit=120)
    words = rp.read_words(out) if rc == 0 else []
    return words if len(words) == n else []


HEAD = 8   # magic, version, done, clock_hz, board_id, image_base, nonce, faults_total (main.c struct results)


def watch(pr, man, im, nonce, state, say, what):
    """Look at a started run until it is done, stops, or runs into the guard: ("done", seconds),
    ("stopped", seconds, trials), ("cap", seconds, trials), or ("bad", seconds, why)."""
    per = sum(n for _, n, _ in decode.layout()[1])
    res_addr, base = int(man["results_addr"], 16), int(im["base"], 16)
    t0 = time.time()
    time.sleep(state["wait"])
    last, same, mine, next_log = None, 0, False, t0 + 600
    while True:
        w = read(pr, res_addr, HEAD + 2 * per, what)
        el = time.time() - t0
        if not w:
            return ("bad", el, "the result block could not be read")
        if w[0] == 0x564C4931 and w[5] == base and w[6] == nonce:
            mine = True
        if mine and w[2] == 1:
            return ("done", el)
        n = w[HEAD] + w[HEAD + per]
        same = same + 1 if n == last else 0
        last = n
        if not mine and el >= state["grace"]:
            return ("bad", el, f"not this start: image {w[5]:#x}, run number {w[6]:#x}")
        if mine and ((n and same >= state["stall"]) or (not n and el >= state["grace"])):
            return ("stopped", el, n)
        if el >= state["max_wait"]:
            return ("cap", el, n)
        if time.time() >= next_log:
            say(f"{what}: {n} trials after {el / 60:.0f} min")
            next_log += 600
        time.sleep(state["poll"])


def symbols(image_dir):
    """[(address, size, name)] of the image's code symbols (nm.txt: address, size, type, name)"""
    out = []
    for ln in open(os.path.join(image_dir, "nm.txt")):
        p = ln.rstrip("\n").split(" ", 3)
        if len(p) == 4 and p[2] in "TtWw":
            out.append((int(p[0], 16), int(p[1], 16), p[3]))
    return out


def var(image_dir, name):
    for ln in open(os.path.join(image_dir, "nm.txt")):
        p = ln.rstrip("\n").split(" ", 3)
        if len(p) == 4 and p[3] == name:
            return int(p[0], 16)
    return None


def named(syms, a):
    a &= ~1
    for addr, size, name in syms:
        if addr <= a < addr + size:
            return name
    return None


ARMV6M = ("stm32g0b1", "samd20")   # Cortex-M0+: no CFSR, HFSR, MMFAR, BFAR


def stall_read(board, pr, im, state, what):
    """What a stopped run shows, read without a write (see --stall)."""
    d = os.path.join(state["src"], "img", im["adapter"])
    base, size = int(im["base"], 16), im["bytes"]
    info = {"read": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    icsr = read(pr, 0xE000ED04, 1, what)
    info["icsr"] = f"{icsr[0]:#010x}" if icsr else None
    vect = icsr[0] & 0x1FF if icsr else None
    regs = {}
    if board not in ARMV6M:
        r = read(pr, 0xE000ED28, 5, what)
        if r:
            regs = dict(zip(("cfsr", "hfsr", "dfsr", "mmfar", "bfar"), r))
            info.update({k: f"{v:#010x}" for k, v in regs.items()})
    for v in ("phase", "fired", "fired_phase"):
        a = var(d, v)
        x = read(pr, a, 1, what) if a is not None else []
        info[v] = x[0] if x else None
    sp0 = int.from_bytes(open(os.path.join(d, "fw.bin"), "rb").read(4), "little")   # the vector table's initial SP
    n = 512
    st = read(pr, sp0 - 4 * n, n, what)
    in_code = lambda a: base <= (a & ~1) < base + size
    frames = []
    for i in range(len(st) - 7):
        r0, r1, r2, r3, r12, lr, pc, xpsr = st[i:i + 8]
        if xpsr >> 24 & 1 and not pc & 1 and in_code(pc) and (in_code(lr) and lr & 1 or lr >= 0xFFFFFF00):
            frames.append({"at": f"{sp0 - 4 * n + 4 * i:#010x}", "pc": f"{pc:#010x}", "lr": f"{lr:#010x}",
                           "xpsr": f"{xpsr:#010x}"})
    info["frames"] = frames
    info["fault"] = vect is not None and 2 <= vect <= 6   # NMI, HardFault, MemManage, BusFault, UsageFault
    syms = symbols(d)
    if info["fault"] and frames:
        f = frames[-1]   # the handler (`b .`) pushes nothing: the frame is at its SP; frames below it are stale
        pc, lr, xpsr = int(f["pc"], 16), int(f["lr"], 16), int(f["xpsr"], 16)
        info.update(pc=f["pc"], lr=f["lr"], pc_symbol=named(syms, pc), lr_symbol=named(syms, lr), ipsr=xpsr & 0x1FF)
    if info.get("ipsr") == 15:
        where = "the interrupt's call"
    elif info["phase"] == 0:
        where = "the trial's setup"
    elif info["phase"] == 1:
        where = "main's call"
    elif info["phase"] == 2:
        where = "the check after the trial"
    else:
        where = "a part of the image not read"
    info["where"] = where
    if not info["fault"]:
        desc = f"no fault: the core was running, no progress for {state['stall'] * state['poll']:g} s"
    elif regs.get("cfsr", 0) >> 15 & 1:
        desc = f"a bus fault at {regs['bfar']:#x}"
    elif regs.get("cfsr", 0) >> 7 & 1:
        desc = f"a memory fault at {regs['mmfar']:#x}"
    elif regs.get("cfsr", 0) >> 16:
        desc = "a usage fault"
    else:
        desc = "a HardFault"
    info["desc"] = desc
    return info


def run(board, pr, man, built, im, outdir, state, say, probe_rs):
    res_addr = int(man["results_addr"], 16)
    what = f"{im['adapter']} {im['base']}"
    state["runs"] += 1
    rec, attempt, failures, stops = None, 0, 0, []
    while rec is None and failures < 3:
        attempt += 1
        nonce = random.getrandbits(32)
        t0 = time.time()
        start(board, pr, man, im, nonce, what)
        got = watch(pr, man, im, nonce, state, say, what)
        took = time.time() - t0
        if got[0] == "bad":
            failures += 1
            say(f"{what}: {got[2]} after {got[1]:.0f} s (attempt {attempt})")
            continue
        if got[0] == "cap":
            say(f"{what}: still running after {got[1]:.0f} s ({got[2]} trials), the guard (--max-wait)")
            break
        words = read(pr, res_addr, NWORDS, what)
        if not words:
            failures += 1
            say(f"{what}: the result block could not be read (attempt {attempt})")
            continue
        res = decode.decode(words, im["adapter"])
        if got[0] == "stopped":
            info = stall_read(board, pr, im, state, what)
            stops.append({"attempt": attempt, "trials": got[2], "seconds": round(got[1], 1)})
            say(f"{what}: stopped at {got[2]} trials after {got[1]:.0f} s: {info['desc']}, in {info['where']}"
                + (f" ({info['pc_symbol']})" if info.get("pc_symbol") else "") + f" (attempt {attempt})")
            if len(stops) < 2:
                continue   # once more, to see whether it stops at the same trial
            info["starts"] = stops
            decode.stop(res, info)
            state["stopped"] += 1
        rec = record(board, res, im, man, built, nonce, took, state["wait"], attempt, probe_rs)
        if stops and got[0] == "done":
            rec["earlier_stops"] = stops   # an earlier start stopped, this one finished: both are kept
    if rec is None:
        state["bad"] += 1
        say(f"{what}: NO RUN FILE")
        return
    with open(os.path.join(outdir, f"{im['adapter']}.json"), "w") as fh:
        json.dump(rec, fh, indent=1)
    verdict = rec["verdict"]
    want = EXPECTED.get(rec["class"])
    note = "" if want is None or verdict in want else "  <-- NOT AS EXPECTED"
    state["unexpected"] += bool(note)
    c = rec["result"]["c"]
    say(f"{what} ({rec['class']}): {verdict}; {c[0]['trials'] + c[1]['trials']} trials, {c[0]['inside'] + c[1]['inside']} inside; "
        f"longest wait of an interrupt off/on: {c[0]['irq_wait_cycles']}/{c[1]['irq_wait_cycles']} cycles; {rec['seconds']:.0f} s{note}")


def record(board, res, im, man, built, nonce, took, w, attempt, probe_rs):
    return {"schema": SCHEMA, "kind": "pools-isr", "board": board, "board_id": res["board_id"],
            "board_decoded": rp.BOARD_IDS.get(res["board_id"]), "adapter": im["adapter"], "class": res["class"],
            "bench_commit": built["bench_commit"], "toolchain_image": built["toolchain_image"], "toolchain": built["toolchain"],
            "libs_pinned": built["libs_pinned"], "clock_hz": res["clock_hz"],
            "image_base": im["base"], "image_bytes": im["bytes"], "image_sha256": im["image_sha256"], "fw_sha256": im["sha256"],
            "bundle": man["bundle"], "bundle_sha256": man["bundle_sha256"], "boot_image_sha256": man["boot_image_sha256"],
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host": socket.gethostname(), "probe_rs": probe_rs,
            "attempt": attempt, "wait_s": w, "seconds": round(took, 1), "run_number": f"{nonce:#010x}",
            "verdict": decode.judge(res), "result": res}


if __name__ == "__main__":
    sys.exit(main())
