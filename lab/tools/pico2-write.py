#!/usr/bin/env python3
"""Write a benchmark bundle to the Pico 2 in parts.

Usage: lab/tools/pico2-write.py BUNDLE.elf
  e.g. firmware/nrf5340-rb-bench/build/v2/rp2350/bundle0.elf, before
  `run-one.py rp2350 ...`, which then finds the bundle on the board and
  writes nothing.
  PART_UNITS=N  units of 4096 bytes per part (default 250, about 1 MB)
  DRY=1         say the parts, touch nothing

Why: while the probe writes flash, the Pico 2's own USB port shows up at
the hub and does not answer (the core is held); 65 s after that the kernel
power-cycles the hub port, and the board is fed from that port: a write
that lasts longer is cut off in the middle
(reports/2026-11-23-bench-v2-far-call.md). A part of 1 MB is written in
under 30 s. After each part the power cycle is waited for, then the board.
Every sector is erased and written once, as by one download, and at the
end the whole bundle is compared with the board (probe-rs verify).
Not needed when the board hangs on a cable that carries power only.

The board lock (~/vl-dev/<lab name>.lock) is taken, as the run scripts do.
Exit: 0 the bundle is on the board (written, or it was there), 1 not.
"""
import fcntl
import os
import re
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CHIP, FW_BOARD = "RP235x", "rp2350"
UNIT, PAUSE = 4096, 75
ALIVE = ["b32", "0x20000000", "1"]


def say(s):
    print(time.strftime("%H:%M:%S", time.gmtime()), s, flush=True)


def probe(args, limit):
    """probe-rs with a time limit: (exit code, output); exit code None after a timeout."""
    try:
        r = subprocess.run(["probe-rs"] + args, capture_output=True, text=True, timeout=limit)
        return r.returncode, re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        return None, f"no answer in {limit} s"


def lab_board():
    """(the board's name in the lab, its probe) from lab/boards.conf"""
    for ln in open(os.path.join(HERE, "../boards.conf")):
        f = ln.split()
        if len(f) >= 6 and not ln.startswith("#") and f[5] == FW_BOARD:
            return f[0], f"{f[3]}:{f[4]}"
    sys.exit(f"lab/boards.conf: no board with firmware board {FW_BOARD}")


def elf_parts(elf, per):
    """the loaded segments of a 32-bit ELF file, [(address, bytes)], in parts of at most `per` units"""
    d = open(elf, "rb").read()
    phoff, = struct.unpack_from("<I", d, 28)
    phentsize, phnum = struct.unpack_from("<HH", d, 42)
    segs = sorted((pa, d[off:off + fsz]) for t, off, va, pa, fsz, msz in
                  (struct.unpack_from("<IIIIII", d, phoff + i * phentsize) for i in range(phnum)) if t == 1 and fsz)
    parts, cur = [], []
    for s in segs:
        if cur and units(cur + [s]) > per:
            parts.append(cur)
            cur = []
        cur.append(s)
    return parts + [cur]


def units(part):
    return sum(-(-len(b) // UNIT) for _, b in part)


def ihex(part):
    """Intel HEX of segments"""
    def rec(t, addr, data):
        b = bytes([len(data), addr >> 8 & 255, addr & 255, t]) + data
        return ":" + (b + bytes([-sum(b) & 255])).hex().upper() + "\n"
    out = []
    for pa, b in part:
        hi = None
        for k in range(0, len(b), 32):
            a = pa + k
            if a >> 16 != hi:
                hi = a >> 16
                out.append(rec(4, 0, struct.pack(">H", hi)))
            out.append(rec(0, a & 0xFFFF, b[k:k + 32]))
    return "".join(out) + ":00000001FF\n"


def answers(pr, tries):
    for _ in range(tries):
        if probe(["read"] + pr + ALIVE, 20)[0] == 0:
            return True
        time.sleep(5)
    return False


def main():
    if len(sys.argv) != 2 or sys.argv[1].startswith("-"):
        sys.exit(__doc__)
    elf = sys.argv[1]
    parts = elf_parts(elf, int(os.environ.get("PART_UNITS", "250")))
    say(f"{elf}: {sum(units(p) for p in parts)} units of {UNIT} bytes in {len(parts)} parts: {[units(p) for p in parts]}")
    if os.environ.get("DRY"):
        return 0
    name, lab_probe = lab_board()
    lock = open(os.path.join(os.environ.get("VL_LOCK_DIR", os.path.expanduser("~/vl-dev")), name + ".lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(f"{name} is in use (lock held)")
    pr = ["--chip", CHIP, "--probe", lab_probe]
    rc, out = probe(["verify"] + pr + [elf], 600)
    # probe-rs 0.32 exits with 0 also when the contents differ: only its own words count
    if rc == 0 and "Verification successful" in out:
        say("on the board already, nothing written")
        return 0
    for n, part in enumerate(parts):
        if not answers(pr, 24):
            say(f"part {n + 1}: the board does not answer: stopped")
            return 1
        with tempfile.NamedTemporaryFile("w", suffix=".hex") as fh:
            fh.write(ihex(part))
            fh.flush()
            t0 = time.time()
            rc, out = probe(["download"] + pr + ["--binary-format", "hex", fh.name], 300)
        say(f"part {n + 1} of {len(parts)}: FLASH WRITE of {units(part)} units from {part[0][0]:#x}, {time.time() - t0:.0f} s: "
            f"{(out.strip().splitlines() or [''])[-1][:160]}")
        if rc != 0:
            say("stopped")
            return 1
        time.sleep(max(0.0, PAUSE - (time.time() - t0)))   # the power cycle of the hub port passes
    answers(pr, 30)
    rc, out = probe(["verify"] + pr + [elf], 600)
    if rc == 0 and "Verification successful" in out:
        say(f"the bundle is on the board (one flash write of the bundle, in {len(parts)} parts)")
        return 0
    say(f"the bundle is NOT on the board: {out.strip()[-200:]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
