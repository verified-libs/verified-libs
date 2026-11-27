#!/bin/bash
# The concurrency check of the pools kind on the host (Makefile here): fetch
# the pinned libraries (host: git only, ../pools/fetch.sh), then build and run it
# inside the toolchain image of benchmark version 2, as ../pools/run.sh does. No
# board is used. Output: the verdict per configuration; exit 0 if every
# judged verdict is as expected.
set -euo pipefail
cd "$(dirname "$0")"
IMG=verified-libs/toolchain:2026-11-13
LIBS=${LIBS:-$HOME/vl-next/kind-pools}
LIBS="$LIBS" bash ../pools/fetch.sh >/dev/null
podman run --rm -v "$PWD/../..":/work:Z -v "$LIBS":/libs:ro,Z -w /work/kinds/pools-isr "$IMG" \
  bash -c "make --no-print-directory LIBS=/libs ${*:-check}"
