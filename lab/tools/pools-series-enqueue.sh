#!/bin/bash
# The pools kind's first series (lab/plans/2026-11-26-pools-series-jobs.md): enqueues ONE job given by its
# name, so that each job is enqueued only with the reviewer's OK.
#   OK="who gave it" bash lab/tools/pools-series-enqueue.sh JOB      JOB e.g. GS, G1, BS, DS, HS, NS, PS
# Every job: worktree ~/vl-wt-pools-series at the series commit f12caf7 (detached); read-options.py first,
# into the job's run directory; then kinds/pools/bench/run-pools.py. Output ~/vl-wt-pools-runs/<board>/<job>/.
# A smoke (xS) runs two configurations whole (8 placements, 2 passes) on the board's first bundle and writes
# it; the series job on the same bundle writes nothing.
set -eu
W=$HOME/vl-wt-pools-series; C=f12caf72e130b0e5dabf163dd688bfe87c8d881f
BQ="python3 -I $HOME/vl-wt-kind-pools/lab/tools/boardqueue.py"
OUT=$HOME/vl-wt-pools-runs
OK="${OK:?set OK to who gave it}"
job() {   # JOB LAB BOARD BUNDLE WRITES RUNS TIMEOUT EXTRA
    local j=$1 lab=$2 b=$3 n=$4 w=$5 runs=$6 to=$7 extra=$8 d
    d="$OUT/$b/$j"
    local nowrite=()
    [ $w = 0 ] && nowrite=(--refuse "FLASH WRITE")
    $BQ add $lab --worktree $W --commit $C --cwd kinds/pools/bench --timeout $to --writes $w --ok "$OK" --note "pools $j" \
        --expect "done: $runs runs, 0 without a file, $w flash writes" --refuse "errors [1-9]" \
        "${nowrite[@]}" \
        -- bash -c "mkdir -p '$d' && python3 -I ../../../lab/tools/read-options.py $b '$d/options.json' && python3 run-pools.py $b '$d' --bundle $n --passes 2 $([ $w = 1 ] && echo --flash) $extra"
}
case "${1:?job}" in
  # NUCLEO-G474RE: bundles 101 (smoke, then all), 100, 102
  GS) job GS nucleo-g474re stm32g474 101 1 32  1000 "--adapter adapter_atomic_pool,adapter_memorypool" ;;
  G1) job G1 nucleo-g474re stm32g474 101 0 84  1600 "" ;;
  G2) job G2 nucleo-g474re stm32g474 100 1 84  1700 "" ;;
  G3) job G3 nucleo-g474re stm32g474 102 1 8   800  "" ;;
  # NUCLEO-G0B1RE: bundles 101 (smoke, then all), 100, 102
  BS) job BS nucleo-g0b1re stm32g0b1 101 1 32  1300 "--adapter adapter_atomic_pool,adapter_memorypool" ;;
  B1) job B1 nucleo-g0b1re stm32g0b1 101 0 68  2100 "" ;;
  B2) job B2 nucleo-g0b1re stm32g0b1 100 1 84  2500 "" ;;
  B3) job B3 nucleo-g0b1re stm32g0b1 102 1 8   800  "" ;;
  # SAM D20 Xplained Pro: bundles 200 (smoke, then all), 201, 202, 203, 204
  DS) job DS sam-d20-xpro samd20 200 1 32  2000 "--adapter adapter_etl,adapter_riot" ;;
  D1) job D1 sam-d20-xpro samd20 200 0 42  2400 "" ;;
  D2) job D2 sam-d20-xpro samd20 201 1 42  2400 "" ;;
  D3) job D3 sam-d20-xpro samd20 202 1 42  2400 "" ;;
  D4) job D4 sam-d20-xpro samd20 203 1 26  1700 "" ;;
  D5) job D5 sam-d20-xpro samd20 204 1 8   1000 "" ;;
  # NUCLEO-H723ZG: bundles 50 (smoke, then all), 51
  HS) job HS nucleo-h723zg stm32h723 50 1 32  1000 "--adapter adapter_atomic_pool,adapter_etl" ;;
  H1) job H1 nucleo-h723zg stm32h723 50 0 168 2500 "" ;;
  H2) job H2 nucleo-h723zg stm32h723 51 1 8   800  "" ;;
  # nRF5340 DK: bundles 50 (smoke, then all), 51; only after N9 and its records' run directories are safe
  NS) job NS nrf5340dk nrf5340 50 1 32  1300 "--adapter adapter_atomic_pool,adapter_etl" ;;
  N1) job N1 nrf5340dk nrf5340 50 0 168 4300 "" ;;
  N2) job N2 nrf5340dk nrf5340 51 1 8   800  "" ;;
  # Pico 2: bundle 12 (smoke with the write: alone, in parts; then all)
  PS) job PS pico2 rp2350 12 1 32  3600 "--adapter adapter_atomic_pool,adapter_etl" ;;
  P1) job P1 pico2 rp2350 12 0 176 15000 "" ;;
  *) echo "no job $1"; exit 2 ;;
esac
