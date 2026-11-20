#!/bin/bash
# Build, flash and run the multi-producer / multi-consumer stress test, then
# decode. Exit 0 only if the libraries in their documented mode are
# error-free and the control was caught; 1 if not; 2 if the run on the board
# failed; 3 if the build failed.
# Usage (on lib-lab1): bash run.sh [mpsc|spmc]   (default: mpsc)
# Environment: BOARD (nrf5340, stm32g0b1, stm32g474, stm32h723, samd20, rp2350), CODE, PROBE,
#   OPT, LTO, MP_PARAMS (-D flags: TRANSFERS, TIMER_PRESCALER, MAIN_SEED,
#   SEED_A, SEED_B are run parameters since 2026-11-15: not compiled in but
#   written into the result block over the debug port at start (main.c
#   params_from_host), so one image serves every run and is flashed only
#   when it changes (--preverify; flash wears out); other flags are compiled
#   in. Records: run_params, build_flags),
#   OUTDIR (default ~/lab-runs), POLL_TRIES (default 200 x 15 s after 60 s),
#   WITH_EXTRA=1: also the MPSC libraries in extra/ (held back from the public
#   tree); records get the suffix -extra and "with_extra": true. Without it
#   (default) the firmware is the one the public tree builds.
#   ONLY=n: the image of MP library n alone (main.c MP_IDX_*; flashed at the
#   board's flash base, so it replaces what is there: a spot check, not for
#   campaigns, which use the bundle); records get -lib<n> and "only_lib".
#   PER_LIB=1: one library per reset over the board's serial port (since
#   2026-11-17; common/uart_host.py, common/vls_uart.h, as
#   ../nrf5340-rb-stress): the run parameters go in the "go" line, not over
#   the debug port, which is touched only before and after a library runs.
#     IMAGES=per_lib (default): one image per library in a bundle
#       (../common/bundle.py), flashed only where an image changed;
#       IMAGES=combined: the same images in one bundle with the ISR stress
#       test's (../nrf5340-rb-stress, its images first and unchanged; built
#       there, IMAGES=combined in its run.sh uses the same bundle), so the
#       board holds both tests and switching between them writes no flash;
#       both tests' build flags must then be the defaults;
#       IMAGES=one: the image of every library, selected per reset
#     Selection index of MP library n: 64 + n (main.c VLS_SEL_BASE).
#     LIBS: the MP library indices to run (default: every one of the mode;
#       main.c MP_IDX_*), LIB_LIMIT: seconds per library (default 1800),
#     UART_TTY: the serial port (default: found from PROBE's serial number)
#   Records get -perlib and "per_lib" (not pooled with records of the
#   debug-port way: a new method).
set -euo pipefail
cd "$(dirname "$0")"
export LC_ALL=C
IMG=verified-libs/toolchain:2026-11-13   # 2026-11-05 + the Rust soft-float targets
BOARD=${BOARD:-nrf5340}
case $BOARD in
    nrf5340)   CHIP=nRF5340_xxAA_APPONLY; BOARD_DESC="nRF5340 DK"; CORE="application (Cortex-M33), 64 MHz" ;;
    stm32g0b1) CHIP=STM32G0B1RE; BOARD_DESC="NUCLEO-G0B1RE"; CORE="Cortex-M0+, 64 MHz" ;;
    stm32g474) CHIP=STM32G474RE; BOARD_DESC="NUCLEO-G474RE"; CORE="Cortex-M4F, 170 MHz" ;;
    stm32h723) CHIP=STM32H723ZG; BOARD_DESC="NUCLEO-H723ZG"; CORE="Cortex-M7, 64 MHz (reset clock)" ;;
    rp2350)    CHIP=RP235x; BOARD_DESC="Raspberry Pi Pico 2 H"; CORE="RP2350 Cortex-M33, 150 MHz" ;;
    samd20)    CHIP=ATSAMD20J18A; BOARD_DESC="SAM D20 Xplained Pro"; CORE="Cortex-M0+, 48 MHz (DFLL48M closed loop on XOSC32K)" ;;
    *) echo "rb-mp-stress: unknown BOARD $BOARD" >&2; exit 3 ;;
esac
[ "$BOARD" = samd20 ] && export PATH="$PWD/../common/samd20/bin:$PATH"   # OpenOCD stand-in for probe-rs
PR="--chip $CHIP${PROBE:+ --probe $PROBE}"
SMPF=""
# NL: library slots to read; WITH_EXTRA=1 adds the MPSC libraries of extra/
# (one adapter file each).
WITH_EXTRA=${WITH_EXTRA:-0}
case "$WITH_EXTRA" in
    0) NX=0; XSUF="" ;;
    1) shopt -s nullglob; XA=(extra/adapter_*.c); shopt -u nullglob; NX=${#XA[@]}; XSUF="-extra"
       [ "$NX" -gt 0 ] || { echo "WITH_EXTRA=1: no extra/adapter_*.c here" >&2; exit 3; } ;;
    *) echo "WITH_EXTRA must be 0 or 1" >&2; exit 3 ;; esac
case ${1:-mpsc} in mpsc) MODE=1; NL=$((8 + NX)) ;; spmc) MODE=2; NL=7 ;;
    smp-mpsc) MODE=1; NL=$((8 + NX)); SMPF="-DSMP_MODE=1" ;; smp-spmc) MODE=2; NL=7; SMPF="-DSMP_MODE=1" ;;
    *) echo "mode: mpsc|spmc|smp-mpsc|smp-spmc (smp-*: RP2350, roles on two cores)" >&2; exit 3 ;; esac
NWORDS=$((12 + NL * 12))
HDR_DONE="564c4d31 00000001"
CODE=${CODE:-flash}
OPT=${OPT:--O2}
LTO=${LTO:-0}
COMPILER=${COMPILER:-gcc}
case "$COMPILER" in gcc|clang) ;;
    atfe|zephyr-gcc) IMG=verified-libs/toolchain:2026-11-16 ;;   # ATfE 23.1.0 / Zephyr SDK 1.0.1 gcc (toolchain/variants)
    st-gcc|st-clang|st-clang-omax)   # ST's compilers (STM32CubeCLT): local image, STM32 boards only (ST licence SLA0048 clause 4)
        case "$BOARD" in stm32*) ;; *) echo "COMPILER=$COMPILER: ST's licence allows ST devices only, not BOARD=$BOARD" >&2; exit 3 ;; esac
        IMG=verified-libs/toolchain-st:cubeclt-1.22.0-base2026-11-13 ;;
    *) echo "COMPILER must be gcc, clang, atfe, zephyr-gcc, st-gcc, st-clang or st-clang-omax" >&2; exit 3 ;; esac
[ "$COMPILER" != st-clang-omax ] || [ "$OPT" = -O3 ] || { echo "COMPILER=st-clang-omax: the Omax preset is -O3 plus LLVM options; use OPT=-O3" >&2; exit 3; }
OUTDIR=${OUTDIR:-$HOME/lab-runs}
strip() { sed 's/\x1b\[[0-9;]*m//g'; }

mkdir -p build "$OUTDIR"
libs=$(bash ../nrf5340-rb-bench/fetch-libs.sh)
# Default timer prescaler: 0 (fastest) starves the main loop on the slower
# boards (nRF5340, G0B1, SAM D20: every library STARVED on 2026-11-12), so
# they default to 2; an explicit -DTIMER_PRESCALER in MP_PARAMS wins.
case "${MP_PARAMS:-}" in *TIMER_PRESCALER*) ;;
    *) case $BOARD in nrf5340|stm32g0b1|samd20) MP_PARAMS="${MP_PARAMS:-} -DTIMER_PRESCALER=2u" ;; esac ;; esac
# Run parameters out of MP_PARAMS (see the header); the rest are build flags.
P_MAIN=0x12345678; P_A=0xCAFEBABE; P_B=0x0BADF00D; P_PRE=0; P_TR=200000; BFLAGS=""
for tok in ${MP_PARAMS:-}; do
    v=${tok#*=}; v=${v%[uU]}
    case "$tok" in
        -DMAIN_SEED=*) P_MAIN=$v ;; -DSEED_A=*) P_A=$v ;; -DSEED_B=*) P_B=$v ;;
        -DTIMER_PRESCALER=*) P_PRE=$v ;; -DTRANSFERS=*) P_TR=$v ;;
        *) BFLAGS="$BFLAGS $tok" ;;
    esac
done
BFLAGS=${BFLAGS# }
# COVERAGE=1 builds (main.c vl_cov): where the interrupts landed, and aimed
# interrupts (COV_AIM 0: off, n: aim before one operation in n; COV_WINDOW:
# largest delay in cycles; COV_SEED). The table goes next to the record
# (cov_report.py).
COV=0; [[ " $BFLAGS " == *" -DCOVERAGE=1 "* ]] && COV=1
# Build key as in ../nrf5340-rb-stress/run.sh: the same image is reused,
# not rebuilt (REBUILD=1 forces a build).
MAKEARGS="BOARD=$BOARD CODE=$CODE OPT='$OPT' LTO=$LTO COMPILER=$COMPILER WITH_EXTRA=$WITH_EXTRA EXTRA='$SMPF $BFLAGS'"
ONLY=${ONLY:-}
if [ -n "$ONLY" ]; then
    case "$ONLY" in *[!0-9]*) echo "ONLY must be a library index" >&2; exit 3 ;; esac
    MAKEARGS="$MAKEARGS ONLY=$ONLY"; ELF=build/lib$ONLY/fw.elf; XSUF="$XSUF-lib$ONLY"
else
    ELF=build/fw.elf
fi
uart_tty() {
    [ -f "../common/$BOARD/board_uart.h" ] && [ -n "${PROBE:-}" ] || return 0
    local sn=${PROBE##*:} c
    c=$(ls /dev/serial/by-id/ 2>/dev/null | grep -- "$sn" || true)
    # the J-Link of the nRF5340 DK has three ports; UARTE0 of the application
    # core answers on if04 (../nrf5340-rb-stress/run.sh)
    [ "$(echo "$c" | grep -c .)" -gt 1 ] && c=$(echo "$c" | grep -- "-if04\$" || true)
    [ "$(echo "$c" | grep -c .)" = 1 ] && echo "/dev/serial/by-id/$c"
    return 0
}
PER_LIB=${PER_LIB:-0}
case "$PER_LIB" in 0|1) ;; *) echo "PER_LIB must be 0 or 1" >&2; exit 3 ;; esac
NIDX=$((8 + NX))                         # MP library indices (main.c MP_NIDX)
IMAGES_ENV=${IMAGES:-}; IMAGES=one; OUTF=$ELF; MAKECMD="make $MAKEARGS"
if [ "$PER_LIB" = 1 ]; then
    [ -z "$ONLY" ] || { echo "PER_LIB=1 and ONLY do not go together (IMAGES=per_lib builds every image)" >&2; exit 3; }
    UART_TTY=${UART_TTY:-$(uart_tty)}
    [ -n "$UART_TTY" ] || { echo "PER_LIB=1 needs the board's serial port (UART_TTY, PROBE)" >&2; exit 3; }
    IMAGES=${IMAGES_ENV:-per_lib}
    SEL_OPT="--sel-symbol vl_select --sel-from-end 16"   # common/select.h
    [ "$BOARD" = rp2350 ] && SEL_OPT="--sel-addr 0x400D800C"   # common/rp2350/board_uart.h
    case "$IMAGES" in
        per_lib) OUTF=build/bundle.json
                 MAKECMD="python3 -I ../common/bundle.py --libs 0-$((NIDX - 1)) --index-base 64 $SEL_OPT -- $MAKEARGS" ;;
        combined)
                 { [ -z "$BFLAGS" ] || [ "$BFLAGS" = -DCOVERAGE=1 ]; } && [ -z "$SMPF" ] && [ "$WITH_EXTRA" = 0 ] \
                     || { echo "IMAGES=combined: the default build only (no build flags in MP_PARAMS but -DCOVERAGE=1, no SMP, no WITH_EXTRA)" >&2; exit 3; }
                 OUTF=../nrf5340-rb-stress/build/bundle.json
                 ISRARGS="BOARD=$BOARD CODE=$CODE OPT='$OPT' LTO=$LTO COMPILER=$COMPILER EXTRA=''"
                 MAKECMD="cd ../nrf5340-rb-stress && make clean >/dev/null && python3 -I ../common/bundle.py --libs 0-39 $SEL_OPT --with ../rb-mp-stress 0-$((NIDX - 1)) 64 \"$MAKEARGS\" -- $ISRARGS" ;;
        one) ;;
        *) echo "IMAGES must be per_lib or one" >&2; exit 3 ;;
    esac
    XSUF="$XSUF-perlib"; [ "$IMAGES" = combined ] && XSUF="$XSUF-combined"
    if [ -z "${LIBS:-}" ]; then
        if [ $MODE = 1 ]; then LIBS=$(seq -s, 0 $((NIDX - 1))); else LIBS=0,1,2,3,4,5,7; fi
    fi
fi
key=$( { echo "$IMG|$MAKEARGS|$libs|$IMAGES"
         ( cd .. && find . \( -name build -o -name target -o -name __pycache__ \) -prune -o -type f \
             \( -name '*.c' -o -name '*.cpp' -o -name '*.h' -o -name '*.hpp' -o -name '*.ld' -o -name '*.mk' \
                -o -name Makefile -o -name '*.rs' -o -name 'Cargo.*' -o -name bundle.py \) -print0 | sort -z | xargs -0 sha256sum ); } \
       | sha256sum | cut -d' ' -f1)
if [ "${REBUILD:-0}" != 1 ] && [ -f $OUTF ] \
   && [ "$(cat build/build.key 2>/dev/null)" = "$key $(sha256sum $OUTF | cut -d' ' -f1)" ]; then
    echo "build: unchanged (build key), reusing $OUTF"
else
    rm -f build/build.key
    podman run --rm -v "$PWD/..":/work:Z -w /work/rb-mp-stress "$IMG" \
        sh -c "make clean >/dev/null; $MAKECMD" > build/make.log 2>&1 \
        || { echo "build failed, see build/make.log" >&2; exit 3; }
    echo "$key $(sha256sum $OUTF | cut -d' ' -f1)" > build/build.key
fi
toolchain=$(podman run --rm "$IMG" cat /etc/verified-libs/toolchain.json)
RUN_PARAMS="mode=$MODE transfers=$P_TR prescaler=$P_PRE main_seed=$P_MAIN seed_a=$P_A seed_b=$P_B"
PER_LIB_JSON=null; IMAGES_JSON=null; rc_run=0
if [ "$PER_LIB" = 1 ]; then
    if [ "$IMAGES" = one ]; then
        # the selection words and the results where the protocol expects them
        read -r RES_ADDR SEL_SYM < <(podman run --rm -v "$PWD/..":/work:Z -w /work/rb-mp-stress "$IMG" \
            arm-none-eabi-nm build/fw.elf | awk '$3 == "results" {r = $1} $3 == "vl_select" {v = $1} END {print r, v}')
        [ "$((16#$RES_ADDR))" = $((0x20000000)) ] || { echo "PER_LIB: results not at 0x20000000 ($RES_ADDR)" >&2; exit 3; }
    fi
    rm -f build/words_*.txt build/dump2_*.txt build/go.txt
    rmode=probe; [ "$BOARD" = rp2350 ] && rmode=aircr
    GO="go mode=$MODE transfers=$P_TR prescaler=$P_PRE main_seed=$P_MAIN seed_a=$P_A seed_b=$P_B"
    [ $COV = 1 ] && GO="$GO cov_aim=${COV_AIM:-0} cov_window=${COV_WINDOW:-0} cov_seed=${COV_SEED:-0} cov_off=${COV_OFF:-0}"
    unf=$(VLS_SEL_BASE=64 VLS_LIBS="$LIBS" VLS_GO="$GO" VLS_DUMP2=$COV python3 ../common/uart_host.py "$UART_TTY" $NIDX $NWORDS "${LIB_LIMIT:-1800}" \
          build $rmode $OUTF -- $PR) || exit 2
    python3 merge_mp.py build/words.txt $(echo "$LIBS" | tr ',' '\n' | sed 's|.*|build/words_&.txt|') \
        || { echo "merging the result blocks failed" >&2; exit 2; }
    [ "$unf" = "[]" ] || rc_run=2
    PER_LIB_JSON=$(jq -cn --argjson u "$unf" --argjson limit "${LIB_LIMIT:-1800}" --arg libs "$LIBS" --arg img "$IMAGES" \
        '{one_library_per_reset: true, control: "uart", results_read: "uart_dump", images: $img, limit_s: $limit,
          libs_run: ($libs | split(",") | map(tonumber)), unfinished: $u}')
    if [ "$IMAGES" != one ]; then
        IMAGES_JSON=$(jq -c '{select_addr, bundles: [.bundles[] | {bundle, sha256, boot_sha256, flash_bytes, libs}],
            libs: (.libs | with_entries(.value |= {sha256, base, bytes, bundle, dir}))}' $OUTF)
    fi
else
# where the host writes the run parameters: the last 8 words of the block
read -r RES_ADDR RES_SIZE < <(podman run --rm -v "$PWD/..":/work:Z -w /work/rb-mp-stress "$IMG" \
    arm-none-eabi-nm -S $ELF | awk '$4 == "results" {print $1, $2}')
PRM_ADDR=$(printf '0x%08x' $((16#$RES_ADDR + 16#$RES_SIZE - 32)))

timeout 180 probe-rs download $PR --allow-erase-all --preverify $ELF 2>&1 | strip | tail -n 1 \
    || { echo "probe failure: flashing failed" >&2; exit 2; }
# a reset in any case (--preverify may have skipped the flashing and its reset)
if [ "$BOARD" = rp2350 ]; then
    # probe-rs 0.32 "reset" can hang on the RP2350: a system reset through
    # the core's AIRCR instead (as ../nrf5340-rb-stress)
    timeout 20 probe-rs write $PR b32 0xE000ED0C 0x05FA0004 >/dev/null 2>&1 || true
else
    # up to three tries, as ../nrf5340-rb-stress/run.sh: right after a
    # download that wrote flash the reset hung once on four boards started
    # together (2026-11-17, step-5 validation)
    ok=0
    for try in 1 2 3; do
        if timeout 60 probe-rs reset $PR 2>&1 | strip; then ok=1; break; fi
        echo "note: probe-rs reset failed (try $try)"; sleep $((2 + RANDOM % 5))
    done
    [ $ok = 1 ] || { echo "probe failure: reset failed" >&2; exit 2; }
fi
# the parameters, once the firmware waits for them (prm_wait = "VLMW")
ok=0
for i in $(seq 1 30); do
    w=$(timeout 30 probe-rs read $PR b32 "$PRM_ADDR" 1 2>/dev/null | strip | awk '{print $2}') || w=""
    [ "$w" = 564c4d57 ] && { ok=1; break; }
    sleep 0.5
done
[ $ok = 1 ] || { echo "probe failure: the firmware did not wait for its parameters (read '$w')" >&2; exit 2; }
# COVERAGE=1 builds (main.c, a prototype): the aimed-interrupt settings into
# vl_cov before the parameters' magic word (COV_AIM 0: off, n: aim before
# one operation in n; COV_WINDOW: largest delay in cycles; COV_SEED)
COV_ADDR=""
if [ $COV = 1 ]; then
    COV_ADDR=$(podman run --rm -v "$PWD/..":/work:Z -w /work/rb-mp-stress "$IMG" \
        arm-none-eabi-nm $ELF | awk '$3 == "vl_cov" {print $1}')
    [ -n "$COV_ADDR" ] || { echo "COVERAGE build without vl_cov" >&2; exit 3; }
    timeout 30 probe-rs write $PR b32 $(printf '0x%08x' $((16#$COV_ADDR + 8))) \
        "${COV_AIM:-0}" "${COV_WINDOW:-0}" >/dev/null 2>&1 \
      && timeout 30 probe-rs write $PR b32 $(printf '0x%08x' $((16#$COV_ADDR + 24))) "${COV_SEED:-0}" "${COV_OFF:-0}" >/dev/null 2>&1 \
      || { echo "probe failure: writing the coverage settings failed" >&2; exit 2; }
fi
sum=$(( (MODE + P_TR + P_PRE + P_MAIN + P_A + P_B) & 0xFFFFFFFF ))
timeout 30 probe-rs write $PR b32 $(printf '0x%08x' $((16#${PRM_ADDR#0x} + 8))) \
        $MODE $P_TR $P_PRE $P_MAIN $P_A $P_B >/dev/null 2>&1 \
    && timeout 30 probe-rs write $PR b32 $(printf '0x%08x' $((16#${PRM_ADDR#0x} + 4))) \
        $(( 0x564C4D50 ^ sum )) >/dev/null 2>&1 \
    || { echo "probe failure: writing the run parameters failed" >&2; exit 2; }
sleep 60
hdr=""
for i in $(seq 1 "${POLL_TRIES:-200}"); do
    hdr=$(timeout 60 probe-rs read $PR b32 0x20000000 3 2>/dev/null | strip | awk '{print $2, $4}') || hdr=""
    [ "$hdr" = "$HDR_DONE" ] && break
    sleep 15
done
[ "$hdr" = "$HDR_DONE" ] || { echo "did not finish (header: $hdr)" >&2; exit 2; }
timeout 60 probe-rs read $PR b32 0x20000000 $NWORDS 2>&1 | strip \
    | awk '{for (i = 2; i <= NF; i++) print $i}' > build/words.txt \
    || { echo "probe failure: reading the results failed" >&2; exit 2; }
if [ -n "$COV_ADDR" ]; then
    ncov=$(timeout 30 probe-rs read $PR b32 $(printf '0x%08x' $((16#$COV_ADDR + 4))) 1 2>/dev/null | strip | awk '{print $2}')
    [ -n "$ncov" ] || { echo "probe failure: reading the coverage table size failed" >&2; exit 2; }
    ncov=$(( 8 + 2 * 16#$ncov ))
    timeout 120 probe-rs read $PR b32 "0x$COV_ADDR" $ncov 2>&1 | strip \
        | awk '{for (i = 2; i <= NF; i++) print $i}' > build/cov.txt \
        || { echo "probe failure: reading the coverage table failed" >&2; exit 2; }
fi
# the header must hold the parameters written (words 1, 3, 7-10: mode,
# transfers, prescaler, seeds); otherwise the firmware ran its build defaults
# (2026-11-17: a firmware started by hand just before ran past its wait)
got=$(sed -n '2p;4p;8p;9p;10p;11p' build/words.txt | paste -sd' ' | sed 's/^000001/000000/')   # mode: + 0x100 in SMP builds
want=$(printf '%08x %08x %08x %08x %08x %08x' $((MODE)) $((P_TR)) $((P_PRE)) $((P_MAIN)) $((P_A)) $((P_B)))
[ "$got" = "$want" ] || { echo "probe failure: the firmware did not take the run parameters (header $got, sent $want)" >&2; exit 2; }
fi   # PER_LIB

jq -n --arg time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --arg fw_sha256 "$(sha256sum $OUTF | cut -d' ' -f1)" \
      --argjson per_lib "$PER_LIB_JSON" --argjson images "$IMAGES_JSON" \
      --arg source_commit "$(bash ../../lab/tools/source-commit.sh .)" \
      --arg probe_rs "$(probe-rs --version | head -1)" \
      --arg build_flags "$BFLAGS" --arg run_params "$RUN_PARAMS" --arg code "$CODE" --arg opt "$OPT" --argjson lto "$LTO" --arg compiler "$COMPILER" \
      --arg board "$BOARD_DESC" --arg core "$CORE" --argjson with_extra "$WITH_EXTRA" --arg only "$ONLY" \
      --arg libs "$libs" --argjson toolchain "$toolchain" --arg img "$IMG" \
      '{time: $time, host: "lib-lab1", board: $board, core: $core, build_flags: $build_flags,
        params_at_runtime: true, run_params: $run_params,
        code_location: $code, opt: $opt, lto: ($lto == 1), compiler_libs: $compiler, fw_sha256: $fw_sha256, source_commit: $source_commit, probe_rs: $probe_rs, with_extra: ($with_extra == 1), only_lib: (if $only == "" then null else ($only | tonumber) end), per_lib: $per_lib, images: $images,
        toolchain_image: $img, toolchain: $toolchain,
        libs_pinned: ($libs | split("\n"))}' > build/meta.json

[ $COV = 1 ] && XSUF="$XSUF-cov-aim${COV_AIM:-0}w${COV_WINDOW:-0}"; [ "${COV_OFF:-0}" = 1 ] && XSUF="$XSUF-norec"
out=$OUTDIR/$BOARD-rb-mp-stress-${1:-mpsc}$XSUF-$(date -u +%Y%m%dT%H%M%SZ).json
if [ $COV = 1 ] && [ "${COV_OFF:-0}" = 1 ]; then
    :                                        # not recorded (cov_off)
elif [ $COV = 1 ] && [ "$PER_LIB" = 0 ]; then  # the table and the image it belongs to (cov_report.py)
    cp build/cov.txt "${out%.json}.cov.txt"; cp "$ELF" "${out%.json}.elf"
elif [ $COV = 1 ]; then
    # one table per library (dump2_<n>.txt), each with its library's image:
    # <record>.cov.<n>.txt, the images once per directory (elf/<sha256>.elf),
    # <record>.cov.list: "<n> <table> <image>" per library
    mkdir -p "$OUTDIR/elf"; : > "${out%.json}.cov.list"
    for l in $(echo "$LIBS" | tr ',' ' '); do
        [ -s build/dump2_$l.txt ] || { echo "note: no coverage table for library $l"; continue; }
        if [ "$IMAGES" = one ]; then e=$ELF
        else e=$(dirname "$OUTF")/../$(jq -r --arg k $((64 + l)) '.libs[$k].elf' "$OUTF"); fi
        sha=$(sha256sum "$e" | cut -d' ' -f1)
        [ -f "$OUTDIR/elf/$sha.elf" ] || cp "$e" "$OUTDIR/elf/$sha.elf"
        cp build/dump2_$l.txt "${out%.json}.cov.$l.txt"
        echo "$l $(basename "${out%.json}").cov.$l.txt elf/$sha.elf" >> "${out%.json}.cov.list"
    done
fi
rc=0
python3 decode.py build/words.txt build/meta.json "$out" || rc=$?
echo "record: $out"
[ $rc_run = 0 ] || { echo "unfinished libraries (per_lib.unfinished): $unf" >&2; rc=$rc_run; }
exit $rc
