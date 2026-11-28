#!/bin/bash
# The pools concurrency series' board jobs: enqueues ONE job given by its name into our lab's job queue
# (not published; a reader repeats a run with run-isr.py directly), so that each job is enqueued only with
# the reviewer's OK.
#   OK="who gave it" C=<series commit, 40 hex> bash kinds/pools-isr/enqueue.sh JOB     JOB e.g. GS, G1
# Every job: worktree ~/vl-wt-pools-isr-series at the series commit (detached, clean, built there with
# kinds/pools-isr/onebuild.sh); read-options.py first, into the job's run directory; then run-isr.py.
# Output ~/vl-wt-pools-isr-runs/<board>/<job>/. A smoke (xS) writes the board's bundle and runs our four
# rows (the three controls and the interrupts-off reference); the series job (x1) runs every image and
# writes nothing.
set -eu
W=$HOME/vl-wt-pools-isr-series
C="${C:?set C to the series commit (40 hex digits)}"
BQ="python3 -I $HOME/vl-wt-kind-pools/lab/tools/boardqueue.py"
OUT=$HOME/vl-wt-pools-isr-runs
OK="${OK:?set OK to who gave it}"
OURS=adapter_ref,adapter_broken_isr_alloc,adapter_broken_isr_free,adapter_ref_primask
job() {   # JOB LAB BOARD WRITES RUNS WAIT TIMEOUT EXTRA
    local j=$1 lab=$2 b=$3 w=$4 runs=$5 wait=$6 to=$7 extra=$8 d
    d="$OUT/$b/$j"
    local nowrite=()
    [ $w = 0 ] && nowrite=(--refuse "FLASH WRITE")
    $BQ add $lab --worktree $W --commit $C --cwd kinds/pools-isr --timeout $to --writes $w --ok "$OK" --note "pools-isr $j" \
        --expect "done: $runs runs, 0 without a file, $w flash writes" --refuse "NOT CAUGHT" --refuse "STOPPED" \
        "${nowrite[@]}" \
        -- bash -c "mkdir -p '$d' && python3 -I ../../lab/tools/read-options.py $b '$d/options.json' && python3 -I run-isr.py $b '$d' --wait $wait $([ $w = 1 ] && echo --flash) $extra"
}
case "${1:?job}" in
  GS) job GS nucleo-g474re stm32g474 1 4  60  1500  "--adapter $OURS" ;;
  G1) job G1 nucleo-g474re stm32g474 0 14 60  3000  "" ;;
  BS) job BS nucleo-g0b1re stm32g0b1 1 4  60  1500  "--adapter $OURS" ;;
  B1) job B1 nucleo-g0b1re stm32g0b1 0 13 60  3000  "" ;;
  DS) job DS sam-d20-xpro  samd20    1 4  60  1500  "--adapter $OURS" ;;
  D1) job D1 sam-d20-xpro  samd20    0 13 60  3000  "" ;;
  HS) job HS nucleo-h723zg stm32h723 1 4  60  1500  "--adapter $OURS" ;;
  H1) job H1 nucleo-h723zg stm32h723 0 14 60  3000  "" ;;
  NS) job NS nrf5340dk     nrf5340   1 4  60  1500  "--adapter $OURS" ;;
  N1) job N1 nrf5340dk     nrf5340   0 14 60  3000  "" ;;
  PS) job PS pico2         rp2350    1 4  480 5000  "--adapter $OURS" ;;
  P1) job P1 pico2         rp2350    0 14 480 15000 "" ;;
  *) echo "no job $1"; exit 2 ;;
esac
