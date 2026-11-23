#!/usr/bin/env python3
"""Run the benchmark images of version 2 on a board, one image per reset,
and write one JSON file per run
(lab/plans/2026-11-22-bench-image-per-library.md). The images and bundles
are built first, without a board: bash onebuild.sh table BOARD.

Usage (on lib-lab1):
  run-one.py BOARD OUTDIR [--bundle N[,N...]] [--flash] [--passes N]
             [--adapter A[,A...]] [--only K] [--wait S] [--from DIR]

  BOARD      nrf5340 stm32g0b1 stm32g474 stm32h723 samd20 rp2350
  --bundle   these bundles of the board, in this order (default: all)
  --flash    a bundle that is not on the board is written to it (one flash
             write per bundle, counted in run.log). Without --flash nothing
             is written: the bundle must be on the board already, which is
             checked by comparing the flash with the bundle.
  --passes   run the images of a bundle N times (default 1): odd passes in
             the bundle's order, even passes in reverse
  --adapter  these configurations only (names as in configs.txt)
  --only     the first K images of each bundle only (a smoke test)
  --wait     seconds off the probe after the reset (default 3): every
             attach stops the cycle counter, so the host stays away while
             an image measures. A run that is not finished at the first
             look is thrown away and repeated with twice the wait. The
             longer wait is kept for the other images of that configuration;
             the next configuration starts with the shortest wait that any
             configuration of this run has finished in.
  --from     where the bundles are (default build/v2/BOARD)

A run: the host writes the selection words (magic, image address,
~address, a random run number) over the probe and resets the chip; the boot
stub starts that image; the image writes its results, its own address and
the run number to the start of RAM. A run file is written only if address
and run number are the ones asked for.

OUTDIR gets run.log, build.json and bundle<N>.json (what was built and
flashed) and <adapter>-p<placement>-pass<P>.json for each run.
Environment: PROBE (probe-rs selector; default: the board's probe in
lab/boards.conf); VL_BOARD_LOCKED=1 if the caller holds the board's lock
(~/vl-dev/<lab name>.lock), which this script otherwise takes.
Exit: 0 every run gave a file, 1 not, 2 the probe or the board failed.
"""
import fcntl
import json
import os
import random
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode  # noqa: E402  (stat(), SCENARIOS, CACHE, BOARDS)

# firmware board: probe-rs chip, board, core (as run.sh)
BOARD = {"nrf5340": ("nRF5340_xxAA_APPONLY", "nRF5340 DK", "application (Cortex-M33)"),
         "stm32g0b1": ("STM32G0B1RE", "NUCLEO-G0B1RE", "Cortex-M0+"),
         "stm32g474": ("STM32G474RE", "NUCLEO-G474RE", "Cortex-M4F"),
         "stm32h723": ("STM32H723ZG", "NUCLEO-H723ZG", "Cortex-M7"),
         "samd20": ("ATSAMD20J18A", "SAM D20 Xplained Pro", "Cortex-M0+"),
         "rp2350": ("RP235x", "Raspberry Pi Pico 2 H", "RP2350 core 0 (Cortex-M33)")}
RESULT_MAGIC, SELECT_MAGIC = 0x564C4235, 0x564C4253
RESULTS = 0x20000000
NLIBS = 2   # the baseline and the configuration
NWORDS = 7 + NLIBS * (2 * 7 * 10 + 1) + 1 + 3 + 2
SCHEMA = "rb-bench-run/2"
MAX_WAIT = 400.0


class ProbeError(Exception):
    pass


def probe(args, limit=60, tries=1):
    """probe-rs with a time limit: (exit code, output); exit code None after a timeout."""
    rc, out = None, ""
    for k in range(tries):
        if k:
            time.sleep(2 + random.random() * 4)
        try:
            r = subprocess.run(["probe-rs"] + args, capture_output=True, text=True, timeout=limit)
            rc, out = r.returncode, re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr)
        except subprocess.TimeoutExpired:
            rc, out = None, f"no answer in {limit} s"
        if rc == 0:
            break
    return rc, out


def must(args, what, **kw):
    rc, out = probe(args, **kw)
    if rc != 0:
        raise ProbeError(f"{what}: {out.strip()[-300:]}")
    return out


def lab_board(board):
    """(the board's name in the lab, its probe) from lab/boards.conf"""
    for ln in open(os.path.join(HERE, "../../lab/boards.conf")):
        f = ln.split("#")[0].split()
        if len(f) >= 6 and f[5] == board:
            return f[0], f"{f[3]}:{f[4]}"
    return None, None


def main():
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in BOARD or args[1].startswith("-"):
        sys.exit(__doc__)
    board, outdir, args = args[0], args[1], args[2:]
    flash, passes, only, wait, bundles, adapters = False, 1, None, 3.0, None, None
    src = os.path.join(HERE, "build/v2", board)
    while args:
        a = args.pop(0)
        if a == "--flash":
            flash = True
        elif a == "--passes" and args:
            passes = int(args.pop(0))
        elif a == "--only" and args:
            only = int(args.pop(0))
        elif a == "--bundle" and args:
            bundles = [int(n) for n in args.pop(0).split(",")]
        elif a == "--adapter" and args:
            adapters = set(args.pop(0).split(","))
        elif a == "--wait" and args:
            wait = float(args.pop(0))
        elif a == "--from" and args:
            src = args.pop(0)
        else:
            sys.exit(__doc__)
    if bundles is None:
        bundles = sorted(int(m.group(1)) for m in (re.fullmatch(r"bundle(\d+)\.json", f) for f in os.listdir(src)) if m)
    mans = [json.load(open(os.path.join(src, f"bundle{n}.json"))) for n in bundles]
    built = json.load(open(os.path.join(src, "build.json")))
    if not mans or any(m["board"] != board for m in mans) or built["board"] != board:
        sys.exit(f"{src}: no bundles of {board}")
    if board == "samd20":   # OpenOCD stand-in for probe-rs, as run.sh
        os.environ["PATH"] = os.path.join(HERE, "../common/samd20/bin") + os.pathsep + os.environ["PATH"]
    lab_name, lab_probe = lab_board(board)
    sel_probe = os.environ.get("PROBE") or lab_probe
    # One run per board at a time: the lock the lab's check and campaign scripts hold (a second probe user
    # stops the first one's cycle counter or takes its probe away).
    lock_dir = os.path.expanduser("~/vl-dev")
    if lab_name and os.path.isdir(lock_dir) and os.environ.get("VL_BOARD_LOCKED") != "1":
        lock = open(os.path.join(lock_dir, lab_name + ".lock"), "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print(f"{board}: busy ({lock.name} is held by another run)", file=sys.stderr)
            sys.exit(2)
    pr = ["--chip", BOARD[board][0]] + (["--probe", sel_probe] if sel_probe else [])
    os.makedirs(outdir, exist_ok=True)
    log = open(os.path.join(outdir, "run.log"), "a")

    def say(msg):
        line = time.strftime("%H:%M:%S ", time.gmtime()) + msg
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    probe_rs = subprocess.run(["probe-rs", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    with open(os.path.join(outdir, "build.json"), "w") as fh:
        json.dump(built, fh, indent=1)
    state = {"wait": wait, "waits": {}, "bad": 0, "runs": 0, "writes": 0}
    say(f"{board}: bundles {bundles} from {src} ({built['bench_commit']}), {passes} passes, {probe_rs}")
    try:
        for man in mans:
            images = [im for im in man["images"] if adapters is None or im["adapter"] in adapters]
            images = images[:only] if only else images
            name = f"bundle {man['bundle']}"
            if not images:
                say(f"{name}: no image asked for, left out")
                continue
            elf = os.path.join(src, os.path.basename(man["bundle_elf"]))
            t0 = time.time()
            rc, out = probe(["verify"] + pr + [elf], limit=600)
            # probe-rs 0.32 exits with 0 also when the contents differ: only its own words count
            if rc == 0 and "Verification successful" in out:
                say(f"{name}: on the board ({time.time() - t0:.0f} s to compare), nothing written")
            elif not flash:
                raise ProbeError(f"{name} is not on the board (or could not be compared; --flash writes it): {out.strip()[-200:]}")
            else:
                # No --allow-erase-all: only the pages of the bundle are erased and written.
                t0 = time.time()
                out = must(["download"] + pr + ["--preverify", elf], f"{name}: flash write", limit=900)
                state["writes"] += 1
                say(f"{name}: FLASH WRITE {state['writes']} of this run, {man['flash_pages_written']} units of {man['unit']} bytes, "
                    f"{time.time() - t0:.0f} s: {(out.strip().splitlines() or [''])[-1]}")
                if board == "rp2350":   # the probe can lose the chip for a while after a download
                    for _ in range(30):
                        if probe(["read"] + pr + ["b32", f"{RESULTS:#x}", "1"], limit=20)[0] == 0:
                            break
                        time.sleep(5)
            with open(os.path.join(outdir, f"bundle{man['bundle']}.json"), "w") as fh:
                json.dump(man, fh, indent=1)
            for p in range(1, passes + 1):
                for im in (images if p % 2 else images[::-1]):
                    run(board, pr, man, built, im, p, outdir, state, say, probe_rs)
    except ProbeError as e:
        say(f"STOPPED: {e}")
        say(f"{state['runs']} runs, {state['bad']} without a file, {state['writes']} flash writes")
        return 2
    say(f"done: {state['runs']} runs, {state['bad']} without a file, {state['writes']} flash writes, wait {state['wait']:g} s"
        + "".join(f", {a} {w:g} s" for a, w in sorted(state["waits"].items()) if w != state["wait"]))
    return 1 if state["bad"] else 0


def run(board, pr, man, built, im, p, outdir, state, say, probe_rs):
    sel, base = int(man["select_addr"], 16), int(im["base"], 16)
    what = f"{im['adapter']} p{im['place']} {im['base']}"
    state["runs"] += 1
    rec, attempt, failures = None, 0, 0
    waits = state["waits"]   # per configuration: the wait its images need
    while rec is None and failures < 3 and waits.get(im["adapter"], state["wait"]) <= MAX_WAIT:
        attempt += 1
        w = waits.get(im["adapter"], state["wait"])
        nonce = random.getrandbits(32)
        t0 = time.time()
        must(["write"] + pr + ["b32", f"{sel:#x}", f"{SELECT_MAGIC:#x}", f"{base:#x}", f"{~base & 0xFFFFFFFF:#x}", f"{nonce:#x}"],
             f"{what}: selection", limit=30, tries=3)
        # "Not finished" in the results, so that the run before cannot be taken for this one. Written after the
        # selection: the STM32H7 can lose the last RAM words written before a reset (common/select.h), and then
        # it is these and not the selection.
        must(["write"] + pr + ["b32", f"{RESULTS + 8:#x}", "0", "0"], f"{what}: clearing the results", limit=30, tries=3)
        if board == "rp2350":
            # probe-rs reset can hang on the RP2350 (rb-stress run.sh): a system reset through the core's AIRCR
            # instead; the probe loses the chip while it resets, so the command's result says nothing
            probe(["write"] + pr + ["b32", "0xE000ED0C", "0x05FA0004"], limit=20)
        else:
            must(["reset"] + pr, f"{what}: reset", limit=60, tries=3)
        time.sleep(w)
        rc, out = probe(["read"] + pr + ["b32", f"{RESULTS:#x}", str(NWORDS)], limit=60)
        words = [int(x, 16) for x in re.sub(r"^[0-9a-fA-F]{8}:", "", out, flags=re.M).split()
                 if re.fullmatch(r"[0-9a-fA-F]{8}", x)] if rc == 0 else []
        took = time.time() - t0
        if len(words) != NWORDS:
            why, failures = f"no read ({len(words)} words)", failures + 1
        elif words[0] != RESULT_MAGIC or words[1] != 7 or words[5] != NLIBS or words[6] != 7:
            why, failures = "header " + " ".join(f"{x:#x}" for x in words[:7]), failures + 1
        elif words[2] != 1:
            # Not finished (or not yet started: then the words of the run before are still there, all but
            # "done"). The look stopped the cycle counter: this run is lost; this configuration's images
            # wait longer.
            why, waits[im["adapter"]] = "not finished", w * 2
        elif words[-2] != base or words[-1] != nonce:
            why, failures = f"not this start: image {words[-2]:#x}, run number {words[-1]:#x}", failures + 1
        else:
            rec = decode_run(board, words, im, man, built, nonce, took, w, attempt, p, probe_rs)
            # the wait a new configuration starts with: the shortest that one has finished in
            state.setdefault("finished", set()).add(w)
            waits[im["adapter"]], state["wait"] = w, min(state["finished"])
            break
        say(f"{what}: {why} after {w:g} s (attempt {attempt})")
    if rec is None or rec.get("invalid"):
        state["bad"] += 1
        say(f"{what} pass {p}: NO RUN FILE" + (f" ({rec['invalid']})" if rec else ""))
        return
    with open(os.path.join(outdir, f"{im['adapter']}-p{im['place']}-pass{p}.json"), "w") as fh:
        json.dump(rec, fh, indent=1)
    s, b = rec["libs"][1]["results"], rec["libs"][0]["results"]
    key = "single/cache_on"

    def mean(res, op):   # a configuration may have no numbers on a core (no compare-and-swap on a Cortex-M0+)
        return res[key][op]["mean"] if res.get(key) and res[key].get(op) else "none"
    say(f"{what} pass {p}: single push/pop {mean(s, 'push')}/{mean(s, 'pop')}, "
        f"baseline {mean(b, 'push')}/{mean(b, 'pop')}, errors {rec['libs'][1]['errors']}, {took:.1f} s")


def decode_run(board, words, im, man, built, nonce, took, wait, attempt, p, probe_rs):
    nscen = len(decode.SCENARIOS)
    trailer = 7 + NLIBS * (2 * nscen * 2 * decode.STAT_WORDS + 1)
    dwt_stalls = words[trailer]
    board_id, overhead, empty_raw, image_base, _ = words[trailer + 1:trailer + 6]
    decode.OVERHEAD = overhead
    pos, libs = 7, []
    for name in ("baseline", im.get("name", im["adapter"])):
        lib = {"name": name, "results": {}}
        for cache in decode.CACHE:
            for scen, _ in decode.SCENARIOS:
                lib["results"][f"{scen}/cache_{cache}"] = {"push": decode.stat(words, pos),
                                                           "pop": decode.stat(words, pos + decode.STAT_WORDS)}
                pos += 2 * decode.STAT_WORDS
        lib["errors"] = words[pos] if name != "baseline" else None
        pos += 1
        libs.append(lib)
    # What was built (compiler, library versions) is in build.json, once per run directory.
    rec = {"schema": SCHEMA, "result_version": words[1], "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "host": os.uname().nodename, "board": BOARD[board][1], "core": BOARD[board][2], "board_id": board_id,
           "board_decoded": decode.BOARDS.get(board_id, str(board_id)), "code_location": "flash",
           "bench_commit": built["bench_commit"], "toolchain_image": built["toolchain_image"],
           "adapter": im["adapter"], "kind": im.get("kind"), "place": im["place"],
           "slot": {k: im[k] for k in ("segment", "offset", "slot_bytes") if k in im}, "image_base": f"{image_base:#010x}",
           "image_bytes": im["bytes"], "fw_sha256": im["sha256"], "image_sha256": im["image_sha256"],
           "fixed_sha256": man["fixed_sha256"], "boot_image_sha256": man["boot_image_sha256"],
           "bundle": man.get("bundle"), "bundle_sha256": man["bundle_sha256"], "far_bytes": man.get("far_bytes", 0),
           "run_number": f"{nonce:#010x}", "pass": p, "attempt": attempt, "wait_s": wait, "seconds": round(took, 2),
           "probe_rs": probe_rs, "clock_hz": words[3], "runs": words[4], "overhead_subtracted": overhead,
           "empty_call_raw_min": empty_raw, "scenarios": [s for s, _ in decode.SCENARIOS], "libs": libs}
    if dwt_stalls:
        rec["invalid"] = f"cycle counter stalled ({dwt_stalls:#x})"
    return rec


if __name__ == "__main__":
    sys.exit(main())
