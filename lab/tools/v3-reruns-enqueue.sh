#!/bin/bash
# Method version 3, the reruns of the nRF5340 DK and the NUCLEO-H723ZG: enqueues ONE job given by its name,
# so that each job is enqueued only with the reviewer's OK (DECISIONS 2026-11-26).
#   bash enqueue-reruns.sh JOB        JOB as in lab/plans/2026-11-26-v3-reruns-jobs.md (e.g. N1, H3)
# Every job: worktree ~/vl-wt-v3-series at the series commit 4032f80; read-options.py first, into the job's
# run directory; then the runner. Output ~/vl-wt-crc-runs/v3/<board>/<job>/.
set -eu
W=$HOME/vl-wt-v3-series; C=4032f809fd8d5d78260efb18b3d07ecd7132242e
BQ="python3 -I $HOME/vl-wt-kind-pools/lab/tools/boardqueue.py"
OUT=$HOME/vl-wt-crc-runs/v3
OK="${OK:?set OK to who gave it}"
job() {   # JOB LAB BOARD KIND BUNDLE WRITES RUNS TIMEOUT EXTRA
    local j=$1 lab=$2 b=$3 kind=$4 n=$5 w=$6 runs=$7 to=$8 extra=$9 cwd runner opts d
    d="$OUT/$b/$j"
    if [ $kind = crc ]; then cwd=kinds/crc/bench; runner="python3 run-crc.py"; opts=../../../lab/tools/read-options.py
    else cwd=firmware/nrf5340-rb-bench; runner="python3 run-one.py"; opts=../../lab/tools/read-options.py; fi
    local nowrite=()
    [ $w = 0 ] && nowrite=(--refuse "FLASH WRITE")
    $BQ add $lab --worktree $W --commit $C --cwd $cwd --timeout $to --writes $w --ok "$OK" --note "v3 rerun $j" \
        --expect "done: $runs runs, 0 without a file, $w flash writes" --refuse "errors [1-9]" \
        "${nowrite[@]}" \
        -- bash -c "mkdir -p '$d' && python3 -I $opts $b '$d/options.json' && $runner $b '$d' --bundle $n $([ $w = 1 ] && echo --flash) $extra"
}
case "${1:?job}" in
  # nRF5340 DK (nrf5340dk): smoke on CRC 25, then CRC 25-28, then version 2 0-4
  N0) job N0 nrf5340dk nrf5340 crc 25 1 2   900  "--passes 1 --only 2" ;;
  N1) job N1 nrf5340dk nrf5340 crc 25 0 144 3600 "--passes 2" ;;
  N2) job N2 nrf5340dk nrf5340 crc 26 1 168 4200 "--passes 2" ;;
  N3) job N3 nrf5340dk nrf5340 crc 27 1 106 2700 "--passes 2" ;;
  N4) job N4 nrf5340dk nrf5340 crc 28 1 142 3600 "--passes 2" ;;
  N5) job N5 nrf5340dk nrf5340 v2 0 1 168 1800 "--passes 2" ;;
  N6) job N6 nrf5340dk nrf5340 v2 1 1 168 1800 "--passes 2" ;;
  N7) job N7 nrf5340dk nrf5340 v2 2 1 162 1800 "--passes 2" ;;
  N8) job N8 nrf5340dk nrf5340 v2 3 1 150 1800 "--passes 2" ;;
  N9) job N9 nrf5340dk nrf5340 v2 4 1 120 1500 "--passes 2" ;;
  # NUCLEO-H723ZG (nucleo-h723zg): smoke on CRC 25, then CRC 25-28, then version 2 0-4
  H0) job H0 nucleo-h723zg stm32h723 crc 25 1 2   900  "--passes 1 --only 2" ;;
  H1) job H1 nucleo-h723zg stm32h723 crc 25 0 144 3000 "--passes 2" ;;
  H2) job H2 nucleo-h723zg stm32h723 crc 26 1 168 3300 "--passes 2" ;;
  H3) job H3 nucleo-h723zg stm32h723 crc 27 1 154 3300 "--passes 2" ;;
  H4) job H4 nucleo-h723zg stm32h723 crc 28 1 142 3000 "--passes 2" ;;
  H5) job H5 nucleo-h723zg stm32h723 v2 0 1 168 2400 "--passes 2" ;;
  H6) job H6 nucleo-h723zg stm32h723 v2 1 1 168 2400 "--passes 2" ;;
  H7) job H7 nucleo-h723zg stm32h723 v2 2 1 162 2400 "--passes 2" ;;
  H8) job H8 nucleo-h723zg stm32h723 v2 3 1 150 2400 "--passes 2" ;;
  H9) job H9 nucleo-h723zg stm32h723 v2 4 1 56  1200 "--passes 2" ;;
  *) echo "no job $1"; exit 2 ;;
esac
