#!/bin/bash
# A test of kinds/crc/repeat.sh in a tree exported from this repository, the
# way a reader gets it (no git history): its build step must record a commit
# that the record writer accepts, so that a repeat makes records. Without a
# board: the export of HEAD (lab/tools/public-export.py) into a throwaway
# directory, then `kinds/crc/repeat.sh --build-only BOARD` from that tree.
# Checks that
#   - the build's commit is the exported one (EXPORTED_FROM, 12 digits),
#   - kinds/crc/bench/crcrecords.py's make() does not refuse that commit,
#   - the exported tree is not written to (no kinds/crc/build in it).
#   bash lab/tools/test-crc-repeat-export.sh [BOARD]   (default stm32g0b1)
# Fetches the libraries at their pins (as a reader's repeat does) and builds
# one board's images in the toolchain image (podman), at nice 10; about a
# minute. Nothing of this repository is changed; the directory is deleted at
# the end. Exit 0: as expected.
set -uo pipefail
export LC_ALL=C
REPO=$(cd "$(dirname "$0")/../.." && pwd)
B=${1:-stm32g0b1}
T=$(mktemp -d "${TMPDIR:-/tmp}/vl-crc-repeat-test.XXXXXX")
trap 'rm -rf "${T:?}"' EXIT
fails=0
ok() { echo "ok: $*"; }
bad() { echo "FAIL: $*"; fails=$((fails + 1)); }

python3 -I "$REPO/lab/tools/public-export.py" "$T/exp" > "$T/export.log" 2>&1 || { cat "$T/export.log"; echo "FAIL: the export"; exit 1; }
want=$(cut -c1-12 "$T/exp/EXPORTED_FROM")
line=$(cd / && nice -n 10 bash "$T/exp/kinds/crc/repeat.sh" --build-only "$B" --out "$T/out" 2>&1 | tail -n 1)
echo "$line"
got=$(sed -n 's/^build: [^,]*, commit \([^,]*\), in .*/\1/p' <<<"$line")
[ "$got" = "$want" ] && ok "the build records the exported commit ($got)" || bad "the build records '$got', the export is $want"
why=$(python3 -I - "$REPO/kinds/crc/bench" "$got" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import crcrecords
_, why = crcrecords.make([{"bench_commit": sys.argv[2]}], {})
print(why or "")
PY
)
case $why in "commit "*) bad "crcrecords.py refuses the commit: $why" ;; *) ok "crcrecords.py takes the commit (next check: $why)" ;; esac
[ ! -e "$T/exp/kinds/crc/build" ] && ok "the exported tree is not written to" || bad "the exported tree has kinds/crc/build"
[ -f "$T/out/src/$want/COMMIT" ] && ok "the copy is under OUT/src/$want" || bad "no copy with COMMIT under OUT/src"
echo "$fails failed"
[ $fails -eq 0 ]
