#!/bin/bash
# Build, flash and run counter-check on one board, print the table.
# Usage (on lib-lab1): BOARD=stm32g474 PROBE=VID:PID:SERIAL bash run.sh
set -euo pipefail
cd "$(dirname "$0")"
IMG=verified-libs/toolchain:2026-11-05
BOARD=${BOARD:-nrf5340}
case $BOARD in
    nrf5340)   CHIP=nRF5340_xxAA_APPONLY ;;
    stm32g0b1) CHIP=STM32G0B1RETx ;;
    stm32g474) CHIP=STM32G474RETx ;;
    stm32h723) CHIP=STM32H723ZGTx ;;
    rp2350)    CHIP=RP235x ;;
    samd20)    CHIP=ATSAMD20J18A; export PATH="$PWD/../common/samd20/bin:$PATH" ;;
    *) echo "unknown BOARD $BOARD" >&2; exit 2 ;;
esac
PR="--chip $CHIP${PROBE:+ --probe $PROBE}"
podman run --rm -v "$PWD/..":/work:Z -w /work/counter-check "$IMG" \
    sh -c "make clean >/dev/null; make BOARD=$BOARD" > /dev/null
probe-rs download $PR --allow-erase-all --preverify build/fw.elf 2>&1 | tail -n 1
probe-rs reset $PR 2>&1 | tail -n 1
# board_init waits ~1 s before it starts the counter; the run takes < 1 s.
sleep "${WAIT:-15}"
words=$(probe-rs read $PR b32 0x20000000 30 | sed 's/^[0-9a-fA-F]*://' | tr -s ' \n' ' ')
python3 - "$BOARD" $words <<'PY'
import sys
b = sys.argv[1]; w = [int(x, 16) for x in sys.argv[2:]]
magic, done, board_id, clk, ovh, n = w[:6]
assert magic == 0x564C4343, f"bad magic {magic:#x}"
assert done == 1, "not done"
nops, mn, mx = w[6:6 + n], w[6 + n:6 + 2 * n], w[6 + 2 * n:6 + 3 * n]
print(f"{b}: {clk / 1e6:g} MHz, BOARD_READ_OVERHEAD {ovh}")
print("  NOPs   raw min   raw max   min - min(0)")
for k, a, z in zip(nops, mn, mx):
    print(f"  {k:4}   {a:7}   {z:7}   {a - mn[0]:6}")
PY
