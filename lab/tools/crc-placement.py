#!/usr/bin/env python3
"""For the CRC pages: where a
configuration's loop lies in each placement, beside its numbers. Facts only;
reads the built images and the run files, writes nothing.

Usage (in the toolchain image, which has arm-none-eabi-objdump and nm):
  python3 -I lab/tools/crc-placement.py BUILD_V2_DIR RUN_DIR BOARD ADAPTER [ADAPTER ...]

Per adapter and placement (img/<adapter>-p<N>/fw.elf): the loop of
crc-loops.py (the shortest backward branch around a table load; for code
without a table, the shortest backward branch), the
address of its first and of its last instruction, each modulo 8 and
modulo 32; whether a 32-bit instruction of the loop crosses an 8-byte or a
32-byte boundary, and whether the loop itself does (first and last byte in
different blocks); the table's address modulo 32 (the word the table load's
base register was loaded with from the literal pool, if it was); and the
means at 1024 bytes, offset 0, cache off and on, of pass 1. The same for the
baseline's loop (the reference function of the configuration's CRC, in the
fixed part), placement 0.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util   # noqa: E402
spec = importlib.util.spec_from_file_location("crc_loops", os.path.join(os.path.dirname(os.path.abspath(__file__)), "crc-loops.py"))
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)

REF = {"CRC-32/ISO-HDLC": "ref32_crc", "CRC-16/IBM-3740": "ref16_crc", "CRC-8/SMBUS": "ref8_crc"}


def disasm(elf):
    out = subprocess.run(["arm-none-eabi-objdump", "-d", "--no-show-raw-insn", elf],
                         capture_output=True, text=True, check=True).stdout
    funcs, words, cur = {}, {}, None
    for line in out.splitlines():
        m = cl.FUNC.match(line)
        if m:
            cur = m.group(2); funcs[cur] = []
            continue
        m = re.match(r"^\s*([0-9a-f]+):\s+\.word\s+0x([0-9a-f]+)", line)
        if m:
            words[int(m.group(1), 16)] = int(m.group(2), 16)
            continue
        m = cl.INSN.match(line)
        if m and cur:
            funcs[cur].append((int(m.group(1), 16), m.group(2), m.group(3)))
    return funcs, words


def loop_in(insns, start, table=True):
    best = None
    addrs = [a for a, _, _ in insns]
    for i, (a, mn, ops) in enumerate(insns):
        m = re.match(r"([0-9a-f]+)", ops)
        if cl.BRANCH.match(re.sub(r"\.(n|w)$", "", mn)) and m:
            t = int(m.group(1), 16)
            if start <= t < a and t in addrs:
                body = insns[addrs.index(t):i + 1]
                if not table or any(cl.TABLE_LOAD.search(o) and mm.startswith("ldr") for _, mm, o in body):
                    if best is None or len(body) < len(best):
                        best = body
    return best


def describe(funcs, words, names):
    """the loop over the given functions (or all from _bench_near_start)"""
    found = [(name, loop_in(funcs[name], funcs[name][0][0])) for name in names if funcs.get(name)]
    found = [x for x in found if x[1]]
    if not found:   # no table (bitwise code): the innermost loop of any of them
        found = [(name, loop_in(funcs[name], funcs[name][0][0], table=False)) for name in names if funcs.get(name)]
        found = sorted([x for x in found if x[1]], key=lambda x: len(x[1]))
    for name, body in found:
        insns = funcs[name]
        nxt = {a: b for (a, _, _), (b, _, _) in zip(insns, insns[1:])}
        sizes = [nxt.get(a, a + 2) - a for a, _, _ in body]
        first, last = body[0][0], body[-1][0] + sizes[-1] - 1
        cross8 = any((a // 8) != ((a + s - 1) // 8) for (a, _, _), s in zip(body, sizes) if s == 4)
        cross32 = any((a // 32) != ((a + s - 1) // 32) for (a, _, _), s in zip(body, sizes) if s == 4)
        # the table: the base register of the table load, loaded from the literal pool in this function
        tab = None
        for _, mn, ops in body:
            m = cl.TABLE_LOAD.search(ops)
            if mn.startswith("ldr") and m:
                base = re.search(r"\[(\w+),", ops).group(1)
                for _, mn2, ops2 in insns:
                    m2 = re.match(rf"{base}, \[pc, #\d+\]\s+@ \(([0-9a-f]+)", ops2)
                    if mn2.startswith("ldr") and m2 and int(m2.group(1), 16) in words:
                        tab = words[int(m2.group(1), 16)]
                break
        return {"fn": name, "first": first, "last": last, "n": len(body), "cross8": cross8, "cross32": cross32,
                "loop8": first // 8 != last // 8, "loop32": first // 32 != last // 32, "table": tab}
    return None


def main():
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    build, rundir, board, ads = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
    hdr = (f"  {'place':>5} {'loop first':>10} {'%8':>3} {'%16':>3} {'%32':>3} {'last':>10} {'%8':>3} {'%32':>3} {'n':>3} "
           f"{'32-bit insn crosses 8/32':>24} {'loop crosses 8/16/32':>20} {'table %8/%16/%32':>16} {'1024 off':>10} {'1024 on':>10}")
    for ad in ads:
        print(f"{board} {ad}")
        print(hdr)
        crc, base, br = None, None, None
        for p in range(0, 32, 4):
            elf = os.path.join(build, board, "img", f"{ad}-p{p}", "fw.elf")
            if not os.path.exists(elf):
                continue
            funcs, words = disasm(elf)
            nm = subprocess.run(["arm-none-eabi-nm", elf], capture_output=True, text=True, check=True).stdout
            start = next(int(l.split()[0], 16) for l in nm.splitlines() if l.endswith(" _bench_near_start"))
            syms = sorted((int(l.split()[0], 16), l.split()[2]) for l in nm.splitlines()
                          if len(l.split()) == 3 and l.split()[1] in "tTwW")
            names = [n for a, n in syms if a >= start and n != "bench_shift" and n in funcs]
            names += [n for n in funcs if n not in names and funcs[n] and funcs[n][0][0] >= start and n != "bench_shift"]
            d = describe(funcs, words, names)
            try:
                r = json.load(open(os.path.join(rundir, f"{ad}-p{p}-pass1.json")))
                crc = r["crc"]
                off = r["libs"][1]["results"]["len1024/offset0/cache_off"]["mean"]
                on = r["libs"][1]["results"]["len1024/offset0/cache_on"]["mean"]
            except (OSError, KeyError, TypeError):
                off = on = None
            if not d:
                print(f"  {p:5}  no table loop found"); continue
            t = d["table"]
            tab = f"{t % 8}/{t % 16}/{t % 32}" if t is not None else "?"
            l16 = "yes" if d["first"] // 16 != d["last"] // 16 else "no"
            print(f"  {p:5} {d['first']:10x} {d['first'] % 8:3} {d['first'] % 16:3} {d['first'] % 32:3} {d['last']:10x} {d['last'] % 8:3} {d['last'] % 32:3} "
                  f"{d['n']:3} {('yes' if d['cross8'] else 'no') + '/' + ('yes' if d['cross32'] else 'no'):>24} "
                  f"{('yes' if d['loop8'] else 'no') + '/' + l16 + '/' + ('yes' if d['loop32'] else 'no'):>20} {tab:>16} {off!s:>10} {on!s:>10}")
            if p == 0 and crc:
                base = describe(funcs, words, [REF[crc]])
                br = r["libs"][0]["results"]
        if crc and base:
            b = base
            print(f"  baseline {REF[crc]}: first {b['first']:x} (%8 {b['first'] % 8}, %32 {b['first'] % 32}), last {b['last']:x} "
                  f"(%8 {b['last'] % 8}, %32 {b['last'] % 32}), {b['n']} instructions, 32-bit insn crosses 8/32: "
                  f"{'yes' if b['cross8'] else 'no'}/{'yes' if b['cross32'] else 'no'}, loop crosses 8/32: "
                  f"{'yes' if b['loop8'] else 'no'}/{'yes' if b['loop32'] else 'no'}, table %32: "
                  f"{b['table'] % 32 if b['table'] is not None else '?'}; 1024 off {br['len1024/offset0/cache_off']['mean']}, "
                  f"on {br['len1024/offset0/cache_on']['mean']}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
