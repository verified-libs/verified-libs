#!/usr/bin/env python3
"""For the CRC pages: for every class of README step 2 that two or more libraries offer,
are their loops the same instructions on a board's core? Reads the built
images; writes nothing.

Usage (in the toolchain image, which has arm-none-eabi-objdump):
  python3 -I lab/tools/crc-loops.py BUILD_V2_DIR [BOARD ...]

BUILD_V2_DIR is kinds/crc/build/v2 of a built tree; per board the image of
placement 0 of each configuration (img/<adapter>-p0/fw.elf) is read. The
code of a configuration is every function from _bench_near_start on (the
adapter and the library; the far filler bench_shift left out). Its loop is
the shortest backward branch within one function whose body loads from a
table: a load with a register offset (ldr, ldrb, ldrh with [rX, rY...]).
Two loops are "the same" if their instructions are the same after
registers are renamed (r0-r12, ip, lr to R) and addresses dropped; else
the line says how long each is and how it differs from the first group:\nthe same instructions in another order, the same mnemonics with other\noperands, or which mnemonics only one has (+ more, - fewer).
"""
import collections
import os
import re
import subprocess
import sys

CLASSES = [   # README step 2: classes two or more libraries offer
    ("CRC-32 table of 256", ["adapter_etl_crc32_t256", "adapter_crcany_crc32_byte", "adapter_libcrc_crc32", "adapter_rust_crc32_table1"]),
    ("CRC-32 table of 16", ["adapter_etl_crc32_t16", "adapter_zephyr_crc32_ieee"]),
    ("CRC-16 table of 256", ["adapter_etl_crc16_t256", "adapter_crcany_crc16_byte", "adapter_libcrc_ccitt_ffff", "adapter_crcpp_ccittfalse_table"]),
    ("CRC-8 table of 256", ["adapter_etl_crc8_t256", "adapter_crcany_crc8_byte", "adapter_acecrc_crc8_byte"]),
    ("CRC-8 table of 16", ["adapter_etl_crc8_t16", "adapter_zephyr_crc8_ccitt"]),
]
INSN = re.compile(r"^\s*([0-9a-f]+):\s+([a-z][a-z0-9.]*)\s*(.*)$")
FUNC = re.compile(r"^([0-9a-f]+) <(.+)>:$")
BRANCH = re.compile(r"^(b|cbz|cbnz|b[a-z]{2})$")
REG = re.compile(r"\b(r1[0-2]|r[0-9]|ip|lr|fp|sl|sb)\b")
TABLE_LOAD = re.compile(r"\[(?:r\d+|ip|lr|sl|sb|fp), (?:r\d+|ip|lr|sl|sb|fp)")


def functions(elf):
    out = subprocess.run(["arm-none-eabi-objdump", "-d", "--no-show-raw-insn", elf],
                         capture_output=True, text=True, check=True).stdout
    funcs, cur = [], None
    for line in out.splitlines():
        m = FUNC.match(line)
        if m:
            cur = (int(m.group(1), 16), m.group(2), [])
            funcs.append(cur)
            continue
        m = INSN.match(line)
        if m and cur and not m.group(2).startswith("."):
            cur[2].append((int(m.group(1), 16), m.group(2), m.group(3).split("@")[0].strip()))
    # objdump labels an address with one symbol only; _bench_near_start shares its address with the adapter
    nm = subprocess.run(["arm-none-eabi-nm", elf], capture_output=True, text=True, check=True).stdout
    start = next((int(l.split()[0], 16) for l in nm.splitlines() if l.endswith(" _bench_near_start")), None)
    return [f for f in funcs if start is not None and f[0] >= start and f[1] != "bench_shift"]


def norm(mn, ops):
    mn = re.sub(r"\.(n|w)$", "", mn)
    ops = re.sub(r"\b[0-9a-f]{6,8} <[^>]*>", "ADDR", ops)
    return f"{mn} {REG.sub('R', ops)}".strip()


def loop_of(elf):
    best = None
    for start, name, insns in functions(elf):
        addrs = [a for a, _, _ in insns]
        for i, (a, mn, ops) in enumerate(insns):
            m = re.match(r"([0-9a-f]+)", ops)
            if BRANCH.match(re.sub(r"\.(n|w)$", "", mn)) and m:
                t = int(m.group(1), 16)
                if start <= t < a and t in addrs:
                    body = insns[addrs.index(t):i + 1]
                    if any(TABLE_LOAD.search(o) and mm.startswith("ldr") for _, mm, o in body):
                        if best is None or len(body) < len(best[1]):
                            best = (name, body)
    return best


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = sys.argv[1]
    boards = sys.argv[2:] or sorted(os.listdir(root))
    for b in boards:
        print(f"== {b}")
        for cls, ads in CLASSES:
            loops = {}
            for ad in ads:
                elf = os.path.join(root, b, "img", f"{ad}-p0", "fw.elf")
                if os.path.exists(elf):
                    lp = loop_of(elf)
                    loops[ad] = [norm(mn, o) for _, mn, o in lp[1]] if lp else None
            have = {k: v for k, v in loops.items() if v}
            short = lambda ad: ad.replace("adapter_", "")
            groups = collections.defaultdict(list)
            for ad, body in have.items():
                groups[tuple(body)].append(short(ad))
            if len(groups) == 1 and len(have) == len(ads):
                body = next(iter(groups))
                tl = sum(1 for x in body if x.startswith("ldr") and TABLE_LOAD.search(x.replace("R", "r0")))
                print(f"  {cls}: {', '.join(short(a) for a in ads)}: same ({len(body)} instructions, {tl} table loads)")
                continue
            if not groups:
                print(f"  {cls}: no table loop found in any of {', '.join(short(a) for a in ads)}")
                continue
            parts = []
            ref = collections.Counter(mn.split()[0] for mn in next(iter(groups)))
            first = next(iter(groups))
            for body, names in groups.items():
                c = collections.Counter(x.split()[0] for x in body)
                extra = sorted((c - ref).elements()); missing = sorted((ref - c).elements())
                if body == first:
                    d = ""
                elif sorted(body) == sorted(first):
                    d = "; the same instructions in another order"
                elif [x.split()[0] for x in body] == [x.split()[0] for x in first]:
                    i = next(k for k in range(len(body)) if body[k] != first[k])
                    d = f"; the same mnemonics in the same order, operands differ (first: '{body[i]}' / '{first[i]}')"
                elif not extra and not missing:
                    d = "; the same mnemonics, other order or operands"
                else:
                    d = ("; +" + " +".join(extra) if extra else "") + ("; -" + " -".join(missing) if missing else "")
                tl = sum(1 for x in body if x.startswith("ldr") and TABLE_LOAD.search(x.replace("R", "r0")))
                parts.append(f"{'/'.join(names)} {len(body)} instructions, {tl} table loads{d}")
            nol = [short(a) for a in ads if not loops.get(a)]
            print(f"  {cls}: differs: " + " | ".join(parts) + (f" | no table loop found: {', '.join(nol)}" if nol else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
