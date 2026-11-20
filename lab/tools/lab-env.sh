#!/bin/bash
# Print this machine's measurement environment as one JSON object.
# Installed as /usr/local/bin/lab-env.
set -eu

cpu=/sys/devices/system/cpu
p0=$cpu/cpufreq/policy0
r() { cat "$1" 2>/dev/null || true; }

sens=$(sensors -j 2>/dev/null || echo '{}')
tctl=$(jq '[.[] | objects | .Tctl.temp1_input? // empty] | .[0]' <<<"$sens")
nvme=$(jq '[.[] | objects | .Composite.temp1_input? // empty] | .[0]' <<<"$sens")

jq -n \
  --arg time "$(date -u +%FT%TZ)" \
  --arg host "$(hostname)" \
  --arg kernel "$(uname -r)" \
  --arg cmdline "$(r /proc/cmdline)" \
  --arg model "$(LC_ALL=C lscpu | sed -n 's/^Model name: *//p')" \
  --arg microcode "$(grep -m1 '^microcode' /proc/cpuinfo | awk '{print $3}')" \
  --arg driver "$(r $p0/scaling_driver)" \
  --arg governor "$(r $p0/scaling_governor)" \
  --arg epp "$(r $p0/energy_performance_preference)" \
  --arg boost "$(r $cpu/cpufreq/boost)" \
  --arg fmin "$(r $p0/scaling_min_freq)" \
  --arg fmax "$(r $p0/scaling_max_freq)" \
  --arg isolated "$(r $cpu/isolated)" \
  --arg nohz "$(r $cpu/nohz_full)" \
  --arg ac "$(cat /sys/class/power_supply/A*/online 2>/dev/null | head -1)" \
  --arg load "$(cut -d' ' -f1-3 /proc/loadavg)" \
  --arg gcc "$(gcc -dumpfullversion 2>/dev/null || true)" \
  --argjson tctl "${tctl:-null}" \
  --argjson nvme "${nvme:-null}" \
  '{
     time: $time, host: $host, kernel: $kernel, cmdline: $cmdline,
     cpu: {model: $model, microcode: $microcode},
     cpufreq: {driver: $driver, governor: $governor, epp: $epp,
               boost: ($boost == "1"),
               min_khz: (($fmin | tonumber?) // null),
               max_khz: (($fmax | tonumber?) // null)},
     isolated_cpus: $isolated, nohz_full: $nohz,
     ac_power: ($ac == "1"),
     temp_c: {tctl: $tctl, nvme: $nvme},
     loadavg: $load,
     compiler: {gcc: $gcc}
   }'
