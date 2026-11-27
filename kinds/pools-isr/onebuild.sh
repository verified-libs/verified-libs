#!/bin/bash
# Build the pools concurrency series' images and bundle for one or more
# boards (build.py), in the toolchain image of benchmark version 2, as the
# first series' kinds/pools/bench/onebuild.sh does. No board is touched.
#   bash onebuild.sh [BOARD...]      (default: the six boards)
# Environment: LIBS (default ~/vl-next/kind-pools, fetched by ../pools/fetch.sh).
# Output: build/v1/<board>/ (build.py), with build.json: the board, the
# commit (lab/tools/source-commit.sh), the toolchain image and the libraries'
# pins, for run-isr.py and the record writer.
set -euo pipefail
cd "$(dirname "$0")"
export LC_ALL=C
boards=${*:-nrf5340 stm32g0b1 stm32g474 stm32h723 samd20 rp2350}
IMG=verified-libs/toolchain:2026-11-13
LIBS=${LIBS:-$HOME/vl-next/kind-pools}
libs=$(LIBS="$LIBS" bash ../pools/fetch.sh)
toolchain=$(podman run --rm "$IMG" cat /etc/verified-libs/toolchain.json)
commit=$(bash ../../lab/tools/source-commit.sh .)
for b in $boards; do
    [ -d "../../firmware/common/$b" ] || { echo "unknown board $b" >&2; exit 2; }
    mkdir -p build/v1
    podman run --rm -v "$PWD/../..":/work:Z -v "$LIBS":/libs:ro,Z -w /work/kinds/pools-isr "$IMG" \
        sh -c "LIBS=/libs python3 -I build.py $b" > "build/v1/make-$b.log" 2>&1 \
        || { echo "$b: build failed, see build/v1/make-$b.log" >&2; tail -n 8 "build/v1/make-$b.log" >&2; exit 1; }
    tail -n 1 "build/v1/make-$b.log"
    jq -n --arg board "$b" --arg bench_commit "$commit" --arg img "$IMG" --argjson toolchain "$toolchain" \
        --arg libs "$libs" \
        '{board: $board, kind: "pools-isr", bench_commit: $bench_commit, toolchain_image: $img, toolchain: $toolchain,
          libs_pinned: ($libs | split("\n"))}' > "build/v1/$b/build.json"
done
