#!/bin/bash
# The CRC kind: fetch the pinned libraries (host: git only), then build and
# run the checks inside the toolchain image of benchmark version 2. No board
# is used.
#   bash run.sh               every target (refcheck test cross bench proof miri)
#   bash run.sh refcheck ...  only these targets (Makefile)
set -euo pipefail
cd "$(dirname "$0")"
IMG=verified-libs/toolchain:2026-11-13
LIBS=${LIBS:-$HOME/vl-next/kind-crc}
LIBS="$LIBS" bash fetch.sh
TARGETS=${*:-refcheck test cross bench proof miri}
# The repository is mounted at /work (bench/build.sh uses the board support
# under firmware/common, unchanged); everything is built in kinds/crc/build.
podman run --rm -v "$PWD/../..":/work:Z -v "$LIBS":/libs:ro,Z -w /work/kinds/crc "$IMG" \
  bash -c "make clean >/dev/null && make --no-print-directory LIBS=/libs $TARGETS"
