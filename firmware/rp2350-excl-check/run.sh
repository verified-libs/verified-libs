#!/bin/bash
# Build, flash and run rp2350-excl-check on the Pico 2, print the results.
# Usage (on lib-lab1): PROBE=VID:PID:SERIAL bash run.sh
set -euo pipefail
cd "$(dirname "$0")"
IMG=verified-libs/toolchain:2026-11-05
PR="--chip RP235x${PROBE:+ --probe $PROBE}"
podman run --rm -v "$PWD/..":/work:Z -w /work/rp2350-excl-check "$IMG" \
    sh -c "make clean >/dev/null; make BOARD=rp2350" > /dev/null
probe-rs download $PR --allow-erase-all build/fw.elf 2>&1 | tail -n 1
timeout 20 probe-rs reset $PR 2>&1 | tail -n 1 || echo "reset timed out (RP2350); running from the download's reset"
sleep "${WAIT:-30}"
words=$(probe-rs read $PR b32 0x20000000 13 | sed 's/^[0-9a-fA-F]*://' | tr -s ' \n' ' ')
python3 - $words <<'PY'
import sys
w = [int(x, 16) for x in sys.argv[1:]]
magic, done, n, nt = w[:4]
assert magic == 0x564C5843, f"bad magic {magic:#x}"
assert done == 1, "not done"
names = ["MPU off (SRAM Non-shareable)", "MPU on, SRAM Inner Shareable", "MPU off again"]
got, f0, f1 = w[4:4 + nt], w[4 + nt:4 + 2 * nt], w[4 + 2 * nt:4 + 3 * nt]
print(f"two cores x {n} LDREX/STREX increments; expect {2 * n}")
for i in range(nt):
    print(f"  {names[i]:30} counter {got[i]:8}  lost {2 * n - got[i]:7}  STREX retries core0 {f0[i]:7} core1 {f1[i]:7}")
PY
