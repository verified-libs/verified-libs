#!/bin/bash
# Pool pilot: fetch the pinned libraries (host: git only), then build and
# run the host test and the Cortex-M4 cross build inside the toolchain
# image of benchmark version 2. No board is used.
#   bash run.sh            both
#   bash run.sh test|cross one of them
set -euo pipefail
cd "$(dirname "$0")"
IMG=verified-libs/toolchain:2026-11-13
LIBS=${LIBS:-$HOME/vl-next/pilot-pools}
LIBS="$LIBS" bash fetch.sh
TARGETS=${*:-test cross}
podman run --rm -v "$PWD":/work:Z -v "$LIBS":/libs:ro,Z -w /work "$IMG" \
  bash -c "make clean >/dev/null && make --no-print-directory LIBS=/libs $TARGETS"
