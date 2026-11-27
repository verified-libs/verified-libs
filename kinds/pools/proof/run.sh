#!/bin/bash
# CBMC on the reference pool (ref_harness.c), in the toolchain image (cbmc 6.6.0).
# Then the same harness against the broken builds of the reference, each of which
# must be refuted: the proof is shown to be able to fail.
#   bash proof/run.sh      (in the image, from kinds/pools)
set -uo pipefail
cd "$(dirname "$0")"
FLAGS="--unwind 9 --unwinding-assertions --bounds-check --pointer-check --signed-overflow-check -DPOOL_BLOCKS=4 -DPOOL_BLOCK_SIZE=32 -I.."
rc=0
run() {   # NAME EXPECT EXTRA-FLAGS
    out=$(timeout 3600 cbmc $FLAGS $3 ref_harness.c 2>&1); r=$?
    if [ $r = 0 ]; then got=pass; elif [ $r = 10 ]; then got=FAIL; else got="error $r"; fi
    first=$(grep -m1 -E "^\[.*\] .*: FAILURE" <<<"$out" | sed 's/^ *//')
    printf '%-34s %-6s (expected %s)  %s\n' "$1" "$got" "$2" "$( [ "$got" = FAIL ] && echo "$first" || grep -m1 -E 'VERIFICATION|properties' <<<"$out")"
    [ "$got" = "$2" ] || rc=1
}
run "reference free list (ours)" pass ""
run "broken: block handed out twice" FAIL "-DPOOL_BROKEN=1"
run "broken: block lost" FAIL "-DPOOL_BROKEN=2"
echo "$([ $rc = 0 ] && echo 'exit 0: every verdict as expected' || echo 'exit 1: a verdict not as expected')"
exit $rc
