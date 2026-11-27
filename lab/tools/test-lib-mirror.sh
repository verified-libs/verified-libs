#!/bin/bash
# A bounded test of the library mirror (lab/tools/lib-mirror.py) as the export test uses it: in a scope of at
# most 200 tasks and 3 GB (systemd-run --user; else ulimit -v) and under a hard timeout, the three real fetch
# scripts of this tree (firmware/nrf5340-rb-bench/fetch-libs.sh, kinds/crc/fetch.sh, kinds/pools/fetch.sh) fetch
# every library of their lock files from the mirror only, with the environment `lib-mirror.py env` prints.
#   bash lab/tools/test-lib-mirror.sh [MIRROR]      exit 0: every case as expected
# Cases:
#   - every library at its pin, its checkout clean, from the mirror alone (no transport but file);
#   - no git process nested deeper than 4 (GIT_TRACE2_EVENT): no fetch calls another fetch. On 2026-11-27 a
#     blob-filtered clone from the shallow mirror nested lazy fetches some 520 deep, until the host ran out of
#     memory;
#   - control: a copy of one mirror repository that still allows blob filters; the sparse fetch must fail at
#     once (GIT_NO_LAZY_FETCH), not nest;
#   - control: the same without GIT_NO_LAZY_FETCH must nest deeper than 4 (the fault, bounded): the nesting
#     check sees it.
# Big temporary data in ${TMPDIR:-~/vl-scratch}; removed at the end. Nothing of this repository is changed.
set -uo pipefail
export LC_ALL=C
REPO=$(cd "$(dirname "$0")/../.." && pwd)
MIRROR=$(cd "${1:-${VL_LIB_MIRROR:-$HOME/vl-scratch/lib-mirror}}" && pwd) || { echo "no mirror"; exit 2; }
T=$(mktemp -d "${TMPDIR:-$HOME/vl-scratch}/vl-mirror-test.XXXXXX")
trap 'rm -rf "${T:?}"' EXIT
fails=0
python3 -I "$REPO/lab/tools/lib-mirror.py" env "$MIRROR" > "$T/env.sh" || { echo "FAIL the mirror does not hold every pin"; exit 1; }
git -C "$REPO" archive HEAD firmware/nrf5340-rb-bench kinds/crc kinds/pools | tar -x -C "$T" || exit 2
bounded() {   # LOG CMD...: in a capped scope, under a timeout, with the mirror's environment and an event trace
    local log=$1; shift
    rm -rf "$T/ev"; mkdir -p "$T/ev"
    if systemd-run --user --scope -q -p TasksMax=200 -p MemoryMax=3G -- true 2>/dev/null; then
        GIT_TRACE2_EVENT=$T/ev timeout 1200 systemd-run --user --scope -q -p TasksMax=200 -p MemoryMax=3G -- \
            bash -c '. "$1"; shift; "$@"' _ "$T/env.sh" "$@" > "$log" 2>&1
    else
        GIT_TRACE2_EVENT=$T/ev timeout 1200 bash -c 'ulimit -v 3000000; . "$1"; shift; "$@"' _ "$T/env.sh" "$@" > "$log" 2>&1
    fi
}
deepest() {   # the deepest nesting of git processes in the last bounded call
    python3 -I - "$T/ev" <<'EOF'
import json, os, sys
m = 0
for f in os.listdir(sys.argv[1]):
    for line in open(os.path.join(sys.argv[1], f), errors="replace"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("event") == "start":
            m = max(m, e["sid"].count("/") + 1)
print(m)
EOF
}
pins_ok() {   # LOCK LIBDIR: every library of LOCK at its pin in LIBDIR, clean
    local bad=0 name url commit
    while read -r name url commit _; do
        [ -n "$name" ] || continue
        [ "$(git -C "$2/$name" rev-parse HEAD 2>/dev/null)" = "$commit" ] && [ -z "$(git -C "$2/$name" status --porcelain 2>/dev/null)" ] \
            || { echo "     $name: not at ${commit:0:12} or not clean"; bad=1; }
    done < <(grep -v '^\s*#' "$1")
    return $bad
}
case_() {   # NAME LOCK LIBDIR CMD...
    local name=$1 lock=$2 libs=$3 d f; shift 3
    f=$T/$(tr -c 'A-Za-z0-9\n' _ <<<"$name")
    bounded "$f.log" "$@"; local rc=$?
    d=$(deepest)
    if [ "$rc" = 0 ] && [ "$d" -le 4 ] && pins_ok "$lock" "$libs" > "$f.pins"; then
        echo "ok   $name: $(grep -vc '^\s*#\|^\s*$' "$lock") libraries at their pins from the mirror, git nested $d deep at most"
    else
        echo "FAIL $name: exit $rc, git nested $d deep"; cat "$f.pins" 2>/dev/null; tail -n 5 "$f.log" | sed 's/^/     /'; fails=$((fails + 1))
    fi
}
case_ "version 2 (fetch-libs.sh)" "$T/firmware/nrf5340-rb-bench/libs.lock" "$T/firmware/nrf5340-rb-bench/build/libs" \
    bash "$T/firmware/nrf5340-rb-bench/fetch-libs.sh"
case_ "CRC (kinds/crc/fetch.sh)" "$T/kinds/crc/libs.lock" "$T/libs-crc" env LIBS="$T/libs-crc" bash "$T/kinds/crc/fetch.sh"
case_ "pools (kinds/pools/fetch.sh)" "$T/kinds/pools/libs.lock" "$T/libs-pools" env LIBS="$T/libs-pools" bash "$T/kinds/pools/fetch.sh"
# controls: version 2's fetch path (a blob-filtered clone with no depth, then a sparse checkout), where the fault
# showed, for Zephyr (large and sparse), from a copy of its mirror repository that allows blob filters again
V2=$T/firmware/nrf5340-rb-bench
line=$(grep -v '^\s*#' "$V2/libs.lock" | awk '$1 == "zephyr-ringbuf"')
read -r name url commit paths <<<"$line"
src=$(python3 -I -c 'import importlib.util,sys; s=importlib.util.spec_from_file_location("m", sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.repo_of(sys.argv[2], sys.argv[3]))' "$REPO/lab/tools/lib-mirror.py" "$MIRROR" "$url")
# hard links for the objects (the mirror's own files are not written), a config file of its own
cp -al "$src" "$T/filtering.git" && rm "$T/filtering.git/config" && cp "$src/config" "$T/filtering.git/config" \
    && git -C "$T/filtering.git" config uploadpack.allowFilter true
sed -i "s|=url.file://$src.insteadOf|=url.file://$T/filtering.git.insteadOf|" "$T/env.sh"
mkdir -p "$T/ctl"; cp "$V2/fetch-libs.sh" "$T/ctl/"
{ printf '%s\n' "$line"; grep -v '^\s*#' "$V2/libs.lock" | awk '$1 == "micoring"'; } > "$T/ctl/libs.lock"
bounded "$T/control.log" bash "$T/ctl/fetch-libs.sh"; rc=$?; d=$(deepest)
if [ "$rc" != 0 ] && [ "$d" -le 4 ]; then
    echo "ok   control: a mirror repository that allows blob filters: the fetch fails (exit $rc), git nested $d deep, no lazy fetch"
else
    echo "FAIL control: a mirror repository that allows blob filters: exit $rc (want not 0), git nested $d deep"; tail -n 5 "$T/control.log" | sed 's/^/     /'; fails=$((fails + 1))
fi
# control: the same without GIT_NO_LAZY_FETCH: the fault of 2026-11-27 (lazy fetches nested in each other), bounded
# by the scope; the nesting check above must see it
sed -i '/GIT_NO_LAZY_FETCH/d' "$T/env.sh"; rm -rf "$T/ctl/build"
bounded "$T/control2.log" bash "$T/ctl/fetch-libs.sh"; rc=$?; d=$(deepest)
if [ "$d" -gt 4 ]; then
    echo "ok   control: the same without GIT_NO_LAZY_FETCH: lazy fetches nest ($d deep before the bound stops them, exit $rc): the check sees the fault"
else
    echo "FAIL control: the same without GIT_NO_LAZY_FETCH: git nested only $d deep (exit $rc): the check would not see the fault"; fails=$((fails + 1))
fi
[ "$fails" = 0 ] && echo "every case as expected" || echo "$fails cases not as expected"
[ "$fails" = 0 ]
