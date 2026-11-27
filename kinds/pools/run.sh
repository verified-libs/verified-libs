#!/bin/bash
# The pools kind: fetch the pinned libraries (host: git only), then build and
# run the checks inside the toolchain image of benchmark version 2. No board
# is used.
#   bash run.sh               every target (test san proof miri cross)
#   bash run.sh test ...      only these targets (Makefile)
set -euo pipefail
cd "$(dirname "$0")"
IMG=verified-libs/toolchain:2026-11-13
LIBS=${LIBS:-$HOME/vl-next/kind-pools}
LIBS="$LIBS" bash fetch.sh >/dev/null
TARGETS=${*:-test san proof miri cross}
podman run --rm -v "$PWD/../..":/work:Z -v "$LIBS":/libs:ro,Z -w /work/kinds/pools "$IMG" \
  bash -c "make --no-print-directory LIBS=/libs $TARGETS"
