#!/bin/bash
# Build and run the demo on the host (x86-64) and, for the same source, show
# the 32-bit load in the Cortex-M33 code. Uses the pinned diffstorm/cb
# fetched by firmware/nrf5340-rb-bench/fetch-libs.sh.
# Usage (on lib-lab1, from the repo mirror): bash run.sh
set -euo pipefail
cd "$(dirname "$0")"
IMG=verified-libs/toolchain:2026-11-05
bash ../../../firmware/nrf5340-rb-bench/fetch-libs.sh >/dev/null
DS=firmware/nrf5340-rb-bench/build/libs/diffstorm-cb-547d0812/src
podman run --rm -v "$PWD/../../..":/work:Z -w /work "$IMG" bash -c "
  set -e
  echo '== host (x86-64, gcc), C11 atomics'
  gcc -std=c11 -D_POSIX_C_SOURCE=200809L -O2 -I$DS verify/findings/diffstorm-cb-overwrite-padding/demo.c $DS/cb.c -o /tmp/demo
  /tmp/demo; echo \"exit=\$? (0 = reproduced)\"
  echo '== Cortex-M33 (arm-none-eabi-gcc -O2): load of overwrite in cb_insert_ex'
  arm-none-eabi-gcc -mcpu=cortex-m33 -mthumb -O2 -std=c11 -include firmware/nrf5340-rb-bench/shims/diffstorm/nanosleep.h \
      -I$DS -c $DS/cb.c -o /tmp/cb_m33.o
  arm-none-eabi-objdump -d /tmp/cb_m33.o | awk '/<cb_insert_ex.part.0>:|<cb_insert_ex>:/{p=1} p&&/^\$/{exit} p' | grep -nE 'ldr(b)?\s+r[0-9]+, \[r0, #16\]'
"
