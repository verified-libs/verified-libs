#!/bin/bash
# A test of public-export.py's rule for the test sources of two kinds (the
# ring buffers, records under records/ but records/crc; the CRC kind,
# records/crc): in a throwaway clone of this repository's HEAD, a made-up CRC
# record (test values, no measurement) is committed, then one file is changed
# per case and the export check must stop exactly the records it should.
#   bash lab/tools/test-public-export.sh      exit 0: every case as expected
#   bash lab/tools/test-public-export.sh --quick   without the CRC ledger cases
# The CRC ledger cases (DECISIONS 2026-11-24, the same-image rule for the CRC
# kind) build the NUCLEO-G0B1RE's CRC images in the clone in the toolchain
# image (podman), at nice 10 on two CPUs: once for two made-up records
# (lab/tools/test-crc-records.py: a build's checksums, no measurement) and
# once per ledger image-ledger.py makes. The cases run with the tree's real
# CRC records beside the made-up ones (the two made-up records replace two
# real ones of that board), and what is expected is counted from the clone's
# records; a ledger then rebuilds the images of every board that has CRC
# records (six). The records of a commit with other test sources are held by
# the ledger, which is held by the checksum of HEAD's test sources (the host
# side included): after a recorded host fix exactly those records stop until
# the ledger is made again, and the two host-fix cases test both steps. A
# full run makes the ledger four times and takes about 32 minutes
# (2026-11-26, 1925 s on this host with 221 CRC records), --quick a few seconds. The libraries are copied from
# VL_CRC_LIBS_FROM_HOST (default ~/vl-next/kind-crc) and checked out at
# their pins.
# Nothing of this repository is changed; the clone is deleted at the end.
set -uo pipefail
export LC_ALL=C
REPO=$(cd "$(dirname "$0")/../.." && pwd)
T=$(mktemp -d "${TMPDIR:-/tmp}/vl-export-test.XXXXXX")
trap 'rm -rf "${T:?}"' EXIT
git clone -q "$REPO" "$T/r" && cd "$T/r" || exit 2
git checkout -q "$(git -C "$REPO" rev-parse HEAD)"
git config user.name test && git config user.email test@invalid
src=$(git rev-parse HEAD)

mkdir -p records/crc/stm32g474
printf '{\n "schema": "crc-bench/1",\n "adapter": "adapter_test",\n "bench_commit": "%s",\n "images": []\n}\n' "$src" \
    > records/crc/stm32g474/adapter_test.json
git add records/crc && git commit -q -m "test: a made-up CRC record"
base=$(git rev-parse HEAD)

fails=0
# case NAME FILE EXPECT_CRC_STOPPED EXPECT_RB_STOPPED
case_() {
    local name=$1 file=$2 crc=$3 rb=$4 out rc got_crc=no got_rb=no
    git reset -q --hard "$base"
    if [ -n "$file" ]; then
        printf '\n/* test change */\n' >> "$file"
        git commit -q -am "test: $name"
    fi
    out=$(python3 lab/tools/public-export.py --check 2>&1); rc=$?
    grep -q "under records/crc/ name commit" <<<"$out" && got_crc=yes
    grep -q "whose test sources (firmware" <<<"$out" && got_rb=yes
    local want_rc=0
    { [ "$crc" = yes ] || [ "$rb" = yes ]; } && want_rc=1
    if [ "$got_crc" = "$crc" ] && [ "$got_rb" = "$rb" ] && [ "$rc" = "$want_rc" ]; then
        echo "ok   $name: CRC records stopped: $got_crc, ring-buffer records stopped: $got_rb"
    else
        echo "FAIL $name: CRC records stopped: $got_crc (want $crc), ring-buffer records stopped: $got_rb (want $rb), rc $rc"
        sed 's/^/     /' <<<"$out"
        fails=$((fails + 1))
    fi
}
case_ "nothing changed"                                ""                                          no  no
case_ "a file of the CRC kind (kinds/crc/ref_crc.c)"   kinds/crc/ref_crc.c                         yes no
case_ "a proof of the CRC kind (kinds/crc/proof/)"     "$(git ls-files kinds/crc/proof | grep -m1 '\.c$')" no no
case_ "a ring-buffer file (firmware/, not common)"     firmware/nrf5340-rb-bench/main.c            no  yes
case_ "the board support (firmware/common)"            firmware/common/benchboot.c                 yes yes
case_ "a version 2 program the CRC kind imports"       firmware/nrf5340-rb-bench/onebundle.py      yes yes

# the export writes the CRC records' commits to SAME_SOURCES_CRC: exactly the
# commits (12 digits, sorted) the records under records/crc of the clone name,
# the made-up record's and the tree's real ones, but those whose records the
# clone's ledger (records/rebuilt.json, entries crc/...) holds: those are not
# of the tree's test sources, the ledger stands for them
git reset -q --hard "$base"
all_same=$(find records/crc -name '*.json' -exec jq -r '.bench_commit[0:12]' {} + | sort -u)
held=$( { [ -f records/rebuilt.json ] && jq -r '.records | keys[] | select(startswith("crc/"))' records/rebuilt.json; } |
        while read -r k; do [ -f "records/$k" ] && jq -r '.bench_commit[0:12]' "records/$k"; done | sort -u)
want_same=$(comm -23 <(echo "$all_same") <(echo "$held") | sed '/^$/d')
if python3 lab/tools/public-export.py "$T/out" >/dev/null && [ "$(cat "$T/out/SAME_SOURCES_CRC")" = "$want_same" ]; then
    echo "ok   the export lists the CRC records' commits in SAME_SOURCES_CRC ($(echo $want_same))"
else
    echo "FAIL SAME_SOURCES_CRC is '$(echo $(cat "$T/out/SAME_SOURCES_CRC" 2>/dev/null))', want '$(echo $want_same)'"; fails=$((fails + 1))
fi
# The same-image rule for CRC records (DECISIONS 2026-11-24): two made-up
# records of a real build of this commit, on a base of their own.
if [ "${1:-}" != --quick ]; then
    B=stm32g0b1
    run2() { nice -n 10 taskset -c 0,1 "$@"; }
    git reset -q --hard "$src"
    export VL_CRC_LIBS_FROM=$T/libs
    cp -a "${VL_CRC_LIBS_FROM_HOST:-$HOME/vl-next/kind-crc}" "$T/libs" 2>/dev/null || mkdir -p "$T/libs"
    if ! (cd kinds/crc/bench && LIBS=$T/libs run2 bash onebuild.sh table "$B") > "$T/build.log" 2>&1; then
        echo "FAIL the CRC images of $B could not be built: $(tail -n 2 "$T/build.log" | tr '\n' ' ')"; fails=$((fails + 1))
    else
        mkdir -p "records/crc/$B"
        python3 -I lab/tools/test-crc-records.py "kinds/crc/build/v2/$B" "records/crc/$B" "${src:0:12}"
        git clean -qfdx kinds/crc/build
        git add records/crc && git commit -q -m "test: two made-up CRC records of a build"
        base2=$(git rev-parse HEAD)
        # ccase NAME WANT_ETL WANT_ZLIB [TEXT]: the check after the changes committed so far
        ccase() {
            local name=$1 we=$2 wz=$3 want=${4:-} out rc ge=no gz=no
            out=$(python3 lab/tools/public-export.py --check 2>&1); rc=$?
            grep -q "^    .*: .*adapter_etl_crc32_t256" <<<"$out" && ge=yes
            grep -q "^    .*: .*adapter_zlib_crc32" <<<"$out" && gz=yes
            local want_rc=0
            { [ "$we" = yes ] || [ "$wz" = yes ]; } && want_rc=1
            if [ "$ge" = "$we" ] && [ "$gz" = "$wz" ] && [ "$rc" = "$want_rc" ] && { [ -z "$want" ] || grep -q "$want" <<<"$out"; }; then
                echo "ok   $name: etl stopped: $ge, zlib stopped: $gz"
            else
                echo "FAIL $name: etl stopped: $ge (want $we), zlib stopped: $gz (want $wz), rc $rc"
                sed 's/^/     /' <<<"$out"; fails=$((fails + 1))
            fi
        }
        # lcase NAME: after a recorded host fix the ledger is no longer of HEAD's test sources (it is held by
        # their checksum, the host side included): exactly the ledger-held records stop, with that message,
        # per commit, and nothing else of the CRC kind does (the made-up records of this commit pass, and so do
        # records of another commit with HEAD's test sources, which the ledger does not hold). The expected
        # groups come from the clone's ledger: its crc/ entries whose record is still there, by their commit.
        lcase() {
            local name=$1 out rc groups bad=0 c n total=0
            groups=$(jq -r '.records | keys[] | select(startswith("crc/"))' records/rebuilt.json |
                while read -r e; do [ -f "records/$e" ] && jq -r '.bench_commit[0:12]' "records/$e"; done |
                grep -v "^${src:0:12}$" | sort | uniq -c)
            out=$(python3 lab/tools/public-export.py --check 2>&1); rc=$?
            [ "$rc" = 1 ] || bad=1
            while read -r n c; do
                [ -n "$c" ] || continue
                total=$((total + n))
                grep -q "RECORDS: $n under records/crc/ name commit $c" <<<"$out" || bad=1
                grep -q "^ *$n: no rebuild from the sources of HEAD in records/rebuilt.json" <<<"$out" || bad=1
            done <<<"$groups"
            [ "$(grep -c 'RECORDS: .* under records/crc/' <<<"$out")" = "$(grep -c . <<<"$groups")" ] || bad=1
            grep -q "^    .*: .*adapter_etl_crc32_t256\|^    .*: .*adapter_zlib_crc32" <<<"$out" && bad=1
            if [ "$bad" = 0 ]; then
                echo "ok   $name: the $total ledger-held records stop until the ledger is made again ($(echo $groups))"
            else
                echo "FAIL $name: expected the ledger-held records to stop, by commit ($(echo $groups)), and nothing else, rc $rc"
                sed 's/^/     /' <<<"$out"; fails=$((fails + 1))
            fi
        }
        ledger_() {   # records/rebuilt.json made from the tree, committed
            run2 python3 lab/tools/image-ledger.py > "$T/ledger.log" 2>&1 ||
                echo "     image-ledger.py: $(tail -n 3 "$T/ledger.log" | tr '\n' ' ')"
            git add records/rebuilt.json && git commit -q -m "test: ledger"
        }
        change() { printf '\n/* test change */\n' >> "$1"; git commit -q -am "test: $1"; }

        ccase "CRC: two records of this commit" no no
        git reset -q --hard "$base2"; change kinds/crc/adapter_etl.cpp
        ccase "CRC: an image file changed, no ledger" yes yes "no rebuild from the sources of HEAD"
        ledger_
        # every CRC record of the clone is now of another commit than HEAD: the two
        # made-up ones (they replace two real ones of the board) and the real ones
        n_crc=$(find records/crc -name '*.json' | wc -l)
        ccase "CRC: the same change, the ledger says every image is the same" no no \
            "0 CRC records ($n_crc more of other commits whose images this tree builds)"
        change kinds/crc/ref_crc.h
        ccase "CRC: a ledger made from another tree is not taken" yes yes "no rebuild from the sources of HEAD"
        git reset -q --hard "$base2"
        sed -i 's/#define NAME    "zlib crc32"$/#define NAME    "zlib crc32 (test)"/' kinds/crc/adapter_zlib.c
        git commit -q -am "test: zlib's adapter builds another image"
        ledger_
        ccase "CRC: one adapter's images changed: its records stop, no others" no yes "HEAD builds another image"
        git reset -q --hard "$base2"
        before=$(git rev-parse HEAD:kinds/crc/bench/run-crc.py)
        printf '\n# test change\n' >> kinds/crc/bench/run-crc.py; git commit -q -am "test: the runner"
        ccase "CRC: the runner changed, no recorded fix" yes yes "host side of the CRC kind"
        after=$(git rev-parse HEAD:kinds/crc/bench/run-crc.py)
        python3 -I lab/tools/test-crc-records.py --fix records/host-fixes.json kinds/crc/bench/run-crc.py "$before" "$after"
        git commit -q -am "test: a recorded host fix of the runner"
        lcase "CRC: the runner changed, with a recorded fix, ledger of before"
        ledger_
        ccase "CRC: the runner changed, with a recorded fix, ledger made again" no no
        git reset -q --hard "$base2"; change kinds/crc/repeat.sh
        ccase "CRC: repeat.sh changed (no test source)" no no
        git reset -q --hard "$base2"
        before=$(git rev-parse HEAD:kinds/crc/bench/crcverify.sh)
        printf '\n# test change\n' >> kinds/crc/bench/crcverify.sh; git commit -q -am "test: the check of a record"
        ccase "CRC: crcverify.sh changed, no recorded fix" yes yes "host side of the CRC kind"
        after=$(git rev-parse HEAD:kinds/crc/bench/crcverify.sh)
        python3 -I lab/tools/test-crc-records.py --fix records/host-fixes.json kinds/crc/bench/crcverify.sh "$before" "$after"
        git commit -q -am "test: a recorded host fix of the check"
        lcase "CRC: crcverify.sh changed, with a recorded fix, ledger of before"
        ledger_
        ccase "CRC: crcverify.sh changed, with a recorded fix, ledger made again" no no
    fi
fi
[ "$fails" = 0 ] && echo "every case as expected" || echo "$fails cases not as expected"
[ "$fails" = 0 ]
