"""Step 4 of the plan: do two libraries with the same class of algorithm
compile to the same inner loop? Reads the cross builds (cross.sh) and their
sizes (build/x/sizes.tsv); runs only arm-none-eabi-objdump on our own builds.

For every configuration and build (core, -Os/-O2): the functions the
configuration adds (sizes.tsv) are disassembled, and every loop is found (a
branch back to an address inside the same function). The innermost loops
(those that contain no other loop) are the per-byte or per-word work. A loop
is reduced to the path one iteration executes: a forward branch inside the
loop that jumps over the loop's exit (a return, or a branch out of the loop)
is taken, every other instruction is on the path. The path is written in a
normal form: addresses, encodings and branch targets dropped, PC-relative
loads as "[pc]", registers renamed in the order they first appear, and the
cycle started at the rotation that gives the smallest text (a loop is a
cycle; where the compiler put its entry does not change the work). Two loops
are
  "same"            if their normal forms are equal (the same instructions
                    per iteration, up to which registers the compiler picked);
  "same opcodes"    if the instructions are the same in the same order but an
                    operand differs (for example the order of a compare's
                    operands, or which pointer is the counter);
  "differ"          otherwise; the number of instructions per iteration is
                    given for both.
For each pair of configurations with the same CRC and the same class, the
work loop of each is compared: the largest innermost loop that reads the
message (a load with a post-increment, or a byte load); a loop that only
builds a table at run time is not it.

  python3 -I loops.py build/x            the comparison, as a table
  python3 -I loops.py build/x show CORE OPT CONFIG...   the loops in full
"""
import itertools
import re
import subprocess
import sys

CLASS = {
    "etl_crc32_t256": ("CRC-32", "table of 256"), "crcany_crc32_byte": ("CRC-32", "table of 256"),
    "libcrc_crc32": ("CRC-32", "table of 256"), "rust_crc32_table1": ("CRC-32", "table of 256"),
    "etl_crc32_t16": ("CRC-32", "table of 16"), "zephyr_crc32_ieee": ("CRC-32", "table of 16"),
    "crcany_crc32_word": ("CRC-32", "slicing by 4"), "zlib_crc32": ("CRC-32", "braided"),
    "crcany_crc32_bit": ("CRC-32", "bitwise"), "ref32": ("CRC-32", "bitwise"),
    "etl_crc16_t256": ("CRC-16", "table of 256"), "crcany_crc16_byte": ("CRC-16", "table of 256"),
    "libcrc_ccitt_ffff": ("CRC-16", "table of 256"), "crcpp_ccittfalse_table": ("CRC-16", "table of 256"),
    "etl_crc16_t16": ("CRC-16", "table of 16"), "zephyr_crc16_itu_t": ("CRC-16", "shifts and XORs"),
    "ref16": ("CRC-16", "bitwise"),
    "etl_crc8_t256": ("CRC-8", "table of 256"), "crcany_crc8_byte": ("CRC-8", "table of 256"),
    "acecrc_crc8_byte": ("CRC-8", "table of 256"),
    "etl_crc8_t16": ("CRC-8", "table of 16"), "zephyr_crc8_ccitt": ("CRC-8", "table of 16"),
    "ref8": ("CRC-8", "bitwise"),
}
REG = re.compile(r"\b(r1[0-2]|r[0-9]|ip|lr|fp|sl|sb)\b")
INSN = re.compile(r"^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$")


def functions(root, core, opt, cfg):
    for line in open(f"{root}/sizes.tsv"):
        p = line.rstrip("\n").split("\t")
        if p[:3] == [core, opt, cfg]:
            return [s.split(":")[0] for s in p[7].split(",") if s.split(":")[1] == "t"] if p[7] else []
    return []


def disasm(elf, fn):
    out = subprocess.run(["arm-none-eabi-objdump", "-d", "--no-show-raw-insn", f"--disassemble={fn}", elf],
                         check=True, capture_output=True, text=True).stdout
    insns = []
    for line in out.splitlines():
        m = INSN.match(line)
        if m:
            ops = m.group(3).split(";")[0].split("@")[0].strip()
            insns.append((int(m.group(1), 16), m.group(2), ops))
    return insns


def loops(insns):
    addrs = [a for a, _, _ in insns]
    found = []
    for i, (a, mn, ops) in enumerate(insns):
        if mn.startswith("b") and not mn.startswith(("bl", "bx", "bic")) or mn in ("bls", "blt", "ble", "blo"):
            t = re.match(r"([0-9a-f]+)", ops)
            if t:
                ta = int(t.group(1), 16)
                if ta <= a and ta in addrs:
                    found.append((addrs.index(ta), i))
    found = [(s, e) for (s, e) in found if is_loop(insns, s, e)]
    inner = [(s, e) for (s, e) in found if not any(s <= s2 and e2 <= e and (s2, e2) != (s, e) for s2, e2 in found)]
    return inner


def is_branch(mn):
    return mn.split(".")[0] in BRANCHES


BRANCHES = {"b", "beq", "bne", "bcs", "bhs", "bcc", "blo", "bmi", "bpl", "bvs", "bvc", "bhi", "bls",
            "bge", "blt", "bgt", "ble", "cbz", "cbnz"}


def target(ops):
    t = re.search(r"\b([0-9a-f]+) <", ops)
    return int(t.group(1), 16) if t else None


def exits(insns, lo, hi, s, e):
    """Does insns[lo..hi] leave the loop [s, e]?"""
    addr_s, addr_e = insns[s][0], insns[e][0]
    for k in range(lo, hi + 1):
        _, mn, ops = insns[k]
        if (mn.startswith("pop") and "pc" in ops) or mn.startswith("bx"):
            return True
        if is_branch(mn):
            t = target(ops)
            if t is not None and not addr_s <= t <= addr_e:
                return True
    return False


def path(insns, s, e):
    """The instructions one iteration of the loop [s, e] executes."""
    out, k = [], s
    index = {a: i for i, (a, _, _) in enumerate(insns)}
    while k <= e:
        a, mn, ops = insns[k]
        out.append((mn, ops))
        t = target(ops) if is_branch(mn) and k < e else None
        if t is not None and t > a and t in index and index[t] <= e and exits(insns, k + 1, index[t] - 1, s, e):
            k = index[t]
            continue
        k += 1
    return out


def is_loop(insns, s, e):
    """A back branch whose path returns or leaves the range is not a loop (for
    example a shared exit block that a later branch jumps back to)."""
    for mn, ops in path(insns, s, e)[:-1]:
        if (mn.startswith("pop") and "pc" in ops) or mn.startswith("bx"):
            return False
    return True


def normal(insns, s, e):
    body = path(insns, s, e)
    best = None
    for r in range(len(body)):
        names, out = {}, []
        for mn, ops in body[r:] + body[:r]:
            ops = re.sub(r"\[pc, #\d+\]", "[pc]", ops)
            if is_branch(mn):
                ops = re.sub(r"\b[0-9a-f]+ <[^>]*>", "", ops)
            ops = re.sub(r"<[^>]*>", "", ops).strip().rstrip(",").strip()
            ops = REG.sub(lambda m: names.setdefault(m.group(1), f"R{len(names)}"), ops)
            out.append(f"{mn} {ops}".strip())
        if best is None or out < best:
            best = out
    return best


def reads_message(body):
    return any(l.startswith("ldrb") or re.search(r"\], #\d+$", l) or l.endswith("]!") for l in body)


def main_loop(root, core, opt, cfg):
    elf = f"{root}/{core}/{opt}/{cfg}.elf"
    best = None
    for fn in functions(root, core, opt, cfg):
        ins = disasm(elf, fn)
        for s, e in loops(ins):
            body = normal(ins, s, e)
            key = (reads_message(body), len(body))
            if best is None or key > best[2]:
                best = (fn, body, key)
    return best and best[:2]


def verdict(la, lb):
    if la is None or lb is None:
        return "differ"
    if la[1] == lb[1]:
        return "same"
    if [l.split()[0] for l in la[1]] == [l.split()[0] for l in lb[1]]:
        return "same opcodes"
    return "differ"


def main():
    root = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == "show":
        core, opt = sys.argv[3], sys.argv[4]
        for cfg in sys.argv[5:]:
            b = main_loop(root, core, opt, cfg)
            print(f"== {cfg} ({core} -{opt}): {b[0] if b else '-'}")
            for line in (b[1] if b else []):
                print("   " + line)
        return
    groups = {}
    for cfg, key in CLASS.items():
        groups.setdefault(key, []).append(cfg)
    print("CRC\tclass\tcore\topt\tconfig A\tconfig B\tloop A\tloop B\tverdict")
    for (crc, cls), cfgs in groups.items():
        for core in ("m0plus", "m4", "m7", "m33"):
            for opt in ("Os", "O2"):
                loopsby = {c: main_loop(root, core, opt, c) for c in cfgs}
                for a, b in itertools.combinations(cfgs, 2):
                    la, lb = loopsby[a], loopsby[b]
                    na = len(la[1]) if la else 0
                    nb = len(lb[1]) if lb else 0
                    print(f"{crc}\t{cls}\t{core}\t{opt}\t{a}\t{b}\t{na}\t{nb}\t{verdict(la, lb)}")


if __name__ == "__main__":
    main()
