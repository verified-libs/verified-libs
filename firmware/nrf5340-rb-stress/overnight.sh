#!/bin/bash
# Unattended stress campaign: repeat the ISR <-> main stress test for HOURS
# hours, varying the settings every run, then write a morning report.
#
# Per run: new random seeds (main-loop pauses and interrupt periods), and the
# next entry of a rotation over mode (single/block), interrupt rate (timer
# prescaler 0/1/2/4 = interrupts every 160-668, 320-1336, 640-2672 or
# 2560-10688 cycles), instruction cache on/off and code in flash/SRAM. Slower
# interrupt rates move fewer bytes so every run stays within ~10-30 minutes.
# Lessons from the first campaign (2026-11-06): prescaler 4 is too slow for
# block mode (the control cannot be caught: the buffer stays full or empty),
# and the cache off with prescaler 0 starves the main loop (interrupt load
# > 100 %); neither combination is in the rotation any more.
#
# Each run writes its JSON record to OUTDIR and one line to OUTDIR/runs.tsv;
# a run that fails to finish is recorded and the campaign continues.
# At the end, summarize.py writes OUTDIR/report.md.
#
# Power cycling (lab/tools/boardpower.sh, monitor hub ports): before each run
# the board's probe must be on USB, otherwise the board is power-cycled. When
# a run fails on the board (run.sh exit 2: probe/flash error or not finished),
# the board is power-cycled and the same settings and seeds run once more
# (run id with suffix "r"). A failed build (exit 3) is not retried. The
# campaign stops early if the probe does not come back after a power cycle or
# after MAX_FAILS (default 3) failed runs in a row.
#
# Usage (on lib-lab1, detached so it survives logout; user linger is on):
#   nohup setsid bash overnight.sh [HOURS] > /dev/null 2>&1 &
# Smoke test: MAX_RUNS=2 TRANSFERS_OVERRIDE=2000 bash overnight.sh 1
#   (SWEEP_REPS_OVERRIDE=n sets the start positions of the sweep entries)
#
# Compiler flags: FLAGS_ROTATION (default "-O2") is a second rotation, e.g.
#   FLAGS_ROTATION="-O2 -Os -O3 -O2+lto -O2+clang"
#   ("+lto": link-time optimisation; "+clang": the libraries and adapters
#   built with clang, see ../common/compiler.mk).
# Order (since 2026-11-15, flash wear): the runs are grouped by build
# configuration, i.e. by flag set and then by code location, and within a
# group go through the rotation's entries for that location in order. With
# one image per library and the run parameters sent at run time (run.sh), a
# group's bundle is flashed once and only verified for the group's other
# runs, so a pass over the whole order (17 entries x the flag sets) writes
# the board's flash once per group, not once per run as the old order
# (ROTATION[n % 17] with FLAGS_ROTATION[n % len]) did. WEAR_ORDER=0 restores
# the old interleaved order.
set -uo pipefail
cd "$(dirname "$0")"
# campaigns run every library (run.sh LIBS is for quick checks only)
[ -z "${LIBS:-}" ] || { echo "overnight.sh: LIBS is set ($LIBS); campaigns run all libraries" >&2; exit 2; }
BOARD=${BOARD:-nrf5340dk}
BP=../../lab/tools/boardpower.sh
MAX_FAILS=${MAX_FAILS:-3}
HOURS=${1:-8}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
export OUTDIR=$HOME/lab-runs/overnight-$STAMP${OUTDIR_TAG:+-$OUTDIR_TAG}
mkdir -p "$OUTDIR"
LOG=$OUTDIR/campaign.log
exec >>"$LOG" 2>&1
END=$(( $(date +%s) + HOURS * 3600 ))

# Rotation over mode, interrupt rate, cache and code location ("flash",
# "sram", or the board's third location). "dma" = the zero-copy API.
# sweep* = the deterministic interrupt sweep (run.sh, main.c): no timer
# prescaler, and the last column is the number of start positions
# (SWEEP_REPS) instead of a byte count. Since 2026-11-12 the sweep entries
# replace the two prescaler-4 single-byte entries: at that interrupt rate the
# control was rarely caught on the fast cores, and the sweep covers every
# interrupt position deterministically. Also since 2026-11-12 the two
# block entries at prescaler 2 are sweep entries (sweep with the cache off,
# sweep-block from flash with the cache on), on every board: on the Pico 2
# and the H723 the control was caught in only 2/10 and 7/12 of those runs,
# and one rotation for all six boards keeps the boards comparable. Block
# mode keeps prescalers 0 and 1. 17 entries (prime: coprime to any number of flag sets below 17).
#        mode   prescaler cache code  transfers
ROTATION=(
  "single 0 1 flash 300000"
  "block  0 1 flash 300000"
  "single 2 1 flash 200000"
  "sweep  - 0 flash 256"
  "sweep  - 1 flash 256"
  "block  1 1 flash 300000"
  "single 2 0 flash 200000"
  "sweep-block - 1 flash 256"
  "single 2 1 sram  200000"
  "block  0 1 sram  300000"
  "sweep-block - 0 flash 256"
  "block  1 1 sram  300000"
  "dma    0 1 flash 300000"
  "dma    2 1 flash 200000"
  "dma    1 1 sram  300000"
  "sweep-dma - 1 flash 256"
  "sweep-block - 1 sram 256"
)
# The firmware board (common/<FW_BOARD>) and the probe come from
# lab/boards.conf: name hub port probe-vid:pid probe-serial firmware-board.
CONF_LINE=$(awk -v b="$BOARD" '!/^#/ && NF >= 6 && $1 == b { print; exit }' ../../lab/boards.conf)
[ -n "$CONF_LINE" ] || { echo "board $BOARD not in lab/boards.conf (6 columns)"; exit 2; }
read -r _ _ _ PROBE_VIDPID PROBE_SERIAL FW_BOARD _ <<< "$CONF_LINE"
PROBE=$PROBE_VIDPID:$PROBE_SERIAL

read -r -a FLAGS <<< "${FLAGS_ROTATION:--O2}"

seed() { local s; while :; do s=$(od -An -N4 -tx4 /dev/urandom | tr -d ' '); [ "$s" != 00000000 ] && break; done; echo "0x${s}u"; }

# Power-cycles the board; returns non-zero if its probe does not come back.
power_cycle() {
    echo "--- power cycle $BOARD ($1)"
    bash "$BP" cycle "$BOARD" 5
}

# One run of run.sh; sets rc and rec, appends a line to runs.tsv.
one_run() {
    local id=$1 pc=$2 start out
    start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "=== run $id $start: $mode prescaler=$pre cache=$cache code=$code transfers=$transfers seeds=$ms/$is opt=$opt lto=$lto compiler=$comp"
    rc=0
    local params="-DMAIN_SEED=$ms -DISR_SEED=$is -DTIMER_PRESCALER=${pre}u -DCACHE_ON=${cache}u -DTRANSFERS=${transfers}u"
    case $mode in sweep*) params="-DMAIN_SEED=$ms -DISR_SEED=$is -DCACHE_ON=${cache}u -DSWEEP_REPS=${transfers}u" ;; esac
    out=$(STRESS_PARAMS="$params" \
          CODE=$code BOARD=$FW_BOARD PROBE=$PROBE OPT=$opt LTO=$lto COMPILER=$comp bash run.sh "$mode" 2>&1) || rc=$?
    echo "$out" | grep -vE 'warning|note:|In file included|from |^ +[0-9]* *\||^ +\|' | tail -n 30
    rec=$(echo "$out" | sed -n 's/^record: //p')
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$start" "$mode" "$pre" "$cache" "$code" \
        "$transfers" "$ms" "$is" "$rc" "${rec:--}" "$pc" "$opt" "$lto" "$comp" >> "$OUTDIR/runs.tsv"
}

echo "campaign $STAMP: $HOURS h, until $(date -d @$END), board $BOARD (firmware $FW_BOARD, probe $PROBE), flags: ${FLAGS[*]}${NO_CACHE_OFF:+, NO_CACHE_OFF=$NO_CACHE_OFF}, PER_LIB=${PER_LIB:-0}"
printf 'run\tstart_utc\tmode\tprescaler\tcache\tcode\ttransfers\tmain_seed\tisr_seed\texit\trecord\tpower_cycled\topt\tlto\tcompiler\n' > "$OUTDIR/runs.tsv"
# Boards without a code-in-SRAM image (no LD_SRAM in board.mk, e.g. the
# SAM D20 with 32 KB RAM) run those entries from flash instead.
eff_code() { if [ "$1" = sram ] && ! grep -q '^LD_SRAM' "../common/$FW_BOARD/board.mk"; then echo flash; else echo "$1"; fi; }
# ORDER: "flag-index entry-index", grouped by flag set and code location
ORDER=()
if [ "${WEAR_ORDER:-1}" = 1 ]; then
    for fx in "${!FLAGS[@]}"; do
        for c in flash sram ccm itcm; do
            for ei in "${!ROTATION[@]}"; do
                read -r _ _ _ ec _ <<<"${ROTATION[$ei]}"
                [ "$(eff_code "$ec")" = "$c" ] && ORDER+=("$fx $ei")
            done
        done
    done
else
    for i in $(seq 0 $(( ${#ROTATION[@]} * ${#FLAGS[@]} - 1 ))); do
        ORDER+=("$((i % ${#FLAGS[@]})) $((i % ${#ROTATION[@]}))")
    done
fi
n=0; fails=0; stop=""
while [ "$(date +%s)" -lt "$END" ] && [ $n -lt ${MAX_RUNS:-1000000} ]; do
    read -r fx ei <<<"${ORDER[$((n % ${#ORDER[@]}))]}"
    read -r mode pre cache code transfers <<<"${ROTATION[$ei]}"
    code=$(eff_code "$code")
    # NO_CACHE_OFF=1: run cache-off entries with the cache on (the RP2350
    # without its XIP cache fetches every instruction over QSPI and is too
    # slow for a run to finish).
    [ "${NO_CACHE_OFF:-0}" = 1 ] && cache=1
    # ROTATION_SMP=1 (RP2350): every second pass through the rotation runs
    # single, block, sweep and sweep-block with the other side on core 1
    # instead of the interrupt (run.sh modes smp, smp-block, sweep-smp,
    # sweep-smp-block); dma and sweep-dma stay as they are.
    if [ "${ROTATION_SMP:-0}" = 1 ] && [ $(( (n / ${#ORDER[@]}) % 2 )) = 1 ]; then
        case $mode in single) mode=smp ;; block) mode=smp-block ;;
            sweep) mode=sweep-smp ;; sweep-block) mode=sweep-smp-block ;; esac
    fi
    case $mode in
        sweep*) transfers=${SWEEP_REPS_OVERRIDE:-$transfers} ;;
        *) transfers=${TRANSFERS_OVERRIDE:-$transfers} ;;
    esac
    f=${FLAGS[$fx]}
    opt=${f%%+*}; lto=0; comp=gcc
    case "$f" in *+lto*) lto=1 ;; esac
    case "$f" in *+clang*) comp=clang ;; esac
    ms=$(seed); is=$(seed)
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
    # rc 4 (still running at run.sh's time limit): too slow for this board, not
    # a board failure: no power cycle, no retry, and it does not stop the campaign.
    if [ "$rc" = 2 ] || [ "$rc" = 3 ]; then fails=$((fails + 1)); else fails=0; fi
    n=$((n + 1))
    [ "$fails" -lt "$MAX_FAILS" ] || { stop="$fails failed runs in a row"; break; }
done
[ -z "$stop" ] || echo "CAMPAIGN STOPPED EARLY: $stop"
echo "campaign done after $n runs: $(date -u)"
python3 summarize.py "$OUTDIR" > "$OUTDIR/report.md" 2>&1
echo "report: $OUTDIR/report.md"
