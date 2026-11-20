#!/bin/bash
# Fetch pinned libraries, build in the toolchain image, then for each code
# location (flash, sram): flash the board, run, decode. Writes one JSON
# record per location to ~/lab-runs/ (OUTDIR: elsewhere).
# Usage (on lib-lab1): bash run.sh [flash|sram ...]   (default: flash sram)
# Environment:
#   BOARD  nrf5340 (default), stm32g0b1, stm32g474, stm32h723: firmware
#          board layer and chip
#   PROBE  probe-rs probe selector VID:PID[:SERIAL]; needed as soon as more
#          than one probe is connected (see lab/boards.conf)
#   OUTDIR where the JSON records go (default ~/lab-runs)
#   SET    spsc (default: the 37 SPSC configurations), mp (the modes for
#          more than one producer or consumer; records <prefix>-mp-...) or
#          rust (the Rust libraries; records <prefix>-rust-...). mp and rust
#          build in toolchain image 2026-11-13 (Rust soft-float targets);
#          nordic (BOARD=nrf5340 only): Nordic's nrf_ringbuf from the nRF5
#          SDK zip (NRF5_SDK=path, checked against nrf5-sdk.lock; records
#          <prefix>-nordic-...)
#   OPT    optimisation flag (default -O2); LTO=1 for link-time optimisation.
#          Records with other flags get a suffix in their file name.
#   MEMCPY newlib (default) or stub: link newlib's memcpy-stub byte loop instead of
#          the C library's memcpy (what a C library built for size, e.g. ST's,
#          links). Records get the suffix -memcpystub. rust (SET=rust or mp
#          only): the Rust archive's own memory functions (compiler_builtins),
#          as a pure Rust firmware links them; records -memcpyrust.
#   SHIFT  placement experiment: N bytes (0-255) between the timing harness
#          and all other code (main.c BENCH_SHIFT), so every library lies N
#          bytes further on. Records get the suffix -shiftN and "shift": N.
#   LIBC   newlib-nano (default), newlib, picolibc, picolibc-atfe, llvmlibc:
#          whose memcpy/memmove/memset/memcmp are linked (common/libc.mk);
#          records -libc-<name>
#   CLOCK_FAST 1: the board's fast clock (nRF5340 128 MHz, H723 520 MHz;
#          common/<board>/board.h BOARD_CLOCK_FAST); records -fastclock
#   COMPILER gcc (default) or clang: compiler for the libraries and their
#          adapters (common/compiler.mk); the harness and the link stay gcc.
#          Records get the suffix -clang.
set -euo pipefail
cd "$(dirname "$0")"
export LC_ALL=C
IMG=verified-libs/toolchain:2026-11-05
BOARD=${BOARD:-nrf5340}
case $BOARD in
    nrf5340)   CHIP=nRF5340_xxAA_APPONLY; BOARD_DESC="nRF5340 DK"; CORE="application (Cortex-M33)"
               PREFIX=nrf5340-rb-bench ;;
    stm32g0b1) CHIP=STM32G0B1RE; BOARD_DESC="NUCLEO-G0B1RE"; CORE="Cortex-M0+"
               PREFIX=stm32g0b1-rb-bench ;;
    stm32g474) CHIP=STM32G474RE; BOARD_DESC="NUCLEO-G474RE"; CORE="Cortex-M4F"
               PREFIX=stm32g474-rb-bench; DEFAULT_VARIANTS="flash sram ccm" ;;
    stm32h723) CHIP=STM32H723ZG; BOARD_DESC="NUCLEO-H723ZG"; CORE="Cortex-M7"
               PREFIX=stm32h723-rb-bench; DEFAULT_VARIANTS="flash sram itcm" ;;
    rp2350)    CHIP=RP235x; BOARD_DESC="Raspberry Pi Pico 2 H"; CORE="RP2350 core 0 (Cortex-M33)"
               PREFIX=rp2350-rb-bench; DEFAULT_WAIT=180 ;;   # ~105 s of measuring at 150 MHz (2 cache states)
    samd20)    CHIP=ATSAMD20J18A; BOARD_DESC="SAM D20 Xplained Pro"; CORE="Cortex-M0+"
               PREFIX=samd20-rb-bench; DEFAULT_VARIANTS="flash" ;;
    *) echo "unknown BOARD $BOARD" >&2; exit 2 ;;
esac
[ "$BOARD" = samd20 ] && export PATH="$PWD/../common/samd20/bin:$PATH"   # OpenOCD stand-in for probe-rs
PR_ARGS="--chip $CHIP${PROBE:+ --probe $PROBE}"
OPT=${OPT:--O2}
LTO=${LTO:-0}
case "$OPT" in -O0|-O1|-O2|-O3|-Os|-Og|-Oz) ;; *) echo "OPT must be one of -O0..-O3, -Os, -Og, -Oz" >&2; exit 2 ;; esac
COMPILER=${COMPILER:-gcc}
case "$COMPILER" in gcc|clang) ;;
    atfe|zephyr-gcc) IMG=verified-libs/toolchain:2026-11-16 ;;   # ATfE 23.1.0 / Zephyr SDK 1.0.1 gcc (toolchain/variants)
    st-gcc|st-clang|st-clang-omax)   # ST's compilers (STM32CubeCLT): local image, STM32 boards only (ST licence SLA0048 clause 4)
        case "$BOARD" in stm32*) ;; *) echo "COMPILER=$COMPILER: ST's licence allows ST devices only, not BOARD=$BOARD" >&2; exit 2 ;; esac
        IMG=verified-libs/toolchain-st:cubeclt-1.22.0-base2026-11-13 ;;
    *) echo "COMPILER must be gcc, clang, atfe, zephyr-gcc, st-gcc, st-clang or st-clang-omax" >&2; exit 2 ;; esac
[ "$COMPILER" != st-clang-omax ] || [ "$OPT" = -O3 ] || { echo "COMPILER=st-clang-omax: the Omax preset is -O3 plus LLVM options; use OPT=-O3" >&2; exit 2; }
MEMCPY=${MEMCPY:-newlib}
case "$MEMCPY" in newlib|stub|rust) ;; *) echo "MEMCPY must be newlib, stub or rust" >&2; exit 2 ;; esac
SHIFT=${SHIFT:-0}
case "$SHIFT" in [0-9]|[0-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5]) ;; *) echo "SHIFT must be 0-255" >&2; exit 2 ;; esac
SHIFT=$((10#$SHIFT))
FLAGS_SUFFIX=""
if [ "$OPT" != -O2 ] || [ "$LTO" = 1 ]; then
    FLAGS_SUFFIX="-${OPT#-}"
    if [ "$LTO" = 1 ]; then FLAGS_SUFFIX="$FLAGS_SUFFIX-lto"; fi
fi
# A different memcpy is a different experiment: keep its records apart.
[ "$MEMCPY" = newlib ] || FLAGS_SUFFIX="$FLAGS_SUFFIX-memcpy$MEMCPY"
[ "$COMPILER" = gcc ] || FLAGS_SUFFIX="$FLAGS_SUFFIX-$COMPILER"
[ "$SHIFT" = 0 ] || FLAGS_SUFFIX="$FLAGS_SUFFIX-shift$SHIFT"
# CLOCK_FAST=1: the board's fast clock (board.h BOARD_CLOCK_FAST): nRF5340
# 128 MHz, NUCLEO-H723ZG 520 MHz; other boards refuse. Records get the
# suffix -fastclock; their clock_hz is the one the firmware ran at.
# LIBC: whose memcpy/memmove/memset/memcmp are linked (common/libc.mk):
# newlib-nano (default), newlib, picolibc, picolibc-atfe, llvmlibc; records
# get the suffix -libc-<name>.
LIBC=${LIBC:-newlib-nano}
case "$LIBC" in newlib-nano) ;; newlib) FLAGS_SUFFIX="$FLAGS_SUFFIX-libc-newlib" ;;
    picolibc|picolibc-atfe|llvmlibc) FLAGS_SUFFIX="$FLAGS_SUFFIX-libc-$LIBC"; IMG=verified-libs/toolchain:2026-11-16 ;;
    *) echo "LIBC must be newlib-nano, newlib, picolibc, picolibc-atfe or llvmlibc" >&2; exit 2 ;; esac
CLOCK_FAST=${CLOCK_FAST:-0}
case "$CLOCK_FAST" in 0) ;; 1) case $BOARD in nrf5340|stm32h723) FLAGS_SUFFIX="$FLAGS_SUFFIX-fastclock" ;;
                              *) echo "CLOCK_FAST=1: no fast clock for BOARD=$BOARD" >&2; exit 2 ;; esac ;;
    *) echo "CLOCK_FAST must be 0 or 1" >&2; exit 2 ;; esac
# SET=mp: the 10-entry firmware with the modes for more than one producer or
# consumer (records <prefix>-mp-...); SET=rust: the 5-entry Rust firmware.
SET=${SET:-spsc}
case "$SET" in spsc) NL=37 ;; mp) NL=10; PREFIX=$PREFIX-mp ;; rust) NL=5; PREFIX=$PREFIX-rust ;;
    nordic) NL=6; PREFIX=$PREFIX-nordic
        [ "$BOARD" = nrf5340 ] || { echo "SET=nordic: Nordic's licence allows Nordic chips only, not BOARD=$BOARD" >&2; exit 2; } ;;
    *) echo "SET must be spsc, mp, rust or nordic" >&2; exit 2 ;; esac
# The sets with Rust code need an image with the soft-float Rust targets
# (toolchain/rust-targets: 2026-11-13; ST's image is built on it). The SPSC
# set keeps 2026-11-05, whose C firmware is byte-identical.
case $SET in spsc|nordic) ;; *) [ "$IMG" != verified-libs/toolchain:2026-11-05 ] || IMG=verified-libs/toolchain:2026-11-13 ;; esac
[ "$MEMCPY" != rust ] || [ "$SET" != spsc ] || { echo "MEMCPY=rust needs SET=rust or mp (Rust code)" >&2; exit 2; }
NWORDS=$((7 + NL * (2 * 7 * 10 + 1) + 1 + 3))
HDR_DONE="564c4235 00000001"
VARIANTS=${*:-${DEFAULT_VARIANTS:-flash sram}}
# Only the code locations that run are built: a variant that does not fit
# (e.g. CCM SRAM with clang code) must not stop a run of the others.
strip() { sed 's/\x1b\[[0-9;]*m//g'; }

mkdir -p build
libs=$(bash fetch-libs.sh)
if [ "$SET" = nordic ]; then   # the nRF5 SDK files: from the zip (NRF5_SDK=path), checked against nrf5-sdk.lock
    if [ -n "${NRF5_SDK:-}" ]; then bash nrf5-sdk.sh "$NRF5_SDK" >/dev/null; fi
    [ "$(cat build/libs/nrf5-sdk/SHA256 2>/dev/null)" = "$(awk '$1 == "sha256" {print $2}' nrf5-sdk.lock)" ] \
        || { echo "SET=nordic needs the nRF5 SDK: NRF5_SDK=path/to/the/zip (nrf5-sdk.lock)" >&2; exit 2; }
    libs="$libs
nrf5-sdk $(awk '$1 == "version" {print $2}' nrf5-sdk.lock) sha256:$(cat build/libs/nrf5-sdk/SHA256)"
fi
podman run --rm -v "$PWD/..":/work:Z -w /work/nrf5340-rb-bench "$IMG" \
    sh -c "make clean >/dev/null; make $(for v in $VARIANTS; do printf 'build/%s/fw.elf ' $v; done)BOARD=$BOARD SET=$SET OPT='$OPT' LTO=$LTO MEMCPY=$MEMCPY COMPILER=$COMPILER SHIFT=$SHIFT LIBC=$LIBC EXTRA='$( [ "$CLOCK_FAST" = 1 ] && echo -DBOARD_CLOCK_FAST=1 )'" > build/make.log
toolchain=$(podman run --rm "$IMG" cat /etc/verified-libs/toolchain.json)

for v in $VARIANTS; do
    elf=build/$v/fw.elf
    echo "######## code in $v"
    # --preverify: an image already on the board is not written again (flash
    # wears out); the reset below starts it either way
    probe-rs download $PR_ARGS --allow-erase-all --preverify $elf 2>&1 | strip | tail -n 1
    probe-rs reset $PR_ARGS 2>&1 | strip
    # Every probe-rs attach/detach stops CYCCNT, so stay off the probe while
    # the firmware measures: ~1 s start delay + a few seconds of measuring (20
    # adapters). Too short a wait shows up as rejected 'stalled' runs: 12 s
    # was enough for 20 adapters, not for 24 + the empty-call calibration;
    # 30 s was still too short for -Os code in SRAM.
    # Then poll until it reports done. No erase from here on: if the chip is
    # locked, fail instead. (Stalls are detected and reject the run.)
    sleep "${BENCH_WAIT:-${DEFAULT_WAIT:-60}}"
    hdr=""
    # 60 polls: the Cortex-M0+ takes longer than the M33.
    for i in $(seq 1 60); do
        hdr=$(probe-rs read $PR_ARGS b32 0x20000000 3 2>/dev/null | strip | awk '{print $2, $4}') || hdr=""
        [ "$hdr" = "$HDR_DONE" ] && break
        sleep 1
    done
    [ "$hdr" = "$HDR_DONE" ] || { echo "firmware did not finish (header: $hdr)" >&2; exit 1; }
    probe-rs read $PR_ARGS b32 0x20000000 $NWORDS 2>&1 | strip \
        | awk '{for (i = 2; i <= NF; i++) print $i}' > build/$v/words.txt

    podman run --rm -v "$PWD/..":/work:Z -w /work/nrf5340-rb-bench "$IMG" \
        arm-none-eabi-nm -S --size-sort -C $elf > build/$v/nm.txt

    jq -n --arg time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
          --arg host "$(hostname)" \
          --arg code_location "$v" \
          --arg fw_sha256 "$(sha256sum $elf | cut -d' ' -f1)" \
          --arg bench_commit "$(bash ../../lab/tools/source-commit.sh .)" \
          --arg probe_rs "$(probe-rs --version | head -1)" \
          --arg libs "$libs" \
          --argjson toolchain "$toolchain" --arg img "$IMG" \
          --arg board "$BOARD_DESC" --arg core "$CORE" \
          --arg opt "$OPT" --argjson lto "$LTO" --arg memcpy "$MEMCPY" --arg compiler "$COMPILER" --argjson shift "$SHIFT" --argjson clock_fast "$CLOCK_FAST" --arg libc "$LIBC" \
          '{time: $time, host: $host, board: $board, core: $core,
            code_location: $code_location, opt: $opt, lto: ($lto == 1),
            compiler_libs: (if $compiler == "gcc" then "arm-none-eabi-gcc" else "\($compiler) (libraries and adapters; harness and link: arm-none-eabi-gcc)" end),
            memcpy: (if $memcpy == "stub" then "newlib memcpy-stub (byte loop, as in a C library built for size)" elif $memcpy == "rust" then "Rust compiler_builtins (for the C code too)" else "C library (newlib-nano from the toolchain image)" end),
            shift: $shift, clock_fast: ($clock_fast == 1), libc: $libc,
            fw_sha256: $fw_sha256, bench_commit: $bench_commit, probe_rs: $probe_rs,
            toolchain_image: $img, toolchain: $toolchain,
            libs_pinned: ($libs | split("\n"))}' \
        > build/$v/meta.json

    mkdir -p "${OUTDIR:-$HOME/lab-runs}"
    out=${OUTDIR:-$HOME/lab-runs}/$PREFIX-$v$FLAGS_SUFFIX-$(date -u +%Y%m%dT%H%M%SZ).json
    python3 decode.py build/$v/words.txt build/$v/meta.json build/$v/nm.txt "$out"
    echo "record: $out"
done
