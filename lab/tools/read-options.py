#!/usr/bin/env python3
"""Read a board's option registers through its probe, zero-write, and write
them as one JSON file (method version 3: the option registers are read
without a write and kept in every record; method.html#log-2026-11-26-v3).

Usage: lab/tools/read-options.py BOARD OUT.json [--dry-run]
  BOARD     nrf5340 | stm32g0b1 | stm32g474 | stm32h723 | samd20 | rp2350
  OUT.json  written: schema board-options/1, the board, the time, the
            probe-rs version, and per region its address, its words and the
            manual section it comes from
  --dry-run print the probe-rs commands, touch no board

Only `probe-rs read` is run: no write, no reset, no erase. The board's lock
(~/vl-dev/<lab name>.lock, as the runners) is taken unless VL_BOARD_LOCKED=1
(the queue's worker holds it). The SAM D20 is read through the OpenOCD
stand-in the runners use (firmware/common/samd20/bin). A read that fails is
written as an error and the program exits 1: a series must not start on a
board whose option registers could not be read.
"""
import datetime
import fcntl
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CHIP = {"nrf5340": "nRF5340_xxAA_APPONLY", "stm32g0b1": "STM32G0B1RE", "stm32g474": "STM32G474RE",
        "stm32h723": "STM32H723ZG", "samd20": "ATSAMD20J18A", "rp2350": "RP235x"}   # as run-one.py
# per board: (name, address, words, source)
REGIONS = {
    "stm32g474": [("FLASH_OPTR", 0x40022020, 1, "RM0440 §3.7.8, offset 0x20")],
    "stm32g0b1": [("FLASH_OPTR", 0x40022020, 1, "RM0444 §3.7.8, offset 0x020")],
    "stm32h723": [("FLASH_OPTSR_CUR", 0x5200201C, 1, "RM0468 §4.9, offset 0x01C"),
                  ("FLASH_OPTSR2_CUR", 0x52002070, 1, "RM0468 §4.9.24, offset 0x070 (CPUFREQ_BOOST)")],
    "nrf5340": [("UICR.APPROTECT", 0x00FF8000, 1, "nRF5340 PS v1.6, UICR; §8.2"),
                ("UICR.SECUREAPPROTECT", 0x00FF801C, 1, "nRF5340 PS v1.6, UICR; §8.2")],
    "samd20": [("NVM User Row", 0x00804000, 2, "DS60001504K §9.4: the NVM User Row, read at 0x804000")],
    # the rows of the second CRC series' check: CRIT0 copies, page 1 (boot configuration), the boot keys, the lock words
    "rp2350": [("OTP raw rows 0x038-0x03f", 0x40134000 + 0x038 * 4, 8, "RP2350 datasheet §13.4, §13.10 (OTP_DATA_RAW)"),
               ("OTP raw rows 0x040-0x07f", 0x40134000 + 0x040 * 4, 64, "RP2350 datasheet §13.10, page 1"),
               ("OTP raw rows 0x080-0x0bf", 0x40134000 + 0x080 * 4, 64, "RP2350 datasheet §13.10, boot keys"),
               ("OTP raw rows 0xf80-0xfff", 0x40134000 + 0xf80 * 4, 128, "RP2350 datasheet §13.5, lock words")],
}


def lab_board(board):
    """(the board's name in the lab, its probe) from lab/boards.conf, as run-one.py"""
    for ln in open(os.path.join(ROOT, "lab/boards.conf")):
        f = ln.split("#")[0].split()
        if len(f) >= 6 and f[5] == board:
            return f[0], f"{f[3]}:{f[4]}"
    return None, None


def parse_words(out, count):
    """The words of `probe-rs read ... b32 ADDR N`: lines 'ADDR: w w w ...'."""
    words = []
    for ln in out.splitlines():
        m = re.match(r"\s*(?:0x)?[0-9a-fA-F]+:\s+(.*)$", ln)
        if m:
            words += [int(w, 16) for w in m.group(1).split()]
    if len(words) != count:
        raise ValueError(f"{len(words)} words read, {count} asked for")
    return words


def main():
    a = [x for x in sys.argv[1:] if x != "--dry-run"]
    dry = "--dry-run" in sys.argv
    if len(a) != 2 or a[0] not in REGIONS:
        sys.exit(__doc__)
    board, out = a
    lab_name, lab_probe = lab_board(board)
    pr = ["--chip", CHIP[board]] + (["--probe", os.environ.get("PROBE") or lab_probe] if (os.environ.get("PROBE") or lab_probe) else [])
    env = dict(os.environ)
    if board == "samd20":
        env["PATH"] = os.path.join(ROOT, "firmware/common/samd20/bin") + os.pathsep + env["PATH"]
    cmds = [(n, addr, cnt, src, ["probe-rs", "read"] + pr + ["b32", f"{addr:#x}", str(cnt)]) for n, addr, cnt, src in REGIONS[board]]
    if dry:
        for c in cmds:
            print(" ".join(c[4]))
        return 0
    lock = None
    if lab_name and os.environ.get("VL_BOARD_LOCKED") != "1":
        lock = open(os.path.expanduser(f"~/vl-dev/{lab_name}.lock"), "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            sys.exit(f"{board}: busy ({lock.name} is held by another run)")
    version = subprocess.run(["probe-rs", "--version"], capture_output=True, text=True, env=env).stdout.strip()
    res, ok = [], True
    for n, addr, cnt, src, cmd in cmds:
        entry = {"name": n, "address": f"{addr:#010x}", "source": src}
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
            text = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr)
            if r.returncode != 0:
                raise ValueError(text.strip()[-300:])
            entry["words"] = [f"{w:#010x}" for w in parse_words(r.stdout, cnt)]
        except (ValueError, subprocess.TimeoutExpired) as e:
            entry["error"] = str(e)
            ok = False
        res.append(entry)
    doc = {"schema": "board-options/1", "board": board, "chip": CHIP[board],
           "time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "probe_rs": version, "regions": res}
    with open(out, "w") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print(f"{board}: {len(res)} regions {'read' if ok else 'NOT all read'} -> {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
