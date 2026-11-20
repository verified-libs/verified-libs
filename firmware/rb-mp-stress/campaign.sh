#!/bin/bash
# Unattended MPSC/SPMC campaign: repeat the rb-mp-stress test for HOURS hours,
# varying the settings every run, then write a report (summarize.py).
#
# Per run: new random seeds for the main loop and both interrupts, and the
# next entry of a rotation over mode (mpsc/spmc), interrupt rate (timer
# prescaler 1-4: each interrupt every 320-1336 ... 2560-10688 cycles) and
# code location (flash/SRAM). Since 2026-11-15 mode, seeds, rate and
# transfers are run parameters (run.sh): one image per code location, so
# the first half of the campaign runs from flash and the second half from
# SRAM, and the board's flash is written twice per campaign at most instead
# of once per run (flash wears out). Takes the board's lock
# (~/vl-dev/<board>.lock, as lab/tools/check.sh). Prescaler 0 is left out: with two interrupts
# every 160-700 cycles the main loop starves (2026-11-08, every library).
# A run counts as valid only if the control (an SPSC queue used with two
# producers / consumers) was caught and no library starved; summarize.py
# reads that from the JSON records, so runs that are invalid show as such
# and never as passes.
#
# Power cycling as in ../nrf5340-rb-stress/overnight.sh: before each run the
# probe must be on USB; a run that fails on the board (run.sh exit 2) is
# retried once after a power cycle; the campaign stops after MAX_FAILS
# (default 3) failed runs in a row or if the probe does not come back.
#
# One library per reset (since 2026-11-17, the owner's decision after
# reports/2026-11-17-mp-per-library-validation.md): PER_LIB=1 (default)
# runs every library from its own image over the serial port, from the
# bundle shared with the ISR stress test (run.sh IMAGES=combined), so a
# library cannot affect another and switching between the two tests.
# campaigns writes no flash where one bundle holds both (nRF5340, H723,
# RP2350; G0B1/G474/SAM D20 need more bundles: run the campaigns of the two
# tests one after the other, not interleaved). Records -perlib-combined;
# not pooled with the one-image records (PER_LIB=0, the way before).
# The combined bundle is built in ../nrf5340-rb-stress/build: run each
# board's campaign in its own copy of the tree (as lab/tools/night-all.sh
# does, ~/vl-night/<board>), never two boards from one tree.
# Coverage (since 2026-11-17, the owner's decision after
# reports/2026-11-17-mp-coverage-prototype.md): COVERAGE=1 (default) builds
# the images with main.c's vl_cov (where every interrupt landed, per
# library: cov_report.py, run on all records at the end; recorded in the
# prescaler 3/4 runs only: at prescaler 1 the recording's cost starved the
# M0+ boards' main loop, so the faster runs switch it off, cov_off) and makes half of
# the slow runs (prescaler 3 and 4) aimed: SysTick pends the interrupts
# 1..COV_WINDOW (default 160) cycles after a push/pop starts (COV_AIM=1),
# alternating which ones each pass of the rotation. Aimed runs count like
# any other (valid only if the control was caught); the report lists them
# apart. COVERAGE=0: the images and rotation as before.
# AIM_SLOW=all (default since 2026-11-19, the owner's decision): every
# prescaler 3/4 run is aimed. In the campaign of 2026-11-17/18 (AIM_SLOW=half)
# the random runs at those rates often did not catch the control (on the
# Pico 2 never), so they were invalid and cost board time; the aimed ones
# caught it in 210 of 210 (reports/2026-11-18-mp-campaign-coverage.md).
# Random interrupts are then used at prescaler 1 and 2 only.
# Usage (on lib-lab1, detached):
#   nohup setsid bash campaign.sh [HOURS] > /dev/null 2>&1 &
# Smoke test: MAX_RUNS=2 TRANSFERS_OVERRIDE=20000 bash campaign.sh 1
set -uo pipefail
cd "$(dirname "$0")"
BOARD=${BOARD:-nrf5340dk}
BP=../../lab/tools/boardpower.sh
MAX_FAILS=${MAX_FAILS:-3}
AIM_SLOW=${AIM_SLOW:-all}
case $AIM_SLOW in all|half) ;; *) echo "AIM_SLOW must be all or half" >&2; exit 2;; esac
HOURS=${1:-6}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
export OUTDIR=$HOME/lab-runs/mp-campaign-$STAMP
mkdir -p "$OUTDIR"
LOG=$OUTDIR/campaign.log
exec >>"$LOG" 2>&1
END=$(( $(date +%s) + HOURS * 3600 ))

#        mode prescaler transfers   (first half: code in flash, then SRAM)
ROTATION=(
  "mpsc 1 1000000"
  "spmc 1 1000000"
  "mpsc 2 1000000"
  "spmc 2 1000000"
  "mpsc 3 500000"
  "spmc 3 500000"
  "mpsc 4 300000"
  "spmc 4 300000"
)
HALF=$(( $(date +%s) + HOURS * 1800 ))
PER_LIB=${PER_LIB:-1}
COVERAGE=${COVERAGE:-1}
case "$COVERAGE" in 1) COV_FLAG="-DCOVERAGE=1 " ;; 0) COV_FLAG="" ;; *) echo "COVERAGE must be 0 or 1"; exit 2 ;; esac
COV_WINDOW=${COV_WINDOW:-160}
case "$PER_LIB" in 1) PL_ARGS="IMAGES=combined LIB_LIMIT=${LIB_LIMIT:-1800}" ;; 0) PL_ARGS="" ;;
    *) echo "PER_LIB must be 0 or 1"; exit 2 ;; esac
CONF_LINE=$(awk -v b="$BOARD" '!/^#/ && NF >= 6 && $1 == b { print; exit }' ../../lab/boards.conf)
[ -n "$CONF_LINE" ] || { echo "board $BOARD not in lab/boards.conf"; exit 2; }
read -r _ _ _ PROBE_VIDPID PROBE_SERIAL FW_BOARD _ <<< "$CONF_LINE"
PROBE=$PROBE_VIDPID:$PROBE_SERIAL
mkdir -p "$HOME/vl-dev"
exec 9>"$HOME/vl-dev/$BOARD.lock"
flock -n 9 || { echo "board $BOARD is busy (another check or campaign holds its lock)"; exit 2; }

seed() { local s; while :; do s=$(od -An -N4 -tx4 /dev/urandom | tr -d ' '); [ "$s" != 00000000 ] && break; done; echo "0x${s}u"; }
power_cycle() { echo "--- power cycle $BOARD ($1)"; bash "$BP" cycle "$BOARD" 5; }

one_run() {
    local id=$1 pc=$2 start out
    start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "=== run $id $start: $mode prescaler=$pre code=$code transfers=$transfers seeds=$ms/$sa/$sb aim=$aim"
    rc=0
    out=$(COV_OFF=$((pre < 3)) COV_AIM=$aim COV_WINDOW=$COV_WINDOW COV_SEED=$cs MP_PARAMS="$COV_FLAG-DMAIN_SEED=$ms -DSEED_A=$sa -DSEED_B=$sb -DTIMER_PRESCALER=${pre}u -DTRANSFERS=${transfers}u" \
          CODE=$code BOARD=$FW_BOARD PROBE=$PROBE PER_LIB=$PER_LIB env $PL_ARGS bash run.sh "$mode" 2>&1) || rc=$?
    echo "$out" | grep -vE 'warning|note:|In file included|from |^ +[0-9]* *\||^ +\|' | tail -n 20
    rec=$(echo "$out" | sed -n 's/^record: //p')
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$start" "$mode" "$pre" "$code" \
        "$transfers" "$ms" "$sa" "$sb" "$rc" "${rec:--}" "$pc" "$aim" >> "$OUTDIR/runs.tsv"
}

echo "mp campaign $STAMP: $HOURS h, until $(date -d @$END), board $BOARD (firmware $FW_BOARD, probe $PROBE), PER_LIB=$PER_LIB, COVERAGE=$COVERAGE (window $COV_WINDOW)"
printf 'run\tstart_utc\tmode\tprescaler\tcode\ttransfers\tmain_seed\tseed_a\tseed_b\texit\trecord\tpower_cycled\taim\n' > "$OUTDIR/runs.tsv"
n=0; fails=0; stop=""
while [ "$(date +%s)" -lt "$END" ] && [ $n -lt ${MAX_RUNS:-1000000} ]; do
    read -r mode pre transfers <<<"${ROTATION[$((n % ${#ROTATION[@]}))]}"
    code=flash; [ "$(date +%s)" -ge "$HALF" ] && [ "$FW_BOARD" != samd20 ] && code=sram   # SAM D20: flash only
    transfers=${TRANSFERS_OVERRIDE:-$transfers}
    ms=$(seed); sa=$(seed); sb=$(seed); cs=$(seed); cs=${cs%u}
    # aimed: every prescaler 3/4 run (AIM_SLOW=all, the default), or half of them, alternating per pass (AIM_SLOW=half)
    aim=0; [ "$COVERAGE" = 1 ] && [ "$pre" -ge 3 ] && { [ "$AIM_SLOW" = all ] || [ $(( (n / ${#ROTATION[@]} + n) % 2 )) = 1 ]; } && aim=1
    pc=no
    if ! bash "$BP" status "$BOARD" | grep -q 'probe present'; then
        power_cycle "probe missing before run $n" || { stop="probe missing and not back after a power cycle"; break; }
        pc=yes
    fi
    one_run "$n" "$pc"
    if [ "$rc" = 2 ]; then
        power_cycle "run $n failed on the board" || { stop="probe not back after a power cycle"; break; }
        one_run "${n}r" yes
    fi
    if [ "$rc" = 2 ] || [ "$rc" = 3 ]; then fails=$((fails + 1)); else fails=0; fi
    n=$((n + 1))
    [ "$fails" -lt "$MAX_FAILS" ] || { stop="$fails failed runs in a row"; break; }
done
[ -z "$stop" ] || echo "CAMPAIGN STOPPED EARLY: $stop"
echo "campaign done after $n runs: $(date -u)"
[ "$COVERAGE" = 1 ] && timeout 3600 python3 cov_report.py $(awk -F'\t' 'NR > 1 && $11 != "-" && $11 !~ /-norec-/ {print $11}' "$OUTDIR/runs.tsv") \
    > "$OUTDIR/coverage.txt" 2>&1
python3 summarize.py "$OUTDIR" > "$OUTDIR/report.md" 2>&1
echo "report: $OUTDIR/report.md"
