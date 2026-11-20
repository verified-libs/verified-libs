#!/bin/bash
# Build and run the one-core contract check (contract.cpp) on the host
# (x86-64 Linux: it single-steps with the trap flag). No board, no toolchain
# image: the host's g++. Uses the library commits pinned in
# ../../firmware/nrf5340-rb-bench/libs.lock (fetch-libs.sh).
# Usage: bash run.sh [ADAPTER ...]   e.g. bash run.sh "pxq SPSC"
# Environment: RB_SLOTS (default 8: slots of the buffers checked; every
#   start position and fill level is tried, so keep it small)
set -euo pipefail
cd "$(dirname "$0")"
[ "$(uname -m)" = x86_64 ] || { echo "needs x86-64 (trap flag)" >&2; exit 2; }
bash ../../firmware/nrf5340-rb-bench/fetch-libs.sh >/dev/null
S=../../firmware/nrf5340-rb-stress
SL=${RB_SLOTS:-8}
mkdir -p build
# the benchmark tree with PRIMASK as host_irq.h's flag (hostify.py), and
# every library object built from it with the benchmark's own rules
python3 hostify.py ../../firmware/nrf5340-rb-bench build/host/nrf5340-rb-bench > build/hostify.txt
tail -n 1 build/hostify.txt
H=build/host/nrf5340-rb-bench
# mutants.c and broken.c as on the boards, PRIMASK likewise
python3 hostify.py $S build/host/nrf5340-rb-stress >> build/hostify.txt
rm -f build/*.o
make -s -f Makefile.host RB_SLOTS=$SL libs
F="-O2 -g -mno-red-zone -DRB_SLOTS=$SL -DBENCH_NO_ALIGN -I. -I$H -I$H/build/libs/pxq-ringbuffer-cortex/RingBuffer_PackedState -include host_irq.h"
gcc $F -std=c11 -c build/host/nrf5340-rb-stress/mutants.c -o build/mutants.o
gcc $F -std=c11 -c build/host/nrf5340-rb-stress/broken.c -o build/broken.o
g++ $F -std=c++20 -c pxq_host.cpp -o build/pxq_host.o
g++ $F -std=c++20 -c contract.cpp -o build/contract.o
# the Rust adapters for the host, their critical section on the same flag
# (rust-adapters/src/cs.rs, --cfg vl_host), with the image's cargo (offline,
# the crates fetch-libs.sh checked out)
podman run --rm -v "$PWD/../..":/work:Z -w /work/firmware/rust-adapters verified-libs/toolchain:2026-11-13 \
    sh -c "VL_RB_SLOTS=$SL RUSTFLAGS='--cfg vl_host' cargo build -q --offline --locked --release \
           --target x86_64-unknown-linux-gnu --target-dir /work/verify/contract/build/rust"
gcc $F -std=c11 -c ../../firmware/rust-adapters/adapters_rust.c -o build/adapters_rust.o
g++ -o build/contract build/*.o build/rust/x86_64-unknown-linux-gnu/release/libvl_rust_adapters.a
echo "RB_SLOTS=$SL; pxq $(git -C $H/build/libs/pxq-ringbuffer-cortex log --oneline -1 | cut -c1-60)"
build/contract "$@"
