#!/usr/bin/env python3
"""Regression tests for the sweep coverage analysis in decode.py
(masked_pcs, sweep_coverage). Host only, no board needed:

    cd firmware/nrf5340-rb-stress && python3 -m unittest -v test_decode

The fixtures are objdump -d listings and linker map lines in the format the
harness produces. w97m_reset is real code (wizard97 + PRIMASK macros, gcc
-O2, STM32G474): nested critical sections (mrs/cpsid twice, msr to restore)
and a cbnz into the masked region.
"""
import os
import tempfile
import unittest

from decode import masked_pcs, sweep_coverage


def func(name, addr, rows):
    """objdump -d style text for one function; rows: (addr, hex, op, args)."""
    out = [f"{addr:08x} <{name}>:"]
    for a, hx, op, args in rows:
        out.append(f" {a:x}:\t{hx:<10}\t{op}\t{args}".rstrip())
    return "\n".join(out) + "\n"


W97M_RESET = [
    (0x8002f60, "f3ef 8310", "mrs", "r3, PRIMASK"),
    (0x8002f64, "b672", "cpsid", "i"),
    (0x8002f66, "f3ef 8010", "mrs", "r0, PRIMASK"),
    (0x8002f6a, "b672", "cpsid", "i"),
    (0x8002f6c, "490e", "ldr", "r1, [pc, #56]\t@ (8002fa8 <w97m_reset+0x48>)"),
    (0x8002f6e, "f8d1 2084", "ldr.w", "r2, [r1, #132]\t@ 0x84"),
    (0x8002f72, "f380 8810", "msr", "PRIMASK, r0"),
    (0x8002f76, "b912", "cbnz", "r2, 8002f7e <w97m_reset+0x1e>"),
    (0x8002f78, "f383 8810", "msr", "PRIMASK, r3"),
    (0x8002f7c, "4770", "bx", "lr"),
    (0x8002f7e, "f8d1 2084", "ldr.w", "r2, [r1, #132]\t@ 0x84"),
    (0x8002f82, "3a01", "subs", "r2, #1"),
    (0x8002f84, "f8c1 2084", "str.w", "r2, [r1, #132]\t@ 0x84"),
    (0x8002f88, "f383 8810", "msr", "PRIMASK, r3"),
    (0x8002f8c, "f3ef 8310", "mrs", "r3, PRIMASK"),
    (0x8002f90, "b672", "cpsid", "i"),
    (0x8002f92, "f3ef 8010", "mrs", "r0, PRIMASK"),
    (0x8002f96, "b672", "cpsid", "i"),
    (0x8002f98, "f8d1 2084", "ldr.w", "r2, [r1, #132]\t@ 0x84"),
    (0x8002f9c, "f380 8810", "msr", "PRIMASK, r0"),
    (0x8002fa0, "2a00", "cmp", "r2, #0"),
    (0x8002fa2, "d1ec", "bne.n", "8002f7e <w97m_reset+0x1e>"),
    (0x8002fa4, "e7e8", "b.n", "8002f78 <w97m_reset+0x18>"),
    (0x8002fa6, "bf00", "nop", ""),
    (0x8002fa8, "20001148", ".word", "0x20001148"),
]
# Reached with interrupts enabled: the first mrs and cpsid, the return, and
# the mrs/cpsid that re-enter the outer critical section in the loop.
W97M_RESET_OPEN = {0x8002f60, 0x8002f64, 0x8002f7c, 0x8002f8c, 0x8002f90}
W97M_RESET_MASKED = {a for a, _, op, _ in W97M_RESET
                     if not op.startswith(".") and op != "nop"} - W97M_RESET_OPEN

LOCK = [(0x8003000, "b672", "cpsid", "i"), (0x8003002, "4770", "bx", "lr")]
UNLOCK = [(0x8003004, "b662", "cpsie", "i"), (0x8003006, "4770", "bx", "lr")]
DIRECT_LOCKED = [   # lock and unlock helpers called directly
    (0x8003010, "b510", "push", "{r4, lr}"),
    (0x8003012, "f7ff fff5", "bl", "8003000 <lock>"),
    (0x8003016, "6803", "ldr", "r3, [r0, #0]"),
    (0x8003018, "3301", "adds", "r3, #1"),
    (0x800301a, "6003", "str", "r3, [r0, #0]"),
    (0x800301c, "f7ff fff2", "bl", "8003004 <unlock>"),
    (0x8003020, "bd10", "pop", "{r4, pc}"),
    (0x8003022, "bf00", "nop", ""),
]
INDIRECT_LOCKED = [  # lock and unlock through pointers (ETL queue_spsc_locked)
    (0x8003030, "b510", "push", "{r4, lr}"),
    (0x8003032, "6843", "ldr", "r3, [r0, #4]"),
    (0x8003034, "4798", "blx", "r3"),
    (0x8003036, "6803", "ldr", "r3, [r0, #0]"),
    (0x8003038, "3301", "adds", "r3, #1"),
    (0x800303a, "6883", "ldr", "r3, [r0, #8]"),
    (0x800303c, "4798", "blx", "r3"),
    (0x800303e, "bd10", "pop", "{r4, pc}"),
]
BRANCHY = [  # masked on one path only; where the paths meet counts as masked
    (0x8003040, "b108", "cbz", "r0, 8003046 <branchy+0x6>"),
    (0x8003042, "b672", "cpsid", "i"),
    (0x8003044, "e000", "b.n", "8003048 <branchy+0x8>"),
    (0x8003046, "3001", "adds", "r0, #1"),
    (0x8003048, "6803", "ldr", "r3, [r0, #0]"),
    (0x800304a, "b662", "cpsie", "i"),
    (0x800304c, "4770", "bx", "lr"),
]


def ins_of(rows):
    return [(a, op, args.replace("\t", " ")) for a, _, op, args in rows if not op.startswith(".")]


class MaskedPcs(unittest.TestCase):
    def test_nested_primask_real_code(self):
        self.assertEqual(masked_pcs(ins_of(W97M_RESET), {}), W97M_RESET_MASKED)

    def test_cbz_cbnz_target_is_followed(self):
        # Regression: the target of cbz/cbnz was read from the <sym+off>
        # label, so the branch was never followed and the masked loop body
        # (0x8002f7e..) counted as interruptible.
        m = masked_pcs(ins_of(W97M_RESET), {})
        for a in (0x8002f7e, 0x8002f82, 0x8002f84, 0x8002f88):
            self.assertIn(a, m)
        self.assertEqual(masked_pcs(ins_of(BRANCHY), {}), {0x8003044, 0x8003048, 0x800304a})

    def test_lock_unlock_helpers(self):
        effect = {0x8003000: "lock", 0x8003004: "unlock"}
        self.assertEqual(masked_pcs(ins_of(DIRECT_LOCKED), effect),
                         {0x8003016, 0x8003018, 0x800301a, 0x800301c})
        self.assertEqual(masked_pcs(ins_of(DIRECT_LOCKED), {}), set())

    def test_no_masking(self):
        self.assertEqual(masked_pcs(ins_of(INDIRECT_LOCKED), {}), set())


class SweepCoverageRp2350(unittest.TestCase):
    """Addresses with 8 digits (RP2350 flash at 0x10000000): objdump prints
    no leading blank before them; nop.w as padding."""

    def test_eight_digit_addresses(self):
        rows = [(0x100000e0, "2200", "movs", "r2, #0"),
                (0x100000e2, "801a", "strh", "r2, [r3, #0]"),
                (0x100000e4, "4770", "bx", "lr"),
                (0x100000e6, "bf00", "nop", ""),
                (0x100000e8, "200006c0", ".word", "0x200006c0"),
                (0x100000ec, "f3af 8000", "nop.w", "")]
        lst = func("broken_reset", 0x100000e0, rows).replace("\n ", "\n")
        self.assertIn("\n100000e0:\t", lst)
        mp = " .text          0x100000e0       0x20 build/broken.o\n"
        bits = [1 << 0 | 1 << 2]                     # 0x100000e0, 0x100000e4
        with tempfile.TemporaryDirectory() as d:
            lf, mf = os.path.join(d, "fw.lst"), os.path.join(d, "fw.map")
            for path, text in ((lf, lst), (mf, mp)):
                with open(path, "w") as fh:
                    fh.write(text)
            r = sweep_coverage(bits, 0x100000e0, lf, mf)
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["object"], r[0]["instructions"], r[0]["interrupted"], r[0]["not_interrupted"]),
                         ("broken.o", 3, 2, ["0x100000e2"]))


class SweepCoverage(unittest.TestCase):
    BASE = 0x08002f00

    def run_cov(self, hits):
        bits = [0] * 8
        for a in hits:
            off = (a - self.BASE) >> 1
            bits[off >> 5] |= 1 << (off & 31)
        lst = (func("w97m_reset", 0x08002f60, W97M_RESET) + "\t...\n\n"
               + func("lock", 0x08003000, LOCK) + func("unlock", 0x08003004, UNLOCK)
               + func("direct_locked", 0x08003010, DIRECT_LOCKED)
               + func("indirect_locked", 0x08003030, INDIRECT_LOCKED)
               + func("never_hit", 0x08003050, [(0x8003050, "4770", "bx", "lr")]))
        mp = (" .text.w97m_reset\n                0x08002f60       0x60 build/w2_wizard97_primask.o\n"
              " .text          0x08003000       0x60 build/fixture.o\n"
              " .text          0x00000000        0x0 build/empty.o\n")
        with tempfile.TemporaryDirectory() as d:
            lf, mf = os.path.join(d, "fw.lst"), os.path.join(d, "fw.map")
            for path, text in ((lf, lst), (mf, mp)):
                with open(path, "w") as fh:
                    fh.write(text)
            return {f["function"]: f for f in sweep_coverage(bits, self.BASE, lf, mf)}

    def test_full_coverage(self):
        hits = set(W97M_RESET_OPEN) | {0x8003000, 0x8003002, 0x8003004, 0x8003006,
                                       0x8003010, 0x8003012, 0x8003020,
                                       0x8003030, 0x8003032, 0x8003034, 0x800303e}
        r = self.run_cov(hits)
        self.assertNotIn("never_hit", r)            # no PC in it: not listed
        w = r["w97m_reset"]
        self.assertEqual(w["object"], "w2_wizard97_primask.o")
        self.assertEqual((w["instructions"], w["interrupted"], w["masked"], w["probably_masked"]),
                         (23, 5, 18, 0))            # .word skipped, trailing nop is padding
        self.assertEqual(w["not_interrupted"], [])
        d = r["direct_locked"]
        self.assertEqual(d["object"], "fixture.o")
        self.assertEqual((d["instructions"], d["masked"], d["not_interrupted"]), (7, 4, []))
        i = r["indirect_locked"]
        self.assertEqual((i["masked"], i["probably_masked"], i["not_interrupted"]), (0, 4, []))

    def test_gap_is_reported(self):
        hits = set(W97M_RESET_OPEN) - {0x8002f8c} | {0x8003000, 0x8003004, 0x8003010, 0x8003012}
        r = self.run_cov(hits)
        self.assertEqual(r["w97m_reset"]["not_interrupted"], ["0x8002f8c"])
        self.assertEqual(r["direct_locked"]["not_interrupted"], ["0x8003020"])


if __name__ == "__main__":
    unittest.main()
