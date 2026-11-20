#!/bin/bash
# The publication re-run (lab/plans/2026-11-18-review-and-v1.md step 8;
# DECISIONS 2026-11-16: every record shown at publication is made at the
# published commit). Per board, from its own copy of the tree
# (~/vl-night/<board>, as night-all.sh), one thing after the other:
#   1. code size (firmware/nrf5340-rb-bench/size.sh; no board)
#   2. the benchmarks from flash: every set (spsc, mp, rust) at every
#      placement shift (0, 4, ..., 28); on the nRF5340 also Nordic's
#      nrf_ringbuf (SET=nordic, shift 0) if the nRF5 SDK copy is there
#   3. the ISR stress campaign for ISR_HOURS hours (overnight.sh, settings
#      as night-all.sh; one flag set, -O2, as the reference campaign of
#      2026-11-15 that repeat.sh compares with: FLAGS="..." for more)
#   4. the multi-producer campaign for MP_HOURS hours (campaign.sh,
#      AIM_SLOW=all)
# The stress campaigns come one after the other because the G0B1, G474 and
# SAM D20 need different bundles for the two tests (campaign.sh).
#
# The tree must be clean: the records carry its commit, and "+dirty" records
# cannot be published (ALLOW_DIRTY=1 for a smoke test). Every board runs
# detached (nohup setsid) and holds the board's lock (~/vl-dev/<board>.lock).
# Every step has a hard time limit.
#
# Flash wear (count it in the report): one write per benchmark image
# (3 sets x 8 shifts = 24 per board, 25 on the nRF5340) plus the bundles of
# the two campaigns. That is why this runs once, for publication.
#
# Usage (on lib-lab1, from the repository):
#   bash lab/tools/publication-rerun.sh ISR_HOURS MP_HOURS [board ...]   (default: all six)
# Smoke test:
#   ALLOW_DIRTY=1 SETS=spsc SHIFTS=0 SIZE=0 MAX_RUNS=2 TRANSFERS_OVERRIDE=20000 \
#     bash lab/tools/publication-rerun.sh 1 1 nucleo-g474re
# Output: ~/lab-runs/publication-<UTC>/<board>.log (one line per step),
# <board>.pid, <board>-bench.tsv, the benchmark logs, and <board>.done at
# the end; the records and campaign directories go where the scripts put
# them (~/lab-runs).
set -uo pipefail

say() { echo "$(date -u +%FT%TZ) $b: $*"; }

one() {   # runs in the board's copy of the tree
    cd "$(dirname "$0")/../.." || exit 2
    echo $$ > "$PUB_DIR/$b.pid"
    local conf vidpid serial FWB PROBE rc set sh
    conf=$(awk -v b="$b" '!/^#/ && NF >= 6 && $1 == b { print; exit }' lab/boards.conf)
    [ -n "$conf" ] || { say "not in lab/boards.conf"; exit 2; }
    read -r _ _ _ vidpid serial FWB _ <<< "$conf"
    PROBE=$vidpid:$serial
    exec 9>"$HOME/vl-dev/$b.lock"
    flock -n 9 || { say "busy (another check or campaign holds its lock)"; exit 2; }
    say "start at $(cat COMMIT): size=$SIZE, sets '$SETS' at shifts '$SHIFTS', ISR $ISR_H h (flags '$FLAGS'), MP $MP_H h"

    if [ "$SIZE" = 1 ]; then
        rc=0
        ( cd firmware/nrf5340-rb-bench && BOARD=$FWB timeout -k 30 3600 bash size.sh ) > "$PUB_DIR/$b-size.log" 2>&1 || rc=$?
        say "size: exit $rc"
    fi

    bench_one() {   # SET SHIFT: one benchmark image; once more after a power cycle if it fails
        local set=$1 sh=$2 log=$PUB_DIR/$b-bench-$1-shift$2.log rc try
        for try in 1 2; do
            rc=0
            ( cd firmware/nrf5340-rb-bench && BOARD=$FWB PROBE=$PROBE SET=$set SHIFT=$sh timeout -k 30 2400 bash run.sh flash ) > "$log" 2>&1 || rc=$?
            [ $rc = 0 ] && break
            if [ $try = 1 ]; then
                say "bench $set shift $sh: exit $rc, power cycle and one more try"
                mv "$log" "$log.try1"
                bash lab/tools/boardpower.sh cycle "$b" 5 >> "$log.try1" 2>&1 || say "power cycle failed"
            fi
        done
        say "bench $set shift $sh: exit $rc"
        printf '%s\t%s\t%s\t%s\t%s\n' "$set" "$sh" "$rc" "$try" "$(sed -n 's/^record: //p' "$log" | tail -1)" >> "$PUB_DIR/$b-bench.tsv"
    }
    for set in $SETS; do
        for sh in $SHIFTS; do bench_one "$set" "$sh"; done
    done
    if [ "$FWB" = nrf5340 ] && [ -n "$SETS" ]; then
        if [ -f firmware/nrf5340-rb-bench/build/libs/nrf5-sdk/SHA256 ] || [ -n "${NRF5_SDK:-}" ]; then
            bench_one nordic 0
        else
            say "bench nordic: skipped, no nRF5 SDK copy (NRF5_SDK=path/to/the/zip)"
        fi
    fi

    # Two campaigns that start in the same second would share a directory
    # (campaign.sh names it by the second): starts are 2 s apart.
    start_gap() { ( flock 8; sleep 2 ) 8>"$HOME/vl-dev/campaign-start.lock"; }

    if [ "$ISR_H" -gt 0 ]; then
        local extra=()
        [ "$b" = pico2 ] && extra=(NO_CACHE_OFF=1 ROTATION_SMP=1)   # as night-all.sh
        start_gap; rc=0
        ( cd firmware/nrf5340-rb-stress && env BOARD="$b" OUTDIR_TAG="$b" FLAGS_ROTATION="$FLAGS" PER_LIB=1 "${extra[@]}" \
            timeout -k 60 $((ISR_H * 3600 + 10800)) bash overnight.sh "$ISR_H" ) > /dev/null 2>&1 || rc=$?
        say "ISR campaign: exit $rc, $(ls -dt "$HOME"/lab-runs/overnight-*-"$b" 2>/dev/null | head -1)"
    fi

    flock -u 9; exec 9>&-   # campaign.sh takes the board's lock itself
    if [ "$MP_H" -gt 0 ]; then
        start_gap; rc=0
        ( cd firmware/rb-mp-stress && env BOARD="$b" AIM_SLOW=all \
            timeout -k 60 $((MP_H * 3600 + 10800)) bash campaign.sh "$MP_H" ) > /dev/null 2>&1 || rc=$?
        say "MP campaign: exit $rc, $(dirname "$(grep -l "board $b " "$HOME"/lab-runs/mp-campaign-*/campaign.log 2>/dev/null | tail -1)")"
    fi
    say "done"
    cp "$PUB_DIR/$b.log" "$PUB_DIR/$b.done"
}

if [ "${1:-}" = --one ]; then b=$2; one; exit 0; fi

REPO=$(cd "$(dirname "$0")/../.." && pwd)
case "${1:-}" in ''|*[!0-9]*) sed -n '2,36p' "$0"; exit 2 ;; esac
case "${2:-}" in ''|*[!0-9]*) sed -n '2,36p' "$0"; exit 2 ;; esac
export ISR_H=$1 MP_H=$2; shift 2
BOARDS=("$@")
[ ${#BOARDS[@]} -gt 0 ] || BOARDS=(nrf5340dk nucleo-g0b1re nucleo-g474re nucleo-h723zg sam-d20-xpro pico2)
export SETS=${SETS-"spsc mp rust"} SHIFTS=${SHIFTS:-"0 4 8 12 16 20 24 28"} SIZE=${SIZE:-1} FLAGS=${FLAGS:-"-O2"}
commit=$(bash "$REPO/lab/tools/source-commit.sh" "$REPO")
case $commit in *+dirty|unknown)
    [ "${ALLOW_DIRTY:-0}" = 1 ] || { echo "the tree is not a clean commit ($commit): commit first (ALLOW_DIRTY=1 for a smoke test)" >&2; exit 2; } ;;
esac
mkdir -p "$HOME/vl-dev"
for b in "${BOARDS[@]}"; do
    grep -q "^$b " "$REPO/lab/boards.conf" || { echo "$b: not in lab/boards.conf" >&2; exit 2; }
    ( exec 9>"$HOME/vl-dev/$b.lock"; flock -n 9 ) || { echo "$b: busy (its lock is held); nothing started" >&2; exit 2; }
done
export PUB_DIR=$HOME/lab-runs/publication-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$PUB_DIR"
echo "$commit" > "$PUB_DIR/COMMIT"
for b in "${BOARDS[@]}"; do
    dst=$HOME/vl-night/$b
    mkdir -p "$dst"
    rsync -a --delete --exclude 'site/_build' \
        --exclude 'build/*.o' --exclude 'build/flash' --exclude 'build/sram' --exclude 'build/ccm' \
        --exclude 'build/itcm' --exclude 'build/fw.*' --exclude 'build/.board' \
        "$REPO/firmware" "$REPO/lab" "$dst/"
    echo "$commit" > "$dst/COMMIT"   # source_commit in the records
    echo "$b: $commit -> $dst, log $PUB_DIR/$b.log"
    ( cd "$dst" && b=$b nohup setsid bash lab/tools/publication-rerun.sh --one "$b" > "$PUB_DIR/$b.log" 2>&1 & )
done
echo "started: $PUB_DIR"
