#!/bin/bash
# Short stress checks during development, on several boards in parallel
# (firmware/nrf5340-rb-stress/README.md, "Quick checks").
#
# Usage (on lib-lab1):
#   lab/tools/check.sh quick|medium|full [BOARD...]
#     quick   modes single and sweep; boards (default): nrf5340dk
#             nucleo-g0b1re; with LIBS=... only those libraries (+ the
#             negative control): a few minutes
#     medium  modes single and sweep, all libraries, all boards: 10-15 min
#     full    every mode (with smp on the Pico 2; sweep2 with 2 start
#             positions), all boards: about 1 h
#   CHECK_MODES="sweep2 ..." replaces the level's modes (run.sh modes)
#   BOARD: names from lab/boards.conf (default: see above; medium and full:
#   all six). Parameters: TRANSFERS=20000, SWEEP_REPS=16 (CHECK_PARAMS
#   adds more STRESS_PARAMS, e.g. "-DCACHE_ON=0u").
#
# Each board runs from its own copy of the working tree (~/vl-dev/<board>,
# made fresh from this tree, uncommitted changes included, so builds do not
# share a directory) under a lock (~/vl-dev/<board>.lock): a board that is
# busy with another check is refused, not shared. Not a campaign: records
# go to ~/lab-runs/check-<UTC stamp>/<board>/, which the site never reads.
# The script waits for all boards and prints one line per board and mode
# (run.sh exit code: 0 passed, 1 errors or control not caught, 2 board or
# probe failure, 3 build failure, 4 too slow); exit 0 only if all passed.
# Run it in the background for medium and full.
set -uo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
LEVEL=${1:-}; shift || true
case "$LEVEL" in
    quick)  MODES="single sweep"; DEF_BOARDS="nrf5340dk nucleo-g0b1re" ;;
    medium) MODES="single sweep"; DEF_BOARDS=all ;;
    full)   MODES="single block dma sweep sweep-block sweep-dma sweep2"; DEF_BOARDS=all ;;
    *) echo "usage: check.sh quick|medium|full [BOARD...]" >&2; exit 2 ;;
esac
MODES=${CHECK_MODES:-$MODES}
CONF=$REPO/lab/boards.conf
ALL=$(awk '!/^#/ && NF >= 6 {print $1}' "$CONF" | paste -sd' ')
BOARDS=${*:-$DEF_BOARDS}; [ "$BOARDS" = all ] && BOARDS=$ALL
for b in $BOARDS; do
    awk -v b="$b" '!/^#/ && NF >= 6 && $1 == b {f=1} END{exit !f}' "$CONF" \
        || { echo "unknown board $b (lab/boards.conf: $ALL)" >&2; exit 2; }
done
# never while a campaign runs (it uses every board) (anchored: a waiting loop that only names it in its command line is not one)
if pgrep -f "^bash overnight\.sh" >/dev/null; then
    echo "a campaign (overnight.sh) is running: no checks on its boards" >&2; exit 2
fi
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=$HOME/lab-runs/check-$STAMP
mkdir -p "$OUT"
commit=$(bash "$REPO/lab/tools/source-commit.sh" "$REPO")
echo "check $LEVEL $STAMP: boards $BOARDS; modes $MODES${LIBS:+; LIBS=$LIBS}; tree $commit; output $OUT"

one_board() {
    local b=$1 W=$HOME/vl-dev/$1 o=$OUT/$1 vidpid serial fwb modes m rc t0
    mkdir -p "$o"
    exec 9>"$HOME/vl-dev/$b.lock"
    flock -n 9 || { echo "$b busy (another check holds $HOME/vl-dev/$b.lock)" > "$o/summary"; return; }
    read -r _ _ _ vidpid serial fwb _ < <(awk -v b="$b" '!/^#/ && NF >= 6 && $1 == b {print; exit}' "$CONF")
    mkdir -p "$W"
    rsync -a --delete --exclude build --exclude __pycache__ "$REPO/firmware" "$REPO/lab" "$W/"
    mkdir -p "$W/firmware/nrf5340-rb-bench/build"
    rm -rf "${W:?}/firmware/nrf5340-rb-bench/build/libs"
    cp -al "$REPO/firmware/nrf5340-rb-bench/build/libs" "$W/firmware/nrf5340-rb-bench/build/"
    # a clean tree: the commit itself (verify-build.sh can rebuild it); with
    # uncommitted changes source-commit.sh's "+dirty" marks the copy
    echo "$commit" > "$W/COMMIT"
    modes=$MODES
    [ "$LEVEL" = full ] && [ "$fwb" = rp2350 ] && modes="$modes smp smp-block sweep-smp sweep-smp-block"
    : > "$o/summary"
    for m in $modes; do
        t0=$(date +%s)
        reps=16; case $m in sweep2*) reps=2 ;; esac   # every pair of delays: far more trials
        ( cd "$W/firmware/nrf5340-rb-stress" && \
          STRESS_PARAMS="-DTRANSFERS=20000u -DSWEEP_REPS=${reps}u ${CHECK_PARAMS:-}" PER_LIB=1 OUTDIR="$o" \
          BOARD=$fwb PROBE=$vidpid:$serial LIBS="${LIBS:-}" bash run.sh "$m" ) > "$o/$m.log" 2>&1
        rc=$?
        printf '%-14s %-16s exit %s  %4s s  %s\n' "$b" "$m" "$rc" "$(( $(date +%s) - t0 ))" \
            "$(grep -m1 'real libraries error-free' "$o/$m.log" || tail -n 1 "$o/$m.log")" >> "$o/summary"
    done
}

pids=()
for b in $BOARDS; do one_board "$b" & pids+=($!); done
wait "${pids[@]}"
cat "$OUT"/*/summary | tee "$OUT/summary.txt"
! grep -qvE ' exit 0 ' "$OUT/summary.txt"
