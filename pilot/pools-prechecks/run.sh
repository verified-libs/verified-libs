#!/bin/bash
# Check 1 of the pool pre-checks: fetch the pinned libraries (host: git
# only), then, in the toolchain image of benchmark version 2, the cross build
# of CMSIS-RTX's pool for three cores (cross.sh) and the host test (host.sh).
# No board is used.
set -euo pipefail
cd "$(dirname "$0")"
IMG=verified-libs/toolchain:2026-11-13
LIBS=${LIBS:-$HOME/vl-next/pools-prechecks}
LIBS="$LIBS" bash fetch.sh
podman run --rm -v "$PWD/../..":/work:Z -v "$LIBS":/libs:ro,Z -w /work/pilot/pools-prechecks "$IMG" \
  bash -c "rm -rf build && bash cross.sh && bash host.sh"
