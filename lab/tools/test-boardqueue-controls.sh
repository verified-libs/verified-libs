#!/bin/bash
# The controls of lab/tools/test_boardqueue.py: copies of boardqueue.py with one rule taken out each, and the
# test that must then fail. Exit 0 only if every control is caught.
#   bash lab/tools/test-boardqueue-controls.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d "${TMPDIR:-/tmp}/boardqueue-controls-XXXXXX")
trap 'rm -rf "$T"' EXIT
fails=0
control() {   # NAME TEST SED-EXPRESSION
    local name=$1 test=$2 expr=$3
    sed "$expr" "$HERE/boardqueue.py" > "$T/bq.py"
    if cmp -s "$HERE/boardqueue.py" "$T/bq.py"; then
        echo "FAIL $name: the rule was not found in boardqueue.py"; fails=$((fails + 1)); return
    fi
    if VL_BOARDQUEUE_UNDER_TEST="$T/bq.py" timeout 300 python3 -I "$HERE/test_boardqueue.py" "$test" > "$T/out" 2>&1; then
        echo "FAIL $name: $test passed without the rule"; fails=$((fails + 1))
    else
        echo "ok   $name: $test fails without the rule"
    fi
}
control "the Pico 2 writes alone" Queue.test_pico_writes_alone 's/exclusive=(board == PICO)/exclusive=False/'
control "the write budget" Queue.test_write_budget_and_ledger 's/if state\["writes"\] > job\["write_budget"\] and not state\["over"\]:/if False:/'
control "a failure stops its board" Queue.test_failure_stops_only_its_own_board 's/print(f"{now()} {board}: STOPPED; the other boards go on")/continue/'
[ "$fails" = 0 ] && echo "every control caught" || echo "$fails controls not caught"
exit $(( fails > 0 ))
