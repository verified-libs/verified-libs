#!/usr/bin/env bash
# Build the CRC kind's benchmark images for one or more boards, in the
# toolchain image of version 2: one image per configuration and placement,
# and the bundles that are written to the boards (onecrc.py). No board is
# touched. As firmware/nrf5340-rb-bench/onebuild.sh, for this kind.
#   bash onebuild.sh table [BOARD...]   images and bundles from ../slots.txt
#   bash onebuild.sh sizes [BOARD...]   image sizes, for "crcslots.py assign"
# BOARD: nrf5340 stm32g0b1 stm32g474 stm32h723 samd20 rp2350 (default: all).
# Environment: BUNDLE=N[,N...] (table: only these bundles); LIBS (default
#   ~/vl-next/kind-crc, fetched by ../fetch.sh from ../libs.lock).
# Output: ../build/v2/<board>/ (see onecrc.py), with build.json: the
# toolchain image, the library pins and the commit of the sources.
set -euo pipefail
cd "$(dirname "$0")"
export LC_ALL=C
mode=${1:-}; shift || true
case "$mode" in table|sizes) ;; *) sed -n '2,13p' "$0" >&2; exit 2 ;; esac
boards=${*:-nrf5340 stm32g0b1 stm32g474 stm32h723 samd20 rp2350}
IMG=verified-libs/toolchain:2026-11-13
LIBS=${LIBS:-$HOME/vl-next/kind-crc}

libs=$(LIBS="$LIBS" bash ../fetch.sh)
toolchain=$(podman run --rm "$IMG" cat /etc/verified-libs/toolchain.json)
commit=$(bash ../../../lab/tools/source-commit.sh .)
gen=$(grep -v '^#' ../generated.lock | sha256sum | cut -c1-64)
for b in $boards; do
    [ -d "../../../firmware/common/$b" ] || { echo "unknown board $b" >&2; exit 2; }
    opt=""
    [ "$mode" != table ] || [ -z "${BUNDLE:-}" ] || opt="--bundle $BUNDLE"
    mkdir -p "../build/v2/$b"
    podman run --rm -v "$PWD/../../..":/work:Z -v "$LIBS":/libs:ro,Z -w /work/kinds/crc "$IMG" \
        sh -c "make --no-print-directory LIBS=/libs build/gen/ok >/dev/null && LIBS=/libs python3 -I bench/onecrc.py $mode $b $opt" \
        2>"../build/v2/$b/make-$mode.log" \
        || { echo "$b: build failed, see build/v2/$b/make-$mode.log" >&2; tail -n 5 "../build/v2/$b/make-$mode.log" >&2; exit 1; }
    jq -n --arg board "$b" --arg bench_commit "$commit" --arg img "$IMG" --argjson toolchain "$toolchain" \
        --arg libs "$libs" --arg gen "$gen" \
        '{board: $board, kind: "crc", bench_commit: $bench_commit, toolchain_image: $img, toolchain: $toolchain,
          libs_pinned: ($libs | split("\n")), crcany_generated_lock_sha256: $gen}' > "../build/v2/$b/build.json"
done
