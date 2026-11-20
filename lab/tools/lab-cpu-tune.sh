#!/bin/bash
# Fix the CPU frequency for reproducible measurements. Run as root at every boot
# (installed as /usr/local/sbin/lab-cpu-tune and started by lab-cpu-tune.service).
set -eu

# 3.0 GHz: just below the 7840U's 3.3 GHz base clock, so the thin laptop
# can hold it during long runs without thermal throttling.
FREQ_KHZ=3000000

cpu=/sys/devices/system/cpu
if [ -w "$cpu/cpufreq/boost" ]; then echo 0 > "$cpu/cpufreq/boost"; fi

for p in "$cpu"/cpufreq/policy*; do
    # Per-policy boost is rejected when global boost is already off; that's fine.
    echo 0 > "$p/boost" 2>/dev/null || true
    echo performance > "$p/scaling_governor"
    # Lower max first, so min is never above max.
    echo "$FREQ_KHZ" > "$p/scaling_max_freq"
    echo "$FREQ_KHZ" > "$p/scaling_min_freq"
done

# Let the unprivileged measuring user read package energy (RAPL).
# Acceptable on a dedicated lab machine with no secrets.
chmod a+r /sys/class/powercap/intel-rapl:*/energy_uj
