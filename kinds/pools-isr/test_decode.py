#!/usr/bin/env python3
"""A test of decode.py without a board: the layout it reads from main.c and
verdict.h has the size of the `results` symbol in every built image
(build/v1/<board>/img/*/nm.txt, after `bash onebuild.sh`), a synthetic block
decodes to the fields put in, and the verdict follows the classes (a control
with faults is caught, without is not; a configuration within its
documentation with faults fails; one outside its documentation gets no
verdict word, only what was observed).

Usage: python3 -I test_decode.py      exit 0: as expected
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode   # noqa: E402

fails = []
n = decode.words_needed()
sizes = {}
for nm in sorted(glob.glob(os.path.join(HERE, "build", "v1", "*", "img", "*", "nm.txt"))):
    for ln in open(nm):
        f = ln.split()
        if len(f) == 4 and f[3] == "results":
            sizes["/".join(nm.split(os.sep)[-4:-1])] = int(f[1], 16)
if not sizes:
    fails.append("no built image (bash onebuild.sh first)")
for b, s in sorted(sizes.items()):
    if s != 4 * n:
        fails.append(f"{b}: results is {s} bytes, decode.py reads {4 * n}")
texts, cr, rs = decode.layout()
per = sum(k for _, k, _ in cr)


def block(faults_off=(), faults_on=(), inside=10, done=1):
    w = []
    for name, k, t in rs:
        if t == "struct cache_res":
            for cache in range(k):
                c = []
                for fn, fk, _ in cr:
                    if fn == "faults":
                        v = [0] * fk
                        for code in (faults_off if cache == 0 else faults_on):
                            v[code] += 1
                        c += v
                    elif fn == "inside":
                        c.append(inside)
                    elif fn == "first_fault":
                        fl = faults_off if cache == 0 else faults_on
                        c.append(fl[0] if fl else 0)
                    elif fn == "first_case":
                        c.append(16 << 16 | 1 << 8 | 2 << 4 | 3)
                    elif fn in ("lat_min", "lat_max"):
                        c.append(14 if fn == "lat_min" else 40 + cache)
                    elif fn == "lat_n":
                        c.append(5)
                    else:
                        c.append(0)
                assert len(c) == per
                w += c
        else:
            w += [{"magic": 0x564C4931, "done": done}.get(name, 0)] if k == 1 else \
                ([10, 12] if name == "cal_lat_min" else [5, 5] if name == "cal_lat_n" else [0] * k)
    assert len(w) == n
    return w


configs = ["adapter_ref", "adapter_broken_isr_alloc", "adapter_broken_isr_free", "adapter_ref_primask", "adapter_etl",
           "adapter_riot", "adapter_threadx", "adapter_cmsis_rtx", "adapter_contiki", "adapter_c_allocator", "adapter_lwip",
           "adapter_memorypool", "adapter_atomic_pool", "adapter_heapless"]
cases = [(0, (6,), (), "caught"), (0, (), (), "NOT CAUGHT"), (3, (), (), "pass"), (6, (), (13,), "FAIL"),
         (4, (6, 6), (), f"outside its documentation; observed in 2 of 0 trials: {texts[6]}"),
         (5, (), (), "outside its documentation; nothing observed in 0 trials")]
for cfg, fo, fn_, want in cases:
    rec = decode.decode(block(fo, fn_), configs[cfg])
    got = decode.judge(rec)
    if got != want:
        fails.append(f"{configs[cfg]} faults {fo}/{fn_}: verdict {got!r}, want {want!r}")
    if decode.CLASS[configs[cfg]] == "outside" and any(w in got for w in ("FAIL", "fail", "pass", "caught", "fault")):
        fails.append(f"{configs[cfg]}: a verdict word for a row outside its documentation: {got!r}")
rec = decode.decode(block((6,), ()), configs[6])
if rec["c"][0]["first"] != {"fault": texts[6], "held": 16, "main": "alloc", "interrupt": 2, "rotation": 3, "d": 0}:
    fails.append(f"first fault decoded as {rec['c'][0]['first']}")
if [c["irq_wait_cycles"] for c in rec["c"]] != [30, 29]:   # lat_max 40 / 41 less the calibration 10 / 12
    fails.append(f"irq_wait_cycles {[c['irq_wait_cycles'] for c in rec['c']]}, want [30, 29]")
if decode.judge(decode.decode(block(inside=0), configs[3])) != "incomplete":
    fails.append("a block with no interrupt inside a call is not incomplete")
# covmap.py's parse of objdump -d: an eight-digit address has no space before it (the Pico 2's 0x1000xxxx),
# a shorter one has; a literal-pool word is not an instruction
import covmap   # noqa: E402
OBJDUMP = """
10001d9c <b_alloc>:
10001d9c:\tf3ef 8210 \tmrs\tr2, PRIMASK
10001da0:\tb672      \tcpsid\ti
10001dbc:\t20001624 \t.word\t0x20001624

08005dd4 <b_alloc>:
 8005dd4:\tf3ef 8210 \tmrs\tr2, PRIMASK
 8005dd8:\tb672      \tcpsid\ti
    5db4:\tf3ef 8210 \tmrs\tr2, PRIMASK
"""
got = covmap.parse(OBJDUMP)
want = [(0x10001d9c, "b_alloc"), (0x10001da0, "b_alloc"), (0x8005dd4, "b_alloc"), (0x8005dd8, "b_alloc"), (0x5db4, "b_alloc")]
if got != want:
    fails.append(f"covmap.parse: {got}, want {want}")
for f in fails:
    print("FAIL " + f)
print(f"{len(sizes)} images, block of {n} words; {len(cases)} verdict cases; {len(fails)} failed")
sys.exit(1 if fails else 0)
