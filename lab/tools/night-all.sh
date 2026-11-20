#!/bin/bash
# Start an unattended stress campaign on several boards at once, each from
# its own copy of the repository (~/vl-night/<board>), because run.sh builds
# in a shared build/ directory. Every board has its own probe and its own
# switchable USB port (lab/boards.conf), so the campaigns do not interfere.
#
# Usage (on lib-lab1, from the repository):
#   bash lab/tools/night-all.sh HOURS [board ...]     (default: all six)
# Smoke test: MAX_RUNS=2 TRANSFERS_OVERRIDE=20000 bash lab/tools/night-all.sh 1
# Per-board settings below; FLAGS_ROTATION has 5 entries (coprime to the
# 17-entry rotation in overnight.sh). -Os+lto since 2026-11-13: the size
# build with link-time optimisation that many products ship.
# One library per reset (run.sh PER_LIB=1, control and results over the
# board's serial port) since 2026-11-14: a library that hangs or overwrites
# memory costs only its own result. PER_LIB=0 for the old way (all libraries
# in one start); campaigns of the two kinds are not added together on the
# comparison page (gen_libdata: this file is part of the test).
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
HOURS=${1:-8}; shift || true
BOARDS=("$@")
[ ${#BOARDS[@]} -gt 0 ] || BOARDS=(nrf5340dk nucleo-g0b1re nucleo-g474re nucleo-h723zg sam-d20-xpro pico2)
FLAGS=${FLAGS:-"-Os -O3 -O2+lto -O2+clang -Os+lto"}   # FLAGS="-O2" etc. to choose
PER_LIB=${PER_LIB:-1}
for b in "${BOARDS[@]}"; do
    extra=""
    case $b in
        pico2) extra="NO_CACHE_OFF=1 ROTATION_SMP=1" ;;   # XIP cache off is too slow; SMP every 2nd pass
    esac
    dst=$HOME/vl-night/$b
    mkdir -p "$dst"
    # Same tree as the repository (build outputs excluded; fetched libraries
    # kept so each copy need not fetch them again).
    rsync -a --delete --exclude 'site/_build' \
        --exclude 'build/*.o' --exclude 'build/flash' --exclude 'build/sram' --exclude 'build/ccm' \
        --exclude 'build/itcm' --exclude 'build/fw.*' --exclude 'build/.board' \
        "$REPO/firmware" "$REPO/lab" "$dst/"
    bash "$REPO/lab/tools/source-commit.sh" "$REPO" > "$dst/COMMIT"   # source_commit in the records
    echo "$b: $(cat "$dst/COMMIT") -> $dst (PER_LIB=$PER_LIB $extra)"
    (cd "$dst/firmware/nrf5340-rb-stress" && env BOARD=$b OUTDIR_TAG=$b FLAGS_ROTATION="$FLAGS" PER_LIB=$PER_LIB $extra \
        nohup setsid bash overnight.sh "$HOURS" > /dev/null 2>&1 &)
    sleep 2   # distinct start times
done
