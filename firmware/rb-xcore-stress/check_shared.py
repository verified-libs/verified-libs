#!/usr/bin/env python3
"""Fail if the shared part (.xshared, 0x20070000..0x2007ffef) differs between
the application core's and the network core's image: every symbol there
must have the same address and size in both, and the section the same
size (rb-xcore-stress/Makefile)."""
import subprocess
import sys

LO, HI = 0x20070000, 0x2007FFF0


def shared(elf):
    out = subprocess.run(["arm-none-eabi-nm", "-S", elf], capture_output=True, text=True, check=True).stdout
    syms = {}
    for ln in out.splitlines():
        f = ln.split()
        if len(f) >= 3 and all(c in "0123456789abcdef" for c in f[0]):
            a = int(f[0], 16)
            if LO <= a < HI and f[-1] != "_estack":   # the app stack top, a linker symbol at LO
                size = int(f[1], 16) if len(f) == 4 else 0
                syms[f[-1]] = (a, size)
    return syms


a, n = shared(sys.argv[1]), shared(sys.argv[2])
bad = sorted(k for k in set(a) | set(n) if a.get(k) != n.get(k))
if bad:
    for k in bad[:20]:
        print(f"{k}: app {a.get(k)}, net {n.get(k)}", file=sys.stderr)
    sys.exit(f"check_shared: the shared part differs in {len(bad)} symbols")
print(f"check_shared: {len(a)} symbols in the shared part, the same in both images "
      f"(up to {max(v[0] + v[1] for v in a.values()) - LO:#x} bytes)")
