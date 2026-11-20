#!/usr/bin/env python3
"""One library per reset, driven over the board's serial port (the stress
tests' run.sh PER_LIB=1 on a board with common/<board>/board_uart.h:
nrf5340-rb-stress, and rb-mp-stress since 2026-11-17; the firmware side is
common/vls_uart.h).

Usage: uart_host.py TTY NLIBS NWORDS LIMIT_S OUTDIR RESET FIRMWARE -- PROBE-RS-ARGS...
  RESET: "probe" (probe-rs reset) or "aircr" (system reset through the
  core's AIRCR, for the RP2350, where probe-rs reset can hang)
  FIRMWARE: the firmware, flashed here with the serial port already open,
  so the "VLS ready" of the first start is not missed (no reset needed):
  an ELF (every library in one image), or build/bundle.json (one image per
  library, ../common/bundle.py): the libraries then run bundle by bundle,
  each bundle flashed before its libraries (see flash_bundle)

The firmware (main.c, HAVE_UART; common/vls_uart.h) says "VLS ready N" after a reset with no
selection and waits about a second for "run <n>"; it then resets itself,
says "VLS start <n>" and waits about a second for the run parameters, "go
name=value ..." (VLS_GO, built by run.sh; without it the firmware's build
defaults), answers "VLS go" with all of them (checked here against the ones
sent; OUTDIR/go.txt keeps the answer), runs library n with the serial port
silent and says "VLS done <n>", and waits for the next command. The debug port is touched
only while no library runs: the reset at the start, and a reset if a library
does not say "done" within LIMIT_S (it is then listed as unfinished; its
block is read over the debug port). After "done" the result block comes over
the serial port ("dump", with a CRC-32; OUTDIR/words_<n>.txt), over the
debug port only if three dumps fail (VLS_DUMP=0: always over the debug
port; run.sh UART_DUMP). VLS_SWD_CHECK=1: also read it over the
debug port and stop (exit 2) if the two differ. VLS_DUMP2=1: after it the
firmware's second block too ("dump2"; OUTDIR/dump2_<n>.txt, serial port only).
Flashing uses probe-rs --preverify: an image that is already on the board
is not written again (one image serves every mode since 2026-11-15; with a
bundle only the images that changed are written, see flash_bundle).
Prints a JSON list of the unfinished libraries on stdout. Exit 2 on a probe
or serial failure.
"""
import json
import os
import struct
import subprocess
import sys
import time
import zlib

import serial

STATE_DIR = os.path.expanduser("~/.cache/verified-libs/flash")


def fail(msg):
    print(f"probe failure: {msg}", file=sys.stderr)
    sys.exit(2)


def main():
    a = sys.argv[1:]
    sep = a.index("--")
    tty, nlibs, nwords, limit, outdir, reset, fw = a[:sep]
    pr = a[sep + 1:]
    nlibs, nwords, limit = int(nlibs), int(nwords), float(limit)
    s = serial.Serial(tty, 115200, timeout=0.2)

    def line(until):
        while time.time() < until:
            b = s.readline()
            if b:
                return b.decode(errors="replace").strip()
        return None

    debug = os.environ.get("VLS_DEBUG") == "1"
    t_start = time.time()

    def dbg(msg):
        # VLS_DEBUG=1: every line from the board and every wait, timed
        if debug:
            print(f"[{time.time() - t_start:7.2f}] {msg}", file=sys.stderr, flush=True)

    def wait_for(prefix, secs):
        until = time.time() + secs
        dbg(f"wait {prefix!r} {secs} s")
        while True:
            ln = line(until)
            if ln is None:
                dbg(f"no {prefix!r}")
                return None
            dbg(f"<< {ln[:80]!r}")
            if ln.strip("\x00").startswith(prefix):
                return ln

    def probe(cmd, *args, timeout=60):
        dbg(f"probe-rs {cmd} {' '.join(args)}")
        # probe arguments before the command's own: the SAM D20's OpenOCD
        # stand-in takes the address and count of "read" from the end
        return subprocess.run(["probe-rs", cmd, *pr, *args], capture_output=True, text=True, timeout=timeout)

    def download(elf, *extra):
        dbg(f"download {elf} {' '.join(extra)}")
        try:
            # the firmware file last: the SAM D20's OpenOCD stand-in takes the last argument
            r = subprocess.run(["probe-rs", "download", *pr, "--allow-erase-all", "--preverify", *extra, elf],
                               capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            fail(f"flashing {elf} failed (time limit)")
        if r.returncode != 0:
            fail(f"flashing {elf} failed")

    bundle = json.load(open(fw)) if fw.endswith(".json") else None
    # paths in bundle.json are relative to the firmware directory it was
    # built in (DIR/build/bundle.json): a combined bundle (bundle.py --with)
    # is used from the other firmware's directory too
    bdir = os.path.dirname(os.path.dirname(os.path.abspath(fw)))

    def bpath(p):
        return os.path.join(bdir, p)
    state = os.path.join(STATE_DIR, zlib.crc32(" ".join(pr).encode()).to_bytes(4, "big").hex() + ".json")
    cur = {"k": 0}

    def flash_bundle(k):
        # Flash wears out (10k erase cycles on most of these chips), so
        # write only what changed. The state file (per probe) remembers what
        # the board holds: the bundle and the image in each slot. Same
        # bundle: one --preverify download of the whole bundle, which writes
        # nothing if the board still holds it (and everything if something
        # else was flashed meanwhile). Otherwise, when at most half of the
        # slots changed (a new build during development): the stub and each
        # changed image on its own with --preverify, so only their flash
        # sectors are erased (--restore-unwritten keeps the rest of a sector,
        # which on the H723 is 128 KB); then the whole bundle as the check
        # (it writes only if something still differs). More changed (the
        # SAM D20's other bundle, or an unknown board): the whole bundle.
        b = bundle["bundles"][k]
        try:
            st = json.load(open(state))
        except (OSError, ValueError):
            st = {}
        slots = {bundle["libs"][str(l)]["base"]: bundle["libs"][str(l)]["image_sha256"] for l in b["libs"]}
        s.reset_input_buffer()
        if st.get("sha256") != b["sha256"]:
            old = st.get("slots") or {}
            changed = [l for l in b["libs"] if old.get(bundle["libs"][str(l)]["base"]) != slots[bundle["libs"][str(l)]["base"]]]
            try:
                os.remove(state)   # unknown until the bundle is confirmed
            except OSError:
                pass
            if old and len(changed) * 2 <= len(b["libs"]):
                if st.get("boot_sha256") != b["boot_sha256"]:
                    download(bpath(b["boot_elf"]), "--restore-unwritten")
                for l in changed:
                    download(bpath(bundle["libs"][str(l)]["elf"]), "--restore-unwritten")
                print(f"bundle {k}: {len(changed)} of {len(b['libs'])} images written", file=sys.stderr)
        download(bpath(b["elf"]))
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(state, "w") as fh:
            json.dump({"sha256": b["sha256"], "boot_sha256": b["boot_sha256"], "slots": slots,
                       "elf": bpath(b["elf"]), "time": time.time()}, fh)
        cur["k"] = k

    def flash():
        if bundle is None:
            s.reset_input_buffer()
            try:
                os.remove(state)   # the board no longer holds a bundle
            except OSError:
                pass
            download(fw)
        else:
            flash_bundle(cur["k"])

    def hard_reset():
        s.reset_input_buffer()
        for _ in range(3):
            try:
                if reset == "aircr":
                    probe("write", "b32", "0xE000ED0C", "0x05FA0004", timeout=20)
                    return
                if probe("reset").returncode == 0:
                    return
            except subprocess.TimeoutExpired:
                pass
            time.sleep(3)
        fail("reset failed")

    def read_block(l):
        for _ in range(3):
            try:
                r = probe("read", "b32", "0x20000000", str(nwords))
            except subprocess.TimeoutExpired:
                continue
            if r.returncode == 0:
                words = [w for ln in r.stdout.splitlines() if ":" in ln for w in ln.split(":", 1)[1].split()]
                if len(words) == nwords:
                    with open(f"{outdir}/words_{l}.txt", "w") as fh:
                        fh.write("\n".join(words) + "\n")
                    return
            time.sleep(2)
        fail(f"reading the results of library {l} failed")

    def save(l, words):
        with open(f"{outdir}/words_{l}.txt", "w") as fh:
            fh.write("".join(f"{w:08x}\n" for w in words))

    def dump(cmd=b"dump", keep=nwords):
        # the block over the serial port ("dump", main.c uart_dump); None if
        # it did not come complete with a matching CRC. "dump2": the
        # firmware's second block (VLS_DUMP2), all of it (keep None).
        s.reset_input_buffer()
        s.write(cmd + b"\n")
        if not wait_for("VLS words", 10):
            return None
        words, until = [], time.time() + 30
        while True:
            ln = line(until)
            if ln is None:
                return None
            ln = ln.strip("\x00")
            if ln.startswith("VLS crc "):
                break
            try:
                words += [int(x, 16) for x in ln.split()]
            except ValueError:
                return None
        try:
            crc = int(ln.split()[2], 16)
        except (IndexError, ValueError):
            return None
        # the whole struct results; the CRC over all of it, the first NWORDS
        # (what decode.py reads, as over the debug port) kept
        if len(words) < (keep or 0) or zlib.crc32(struct.pack(f"<{len(words)}I", *words)) != crc:
            return None
        return words[:keep] if keep else words

    use_dump = os.environ.get("VLS_DUMP", "1") == "1"

    def fetch(l):
        # after "done": the block over the serial port (three tries), else
        # over the debug port. VLS_SWD_CHECK=1: read it over the debug port
        # too and stop if the two differ (the block does not change while
        # the firmware waits for commands). VLS_DUMP=0: debug port only.
        if not use_dump:
            read_block(l)
            return
        for _ in range(3):
            words = dump()
            if words is not None:
                break
        else:
            print(f"library {l}: no valid dump over the serial port, read over the debug port", file=sys.stderr)
            read_block(l)
            return
        save(l, words)
        if os.environ.get("VLS_DUMP2") == "1":
            # the second block (rb-mp-stress COVERAGE builds: the coverage
            # table) into OUTDIR/dump2_<n>.txt; serial port only, a warning
            # if it does not come
            for _ in range(3):
                w2 = dump(b"dump2", None)
                if w2 is not None:
                    with open(f"{outdir}/dump2_{l}.txt", "w") as fh:
                        fh.write("".join(f"{w:08x}\n" for w in w2))
                    break
            else:
                print(f"library {l}: no valid dump2 over the serial port", file=sys.stderr)
        if os.environ.get("VLS_SWD_CHECK") == "1":
            read_block(l)
            swd = [int(x, 16) for x in open(f"{outdir}/words_{l}.txt").read().split()]
            if swd != words:
                diff = [i for i in range(nwords) if swd[i] != words[i]]
                fail(f"library {l}: serial dump and debug-port read differ at words {diff[:8]}")

    def ready():
        # after a reset: "VLS ready" (no selection); a probe-rs reset can leave
        # some cores halted until the next debug access, so poke once if quiet
        if wait_for("VLS ready", 8):
            return True
        try:
            probe("read", "b32", "0x20000000", "1", timeout=20)
        except subprocess.TimeoutExpired:
            pass
        return wait_for("VLS ready", 8) is not None

    def recover(what):
        # a reset through the debug port; if the board still does not answer
        # (an RP2350 probe-rs reset can hang), flash it again as a last resort
        hard_reset()
        if ready():
            return
        flash()
        if not ready():
            fail(f"no 'VLS ready' {what}")

    go = os.environ.get("VLS_GO", "").strip()
    try:
        sent = {k: int(v, 0) for k, v in (t.split("=", 1) for t in go.split()[1:])}
    except ValueError:
        fail(f"VLS_GO is not 'go name=value ...': {go!r}")
    if go and go.split()[0] != "go":
        fail(f"VLS_GO is not 'go name=value ...': {go!r}")

    kick = {"needed": False}
    # VLS_SEL_BASE: the selection index of library l is base + l (the
    # firmware's VLS_SEL_BASE, bundle.py --index-base; rb-mp-stress: 64)
    sel_base = int(os.environ.get("VLS_SEL_BASE", "0"))

    def select_by_debug_port(g):
        # The image running does not take "run g" (an image of another
        # firmware in the same bundle, whose range ends below g, e.g. the
        # ISR test's): the selection words written over the debug port, then
        # a reset through it. Only between libraries, never while one runs.
        if bundle is None:
            fail(f"selection {g}: the firmware does not take it and there is no bundle.json")
        a = int(bundle["select_addr"], 16)

        def write(*args):
            # three tries: a probe-rs call can hang (2026-11-17, nRF5340's
            # J-Link, 30 s)
            for _ in range(3):
                try:
                    if probe("write", "b32", *args, timeout=30).returncode == 0:
                        return True
                except subprocess.TimeoutExpired:
                    pass
                time.sleep(2)
            return False
        if not write(f"{a:#x}", "0x564C5345", str(g), f"{~g & 0xFFFFFFFF:#x}", "0"):
            fail(f"writing selection {g} over the debug port failed")
        if 0x20000000 <= a < 0x40000000:
            # STM32H7: the RAM ECC write buffer loses the last words written
            # before a reset, debug-port writes too (2026-11-17: the stub then
            # never saw the selection; with these writes 3 of 3 started):
            # four more words just below the selection (the top of the stack,
            # unused before the reset), then a read. Not on the RP2350, whose
            # selection is in the watchdog's registers.
            if not write(f"{a - 16:#x}", "0", "0", "0", "0"):
                fail(f"writing selection {g} over the debug port failed")
            try:
                probe("read", "b32", f"{a - 16:#x}", "8", timeout=30)
            except subprocess.TimeoutExpired:
                pass
        dbg(f"selection {g} written at {a:#x}")
        hard_reset()

    def start(l):
        # "run <n>", then the run parameters after "VLS start <n>"; True if
        # the firmware confirmed them, False if it did not answer
        g = sel_base + l
        s.write(f"run {g}\n".encode())
        ans = wait_for((f"VLS start {g}", "VLS error bad library"), 0.5 if kick["needed"] else 3)
        if ans is not None and ans.strip("\x00").startswith("VLS error bad library"):
            select_by_debug_port(g)
            ans = wait_for(f"VLS start {g}", 15)
            if ans is None:
                return False
        if ans is None:
            # The firmware resets itself after "run" (main.c select_and_reset).
            # The SAM D20 with EDBG firmware 3.25 (2026-11-15) then stays in
            # reset until the next debug access (the DSU's CPU reset extension:
            # the EDBG holds SWCLK low between sessions; with 1.0f it did
            # not): a reset through the debug port, which keeps the selection
            # in RAM, starts the selected library.
            # once seen, the next libraries get the reset after 0.5 s
            kick["needed"] = True
            hard_reset()
            if not wait_for(f"VLS start {g}", 15):
                return False
        if go:
            # in pieces of 16 bytes: the SAM D20's EDBG loses a longer line
            # written at once (2026-11-15: the 130-byte line never arrived
            # whole, in 16-byte pieces 5 ms apart it did, 2 of 2 each)
            # (VLS_GO_CHUNK: piece size, 0 = the whole line at once; for
            # testing a probe's serial port)
            data = (go + "\n").encode()
            n = int(os.environ.get("VLS_GO_CHUNK", "16")) or len(data)
            for i in range(0, len(data), n):
                s.write(data[i:i + n])
                s.flush()
                time.sleep(0.005)
        ans = wait_for(("VLS go", "VLS error"), 10)
        if ans is None:
            return False
        # a rejection, a garbled answer or other values than sent (a byte lost
        # on the line): False, so the caller resets (which also stops a
        # library started with wrong values) and tries once more
        ans = ans.strip("\x00")
        if ans.startswith("VLS error"):
            print(f"library {l}: the firmware did not take the run parameters ({ans}; sent {go!r})", file=sys.stderr)
            return False
        try:
            got = {k: int(v, 16) for k, v in (t.split("=", 1) for t in ans.split()[2:])}
        except ValueError:
            return False
        bad = {k: (v, got.get(k)) for k, v in sent.items() if got.get(k) != v}
        if bad:
            print(f"library {l}: run parameters sent and confirmed differ: {bad}", file=sys.stderr)
            return False
        with open(f"{outdir}/go.txt", "w") as fh:
            fh.write(ans + "\n")
        return True

    unfinished = []

    def flashed():
        # after flashing: wait for "VLS ready"
        flash()
    # The RP2350 stays halted for about a minute after probe-rs download
    # (seen 2026-11-14); the other boards say "ready" within about a second.
    # When --preverify skipped the flashing, the board was not reset: the
    # image of the last run still waits for commands after its "done", so
    # "reset" over the serial port restarts it at once (instead of 90 s).
        if not wait_for("VLS ready", 5):
            s.write(b"reset\n")
            # (SAM D20: the reset needs a debug access, see start())
            if not wait_for("VLS ready", 5 if reset == "probe" else 85):
                hard_reset()
                if not wait_for("VLS ready", 85) and not ready():
                    recover(f"on {tty} after flashing")
    # VLS_LIBS (run.sh LIBS): only these libraries, e.g. "11,35,40"
    only = os.environ.get("VLS_LIBS", "").strip()
    todo = [int(x) for x in only.split(",")] if only else list(range(nlibs))
    if any(not 0 <= l < nlibs for l in todo):
        fail(f"VLS_LIBS {only!r}: not all in 0..{nlibs - 1}")
    if bundle is not None:
        if any(str(sel_base + l) not in bundle["libs"] for l in todo):
            fail(f"libraries {[l for l in todo if str(sel_base + l) not in bundle['libs']]} are not in {fw}")
        # bundle by bundle, starting with the one on the board if it is needed
        need = sorted({bundle["libs"][str(sel_base + l)]["bundle"] for l in todo})
        try:
            last = json.load(open(state)).get("sha256")
        except (OSError, ValueError):
            last = None
        need.sort(key=lambda k: bundle["bundles"][k]["sha256"] != last)
        todo = [l for k in need for l in todo if bundle["libs"][str(sel_base + l)]["bundle"] == k]
    for i, l in enumerate(todo):
        k = bundle["libs"][str(sel_base + l)]["bundle"] if bundle is not None else 0
        if i == 0 or k != cur["k"]:
            cur["k"] = k
            flashed()
        t0 = time.time()
        if not start(l):
            # once more from a clean reset
            recover(f"before library {l}")
            if not start(l):
                fail(f"library {l} did not start")
        done = wait_for(f"VLS done {sel_base + l}", limit)
        if done:
            fetch(l)
        else:
            read_block(l)   # whatever the library got to, over the debug port
        if done:
            print(f"library {l}: {time.time() - t0:.0f} s", file=sys.stderr)
        else:
            unfinished.append(l)
            print(f"library {l} did not finish in {limit:.0f} s", file=sys.stderr)
            recover(f"after library {l}")
    print(json.dumps(unfinished))


if __name__ == "__main__":
    main()
