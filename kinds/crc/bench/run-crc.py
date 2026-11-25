#!/usr/bin/env python3
"""Run the CRC kind's benchmark images on a board, one image per reset, and
write one JSON file per run, by the method of version 2
(firmware/nrf5340-rb-bench/run-one.py: its probe calls, board table, lock
and lab table are used unchanged; only the result block is this kind's).
The images and bundles are built first, without a board:
bash onebuild.sh table BOARD.

Usage (on lib-lab1):
  run-crc.py BOARD OUTDIR [--bundle N[,N...]] [--flash] [--passes N]
             [--adapter A[,A...]] [--only K] [--wait S] [--from DIR]
  run-crc.py decode WORDS-FILE MANIFEST.json ADAPTER PLACEMENT
             (no board: decode a result block read by hand, for a check)

  --bundle   these bundles of the board, in this order (default: all)
  --flash    a bundle that is not on the board is written to it (one flash
             write per bundle, counted in run.log). Without --flash nothing
             is written: the bundle must be on the board already, which is
             checked by comparing the flash with the bundle. On the Pico 2 a
             bundle of more than PART_UNITS units is written in parts
             (write_parts()), then compared as a whole.
  --passes   run the images of a bundle N times (default 1): odd passes in
             the bundle's order, even passes in reverse
  --adapter  these configurations only (names as in ../configs.txt)
  --only     the first K images of each bundle only (a smoke test)
  --wait     seconds off the probe after the reset (default 5): an attach
             stops the cycle counter. A run not finished at the first look
             is thrown away and repeated with twice the wait, as run-one.py.
  --from     where the bundles are (default ../build/v2/BOARD)

A run, as in version 2: the host writes the selection words (magic, image
address, ~address, a random run number) over the probe and resets the chip
(on the Pico 2 it first switches the XIP cache on over the probe: the
switch keeps its value over the reset, see run());
the boot stub starts that image; the image writes its results, its own
address and the run number at the start of RAM (bench/main.c, struct
results, "VLC1" version 2). A run file is written only if address and run
number are the ones asked for, the image says it is done, the cycle counter
ran, and the configuration's results equal the reference's on every call
(errors 0); otherwise the run is logged as giving no file.

OUTDIR gets run.log, build.json and bundle<N>.json (what was built and
flashed) and <adapter>-p<placement>-pass<P>.json for each run (schema
"crc-bench-run/1"; the cycles are the board's time_call() counts less the
board's counter-read overhead, as in version 2; the baseline is the
reference of the same CRC in the same image).
Environment: PROBE, VL_BOARD_LOCKED as run-one.py.
Exit: 0 every run gave a file, 1 not, 2 the probe or the board failed.
"""
import fcntl
import importlib.util
import json
import os
import random
import re
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.dirname(HERE)
RB = os.path.normpath(os.path.join(KIND, "../../firmware/nrf5340-rb-bench"))
sys.path.insert(0, RB)
_spec = importlib.util.spec_from_file_location("run_one", os.path.join(RB, "run-one.py"))
v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2)   # probe(), must(), lab_board(), BOARD, ProbeError, SELECT_MAGIC, RESULTS, MAX_WAIT

SCHEMA = "crc-bench-run/1"
RESULT_MAGIC, RESULT_VERSION = 0x564C4331, 2      # "VLC1", bench/main.c
NLEN, NOFF, NLIBS, STAT_WORDS = 6, 2, 2, 5
HEAD = 9 + NLEN + NOFF                            # magic .. crc_id, lens, offs
LIB_WORDS = 2 * NLEN * NOFF * STAT_WORDS + 1      # s[cache][len][off], errors
NWORDS = HEAD + NLIBS * LIB_WORDS + 4 + 2         # + dwt_stalls, board_id, read_overhead, empty_call_min, image_base, nonce
CRC_NAMES = ["CRC-32/ISO-HDLC", "CRC-16/IBM-3740", "CRC-8/SMBUS"]   # crc.h enum crc_id
CACHE = ["off", "on"]
BOARD_IDS = {1: "nRF5340 DK, application core (Cortex-M33)", 2: "NUCLEO-G0B1RE (STM32G0B1RET6, Cortex-M0+)",
             3: "NUCLEO-G474RE (STM32G474RET6, Cortex-M4F)", 4: "NUCLEO-H723ZG (STM32H723ZGT6, Cortex-M7)",
             5: "SAM D20 Xplained Pro (ATSAMD20J18A, Cortex-M0+)", 6: "Raspberry Pi Pico 2 H (RP2350A, core 0, Cortex-M33)"}


def stat(words, pos, overhead):
    mn, mx, total, first, count = words[pos:pos + STAT_WORDS]
    if count == 0:
        return None
    return {"min": mn - overhead, "max": mx - overhead, "mean": round(total / count - overhead, 3),
            "first": first - overhead, "count": count}


def decode(words, name):
    """The result block (NWORDS words) -> (header dict, [baseline, configuration] results)."""
    if len(words) != NWORDS:
        raise ValueError(f"{len(words)} words, {NWORDS} expected")
    magic, version, done, clock_hz, runs, nlen, noff, nlibs, crc_id = words[:9]
    if magic != RESULT_MAGIC or version != RESULT_VERSION or (nlen, noff, nlibs) != (NLEN, NOFF, NLIBS):
        raise ValueError("header " + " ".join(f"{x:#x}" for x in words[:9]))
    lens, offs = words[9:9 + NLEN], words[9 + NLEN:HEAD]
    t = HEAD + NLIBS * LIB_WORDS
    dwt_stalls, board_id, overhead, empty_raw, image_base, nonce = words[t:t + 6]
    libs = []
    for k, lname in enumerate(("baseline", name)):
        pos = HEAD + k * LIB_WORDS
        res = {}
        for c, cache in enumerate(CACHE):
            for li, ln in enumerate(lens):
                for oi, off in enumerate(offs):
                    res[f"len{ln}/offset{off}/cache_{cache}"] = stat(words, pos + ((c * NLEN + li) * NOFF + oi) * STAT_WORDS, overhead)
        libs.append({"name": lname, "results": res, "errors": words[pos + LIB_WORDS - 1]})
    head = {"done": done, "clock_hz": clock_hz, "runs": runs, "crc_id": crc_id,
            "crc": CRC_NAMES[crc_id] if crc_id < len(CRC_NAMES) else str(crc_id), "lens": list(lens), "offsets": list(offs),
            "dwt_stalls": dwt_stalls, "board_id": board_id, "overhead": overhead, "empty_call_raw_min": empty_raw,
            "image_base": image_base, "nonce": nonce}
    return head, libs


def read_words(out):
    return [int(x, 16) for x in re.sub(r"^[0-9a-fA-F]{8}:", "", out, flags=re.M).split() if re.fullmatch(r"[0-9a-fA-F]{8}", x)]


def main():
    args = sys.argv[1:]
    if args[:1] == ["decode"] and len(args) == 5:
        man = json.load(open(args[2]))
        im = next(i for i in man["images"] if i["adapter"] == args[3] and i["place"] == int(args[4]))
        head, libs = decode([int(w, 16) for w in open(args[1]).read().split()], im["name"])
        print(json.dumps({"head": head, "libs": libs}, indent=1))
        return 0
    if len(args) < 2 or args[0] not in v2.BOARD or args[1].startswith("-"):
        sys.exit(__doc__)
    board, outdir, args = args[0], args[1], args[2:]
    flash, passes, only, wait, bundles, adapters = False, 1, None, 5.0, None, None
    src = os.path.join(KIND, "build/v2", board)
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
    if not mans or any(m["board"] != board or m.get("kind") != "crc" for m in mans) or built["board"] != board:
        sys.exit(f"{src}: no CRC bundles of {board}")
    if any(m["result_bytes"] != 4 * NWORDS for m in mans):
        sys.exit(f"{src}: the images' result block is not the {4 * NWORDS} bytes this script reads")
    if board == "samd20":   # OpenOCD stand-in for probe-rs, as run-one.py
        os.environ["PATH"] = os.path.join(RB, "../common/samd20/bin") + os.pathsep + os.environ["PATH"]
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
    state = {"wait": wait, "waits": {}, "bad": 0, "runs": 0, "writes": 0}
    say(f"{board}: CRC bundles {bundles} from {src} ({built['bench_commit']}), {passes} passes, {probe_rs}")
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
            rc, out = v2.probe(["verify"] + pr + [elf], limit=600)
            if rc == 0 and "Verification successful" in out:
                say(f"{name}: on the board ({time.time() - t0:.0f} s to compare), nothing written")
            elif not flash:
                raise v2.ProbeError(f"{name} is not on the board (or could not be compared; --flash writes it): {out.strip()[-200:]}")
            else:
                t0 = time.time()
                if board == "rp2350" and man["flash_pages_written"] > PART_UNITS:
                    write_parts(elf, pr, outdir, name, say)
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
            for p in range(1, passes + 1):
                for im in (images if p % 2 else images[::-1]):
                    run(board, pr, man, built, im, p, outdir, state, say, probe_rs)
    except v2.ProbeError as e:
        say(f"STOPPED: {e}")
        say(f"{state['runs']} runs, {state['bad']} without a file, {state['writes']} flash writes")
        return 2
    say(f"done: {state['runs']} runs, {state['bad']} without a file, {state['writes']} flash writes, wait {state['wait']:g} s")
    return 1 if state["bad"] else 0


def run(board, pr, man, built, im, p, outdir, state, say, probe_rs):
    sel, base = int(man["select_addr"], 16), int(im["base"], 16)
    res_addr = int(man["results_addr"], 16)
    what = f"{im['adapter']} p{im['place']} {im['base']}"
    state["runs"] += 1
    rec, attempt, failures = None, 0, 0
    waits = state["waits"]
    while rec is None and failures < 3 and waits.get(im["adapter"], state["wait"]) <= v2.MAX_WAIT:
        attempt += 1
        w = waits.get(im["adapter"], state["wait"])
        nonce = random.getrandbits(32)
        t0 = time.time()
        v2.must(["write"] + pr + ["b32", f"{sel:#x}", f"{v2.SELECT_MAGIC:#x}", f"{base:#x}", f"{~base & 0xFFFFFFFF:#x}", f"{nonce:#x}"],
                f"{what}: selection", limit=30, tries=3)
        # "not finished" (done and clock_hz), after the selection, as run-one.py (the STM32H7 note there)
        v2.must(["write"] + pr + ["b32", f"{res_addr + 8:#x}", "0", "0"], f"{what}: clearing the results", limit=30, tries=3)
        if board == "rp2350":
            # XIP_CTRL keeps its value over this reset, and an image looked at before it had finished may
            # have left the XIP cache off (main.c measures with it off, then on): the next start would run
            # with it off until its first board_cache() (start-up about 50 times slower, empty call 275
            # cycles instead of 5). Every start gets the state a finished run leaves: the cache on.
            v2.must(["write"] + pr + ["b32", XIP_CTRL_SET, XIP_CTRL_EN], f"{what}: XIP cache on", limit=30, tries=3)
            v2.probe(["write"] + pr + ["b32", "0xE000ED0C", "0x05FA0004"], limit=20)
        else:
            v2.must(["reset"] + pr, f"{what}: reset", limit=60, tries=3)
        time.sleep(w)
        rc, out = v2.probe(["read"] + pr + ["b32", f"{res_addr:#x}", str(NWORDS)], limit=60)
        words = read_words(out) if rc == 0 else []
        took = time.time() - t0
        try:
            head, libs = decode(words, im["name"])
        except ValueError as e:
            why, failures = str(e), failures + 1
        else:
            if head["done"] != 1:
                why, waits[im["adapter"]] = "not finished", w * 2
            elif head["image_base"] != base or head["nonce"] != nonce:
                why, failures = f"not this start: image {head['image_base']:#x}, run number {head['nonce']:#x}", failures + 1
            else:
                rec = record(board, head, libs, im, man, built, nonce, took, w, attempt, p, probe_rs)
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
    key = "len1024/offset0/cache_on"
    s, b = rec["libs"][1]["results"][key], rec["libs"][0]["results"][key]
    say(f"{what} pass {p}: 1024 bytes, cache on: {s['mean'] if s else 'none'} cycles, "
        f"reference {b['mean'] if b else 'none'}, errors {rec['libs'][1]['errors']}, {took:.1f} s")


# The Pico 2 in this lab: while the probe writes flash, the board's own USB
# port cannot answer its host, and about 65 s after the write starts the
# host's hub power-cycles that port, so a long write loses the board's
# power. A part of at most PART_UNITS units of 4096 bytes takes 25 to 30 s.
XIP_CTRL_SET, XIP_CTRL_EN = "0x400CA000", "0x3"   # RP2350: XIP_CTRL (0x400C8000) through its set alias; EN_SECURE | EN_NONSECURE
PART_UNITS = 250
PART_SPACING = 70   # seconds from the start of a part before the next: past that power cycle, if one comes


def write_parts(elf, pr, outdir, name, say):
    """Write the loadable segments of elf in parts of whole segments, each
    at most PART_UNITS units, as Intel HEX files; wait between parts until
    the board answers again. The caller compares the whole bundle after."""
    d = open(elf, "rb").read()
    phoff, = struct.unpack_from("<I", d, 28)
    phentsize, phnum = struct.unpack_from("<HH", d, 42)
    segs = sorted((pa, d[off:off + fsz]) for t, off, va, pa, fsz, msz in
                  (struct.unpack_from("<IIIIII", d, phoff + i * phentsize) for i in range(phnum)) if t == 1 and fsz)

    def units(part):
        return sum(-(-len(b) // 4096) for _, b in part)
    parts, cur = [], []
    for seg in segs:
        if units([seg]) > PART_UNITS:
            raise v2.ProbeError(f"{name}: a segment at {seg[0]:#x} is larger than a part ({PART_UNITS} units)")
        if cur and units(cur + [seg]) > PART_UNITS:
            parts.append(cur)
            cur = []
        cur.append(seg)
    parts.append(cur)

    def rec(kind, addr, data):
        b = bytes([len(data), addr >> 8 & 255, addr & 255, kind]) + data
        return ":" + (b + bytes([-sum(b) & 255])).hex().upper() + "\n"
    say(f"{name}: {units(segs)} units in {len(parts)} parts of at most {PART_UNITS}")
    for n, part in enumerate(parts):
        hexfile = os.path.join(outdir, f"{os.path.basename(elf)}.part{n}.hex")
        with open(hexfile, "w") as fh:
            for pa, b in part:
                hi = None
                for k in range(0, len(b), 32):
                    a = pa + k
                    if a >> 16 != hi:
                        hi = a >> 16
                        fh.write(rec(4, 0, struct.pack(">H", hi)))
                    fh.write(rec(0, a & 0xFFFF, b[k:k + 32]))
            fh.write(":00000001FF\n")
        for _ in range(24):   # the board must answer before a part starts (at most 2 minutes)
            if v2.probe(["read"] + pr + ["b32", f"{segs[0][0]:#x}", "1"], limit=30)[0] == 0:
                break
            time.sleep(5)
        else:
            raise v2.ProbeError(f"{name} part {n}: the board does not answer")
        t0 = time.time()
        out = v2.must(["download"] + pr + ["--preverify", "--binary-format", "hex", hexfile], f"{name} part {n}: flash write",
                      limit=300)
        say(f"{name} part {n}: {units(part)} units {part[0][0]:#x}..{part[-1][0] + len(part[-1][1]):#x}, "
            f"{time.time() - t0:.0f} s: {(out.strip().splitlines() or [''])[-1]}")
        os.remove(hexfile)
        time.sleep(max(0.0, PART_SPACING - (time.time() - t0)))
    for _ in range(24):
        if v2.probe(["read"] + pr + ["b32", f"{segs[0][0]:#x}", "1"], limit=30)[0] == 0:
            return
        time.sleep(5)
    raise v2.ProbeError(f"{name}: the board does not answer after the last part")


def record(board, head, libs, im, man, built, nonce, took, wait, attempt, p, probe_rs):
    rec = {"schema": SCHEMA, "result_version": RESULT_VERSION, "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "host": os.uname().nodename, "board": v2.BOARD[board][1], "core": v2.BOARD[board][2], "board_id": head["board_id"],
           "board_decoded": BOARD_IDS.get(head["board_id"], str(head["board_id"])), "code_location": "flash",
           "kind": "crc", "crc": head["crc"], "bench_commit": built["bench_commit"], "toolchain_image": built["toolchain_image"],
           "adapter": im["adapter"], "lang": im.get("kind"), "name": im["name"], "place": im["place"],
           "slot": {k: im[k] for k in ("segment", "offset", "slot_bytes") if k in im},
           "image_base": f"{head['image_base']:#010x}", "image_bytes": im["bytes"], "fw_sha256": im["sha256"],
           "image_sha256": im["image_sha256"], "fixed_sha256": man["fixed_sha256"],
           "boot_image_sha256": man["boot_image_sha256"], "bundle": man.get("bundle"), "bundle_sha256": man["bundle_sha256"],
           "far_bytes": man.get("far_bytes", 0), "layout": man.get("layout"), "run_number": f"{nonce:#010x}", "pass": p, "attempt": attempt,
           "wait_s": wait, "seconds": round(took, 2), "probe_rs": probe_rs, "clock_hz": head["clock_hz"],
           "runs": head["runs"], "lens": head["lens"], "offsets": head["offsets"],
           "overhead_subtracted": head["overhead"], "empty_call_raw_min": head["empty_call_raw_min"], "libs": libs}
    if head["dwt_stalls"]:
        rec["invalid"] = f"cycle counter stalled ({head['dwt_stalls']:#x})"
    elif libs[1]["errors"] or libs[0]["errors"]:
        rec["invalid"] = f"results differ from the reference ({libs[1]['errors']} calls; baseline {libs[0]['errors']})"
    elif head["crc_id"] >= len(CRC_NAMES):
        rec["invalid"] = f"unknown CRC {head['crc_id']}"
    return rec


if __name__ == "__main__":
    sys.exit(main())
