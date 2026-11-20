#!/usr/bin/env python3
"""Coverage of the interrupts in a COVERAGE=1 run of rb-mp-stress (main.c
vl_cov, a prototype since 2026-11-17): where in each library's code the
interrupts landed.

Usage: cov_report.py RECORD_JSON [RECORD_JSON ...]
Each record needs its .cov.txt and .elf next to it (run.sh stores them; one
image of all libraries, PER_LIB=0), or its .cov.list (PER_LIB=1: one table
per library, each with its library's image).
Prints per record and library: interrupts that landed in the library's code
(its own functions and the adapter around them), the instructions of the
library functions that were interrupted at all, how many instruction
boundaries were interrupted at least once / at least 10 times, and the
smallest and median count. An instruction boundary never interrupted is a
place where a race cannot have been seen in this run.

The image is disassembled with the toolchain image's objdump (-d -l: the
source file of each instruction, so code the compiler inlined from a
library header counts as the library's).
"""
import json
import os
import re
import statistics
import subprocess
import sys

IMG = "verified-libs/toolchain:2026-11-13"
COV_MAGIC = 0x564C4356
HARNESS = re.compile(r"(rb-mp-stress/main\.c|/common/|startup|libgcc|newlib|libc)")


def disassemble(elf):
    """addr -> (function, source file, masked): masked if interrupts are
    off at that instruction boundary (after cpsid i, up to and including
    the msr PRIMASK / cpsie i that ends it, also along branches out of the
    masked region): no interrupt can land there, so not counted."""
    d, f = os.path.dirname(os.path.abspath(elf)), os.path.basename(elf)
    out = subprocess.run(["podman", "run", "--rm", "-v", f"{d}:/r:Z,ro", IMG, "arm-none-eabi-objdump", "-d", "-l",
                          "--no-show-raw-insn", "-C", f"/r/{f}"], capture_output=True, text=True, check=True).stdout
    funcs = {}            # function -> [(addr, source, mnemonic, operands)]
    func, src = None, ""
    for line in out.splitlines():
        m = re.match(r"^([0-9a-f]{8}) <(.+)>:$", line)
        if m:
            func, src = m.group(2), ""
            funcs.setdefault(func, [])
            continue
        m = re.match(r"^(/\S+|\S+\.\w+):\d+", line)
        if m and not line.startswith(" "):
            src = m.group(1)
            continue
        m = re.match(r"^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$", line)   # no indent at 8 hex digits (RP2350)
        if m and func and not m.group(2).startswith(".") and not m.group(2).startswith("nop"):
            funcs[func].append((int(m.group(1), 16), src, m.group(2), m.group(3)))
    insns = {}
    for fn, lst in funcs.items():
        idx = {a: i for i, (a, _, _, _) in enumerate(lst)}
        # Walk every path from the entry with the PRIMASK state and the
        # registers that saved it (mrs rX, PRIMASK / msr PRIMASK, rX nest,
        # e.g. wizard97's macros). A boundary is masked if every path
        # reaches it with interrupts off.
        arrive = {}                      # index -> set of masked states seen
        work, done = [(0, False, ())], set()
        while work:
            i, mk, saved = work.pop()
            while i < len(lst):
                if (i, mk, saved) in done:
                    break
                done.add((i, mk, saved))
                arrive.setdefault(i, set()).add(mk)
                _, _, mn, op = lst[i]
                sv = dict(saved)
                m = re.match(r"(\w+), PRIMASK", op)
                if mn == "mrs" and m:
                    sv[m.group(1)] = mk
                elif mn == "msr" and op.startswith("PRIMASK"):
                    mk = sv.get(op.split(",")[-1].strip(), False)
                elif mn == "cpsid" and op.startswith("i"):
                    mk = True
                elif mn == "cpsie" and op.startswith("i"):
                    mk = False
                saved = tuple(sorted(sv.items()))
                t = re.search(r"\b([0-9a-f]+) <", op)
                if mn.startswith(("b", "cb")) and t and int(t.group(1), 16) in idx:
                    work.append((idx[int(t.group(1), 16)], mk, saved))
                    if mn in ("b", "b.n", "b.w"):
                        break
                if (mn in ("bx", "pop", "pop.w") and ("lr" in op or "pc" in op)) or mn in ("b", "b.n", "b.w"):
                    break
                i += 1
        masked = {lst[i][0] for i, st in arrive.items() if st == {True}}
        # The boundary right after the instruction that unmasks (msr PRIMASK
        # / cpsie i) is not taken either: the core runs one more instruction
        # before a pending interrupt (seen on the G474: 0 there, all of them
        # one instruction later). Not counted, like the masked ones.
        for i, (a, _, mn, op) in enumerate(lst[:-1]):
            if a in masked and ((mn == "msr" and op.startswith("PRIMASK")) or (mn == "cpsie" and op.startswith("i"))):
                masked.add(lst[i + 1][0])
        # basic blocks: a new one at every branch target and after every
        # branch, so a block with any interrupt in it was executed
        targets = set()
        for a, _, mn, op in lst:
            t = re.search(r"\b([0-9a-f]+) <", op)
            if mn.startswith(("b", "cb")) and t:
                targets.add(int(t.group(1), 16))
        blk, new_blk = 0, True
        for a, s_, mn, op in lst:
            if new_blk or a in targets:
                blk += 1
            insns[a] = (fn, s_, a in masked, blk)
            new_blk = mn.startswith(("b", "cb")) or (mn == "pop" and "pc" in op) or (mn == "ldr" and op.startswith("pc"))
    return insns


def load_cov(path):
    w = [int(x, 16) for x in open(path).read().split()]
    if w[0] != COV_MAGIC:
        sys.exit(f"{path}: bad magic")
    n = w[1]
    hdr = dict(zip(["magic", "n", "aim", "window", "full", "aims", "aim_seed"], w[:7]))
    keys, cnts = w[8:8 + n], w[8 + n:8 + 2 * n]
    hits = {}             # slot -> {pc: [count A, count B]}
    for k, c in zip(keys, cnts):
        if not k:
            continue
        slot, pc, irq = c >> 24, k & ~1, k & 1
        hits.setdefault(slot, {}).setdefault(pc, [0, 0])[irq] += c & 0xFFFFFF
    return hdr, hits


_dis = {}


def tables(base):
    """[(header, {slot: {pc: [A, B]}}, insns)] of a record: one table and
    image (PER_LIB=0), or one per library (.cov.list)."""
    if os.path.exists(base + ".cov.txt"):
        pairs = [(base + ".cov.txt", base + ".elf")]
    else:
        d = os.path.dirname(os.path.abspath(base))
        pairs = [(os.path.join(d, c), os.path.join(d, e))
                 for c, e in (ln.split()[1:3] for ln in open(base + ".cov.list") if ln.strip())]
    out = []
    for c, e in pairs:
        if e not in _dis:
            _dis[e] = disassemble(e)
        out.append((*load_cov(c), _dis[e]))
    return out


def report(rec_path):
    rec = json.load(open(rec_path))
    base = rec_path[:-5]
    parts = tables(base)
    if not parts:
        sys.exit(f"{rec_path}: no coverage tables")
    hdr = parts[0][0]
    names = [l["name"] for l in rec["libs"]] if isinstance(rec.get("libs"), list) else []
    print(f"## {os.path.basename(rec_path)}")
    print(f"mode {rec.get('mode')}, prescaler {rec.get('params', {}).get('timer_prescaler', '?')}, "
          f"aim {hdr['aim']} window {hdr['window']} cycles, aims {hdr['aims']}, table full {hdr['full']}")
    out = []
    for slot, h, insns in sorted((sl, h, ins) for _, hs, ins in parts for sl, h in hs.items()):
        func_insns = {}
        for a, (f, s, mk, blk) in insns.items():
            func_insns.setdefault(f, []).append((a, s, mk, blk))
        total = sum(a + b for a, b in h.values())
        lib_funcs = {}
        in_lib = 0
        for pc, (a, b) in h.items():
            f, s, _, _ = insns.get(pc, ("?", "", False, 0))
            if not HARNESS.search(s or "x/common/"):
                in_lib += a + b
                lib_funcs.setdefault(f, 0)
                lib_funcs[f] += a + b
        name = names[slot] if slot < len(names) else f"slot {slot}"
        rows = []
        tot = {"executed": 0, "hit": 0, "hit10": 0, "unseen": 0, "masked": 0}
        exec_counts = []
        for f in sorted(lib_funcs, key=lambda f: -lib_funcs[f]):
            fi = [x for x in func_insns.get(f, []) if not HARNESS.search(x[1] or "x/common/")]
            seen_blocks = {blk for a, _, _, blk in fi if sum(h.get(a, [0, 0]))}
            ex = [sum(h.get(a, [0, 0])) for a, _, mk, blk in fi if not mk and blk in seen_blocks]
            r = {"function": f, "interrupts": lib_funcs[f], "executed": len(ex), "hit": sum(c > 0 for c in ex),
                 "hit10": sum(c >= 10 for c in ex), "min": min(ex) if ex else 0,
                 "median": statistics.median(ex) if ex else 0,
                 "unseen": sum(1 for a, _, mk, blk in fi if not mk and blk not in seen_blocks),
                 "masked": sum(1 for x in fi if x[2])}
            rows.append(r)
            exec_counts += ex
            for k in tot:
                tot[k] += r[k]
        print(f"\n### {name}\ninterrupts {total}, in library code {in_lib} ({100 * in_lib / max(total, 1):.1f} %); "
              f"boundaries in executed blocks {tot['executed']}: interrupted >=1x {tot['hit']}, >=10x {tot['hit10']}, "
              f"median {statistics.median(exec_counts) if exec_counts else 0}; "
              f"in blocks never interrupted {tot['unseen']}; masked {tot['masked']}")
        for r in rows[:8]:
            print(f"  {r['function'][:56]:56} {r['hit']:>4}/{r['executed']:<4} >=10x {r['hit10']:>4}  "
                  f"min {r['min']:>6} median {r['median']:>8}  unseen {r['unseen']}")
        out.append({"slot": slot, "library": name, "interrupts": total, "in_library": in_lib, **tot,
                    "median": statistics.median(exec_counts) if exec_counts else 0,
                    "min": min(exec_counts) if exec_counts else 0, "functions": rows})
    json.dump({"record": os.path.basename(rec_path), "cov": hdr, "libs": out}, open(base + ".cov.json", "w"), indent=1)
    print()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        report(p)
