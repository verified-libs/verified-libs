#!/bin/bash
# Build, flash and run nrf5340-cyccnt on lib-lab1, then print the results.
# Usage (on lib-lab1, from this folder): bash run.sh
set -euo pipefail
cd "$(dirname "$0")"
IMG=verified-libs/toolchain:2026-11-05
# Application core only: the network core is blank and stays locked, and the
# stock nRF5340_xxAA target would erase the chip to unlock it on every attach.
CHIP=nRF5340_xxAA_APPONLY
strip() { sed 's/\x1b\[[0-9;]*m//g'; }

podman run --rm -v "$PWD":/work:Z "$IMG" sh -c 'make clean >/dev/null; make' >/dev/null

# Erase-all is allowed only here: a blank or foreign chip is locked.
probe-rs download --chip $CHIP --allow-erase-all --preverify build/fw.elf 2>&1 | strip | tail -n 1
probe-rs reset --chip $CHIP 2>&1 | strip
sleep 2   # first boot writes UICR and resets itself

# From here on no erase is allowed: if the chip is locked, fail instead.
words=$(probe-rs read --chip $CHIP b32 0x20000000 15 2>&1 | strip \
        | awk '{for (i = 2; i <= NF; i++) print $i}')
set -- $words
[ "${1:-}" = 564c4231 ] || { echo "no results (bad magic): $words" >&2; exit 1; }
[ "$3" = 00000001 ] || { echo "measurement not finished" >&2; exit 1; }
h() { printf '%d' "0x$1"; }
echo "hfclkctrl=$(h $4) (1 = HCLK 64 MHz)  runs=$(h $5)  cache_at_reset=$(h ${15})"
printf '%-16s min=%4d max=%4d mean=%.3f\n' \
    overhead       "$(h $6)"  "$(h $7)"  "$(echo "$(h $8)/$(h $5)" | bc -l)" \
    nop100_nocache "$(h $9)"  "$(h ${10})" "$(echo "$(h ${11})/$(h $5)" | bc -l)" \
    nop100_cache   "$(h ${12})" "$(h ${13})" "$(echo "$(h ${14})/$(h $5)" | bc -l)"
