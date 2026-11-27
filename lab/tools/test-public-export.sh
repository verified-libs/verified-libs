#!/bin/bash
# A test of public-export.py's rule for the test sources of three kinds (the
# ring buffers, records under records/ but records/crc and records/pools; the
# CRC kind, records/crc; the pools kind, records/pools): in a throwaway clone
# of this repository's HEAD, a made-up CRC record and a made-up pools record
# (test values, no measurement) are committed, then one file is changed per
# case and the export check must stop exactly the records it should.
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
# full run makes the ledger four times and took about 32 minutes
# (2026-11-26, 1925 s on this host with 221 CRC records); since method
# version 3 it also rebuilds the 176 version 2 records of the boards not
# measured again, each time, and takes over an hour. --quick: a few seconds. The libraries are copied from
# VL_CRC_LIBS_FROM_HOST (default ~/vl-next/kind-crc) and checked out at
# their pins.
# The rebuilds take their libraries from a local mirror only
# (lab/tools/lib-mirror.py, VL_LIB_MIRROR, default ~/vl-scratch/lib-mirror):
# it is filled before the first case (the network only for a pin it lacks;
# if a pin cannot be fetched the test stops there, "could not fetch"), and
# from then on git may use no other transport than file (GIT_ALLOW_PROTOCOL),
# so a network fault cannot change a case's verdict. A last case shuts the
# mirror off with no library at hand: every rebuild of the ledger fails at its
# fetch, and the held records must stop as "could not fetch", never as
# records HEAD builds another image of.
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
mkdir -p records/pools/stm32g474
printf '{\n "schema": "pools-bench/1",\n "adapter": "adapter_test",\n "bench_commit": "%s",\n "images": []\n}\n' "$src" \
    > records/pools/stm32g474/adapter_test.json
git add records/crc records/pools && git commit -q -m "test: a made-up CRC record and a made-up pools record"
base=$(git rev-parse HEAD)

fails=0
# case NAME FILE EXPECT_CRC_STOPPED EXPECT_RB_STOPPED EXPECT_POOLS_STOPPED [EXPECT_POOLS_ISR_STOPPED]
# The pools concurrency kind's test sources hold the pools kind's (POOLS_ISR_TEST_SOURCES), so its records
# (records/pools-isr, of a commit whose sources differ from HEAD's, held by the host fixes) stop wherever the
# pools records do; the sixth column is given where it differs.
case_() {
    local name=$1 file=$2 crc=$3 rb=$4 pools=$5 isr=${6:-$5} out rc got_crc=no got_rb=no got_pools=no got_isr=no
    git reset -q --hard "$base"
    if [ -n "$file" ]; then
        printf '\n/* test change */\n' >> "$file"
        git commit -q -am "test: $name"
    fi
    out=$(python3 lab/tools/public-export.py --check 2>&1); rc=$?
    grep -q "under records/crc/ name commit" <<<"$out" && got_crc=yes
    grep -q "whose test sources (firmware" <<<"$out" && got_rb=yes
    grep -q "under records/pools/ name commit" <<<"$out" && got_pools=yes
    grep -q "under records/pools-isr/ name commit" <<<"$out" && got_isr=yes
    # without records of that kind in the tree, none can stop
    [ -n "$(git ls-files records/pools-isr | head -1)" ] || isr=no
    local want_rc=0
    { [ "$crc" = yes ] || [ "$rb" = yes ] || [ "$pools" = yes ] || [ "$isr" = yes ]; } && want_rc=1
    if [ "$got_crc" = "$crc" ] && [ "$got_rb" = "$rb" ] && [ "$got_pools" = "$pools" ] && [ "$got_isr" = "$isr" ] && [ "$rc" = "$want_rc" ]; then
        echo "ok   $name: CRC records stopped: $got_crc, ring-buffer records stopped: $got_rb, pools records stopped: $got_pools, pools concurrency records stopped: $got_isr"
    else
        echo "FAIL $name: CRC records stopped: $got_crc (want $crc), ring-buffer records stopped: $got_rb (want $rb), pools records stopped: $got_pools (want $pools), pools concurrency records stopped: $got_isr (want $isr), rc $rc"
        sed 's/^/     /' <<<"$out"
        fails=$((fails + 1))
    fi
}
case_ "nothing changed"                                ""                                          no  no  no
case_ "a file of the CRC kind (kinds/crc/ref_crc.c)"   kinds/crc/ref_crc.c                         yes no  no
case_ "a proof of the CRC kind (kinds/crc/proof/)"     "$(git ls-files kinds/crc/proof | grep -m1 '\.c$')" no no no
case_ "a ring-buffer file (firmware/, not common)"     firmware/nrf5340-rb-bench/main.c            no  yes no
case_ "the board support (firmware/common)"            firmware/common/benchboot.c                 yes yes yes
case_ "a version 2 program the kinds import"           firmware/nrf5340-rb-bench/onebundle.py      yes yes yes
case_ "pools: the reference (kinds/pools/adapter_ref.c)" kinds/pools/adapter_ref.c                 no  no  yes
case_ "pools: the bench program (bench/main.c)"        kinds/pools/bench/main.c                    no  no  yes
case_ "pools: the runner (bench/run-pools.py)"         kinds/pools/bench/run-pools.py              no  no  yes
case_ "pools: the slots (slots.txt)"                   kinds/pools/slots.txt                       no  no  yes
case_ "pools: the host test (test_pool.c)"             kinds/pools/test_pool.c                     no  no  no
case_ "pools: a proof (kinds/pools/proof/)"            "$(git ls-files kinds/pools/proof | grep -m1 '\.c$')" no no no
case_ "pools: a host-only shim (shims/host/)"          kinds/pools/shims/host/ARMCM_host.h         no  no  no
case_ "pools: the host Makefile"                       kinds/pools/Makefile                        no  no  no
case_ "pools: the record path's test"                  kinds/pools/bench/test_poolrecords.py       no  no  no
case_ "pools: the claims file (claims.tsv)"            kinds/pools/claims.tsv                      no  no  no
case_ "pools: the repeat script (repeat.sh)"           kinds/pools/repeat.sh                       no  no  no
case_ "pools: the comparison (bench/poolscompare.py)"  kinds/pools/bench/poolscompare.py           no  no  no
case_ "pools: control, an adapter (adapter_lwip.c)"    kinds/pools/adapter_lwip.c                  no  no  yes
case_ "pools concurrency: its image (pools-isr/main.c)" kinds/pools-isr/main.c                     no  no  no  yes
case_ "pools concurrency: its host check (contract.c)"  kinds/pools-isr/contract.c                  no  no  no

# an archived series whose records have left the tree (method version 3: replaced at their paths by the
# records measured again) is kept in the public history its entry names: nothing stops; a series only partly
# gone still stops the export (the records are not the ones archived)
acase() {   # NAME WANT_STOPPED PATH...
    local name=$1 want=$2 out rc got=no; shift 2
    git reset -q --hard "$base"; git rm -q -r "$@"; git commit -q -m "test: $name"
    out=$(python3 lab/tools/public-export.py --check 2>&1); rc=$?
    grep -q "the records are not the ones archived" <<<"$out" && got=yes
    local want_rc=0
    [ "$want" = yes ] && want_rc=1
    if [ "$got" = "$want" ] && [ "$rc" = "$want_rc" ]; then
        echo "ok   $name: stopped: $got"
    else
        echo "FAIL $name: stopped: $got (want $want), rc $rc"; sed 's/^/     /' <<<"$out"; fails=$((fails + 1))
    fi
}
# (version 1's series: its 215 records are still in the tree, under records/bench, stress and campaign; the
# series "before method version 3" left it when the records measured again replaced them)
one_archived=$(git ls-files records/bench | grep -m1 '\.json$')
acase "archive: version 1's records all left the tree" no records/bench records/stress records/campaign
acase "archive: only version 1's stress records left (a series partly gone)" yes records/stress
acase "archive: one record of version 1 left the tree" yes "$one_archived"

# session names (site/session-names.txt): one put into a public file stops the export, which names the file
# and the line; the same in a path left out (lab/drafts) does not
scase() {   # NAME FILE WANT_STOPPED
    local name=$1 file=$2 want=$3 out rc got=no want_rc=0
    git reset -q --hard "$base"
    printf '\nwritten by %s\n' "$(grep -v '^#' site/session-names.txt | sed -n 1p)" >> "$file"
    git commit -q -am "test: $name"
    out=$(python3 lab/tools/public-export.py --check 2>&1); rc=$?
    grep -q "SESSION NAME: $file:$(wc -l < "$file"):" <<<"$out" && got=yes
    [ "$want" = yes ] && want_rc=1
    if [ "$got" = "$want" ] && [ "$rc" = "$want_rc" ] && grep -q "$([ "$want" = yes ] && echo 1 || echo 0) with session names" <<<"$out"; then
        echo "ok   $name: stopped: $got"
    else
        echo "FAIL $name: stopped: $got (want $want), rc $rc"; sed 's/^/     /' <<<"$out"; fails=$((fails + 1))
    fi
}
scase "session name: in a public file (README.md)" README.md yes
scase "session name: in a path left out (lab/drafts)" "$(git ls-files lab/drafts | grep -m1 '\.md$')" no

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
want_pools=$(find records/pools -name '*.json' -exec jq -r '.bench_commit[0:12]' {} + | sort -u)
if [ -f "$T/out/SAME_SOURCES_POOLS" ] && [ "$(cat "$T/out/SAME_SOURCES_POOLS")" = "$want_pools" ]; then
    echo "ok   the export lists the pools records' commits in SAME_SOURCES_POOLS ($(echo $want_pools))"
else
    echo "FAIL SAME_SOURCES_POOLS is '$(echo $(cat "$T/out/SAME_SOURCES_POOLS" 2>/dev/null))', want '$(echo $want_pools)'"; fails=$((fails + 1))
fi
# The ledger's plan (image-ledger.py --plan: what it would rebuild and the checksum each entry would hold,
# nothing built): a file that only builds the pools kind's images changed, so every real pools record and
# every pools concurrency record is one to hold. Each must have its kind's checksum (2026-11-27: the ledger
# took the pools kind's checksum for the concurrency records, whose fields are others, and stopped with a
# KeyError, in the full test only); a kind without a check of a record would be said as such and not planned
# (the made-up pools record has no images, so the plan names it as not rebuilt: that is expected).
git reset -q --hard "$base"
printf '\n# test change\n' >> kinds/pools/configs.txt; git commit -q -am "test: kinds/pools/configs.txt (the plan)"
n_p=$(find records/pools -name '*.json' -exec jq -r 'select(.bench_commit != "'"$src"'") | input_filename' {} + | wc -l)
n_i=$(find records/pools-isr -name '*.json' 2>/dev/null | wc -l)
out=$(python3 lab/tools/image-ledger.py --plan 2>&1); rc=$?
got_p=$(grep -c '^would rebuild pools/' <<<"$out"); got_i=$(grep -c '^would rebuild pools-isr/' <<<"$out")
if [ "$rc" = 0 ] && ! grep -q 'Traceback\|pools concurrency records not rebuilt' <<<"$out" && [ "$got_p" = "$n_p" ] && [ "$got_i" = "$n_i" ]; then
    echo "ok   the ledger's plan after a pools build file changed: $got_p pools records and $got_i pools concurrency records to rebuild, each with its kind's checksum, rc 0"
else
    echo "FAIL the ledger's plan after a pools build file changed: $got_p of $n_p pools records, $got_i of $n_i pools concurrency records planned, rc $rc"
    sed 's/^/     /' <<<"$out" | grep -v '^     would rebuild' | tail -n 12; fails=$((fails + 1))
fi
git reset -q --hard "$base"
# The same-image rule for CRC records (DECISIONS 2026-11-24): two made-up
# records of a real build of this commit, on a base of their own.
if [ "${1:-}" != --quick ]; then
    B=stm32g0b1
    run2() { nice -n 10 taskset -c 0,1 "$@"; }
    MIRROR=${VL_LIB_MIRROR:-$HOME/vl-scratch/lib-mirror}
    python3 -I lab/tools/lib-mirror.py fill "$MIRROR" > "$T/mirror.log" 2>&1 ||
        { echo "FAIL could not fetch the libraries into the mirror $MIRROR (no case run):"; grep -v ': in the mirror$' "$T/mirror.log" | sed 's/^/     /'; exit 1; }
    # the mirror as the rebuilds use it, bounded (lab/tools/test-lib-mirror.sh): every pin from it, no fetch nested
    # in another (2026-11-27: lazy fetches nested some 520 deep from the mirror and the host ran out of memory)
    TMPDIR=$T bash lab/tools/test-lib-mirror.sh "$MIRROR" > "$T/mirror-test.log" 2>&1 ||
        { echo "FAIL the library mirror is not safe to use (lab/tools/test-lib-mirror.sh; no case run):"; sed 's/^/     /' "$T/mirror-test.log"; exit 1; }
    eval "$(python3 -I lab/tools/lib-mirror.py env "$MIRROR")"
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
            # not the ledger's entries of records an archived series covers: the export holds those by the archive
            groups=$(jq -r '.records | keys[] | select(startswith("crc/"))' records/rebuilt.json |
                while read -r e; do [ -f "records/$e" ] && echo "$e"; done | not_archived |
                while read -r e; do jq -r '.bench_commit[0:12]' "records/$e"; done |
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
            run2 python3 lab/tools/image-ledger.py > "$T/ledger.log" 2>&1 || {
                # the lines that say why, not the log's last lines (a later MATCH)
                why=$(grep -E ': (DIFFERS|build failed|could not|not a record|commit .* cannot|toolchain image .* not present)|^could not fetch|lacks' "$T/ledger.log" | head -n 5)
                echo "     image-ledger.py: ${why:-$(tail -n 3 "$T/ledger.log")}" | cut -c1-400; }
            git add records/rebuilt.json && git commit -q -m "test: ledger"
        }
        change() { printf '\n/* test change */\n' >> "$1"; git commit -q -am "test: $1"; }
        # not_archived: of the record paths (under records/) on stdin, those no archive entry of the record's
        # commit covers (public-export.py archived() and under(), as the export and image-ledger.py hold them)
        not_archived() {
            python3 -I -c '
import importlib.util, json, sys
s = importlib.util.spec_from_file_location("pe", "lab/tools/public-export.py"); pe = importlib.util.module_from_spec(s)
s.loader.exec_module(pe); arch = pe.archived()
for n in sys.stdin.read().split():
    c = json.load(open("records/" + n)).get("bench_commit", "")[:12]
    if not any(pe.under(n, e) for e in arch.get(c, [])):
        print(n)'
        }

        ccase "CRC: two records of this commit" no no
        git reset -q --hard "$base2"; change kinds/crc/adapter_etl.cpp
        ccase "CRC: an image file changed, no ledger" yes yes "no rebuild from the sources of HEAD"
        ledger_
        # every CRC record of the clone is now of another commit than HEAD: the two
        # made-up ones (they replace two real ones of the board) and the real ones
        n_crc=$( (cd records && find crc -name '*.json') | not_archived | wc -l)
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
        # pools (the ledger's pools/ entries, image-ledger.py): a file that only builds images (configs.txt)
        # changed; without a ledger the pools records stop, with one made again from this tree they stand (the
        # made-up pools record, which has no images, is taken out first)
        # pcase NAME WANT_POOLS_STOPPED WANT_ISR_STOPPED TEXT [ISR_TEXT]: the pools concurrency records are built
        # from the pools kind's sources too, so the same change touches them
        pcase() {
            local name=$1 want=$2 want_i=$3 text=$4 text_i=${5:-} out rc got=no got_i=no want_rc=0
            out=$(python3 lab/tools/public-export.py --check 2>&1); rc=$?
            grep -q "under records/pools/ name commit" <<<"$out" && got=yes
            grep -q "under records/pools-isr/ name commit" <<<"$out" && got_i=yes
            { [ "$want" = yes ] || [ "$want_i" = yes ]; } && want_rc=1
            if [ "$got" = "$want" ] && [ "$got_i" = "$want_i" ] && [ "$rc" = "$want_rc" ] && grep -q "$text" <<<"$out" &&
               { [ -z "$text_i" ] || grep -q "$text_i" <<<"$out"; }; then
                echo "ok   $name: pools records stopped: $got, pools concurrency records stopped: $got_i"
            else
                echo "FAIL $name: pools records stopped: $got (want $want), pools concurrency records stopped: $got_i (want $want_i), rc $rc"
                sed 's/^/     /' <<<"$out"; fails=$((fails + 1))
            fi
        }
        git reset -q --hard "$base2"
        if git cat-file -e HEAD:records/pools/stm32g474/adapter_test.json 2>/dev/null; then
            git rm -q records/pools/stm32g474/adapter_test.json; git commit -q -m "test: without the made-up pools record"
        fi
        n_pools=$(git ls-files records/pools | grep -c '\.json$')
        n_isr=$(git ls-files records/pools-isr | grep -c '\.json$')
        printf '\n# test change\n' >> kinds/pools/configs.txt; git commit -q -am "test: kinds/pools/configs.txt"
        pcase "pools: configs.txt changed, no ledger" yes yes "$n_pools: no rebuild from the sources of HEAD" "$n_isr: no rebuild from the sources of HEAD"
        ledger_
        pcase "pools: configs.txt changed, the ledger made again" no no "0 pools records ($n_pools more of other commits" \
            "0 pools concurrency records ($n_isr more of other commits"
        base3=$(git rev-parse HEAD)
        # a fetch that fails: no mirror, no library at hand, no transport but file: every rebuild fails at its
        # fetch; the held records stop, each with "could not fetch", none as "HEAD builds another image"
        ( export GIT_CONFIG_COUNT=0 VL_CRC_LIBS_FROM=$T/none VL_POOLS_LIBS_FROM=$T/none; unset VL_LIB_MIRROR VL_LIBS_FROM
          run2 python3 lab/tools/image-ledger.py > "$T/ledger-nofetch.log" 2>&1 )
        git add records/rebuilt.json && git commit -q -m "test: a ledger whose fetches failed"
        out=$(python3 lab/tools/public-export.py --check 2>&1); rc=$?
        why=$(grep -E '^ +[0-9]+: ' <<<"$out")
        n_led=$(jq '.records | length' records/rebuilt.json)
        n_nf=$(jq '[.records[] | select(.result == "not checked" and (.note | startswith("could not fetch the libraries")))] | length' records/rebuilt.json)
        if [ "$rc" = 1 ] && [ -n "$why" ] && ! grep -qv "could not fetch the libraries" <<<"$why" && [ "$n_nf" = "$n_led" ] && [ "$n_led" -gt 0 ]; then
            echo "ok   a fetch that fails: all $n_led ledger entries \"could not fetch\", the export stops them as such, none \"builds another image\""
        else
            echo "FAIL a fetch that fails: $n_nf of $n_led ledger entries \"could not fetch\", rc $rc; the reasons:"
            sed 's/^/     /' <<<"$why" | cut -c1-300; tail -n 5 "$T/ledger-nofetch.log" | sed 's/^/     /'; fails=$((fails + 1))
        fi
        # the pools concurrency kind's check of a record (kinds/pools-isr/bench/isrverify.sh) as a control: an image
        # source of that kind alone changed so that every image's flash bytes change (the result block's magic
        # number in main.c); with the ledger of before its records stop for want of a rebuild, the pools records
        # stand; with the ledger made again every one of them stops as one HEAD builds another image of
        git reset -q --hard "$base3"
        sed -i 's/^#define RESULT_MAGIC 0x564C4931u/#define RESULT_MAGIC 0x564C4932u/' kinds/pools-isr/main.c
        git commit -q -am "test: kinds/pools-isr/main.c, other flash bytes"
        pcase "pools concurrency: an image source changed, ledger of before" no yes "0 pools records ($n_pools more of other commits" \
            "$n_isr: no rebuild from the sources of HEAD"
        ledger_
        pcase "pools concurrency: an image source changed, the ledger made again" no yes "0 pools records ($n_pools more of other commits" \
            "$n_isr: HEAD builds another image"
    fi
fi
[ "$fails" = 0 ] && echo "every case as expected" || echo "$fails cases not as expected"
[ "$fails" = 0 ]
