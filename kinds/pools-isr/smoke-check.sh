#!/bin/bash
# The check after a smoke job of the pools concurrency series (lab/plans/2026-11-27-pools-isr-jobs.md):
# records made from the smoke's run directory, outside the repository, with isrrecords.py: four records
# (the three controls caught, the interrupts-off reference passing), each with option registers and some
# coverage. Run in the series worktree, in the toolchain image for objdump:
#   bash kinds/pools-isr/smoke-check.sh RUNDIR
# Exit 0: as expected. The records it makes are deleted at the end.
set -euo pipefail
cd "$(dirname "$0")"
D=$(cd "${1:?run directory}" && pwd)
T=$(mktemp -d "${TMPDIR:-/tmp}/vl-isr-smoke.XXXXXX")
trap 'rm -rf "${T:?}"' EXIT
podman run --rm -v "$PWD/../..":/work:Z -v "$D":/run:ro,Z -v "$T":/out:Z -w /work/kinds/pools-isr \
    verified-libs/toolchain:2026-11-13 python3 -I isrrecords.py --out /out /run | tee "$T/check.txt"
n=$(find "$T" -name 'adapter_*.json' | wc -l)
grep -q "^4 records, 0 problems" "$T/check.txt" && [ "$n" = 4 ] || { echo "FAIL: not four records without a problem"; exit 1; }
for f in "$T"/*/adapter_*.json; do
    jq -e '.coverage.reached > 0 and (.option_registers | length) > 0' "$f" >/dev/null || { echo "FAIL: $f: no coverage or no options"; exit 1; }
done
echo "smoke check: as expected"
