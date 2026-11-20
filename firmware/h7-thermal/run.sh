#!/bin/bash
# Build, flash and follow h7-thermal on the NUCLEO-H723ZG (README.md): the
# die temperature once a second, printed every 10 s, and a JSON record at
# the end (OUTDIR, default ~/lab-runs/stm32h723-thermal-<time>.json).
# Environment: PROBE (probe-rs selector), IDLE_S, LOAD_S, COOL_S, LIMIT_C
# SAMPLE_MS (compiled in; defaults 60, 600, 300, 85, 1000).
set -euo pipefail
cd "$(dirname "$0")"
IMG=verified-libs/toolchain:2026-11-05
PR="--chip STM32H723ZG${PROBE:+ --probe $PROBE}"
EXTRA=""
for v in IDLE_S LOAD_S COOL_S LIMIT_C SAMPLE_MS; do [ -n "${!v:-}" ] && EXTRA="$EXTRA -D$v=${!v}"; done
if [ "${FOLLOW:-0}" != 1 ]; then   # FOLLOW=1: only follow a run already going on the board
podman run --rm -v "$PWD/..":/work:Z -w /work/h7-thermal "$IMG" sh -c "make clean >/dev/null; make EXTRA='$EXTRA'" > /dev/null
probe-rs download $PR --preverify build/fw.elf 2>&1 | tail -n 1
probe-rs reset $PR 2>&1 | tail -n 1
fi
OUT=${OUTDIR:-$HOME/lab-runs}/stm32h723-thermal-$(date -u +%Y%m%dT%H%M%SZ).json
rd() { probe-rs read $PR b32 0x20000000 "$1" 2>/dev/null | sed 's/^[0-9a-fA-F]*://' | tr -s ' \n' ' '; }
HDR=15   # words before the samples (main.c struct results)
while :; do
    sleep 10
    w=($(rd $HDR)) || continue
    [ "${#w[@]}" -ge $HDR ] || continue
    n=$((16#${w[3]})); done=$((16#${w[5]}))
    if [ "$n" -gt 0 ]; then
        s=($(probe-rs read $PR b32 $(printf '0x%x' $((0x20000000 + 4 * (HDR + 4 * (n - 1))))) 4 2>/dev/null | sed 's/^[0-9a-fA-F]*://'))
        python3 - "${w[11]}" "${w[12]}" "${s[@]}" "$n" <<'PY'
import sys
t0v, ramp = int(sys.argv[1], 16), int(sys.argv[2], 16)
t_ms, mf, pclk, ph = (int(x, 16) for x in sys.argv[3:7]); n = sys.argv[7]
t0 = 130 if (t0v >> 16) & 3 else 30
T = t0 + (pclk * 15 / mf - 100 * (t0v & 0xFFFF)) / (ramp & 0xFFFF) if mf and ramp else float("nan")
print(f"{t_ms / 1000:6.0f} s  phase {['', 'idle 64 MHz', 'load 520 MHz', 'cool 64 MHz', 'done'][ph]:13} {T:5.1f} C  ({n} samples)", flush=True)
PY
    fi
    [ "$done" = 1 ] && break
done
words=$(rd $((HDR + 4 * n)))
python3 - "$OUT" $words <<'PY'
import json, sys
out = sys.argv[1]; w = [int(x, 16) for x in sys.argv[2:]]
assert w[0] == 0x564C5448, "bad magic"
n = w[3]; t0v, ramp = w[11], w[12] & 0xFFFF
t0 = 130 if (t0v >> 16) & 3 else 30; fmt0 = t0v & 0xFFFF; smp = w[10]
rows = []
for i in range(n):
    t_ms, mf, pclk, ph = w[15 + 4 * i: 19 + 4 * i]
    T = t0 + (pclk * smp / mf - 100 * fmt0) / ramp
    rows.append({"t_s": t_ms / 1000, "phase": ["", "idle", "load", "cool"][ph], "celsius": round(T, 2),
                 "mfreq": mf, "pclk_hz": pclk})
rec = {"schema": "h7-thermal/1", "board": "NUCLEO-H723ZG", "core_hz_load": 520000000, "core_hz_idle": 64000000,
       "idle_s": w[6], "load_s": w[7], "cool_s": w[8], "limit_c": w[9], "aborted": bool(w[4]),
       "load_iterations": w[13], "sample_ms": w[14], "dts": {"t0_c": t0, "fmt0_100hz": fmt0, "ramp_hz_per_c": ramp, "smp_time": smp},
       "samples": rows}
json.dump(rec, open(out, "w"), indent=1)
by = {}
for r in rows:
    by.setdefault(r["phase"], []).append(r["celsius"])
for p in ("idle", "load", "cool"):
    v = by.get(p, [])
    if v:
        print(f"{p:5}: start {v[0]:.1f} C, end {v[-1]:.1f} C, max {max(v):.1f} C ({len(v)} samples)")
print("aborted at the limit" if rec["aborted"] else "not aborted", "| record:", out)
PY
