#!/bin/bash
# A test of kinds/pools/repeat.sh in a tree exported from this repository,
# the way a reader gets it (no git history): its build step must record a
# commit that the record writer accepts, so that a repeat makes records. As
# lab/tools/test-crc-repeat-export.sh, for the pools kind. Without a board:
# the export of HEAD (lab/tools/public-export.py) into a throwaway directory,
# then `kinds/pools/repeat.sh --build-only BOARD` from that tree. Checks that
#   - the build's commit is the exported one (EXPORTED_FROM, 12 digits),
#   - kinds/pools/bench/poolrecords.py's make() does not refuse that commit,
#   - the exported tree is not written to (no kinds/pools/build in it),
#   - the copy of the sources is under OUT/src/<commit> with its COMMIT file,
#   - the comparison (bench/poolscompare.py) finds our records of the board
#     the same as themselves, and those of another board different.
#   bash lab/tools/test-pools-repeat-export.sh [BOARD]   (default stm32g0b1)
# Fetches the libraries at their pins (as a reader's repeat does) and builds
# one board's images in the toolchain image (podman), at nice 10; a few
# minutes. Nothing of this repository is changed; the directory is deleted
# at the end (TMPDIR: put it on a disk, not in /tmp). Exit 0: as expected.
set -uo pipefail
export LC_ALL=C
REPO=$(cd "$(dirname "$0")/../.." && pwd)
B=${1:-stm32g0b1}
T=$(mktemp -d "${TMPDIR:-/tmp}/vl-pools-repeat-test.XXXXXX")
trap 'rm -rf "${T:?}"' EXIT
fails=0
ok() { echo "ok: $*"; }
bad() { echo "FAIL: $*"; fails=$((fails + 1)); }

python3 -I "$REPO/lab/tools/public-export.py" "$T/exp" > "$T/export.log" 2>&1 || { cat "$T/export.log"; echo "FAIL: the export"; exit 1; }
want=$(cut -c1-12 "$T/exp/EXPORTED_FROM")
line=$(cd / && nice -n 10 bash "$T/exp/kinds/pools/repeat.sh" --build-only "$B" --out "$T/out" 2>&1 | tail -n 1)
echo "$line"
got=$(sed -n 's/^build: [^,]*, commit \([^,]*\), in .*/\1/p' <<<"$line")
[ "$got" = "$want" ] && ok "the build records the exported commit ($got)" || bad "the build records '$got', the export is $want"
why=$(python3 -I - "$REPO/kinds/pools/bench" "$got" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import poolrecords
_, why = poolrecords.make([{"bench_commit": sys.argv[2]}], {})
print(why or "")
PY
)
case $why in "commit "*) bad "poolrecords.py refuses the commit: $why" ;; *) ok "poolrecords.py takes the commit (next check: $why)" ;; esac
[ ! -e "$T/exp/kinds/pools/build" ] && ok "the exported tree is not written to" || bad "the exported tree has kinds/pools/build"
[ -f "$T/out/src/$want/COMMIT" ] && [ "$(cat "$T/out/src/$want/COMMIT")" = "$want" ] \
    && ok "the copy is under OUT/src/$want, with its COMMIT" || bad "no copy with COMMIT under OUT/src"
ls "$T/out/src/$want/kinds/pools/build/v2/$B"/bundle*.json >/dev/null 2>&1 \
    && ok "the copy has the board's bundles ($(ls "$T/out/src/$want/kinds/pools/build/v2/$B"/bundle*.json | wc -l))" \
    || bad "no bundles of $B in the copy"
cmp_=$T/exp/kinds/pools/bench/poolscompare.py
other=stm32g474; [ "$B" = stm32g474 ] && other=stm32g0b1
python3 -I "$cmp_" "$T/exp/records/pools/$B" "$T/exp/records/pools/$B" > "$T/cmp-same.txt" 2>&1
[ $? = 0 ] && ok "poolscompare.py: our records of $B are the same as themselves ($(sed -n 3p "$T/cmp-same.txt"))" \
    || { bad "poolscompare.py does not find our records of $B the same as themselves"; cat "$T/cmp-same.txt"; }
python3 -I "$cmp_" "$T/exp/records/pools/$other" "$T/exp/records/pools/$B" > "$T/cmp-other.txt" 2>&1
[ $? = 1 ] && ok "poolscompare.py: the records of $other differ from those of $B (control)" \
    || bad "poolscompare.py does not tell $other from $B"
echo "$fails failed"
[ $fails -eq 0 ]
