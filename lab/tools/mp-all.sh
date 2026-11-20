#!/bin/bash
# Start the MPSC/SPMC campaign (firmware/rb-mp-stress/campaign.sh) on several
# boards at once, each from its own copy of the repository (~/vl-night/<board>),
# as night-all.sh does for the ISR campaign: run.sh builds the combined bundle
# in a shared build/ directory, so two boards never share one tree.
# Campaigns may run day or night whenever the boards are not needed for
# development (owner, 2026-11-17); stop one with kill on its process group
# when a board is needed.
#
# Usage (on lib-lab1, from the repository):
#   bash lab/tools/mp-all.sh HOURS [board ...]     (default: all six)
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
HOURS=${1:-6}; shift || true
BOARDS=("$@")
[ ${#BOARDS[@]} -gt 0 ] || BOARDS=(nrf5340dk nucleo-g0b1re nucleo-g474re nucleo-h723zg sam-d20-xpro pico2)
for b in "${BOARDS[@]}"; do
    dst=$HOME/vl-night/$b
    mkdir -p "$dst"
    rsync -a --delete --exclude 'site/_build' \
        --exclude 'build/*.o' --exclude 'build/flash' --exclude 'build/sram' --exclude 'build/ccm' \
        --exclude 'build/itcm' --exclude 'build/fw.*' --exclude 'build/.board' \
        "$REPO/firmware" "$REPO/lab" "$dst/"
    bash "$REPO/lab/tools/source-commit.sh" "$REPO" > "$dst/COMMIT"   # source_commit in the records
    echo "$b: $(cat "$dst/COMMIT") -> $dst (MP campaign, $HOURS h)"
    (cd "$dst/firmware/rb-mp-stress" && env BOARD=$b nohup setsid bash campaign.sh "$HOURS" > /dev/null 2>&1 &)
    sleep 2   # distinct start times (OUTDIR is per second)
done
