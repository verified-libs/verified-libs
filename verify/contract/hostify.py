#!/usr/bin/env python3
"""Host copy of the benchmark tree for the contract check: the Cortex-M
interrupt masking in inline assembly ("mrs %0, primask", "msr primask, %0",
"cpsid i", "cpsie i", in the shims, adapters and library headers) becomes
calls of host_irq.h's flag; nothing else changes.

Usage: hostify.py SRC_DIR DST_DIR
  The tree is copied with hard links; a file that contains such assembly is
  written anew (never through the link), so the originals stay untouched.
  Prints every rewritten statement; a statement in a form it does not know
  stays as it is (noted on stderr), so a host build that uses it fails.
"""
import os
import re
import shutil
import sys

ASM = re.compile(r'(?:__asm__|__asm|asm)\s*(?:volatile|__volatile__)?\s*\((?P<body>(?:[^()]|\([^()]*\))*)\)\s*;', re.S)
STR = re.compile(r'"((?:[^"\\]|\\.)*)"')


def rewrite(stmt, body):
    strings = STR.findall(body.split(":")[0])
    code = "".join(strings).replace("\\n", "\n").replace("\\t", " ")
    insns = [i.strip() for i in re.split(r"[\n;]", code) if i.strip()]
    if not any(re.search(r"primask|cpsid|cpsie|ipsr|^(dsb|isb|dmb)\b", i, re.I) for i in insns):
        return None
    parts = body.split(":")
    outs = re.findall(r'"=r"\s*\(([^)]*)\)', parts[1]) if len(parts) > 1 else []
    ins = re.findall(r'"r"\s*\(([^)]*)\)', parts[2]) if len(parts) > 2 else []
    calls = ['__asm__ volatile("" ::: "memory");']   # a barrier keeps its compiler ordering
    for i in insns:
        m = re.fullmatch(r"mrs\s+%(\d+)\s*,\s*primask", i, re.I)
        if m:
            calls.append(f"{outs[int(m.group(1))]} = vl_get_primask();"); continue
        m = re.fullmatch(r"msr\s+primask\s*,\s*%(\d+)", i, re.I)
        if m:
            k = int(m.group(1)) - len(outs)
            calls.append(f"vl_set_primask({ins[k]});"); continue
        if re.fullmatch(r"cpsid\s+i", i, re.I):
            calls.append("vl_cpsid();"); continue
        if re.fullmatch(r"cpsie\s+i", i, re.I):
            calls.append("vl_cpsie();"); continue
        m = re.fullmatch(r"mrs\s+%(\d+)\s*,\s*ipsr", i, re.I)
        if m:   # "in an interrupt handler?": the contract check's own flag
            calls.append(f"{outs[int(m.group(1))]} = vl_get_ipsr();"); continue
        if re.fullmatch(r"(dsb|isb|dmb)(\s+(sy|#?0x[fF]|#?15))?", i, re.I):
            continue
        # left as it is: the host build fails if this file is compiled
        print(f"hostify: note: left unchanged (unknown form {i!r}): {' '.join(stmt.split())[:100]}", file=sys.stderr)
        return None
    return "do { " + " ".join(calls) + " } while (0);"


def main():
    src, dst = sys.argv[1:3]
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, copy_function=os.link, symlinks=True)
    n = 0
    for root, _, files in os.walk(dst):
        for f in files:
            if not f.endswith((".c", ".h", ".cpp", ".hpp", ".cc")):
                continue
            p = os.path.join(root, f)
            if os.path.islink(p):
                continue
            try:
                text = open(p, encoding="utf-8", errors="surrogateescape").read()
            except OSError:
                continue
            if not re.search(r"primask|cpsid|cpsie|ipsr|\b(dsb|isb|dmb)\b", text, re.I):
                continue
            def sub(m):
                nonlocal n
                r = rewrite(m.group(0), m.group("body"))
                if r is None:
                    return m.group(0)
                n += 1
                print(f"{os.path.relpath(p, dst)}: {' '.join(m.group(0).split())[:90]}  ->  {r}")
                return r
            new = ASM.sub(sub, text)
            if new != text:
                os.unlink(p)   # break the hard link: the original is never written
                open(p, "w", encoding="utf-8", errors="surrogateescape").write(new)
    print(f"hostify: {n} assembly statements rewritten")


if __name__ == "__main__":
    main()
