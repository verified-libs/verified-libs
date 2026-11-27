#!/bin/bash
# Check 2 of the pool pre-checks: the model of the exclusive monitor
# (excl_model.h) in the one-core check with an interrupt at every instruction
# (excl_check.c). Host gcc on x86-64 Linux, as ../contract; no board, no
# toolchain image. Exit 0 if every verdict is as expected.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
gcc -O2 -g -Wall -Wextra -o build/excl_check excl_check.c
./build/excl_check
