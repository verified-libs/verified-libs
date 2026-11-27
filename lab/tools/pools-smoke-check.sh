#!/bin/bash
# After a pools smoke job (lab/plans/2026-11-26-pools-series-jobs.md): the job's check, then records of its two
# configurations made from the smoke's run directory (outside the repository) and rebuilt by poolverify.sh at
# the series commit (which compares the sizes too). No board is touched. Exit 0 only if the check passed, two
# records were made, both with their sizes, and both MATCH.
#   bash lab/tools/pools-smoke-check.sh BOARD JOB CLOCK_HZ        e.g. stm32g474 GS 170000000
set -u
b=${1:?board} j=${2:?job} clock=${3:?clock}
W=$HOME/vl-wt-pools-series
d=$HOME/vl-wt-pools-runs/$b/$j
recs=$HOME/vl-wt-pools-runs/$b/$j-records
python3 -I $HOME/vl-v3-proof/check_job.py "$d" 32 "$clock" "$b" || exit 1
rm -rf "$recs"
python3 -I $W/kinds/pools/bench/poolrecords.py --out "$recs" "$d" || { echo "FAULT $b $j: records not made"; exit 1; }
n=$(find "$recs" -name '*.json' | wc -l)
[ "$n" = 2 ] || { echo "FAULT $b $j: $n records, 2 expected"; exit 1; }
for r in "$recs"/*/*.json; do
    jq -e '.sizes | (.code_bytes > 0) and (.ram_bytes >= 1056) and (.flash_bytes == .code_bytes + .const_bytes)' "$r" >/dev/null \
        || { echo "FAULT $b $j: $(basename "$r"): sizes missing or not whole"; exit 1; }
done
mkdir -p $HOME/vl-v3-proof/tmp
TMPDIR=$HOME/vl-v3-proof/tmp VL_LIBS_FROM=$HOME/vl-next/kind-pools bash $W/kinds/pools/bench/poolverify.sh "$recs"/*/*.json \
    || { echo "FAULT $b $j: poolverify did not MATCH"; exit 1; }
echo "SMOKE OK $b $j: check passed, 2 records, both MATCH"
