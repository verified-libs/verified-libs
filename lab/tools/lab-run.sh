#!/bin/bash
# Run a command on the isolated benchmark cores and record environment,
# wall time, package energy and temperature as JSON.
# Installed as /usr/local/bin/lab-run.
#
# Usage: lab-run [-c CPULIST] [-o FILE] -- command [args...]
#   -c  CPUs to run on (default: the kernel's isolated CPUs). The command gets
#       this CPU mask; multithreaded benchmarks should pin their own threads.
#   -o  JSON output file (default: ~/lab-runs/<UTC time>.json)
#
# Energy is the whole package (RAPL), not only the isolated cores.
set -euo pipefail

cpus=$(cat /sys/devices/system/cpu/isolated)
out=""
while getopts "c:o:" opt; do
    case $opt in
        c) cpus=$OPTARG ;;
        o) out=$OPTARG ;;
        *) exit 2 ;;
    esac
done
shift $((OPTIND - 1))
[ "${1:-}" = "--" ] && shift
[ $# -gt 0 ] || { echo "usage: lab-run [-c cpus] [-o file] -- command [args...]" >&2; exit 2; }
[ -n "$cpus" ] || { echo "lab-run: no isolated CPUs, pass -c" >&2; exit 2; }

rapl=/sys/class/powercap/intel-rapl:0
range=$(cat "$rapl/max_energy_range_uj")

env_before=$(lab-env)
e0=$(cat "$rapl/energy_uj")
t0=$(date +%s%N)
set +e
taskset -c "$cpus" "$@"
rc=$?
set -e
t1=$(date +%s%N)
e1=$(cat "$rapl/energy_uj")
env_after=$(lab-env)

if [ "$e1" -ge "$e0" ]; then de=$((e1 - e0)); else de=$((e1 + range - e0)); fi

if [ -z "$out" ]; then
    mkdir -p "$HOME/lab-runs"
    out="$HOME/lab-runs/$(date -u +%Y%m%dT%H%M%S%NZ).json"
fi

jq -n \
  --argjson before "$env_before" \
  --argjson after "$env_after" \
  --arg cmd "$*" --arg cpus "$cpus" \
  --argjson rc "$rc" --argjson ns "$((t1 - t0))" --argjson uj "$de" \
  '{
     schema: "lab-run/0.1",
     command: $cmd, cpus: $cpus, exit_code: $rc,
     wall_s: ($ns / 1e9),
     energy: {package_j: ($uj / 1e6)},
     env: $before,
     temp_after_c: $after.temp_c
   }' > "$out"

echo "lab-run: $out" >&2
exit "$rc"
