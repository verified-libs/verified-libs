#!/bin/bash
# Repeat our CRC results on your own board, with one command. As the
# repository's repeat.sh (benchmark version 2), for the CRC kind.
#
#   kinds/crc/repeat.sh                 quick: up to three configurations of
#                                       one bundle, two passes (Pico 2: 34 min)
#   kinds/crc/repeat.sh --level full    every configuration of the board,
#                                       two passes (our series: 33 min to 3 h 40)
#   kinds/crc/repeat.sh --board pico2   choose a board when more than one is
#                                       connected (names as in ../../repeat.sh)
#   kinds/crc/repeat.sh --out DIR       where the results go (default
#                                       ~/verified-libs-repeat/crc-BOARD-TIME)
#   kinds/crc/repeat.sh --check         only check the tools and find the board
#   kinds/crc/repeat.sh --build-only B  only build the images of board directory B
#                                       (rp2350, stm32g474 ...), no board needed:
#                                       prints the commit the build records
#
# What it does: finds the board as ../../repeat.sh --check does; builds the
# images of this tree in the toolchain image (bench/onebuild.sh; the libraries
# are fetched once at their pins, libs.lock, into build/libs); writes a bundle
# that is not on the board to it and runs its images (bench/run-crc.py, two
# passes, as our series); makes records of the runs (bench/crcrecords.py) and
# compares them with ours under records/crc (bench/crccompare.py); packs
# everything into one archive to send us (site/content/reproduce.md).
# In a tree exported from our repository (no git history, EXPORTED_FROM), the
# images are built and run from a copy of the sources under OUT/src/<commit>
# whose COMMIT file holds the exported commit (lab/tools/source-commit.sh
# reads it), as ../../repeat.sh does: the records then name a commit that can
# be rebuilt, and this tree is not written to. The copy is removed before the
# archive is packed (--build-only keeps it). In a git checkout everything
# happens in this tree, at its HEAD.
# The records name the commit they were measured at; this tree builds the
# images of our records byte for byte if its CRC test sources are those of
# that commit (bash kinds/crc/bench/crcverify.sh checks that without a
# board), and the comparison says for every image whether yours is the same.
#
# Needs: Linux, git, podman, jq, python3, probe-rs 0.32 (OpenOCD 0.12 for the
# SAM D20) and the toolchain image verified-libs/toolchain:2026-11-13, as
# ../../repeat.sh. Flash: the quick level writes one bundle, the full level
# every bundle of the board (nRF5340 DK 3, NUCLEO-G0B1RE 5, NUCLEO-G474RE 5,
# NUCLEO-H723ZG 3, SAM D20 Xplained Pro 9, Pico 2 1); a bundle that is on the
# board already is not written.
set -uo pipefail
KIND=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$KIND/../.." && pwd)
LEVEL=quick; BOARD=; OUT=; CHECK_ONLY=0; BUILD_ONLY=
while [ $# -gt 0 ]; do
    case $1 in
        --level) LEVEL=$2; shift ;;
        --board) BOARD=$2; shift ;;
        --out) OUT=$2; shift ;;
        --check) CHECK_ONLY=1 ;;
        --build-only) BUILD_ONLY=$2; shift ;;
        -h|--help) sed -n '2,42p' "$0"; exit 0 ;;
        *) echo "unknown argument $1 (--help)" >&2; exit 2 ;;
    esac
    shift
done
case $LEVEL in quick|full) ;; *) echo "--level quick|full" >&2; exit 2 ;; esac
say() { printf '%s\n' "$*"; }
die() { printf 'kinds/crc/repeat.sh: %s\n' "$*" >&2; exit 2; }

src_kind() {   # the kind's directory to build and run in, printed (see the head of this file)
    local c w
    if [ ! -f "$REPO/EXPORTED_FROM" ]; then echo "$KIND"; return; fi
    c=$(cut -c1-12 "$REPO/EXPORTED_FROM"); w=$OUT/src/$c
    if [ ! -d "$w" ]; then
        mkdir -p "$w" && cp -a "$REPO/kinds" "$REPO/firmware" "$REPO/lab" "$w/" || die "could not copy the sources to $w"
        rm -rf "${w:?}/kinds/crc/build" "${w:?}/firmware/nrf5340-rb-bench/build"
        echo "$c" > "$w/COMMIT"
    fi
    echo "$w/kinds/crc"
}

drop_src() {   # the copies of the sources (src_kind), with their libraries and images: not for the archive
    local c
    for c in "$OUT"/src/*; do
        [ -d "$c" ] && [ -f "$c/COMMIT" ] && rm -rf "${c:?}"
    done
    rmdir "$OUT/src" 2>/dev/null
    return 0
}

if [ -n "$BUILD_ONLY" ]; then   # the build step alone, without a board
    [ -d "$REPO/firmware/common/$BUILD_ONLY" ] || die "--build-only: no board directory $BUILD_ONLY"
    OUT=${OUT:-$HOME/verified-libs-repeat/crc-build-$BUILD_ONLY-$(date -u +%Y%m%dT%H%M%SZ)}
    mkdir -p "$OUT/logs" && OUT=$(cd "$OUT" && pwd)
    SRC=$(src_kind) || exit 2
    ( cd "$SRC/bench" && LIBS=$SRC/build/libs bash onebuild.sh table "$BUILD_ONLY" ) > "$OUT/logs/build.log" 2>&1 \
        || die "the build failed ($OUT/logs/build.log)"
    say "build: $BUILD_ONLY, commit $(jq -r .bench_commit "$SRC/build/v2/$BUILD_ONLY/build.json"), in $SRC"
    exit 0
fi

# the board, its probe and the tools: as the repository's repeat.sh finds them
found=$(bash "$REPO/repeat.sh" --check --only stress ${BOARD:+--board "$BOARD"}) || exit 2
line=$(grep -m1 '^board: ' <<<"$found")
BOARD=$(sed -n 's/^board: \([^ ]*\) (probe \([^)]*\)).*/\1/p' <<<"$line")
PROBE=$(sed -n 's/^board: \([^ ]*\) (probe \([^)]*\)).*/\2/p' <<<"$line")
[ -n "$BOARD" ] && [ -n "$PROBE" ] || die "no board found: $found"
case $BOARD in
    nrf5340dk) FWB=nrf5340 ;; nucleo-g0b1re) FWB=stm32g0b1 ;; nucleo-g474re) FWB=stm32g474 ;;
    nucleo-h723zg) FWB=stm32h723 ;; sam-d20-xpro) FWB=samd20 ;; pico2) FWB=rp2350 ;;
esac
ours=$REPO/records/crc/$FWB
ls "$ours"/*.json >/dev/null 2>&1 || die "no CRC records of ours for $BOARD (records/crc/$FWB)"
say "board: $BOARD (probe $PROBE), level $LEVEL, CRC kind"
[ "$CHECK_ONLY" = 1 ] && { say "tools and board OK"; exit 0; }

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=${OUT:-$HOME/verified-libs-repeat/crc-$BOARD-$STAMP}
mkdir -p "$OUT/logs" && OUT=$(cd "$OUT" && pwd)
: > "$OUT/summary.txt"
note() { say "$*"; printf '%s\n' "$*" >> "$OUT/summary.txt"; }
note "verified-libs repeat, CRC kind, on $BOARD, level $LEVEL, $STAMP; from $(git -C "$REPO" rev-parse --short=12 HEAD 2>/dev/null || cut -c1-12 "$REPO/EXPORTED_FROM" 2>/dev/null || echo unknown)"

say "building the images (once: fetching the pinned libraries) ..."
SRC=$(src_kind) || exit 2
LIBS=$SRC/build/libs
( cd "$SRC/bench" && LIBS=$LIBS bash onebuild.sh table "$FWB" ) > "$OUT/logs/build.log" 2>&1 \
    || { note "FAILED: the build (logs/build.log)"; drop_src; exit 1; }
BUILT=$SRC/build/v2/$FWB
sel=; bundles=
if [ "$LEVEL" = quick ]; then   # the first bundle, up to three configurations that lie wholly (eight placements) in it
    bundles=$(ls "$BUILT" | sed -n 's/^bundle\([0-9]*\)\.json$/\1/p' | sort -n | head -1)
    sel=$(jq -r '[.images | group_by(.adapter)[] | select(length == 8) | .[0].adapter] | .[0:3] | join(",")' "$BUILT/bundle$bundles.json")
    [ -n "$sel" ] || { note "FAILED: no whole configuration in bundle $bundles"; drop_src; exit 1; }
fi
say "running ${sel:+configurations $sel, }two passes; a bundle that is not on the board is written to it ..."
( cd "$SRC/bench" && PROBE=$PROBE python3 run-crc.py "$FWB" "$OUT/runs" --flash --passes 2 \
    ${bundles:+--bundle "$bundles"} ${sel:+--adapter "$sel"} ) > "$OUT/logs/run.log" 2>&1
rc=$?
python3 -I "$KIND/bench/crcrecords.py" --out "$OUT/records" "$OUT/runs" > "$OUT/logs/records.log" 2>&1
if [ $rc -ne 0 ] || ! ls "$OUT/records/$FWB"/*.json >/dev/null 2>&1; then
    note "FAILED (run-crc.py exit $rc: 1 a run without a result, 2 probe or board; logs/run.log, logs/records.log)"
else
    note "runs: $(grep -o '[0-9]* runs, .* flash writes' "$OUT/runs/run.log" | tail -n 1); $(tail -n 1 "$OUT/logs/records.log")"
    python3 -I "$KIND/bench/crccompare.py" "$ours" "$OUT/records/$FWB" > "$OUT/compare.txt" 2>&1
    case $? in 0) note "same as ours ($(sed -n 3p "$OUT/compare.txt"))" ;;
               1) note "DIFFERS from ours, see compare.txt" ;;
               *) note "could not be compared, see compare.txt" ;; esac
fi
{
    echo "board: $BOARD ($FWB)"; echo "probe: $PROBE"
    echo "host: $(uname -srm)"; echo "podman: $(podman --version)"
    [ "$FWB" = samd20 ] && echo "openocd: $(openocd --version 2>&1 | head -1)" || echo "probe-rs: $(probe-rs --version 2>/dev/null | head -1)"
    echo "Fill in: board revision printed on the board, how the board was powered, anything changed:"
} > "$OUT/info.txt"
drop_src
tar -czf "$OUT.tar.gz" -C "$(dirname "$OUT")" "$(basename "$OUT")"
say ""
cat "$OUT/summary.txt"
say ""
say "Everything is in $OUT.tar.gz. Add the board revision to info.txt"
say "if you can, and send it to contact@verified-libs.org (site/content/reproduce.md)."
grep -q "FAILED\|DIFFERS\|could not" "$OUT/summary.txt" && exit 1
exit 0
