#!/usr/bin/env bash
# Build the benchmark images of version 2 for one or more boards, in the
# toolchain image: one image per configuration and placement, and the
# bundles that are written to the boards (onebundle.py). No board is
# touched.
#   bash onebuild.sh table [BOARD...]   images and bundles from slots.txt
#   bash onebuild.sh sizes [BOARD...]   image sizes, for "oneslots.py assign"
# BOARD: nrf5340 stm32g0b1 stm32g474 stm32h723 samd20 rp2350 (default: all).
# Environment: BUNDLE=N[,N...] (table: only these bundles),
#   NRF5_SDK=path/to/the/zip (once, for Nordic's configurations; as run.sh).
# Output: build/v2/<board>/ (see onebundle.py), with build.json: the
# toolchain image, the library pins and the commit of the sources.
set -euo pipefail
cd "$(dirname "$0")"
export LC_ALL=C
mode=${1:-}; shift || true
case "$mode" in table|sizes) ;; *) sed -n '2,12p' "$0" >&2; exit 2 ;; esac
boards=${*:-nrf5340 stm32g0b1 stm32g474 stm32h723 samd20 rp2350}
# One toolchain image for every configuration (the one with the Rust
# targets; its C compilers are those of 2026-11-05).
IMG=verified-libs/toolchain:2026-11-13

mkdir -p build
libs=$(bash fetch-libs.sh)
if [ -n "${NRF5_SDK:-}" ]; then bash nrf5-sdk.sh "$NRF5_SDK" >/dev/null; fi
toolchain=$(podman run --rm "$IMG" cat /etc/verified-libs/toolchain.json)
commit=$(bash ../../lab/tools/source-commit.sh .)
for b in $boards; do
    [ -d "../common/$b" ] || { echo "unknown board $b" >&2; exit 2; }
    blibs=$libs
    if [ "$b" = nrf5340 ]; then   # Nordic's configurations: the nRF5 SDK files, checked against nrf5-sdk.lock
        [ "$(cat build/libs/nrf5-sdk/SHA256 2>/dev/null)" = "$(awk '$1 == "sha256" {print $2}' nrf5-sdk.lock)" ] \
            || { echo "nrf5340: Nordic's configurations need the nRF5 SDK: NRF5_SDK=path/to/the/zip (nrf5-sdk.lock)" >&2; exit 2; }
        blibs="$libs
nrf5-sdk $(awk '$1 == "version" {print $2}' nrf5-sdk.lock) sha256:$(cat build/libs/nrf5-sdk/SHA256)"
    fi
    opt=""
    [ "$mode" != table ] || [ -z "${BUNDLE:-}" ] || opt="--bundle $BUNDLE"
    mkdir -p "build/v2/$b"
    podman run --rm -v "$PWD/..":/work:Z -w /work/nrf5340-rb-bench "$IMG" \
        sh -c "make clean >/dev/null && python3 -I onebundle.py $mode $opt -- BOARD=$b 2>build/v2/$b/make-$mode.log" \
        || { echo "$b: build failed, see build/v2/$b/make-$mode.log" >&2; tail -n 5 "build/v2/$b/make-$mode.log" >&2; exit 1; }
    jq -n --arg board "$b" --arg bench_commit "$commit" --arg img "$IMG" --argjson toolchain "$toolchain" --arg libs "$blibs" \
        '{board: $board, bench_commit: $bench_commit, toolchain_image: $img, toolchain: $toolchain,
          libs_pinned: ($libs | split("\n"))}' > "build/v2/$b/build.json"
done
