#!/usr/bin/env python3
"""A test of run-isr.py and isrrecords.py without a board: a stand-in for
probe-rs (written into a temporary directory and put first on PATH) answers
the runner's calls as a board would. verify says the bundle is on the board,
write keeps the words written, reset does nothing, and read gives a result
block (decode.py's layout) for the image and run number of the last
selection: done, every control caught, nothing seen for the others, a few
coverage bits. Then:
  - the runner writes one run file per image of the bundle, writes no flash
    (no --flash), and says every verdict is as expected;
  - the record writer makes one record per image, with option registers and
    coverage, in the plan's classes (no verdict word for a library outside
    its documentation);
  - and refuses: a run directory without options.json; a build of a tree
    with uncommitted changes; a board whose control was not caught (no
    record of that board at all);
  - the progress watch (VL_TEST_MODES per configuration): a run whose done
    comes late is judged; a slow run whose trial counter moves at every
    look is not stopped; a run whose counter stands still with a fault in
    the core is stopped, started once more, read without a write (fault
    registers, phase, the exception frame on the stack, named from nm.txt)
    and judged with the host check's crash text, the place, and "cache on
    not run"; a stall without a fault says "a call did not return".
Needs the built bundle of BOARD (bash onebuild.sh BOARD) and, for the
coverage, arm-none-eabi-objdump: run it in the toolchain image
(bash run.sh test-runner, or python3 -I test_runner.py [BOARD]).
Exit 0: as expected.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode   # noqa: E402

BOARD = sys.argv[1] if len(sys.argv) > 1 else "stm32g474"
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
sys.path.insert(0, os.environ["VL_TEST_HERE"])
import decode
st_path = os.environ["VL_TEST_STATE"]
st = json.load(open(st_path)) if os.path.exists(st_path) else {"mem": {}, "calls": []}
a = sys.argv[1:]
st["calls"].append(a[0] if a else "")
def save():
    json.dump(st, open(st_path, "w"))
if a == ["--version"]:
    print("probe-rs 0.32.0 (test stand-in)"); save(); sys.exit(0)
op = a[0]
rest, i = [], 1
while i < len(a):
    if a[i] in ("--chip", "--probe"):
        i += 2
    elif a[i].startswith("--"):
        i += 1
    else:
        rest.append(a[i]); i += 1
if op == "verify":
    print("Verification successful"); save(); sys.exit(0)
if op == "download":
    st["download"] = st.get("download", 0) + 1; save(); sys.exit(0)
if op == "reset":
    st["looks"] = 0
    save(); sys.exit(0)
if op == "write":
    addr = int(rest[1], 16)
    for k, w in enumerate(rest[2:]):
        st["mem"][str(addr + 4 * k)] = int(w, 16)
    save(); sys.exit(0)
if op == "read":
    addr, n = int(rest[1], 16), int(rest[2])
    sel = int(os.environ["VL_TEST_SEL"], 16)
    res_addr = int(os.environ["VL_TEST_RES"], 16)
    base, nonce = st["mem"].get(str(sel + 4), 0), st["mem"].get(str(sel + 12), 0)
    imgs = json.load(open(os.environ["VL_TEST_MAN"]))["images"]
    im = next(i for i in imgs if int(i["base"], 16) == base)
    adapter = im["adapter"]
    mode = json.loads(os.environ.get("VL_TEST_MODES", "{}")).get(adapter, "done")
    texts, cr, rs = decode.layout()
    per = sum(k for _, k, _ in cr)
    d = os.path.join(os.environ["VL_TEST_BUILD"], "img", adapter)
    nm = [ln.split(" ", 3) for ln in open(os.path.join(d, "nm.txt")).read().splitlines()]
    code = [x for x in nm if len(x) == 4 and x[2] in "Tt" and int(x[1], 16) >= 8]
    sp0 = int.from_bytes(open(os.path.join(d, "fw.bin"), "rb").read(4), "little")
    looks = st.get("looks", 0)
    if addr == res_addr and n == 8 + 2 * per:
        st["looks"] = looks = looks + 1
    if addr == res_addr:
        bad = decode.CLASS[adapter] == "control" and adapter != os.environ.get("VL_TEST_UNCAUGHT")
        if mode == "late":
            done, t0 = int(looks >= 4), 100 * looks
        elif mode == "slow":
            done, t0 = int(looks >= 12), looks
        elif mode.startswith("stall"):
            done, t0 = 0, 4000 + 10 * min(looks, 2)
        else:
            done, t0 = 1, 100
        w = []
        for name, k, t in rs:
            if t == "struct cache_res":
                for cache in range(k):
                    run_on = cache == 0 or not mode.startswith("stall")
                    for fn, fk, _ in cr:
                        if fn == "faults":
                            v = [0] * fk
                            if bad:
                                v[6] = 3
                            w += v
                        else:
                            w.append({"trials": t0, "inside": 60, "before": 20, "after": 20, "lat_min": 14, "lat_max": 30,
                                      "lat_n": 60, "first_fault": 6 if bad else 0}.get(fn, 0) if run_on else 0)
            elif k == 1:
                w.append({"magic": 0x564C4931, "version": 1, "done": done, "clock_hz": 170000000, "board_id": 3,
                          "image_base": base, "nonce": nonce}.get(name, 0))
            elif name == "cov":
                w += [0x5] + [0] * (k - 1)
            else:
                w += {"cal_lat_min": [12, 12], "cal_lat_n": [50, 50]}.get(name, [0] * k)
        w = w[:n]
    elif addr == 0xE000ED04:
        w = [0x803 if mode == "stall" else 0]
    elif addr == 0xE000ED28:
        w = [0x8200, 0x40000000, 0, 0xC6C5C4C3, 0xC6C5C4C3]
    elif addr == sp0 - 4 * n:
        w = [0] * n
        pc, lr = int(code[0][0], 16) + 2, int(code[1][0], 16) + 3
        w[-60:-52] = [32, 32, 3, 0x20001628, 0, lr, pc & ~1, 0x21000000]
        w[-200:-192] = [0, 0, 0, 0, 0, lr, pc & ~1, 0x0100000F]   # a stale frame deeper in the stack
    else:
        vals = {x[3]: v for x in nm if len(x) == 4 for v in [{"phase": 2, "fired": 1, "fired_phase": 1}.get(x[3])] if v is not None}
        w = [next((v for x in nm if len(x) == 4 and int(x[0], 16) == addr for v in [vals.get(x[3])] if v is not None), 0)] * n
    for i in range(0, n, 4):
        print(f"{addr + 4 * i:08x}: " + " ".join(f"{x:08x}" for x in w[i:i + 4]))
    save(); sys.exit(0)
print("unknown call", a, file=sys.stderr); save(); sys.exit(1)
'''

fails = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


def run(cmd, env):
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


src = os.path.join(HERE, "build", "v1", BOARD)
if not os.path.exists(os.path.join(src, "bundle300.json")):
    sys.exit(f"no bundle of {BOARD}: bash onebuild.sh {BOARD} first")
with tempfile.TemporaryDirectory() as t:
    fake = os.path.join(t, "bin")
    os.makedirs(fake)
    with open(os.path.join(fake, "probe-rs"), "w") as fh:
        fh.write(FAKE)
    os.chmod(os.path.join(fake, "probe-rs"), 0o755)
    # a copy of the build, as of a committed tree
    b = os.path.join(t, "build")
    shutil.copytree(src, b, ignore=shutil.ignore_patterns("*.o", "*.elf", "*.map"))
    built = json.load(open(os.path.join(b, "build.json")))
    built["bench_commit"] = "0123456789ab"
    json.dump(built, open(os.path.join(b, "build.json"), "w"))
    man = json.load(open(os.path.join(b, "bundle300.json")))
    env = dict(os.environ, PATH=fake + os.pathsep + os.environ["PATH"], VL_TEST_HERE=HERE, VL_BOARD_LOCKED="1",
               VL_TEST_STATE=os.path.join(t, "state.json"), VL_TEST_SEL=man["select_addr"],
               VL_TEST_MAN=os.path.join(b, "bundle300.json"), VL_TEST_BUILD=b)
    opts = {"schema": "board-options/1", "board": BOARD, "time": "2026-11-27T00:00:00Z", "probe_rs": "test",
            "regions": [{"name": "FLASH_OPTR", "address": "0x40022020", "source": "test", "words": ["0xfbeff8aa"]}]}

    env["VL_TEST_RES"] = man["results_addr"]

    def runner(out, extra_env=None, extra=()):
        os.makedirs(out, exist_ok=True)
        json.dump(opts, open(os.path.join(out, "options.json"), "w"))
        return run([sys.executable, "-I", os.path.join(HERE, "run-isr.py"), BOARD, out, "--wait", "0.01", "--poll", "0.01",
                    "--grace", "0.5", "--from", b] + list(extra), dict(env, **(extra_env or {})))

    out = os.path.join(t, "runs")
    p = runner(out)
    files = sorted(f for f in os.listdir(out) if f.startswith("adapter_"))
    check(p.returncode == 0, f"run-isr.py exit 0 (got {p.returncode}: {p.stdout[-300:]}{p.stderr[-300:]})")
    check(len(files) == len(man["images"]), f"one run file per image ({len(files)} of {len(man['images'])})")
    st = json.load(open(env["VL_TEST_STATE"]))
    check("download" not in st, "no flash write without --flash")
    check("0 verdicts not as expected" in p.stdout, "every verdict as expected in run.log")
    rec_out = os.path.join(t, "records")
    q = run([sys.executable, "-I", os.path.join(HERE, "isrrecords.py"), "--out", rec_out, "--images", os.path.join(HERE, "build", "v1"), out], env)
    recs = sorted(os.listdir(os.path.join(rec_out, BOARD))) if os.path.isdir(os.path.join(rec_out, BOARD)) else []
    check(q.returncode == 0 and len(recs) == len(man["images"]), f"a record per image ({len(recs)}; {q.stdout[-300:]})")
    if recs:
        r = json.load(open(os.path.join(rec_out, BOARD, recs[0])))
        check(r["schema"] == "pools-isr/1" and r["option_registers"] and r["coverage"]["instructions"] > 0,
              "a record has its schema, option registers and coverage")
        outside = [json.load(open(os.path.join(rec_out, BOARD, f))) for f in recs]
        outside = [x for x in outside if x["class"] == "outside"]
        check(outside and all(not any(w in x["verdict"] for w in ("pass", "FAIL", "fail", "caught", "fault")) for x in outside),
              "no verdict word for a library outside its documentation")
    # refusals
    os.remove(os.path.join(out, "options.json"))
    q = run([sys.executable, "-I", os.path.join(HERE, "isrrecords.py"), "--check", out], env)
    check(q.returncode == 1 and "options.json" in q.stdout, "refused: a run directory without options.json")
    built["bench_commit"] = "0123456789ab+dirty"
    json.dump(built, open(os.path.join(b, "build.json"), "w"))
    out2 = os.path.join(t, "runs-dirty")
    runner(out2)
    q = run([sys.executable, "-I", os.path.join(HERE, "isrrecords.py"), "--check", out2], env)
    check(q.returncode == 1 and "cannot be rebuilt" in q.stdout and "0 records" in q.stdout, "refused: a build of a dirty tree")
    built["bench_commit"] = "0123456789ab"
    json.dump(built, open(os.path.join(b, "build.json"), "w"))
    out3 = os.path.join(t, "runs-uncaught")
    p = runner(out3, {"VL_TEST_UNCAUGHT": "adapter_broken_isr_free"})
    check("NOT AS EXPECTED" in p.stdout, "the runner says so when a control is not caught")
    q = run([sys.executable, "-I", os.path.join(HERE, "isrrecords.py"), "--check", "--images", os.path.join(HERE, "build", "v1"), out3], env)
    check(q.returncode == 1 and "0 records" in q.stdout and "not caught" in q.stdout, "refused: no record of a board whose control was not caught")
    # the progress watch
    modes = {"adapter_etl": "stall", "adapter_contiki": "stall_nofault", "adapter_lwip": "slow", "adapter_ref_primask": "late"}
    out4 = os.path.join(t, "runs-watch")
    p = runner(out4, {"VL_TEST_MODES": json.dumps(modes)}, ["--adapter", ",".join(modes)])
    got = {a: json.load(open(os.path.join(out4, a + ".json"))) for a in modes if os.path.exists(os.path.join(out4, a + ".json"))}
    check(len(got) == 4, f"a run file for each of the four watched runs ({sorted(got)}; {p.stdout[-400:]})")
    if len(got) == 4:
        check(got["adapter_ref_primask"]["verdict"] == "pass" and "stopped" not in got["adapter_ref_primask"]["result"],
              "done set late: judged, not stopped")
        check(got["adapter_lwip"]["verdict"] == "pass" and "stopped" not in got["adapter_lwip"]["result"]
              and got["adapter_lwip"]["result"]["c"][0]["trials"] >= 12, "slow but moving: not stopped, judged when done")
        e = got["adapter_etl"]
        st_ = e["result"].get("stopped", {})
        v = e["verdict"]
        arm6 = BOARD in ("stm32g0b1", "samd20")
        check(v.startswith("outside its documentation; observed in 1 of ") and "the program crashed" in v
              and "the sweep stopped at trial 4021 with the cache off, in the check after the trial" in v
              and ("a HardFault" if arm6 else "a bus fault at 0xc6c5c4c3") in v and "cache on not run" in v, f"a stall with a fault: {v}")
        check(not any(x in v for x in ("pass", "FAIL", "fail", "caught")), "no verdict word for a library outside its documentation, stopped")
        check(len(st_.get("starts", [])) == 2 and st_["starts"][0]["trials"] == st_["starts"][1]["trials"] == 4020,
              f"started once more, the same trial number both times ({st_.get('starts')})")
        check(st_.get("pc_symbol") and st_.get("pc_symbol") in v and st_.get("frames") and len(st_["frames"]) == 2
              and st_.get("pc") == st_["frames"][-1]["pc"], f"the frame at the handler's SP, named from nm.txt ({st_.get('pc_symbol')})")
        check(("cfsr" not in st_) if arm6 else st_.get("bfar") == "0xc6c5c4c3", "the fault registers (none on the Cortex-M0+)")
        c = got["adapter_contiki"]["verdict"]
        check(c.startswith("outside its documentation; observed in 1 of ") and "a call did not return" in c and "no fault" in c,
              f"a stall without a fault: {c}")
    check("2 stopped before done" in p.stdout, "run.log counts the stopped runs")
print(f"{len(fails)} failed")
sys.exit(1 if fails else 0)
