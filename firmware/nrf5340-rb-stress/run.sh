#!/bin/bash
# Build, flash and run the ISR <-> main stress test on a board (default the
# nRF5340 DK), then decode. Writes a JSON record. Exit code 0 only if the real libraries are
# error-free and the negative control was caught; 1 if not; 2 if the run on
# the board failed (probe or flash error, or the test did not finish: a power
# cycle may help); 3 if the build failed; 4 if the test was still running at
# the time limit (too slow, not hung).
# Usage (on lib-lab1): bash run.sh [single|block|dma|smp|smp-block|sweep|sweep-block|sweep-dma|sweep-smp|sweep-smp-block|sweep2|sweep2-block|sweep2-dma]
#   (default: single; smp*, sweep-smp*: RP2350 only, the other side on core 1;
#   sweep*: deterministic interrupt sweep, one SysTick interrupt per call at
#   every delay, see main.c; SWEEP_REPS=n in STRESS_PARAMS sets start positions)
#   dma = the zero-copy API of the libraries that have one
#   sweep2*: two interrupts per call, every pair of delays (main.c; slow:
#   use a few SWEEP_REPS)
# Optional environment (used by overnight.sh):
#   NORDIC=1       BOARD=nrf5340 only: also Nordic's nrf_ringbuf (library 40),
#                  from the nRF5 SDK zip (NRF5_SDK=path, nrf5-sdk.lock); a
#                  firmware of its own, records nrf5340-rb-nordic-stress-*
#   STRESS_PARAMS  extra -D flags, e.g. "-DMAIN_SEED=0x1234u -DTIMER_PRESCALER=2u"
#   CODE           where code runs: flash (default), sram, or ccm/itcm where
#                  the board has it
#   BOARD          nrf5340 (default), stm32g0b1, stm32g474, stm32h723
#   PROBE          probe-rs probe selector VID:PID[:SERIAL] (needed with more
#                  than one probe connected; see lab/boards.conf)
#   OUTDIR         where the JSON record goes (default ~/lab-runs)
#   POLL_TRIES     polls of 15 s after the first 120 s (default 600: 2.5 h, in
#                  practice up to about 3.2 h since each poll also takes a few
#                  seconds; the slowest run measured, sweep-block with 256
#                  start positions and the cache off on the nRF5340, needs
#                  about 1.7 h)
#   OPT, LTO       optimisation (default -O2) and link-time optimisation (1)
#   PER_LIB=1      one library per reset: the firmware is flashed once, then
#                  for each library the script writes its index into the
#                  result block (main.c select_*), resets the board, waits
#                  for that library alone and reads the block; merge_words.py
#                  puts the blocks together. A library that hangs, crashes or
#                  writes over memory costs only its own result: it is named
#                  "did not finish" (not error-free) and the run goes on.
#                  LIB_LIMIT: seconds per library (default 1800), LIB_POLL:
#                  seconds between polls (default 5). Records: "per_lib".
#                  On a board with a serial port to the host
#                  (common/<board>/board_uart.h) the libraries are chosen and
#                  their end is signalled over it (uart_host.py), and the
#                  debug port is not touched while a library runs; the port is
#                  found from PROBE's serial number in /dev/serial/by-id
#                  (UART_TTY overrides it, UART_TTY=none forces the debug port).
#                  UART_DUMP=1 (default): the result block comes over the
#                  serial port too ("dump", CRC-checked); 0: read over the
#                  debug port after "done". The nRF5340 DK needs J-Link OB
#                  firmware of 2023-10-30 or later: older firmware (as
#                  shipped) stopped passing data after some hundred kB until
#                  the probe was reset (2026-11-14).
#   LIBS           only these libraries (PER_LIB=1 over the serial port):
#                  indices into decode.py's LIBS, comma-separated, e.g.
#                  LIBS=11,40; the negative control is always added. The
#                  others are not run and are named in the record
#                  ("not_run", "partial": true); they never count as passed.
#                  For quick checks during development (minutes instead of
#                  an hour); campaigns always run all libraries.
#   IMAGES         per_lib (default with PARAMS_AT_RUNTIME=1): one firmware
#                  image per library (main.c ONLY_LIB), all of them side by
#                  side in flash with a boot stub that starts the selected
#                  one (../common/bundle.py, slotboot.c; since 2026-11-15).
#                  A library is then tested in an image that holds no other
#                  library's code, so adding, changing or a build failure of
#                  one library cannot change another's image or result. The
#                  bundle is flashed only when an image changed, and then only
#                  the changed images (uart_host.py flash_bundle: flash wears
#                  out). The SAM D20's 256 KB hold two bundles, flashed in
#                  turn. Records: "images" (per library: sha256, address).
#                  one: every library in one image (as before 2026-11-15;
#                  the only choice with PARAMS_AT_RUNTIME=0).
#   REBUILD=1      build even if the build key is unchanged (see below)
#   PARAMS_AT_RUNTIME  1 (default with PER_LIB=1 over the serial port): one
#                  image for every mode (main.c, since 2026-11-15); the mode
#                  and the run parameters in STRESS_PARAMS (MAIN_SEED,
#                  ISR_SEED, TIMER_PRESCALER, CACHE_ON, TRANSFERS,
#                  SWEEP_REPS) are not compiled in but sent to the firmware
#                  after each reset ("go" line, uart_host.py), and an image
#                  already on the board is not flashed again. The other
#                  STRESS_PARAMS stay build flags. Records: build_flags (what
#                  was compiled in), run_params (the "go" line) and
#                  run_params_confirmed (the firmware's answer).
#                  0 (default otherwise, the debug-port control): everything
#                  compiled in, as before 2026-11-15. PARAMS_AT_RUNTIME=1
#                  without the serial port only builds (verify-build.sh) and
#                  then stops with exit 3.
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
    *) echo "unknown BOARD $BOARD" >&2; exit 3 ;;
esac
[ "$BOARD" = samd20 ] && export PATH="$PWD/../common/samd20/bin:$PATH"   # OpenOCD stand-in for probe-rs
PR="--chip $CHIP${PROBE:+ --probe $PROBE}"
NL=40   # libraries in the result block (NLIBS in main.c)
NORDIC=${NORDIC:-0}
case "$NORDIC" in 0) ;; 1) [ "$BOARD" = nrf5340 ] || { echo "NORDIC=1: Nordic's licence allows Nordic chips only, not BOARD=$BOARD" >&2; exit 3; }
                          NL=41 ;;
    *) echo "NORDIC must be 0 or 1" >&2; exit 3 ;; esac
NWORDS=$((6 + NL * 2 * 8 + 5 + 2))
HDR_DONE="564c5331 00000001"
MODE=${1:-single}
case $MODE in single) EXTRA="" ;; block) EXTRA="-DBLOCK_MODE=1" ;; dma) EXTRA="-DDMA_MODE=1" ;;
    smp) EXTRA="-DSMP_MODE=1" ;; smp-block) EXTRA="-DSMP_MODE=1 -DBLOCK_MODE=1" ;;
    sweep) EXTRA="-DSWEEP_MODE=1" ;; sweep-block) EXTRA="-DSWEEP_MODE=1 -DBLOCK_MODE=1" ;;
    sweep-dma) EXTRA="-DSWEEP_MODE=1 -DDMA_MODE=1" ;;
    sweep-smp) EXTRA="-DSWEEP_MODE=1 -DSMP_MODE=1" ;; sweep-smp-block) EXTRA="-DSWEEP_MODE=1 -DSMP_MODE=1 -DBLOCK_MODE=1" ;;
    sweep2) EXTRA="-DSWEEP_MODE=2" ;; sweep2-block) EXTRA="-DSWEEP_MODE=2 -DBLOCK_MODE=1" ;;
    sweep2-dma) EXTRA="-DSWEEP_MODE=2 -DDMA_MODE=1" ;;
    *) echo "mode: single|block|dma|smp|smp-block|sweep|sweep-block|sweep-dma|sweep-smp|sweep-smp-block|sweep2|sweep2-block|sweep2-dma" >&2; exit 3 ;; esac
# sweep: reps, cov_base, cov_words, cov_outside, cap[NL], 8 x [NL][2], bitmap
case $MODE in sweep*) NWORDS=$((NWORDS + 4 + NL + 8 * NL * 2 + 1024)) ;; esac
case $MODE in *smp*) [ "$BOARD" = rp2350 ] || { echo "mode $MODE needs a board with a second core (rp2350)" >&2; exit 3; } ;; esac
PER_LIB=${PER_LIB:-0}
case "$PER_LIB" in 0|1) ;; *) echo "PER_LIB must be 0 or 1" >&2; exit 3 ;; esac

uart_tty() {
    [ -f "../common/$BOARD/board_uart.h" ] && [ -n "${PROBE:-}" ] || return 0
    local sn=${PROBE##*:} c
    c=$(ls /dev/serial/by-id/ 2>/dev/null | grep -- "$sn" || true)
    # the J-Link of the nRF5340 DK has three ports; UARTE0 of the application
    # core (P0.20/P0.22) answers on if04 (tested 2026-11-14)
    [ "$(echo "$c" | grep -c .)" -gt 1 ] && c=$(echo "$c" | grep -- "-if04\$" || true)
    [ "$(echo "$c" | grep -c .)" = 1 ] && echo "/dev/serial/by-id/$c"
    return 0
}
CONTROL=swd
if [ "$PER_LIB" = 1 ]; then
    UART_TTY=${UART_TTY:-$(uart_tty)}
    [ "$UART_TTY" = none ] && UART_TTY=""
    [ -n "$UART_TTY" ] && CONTROL=uart
fi
LIBS=${LIBS:-}
if [ -n "$LIBS" ]; then
    [ "$CONTROL" = uart ] || { echo "LIBS needs PER_LIB=1 and the board's serial port" >&2; exit 3; }
    CTRL=$(python3 -c 'import decode; print(next(i for i, n in enumerate(decode.LIBS) if "broken" in n))')
    LIBS=$(echo "$LIBS,$CTRL" | tr ',' '\n' | sed '/^$/d' | sort -n | uniq | paste -sd,)
    for l in ${LIBS//,/ }; do
        [[ "$l" =~ ^[0-9]+$ ]] && [ "$l" -lt "$NL" ] || { echo "LIBS: $l is not a library index (0..$((NL - 1)))" >&2; exit 3; }
    done
fi
PAR_DEFAULT=0; [ "$CONTROL" = uart ] && PAR_DEFAULT=1
PARAMS_AT_RUNTIME=${PARAMS_AT_RUNTIME:-$PAR_DEFAULT}
case "$PARAMS_AT_RUNTIME" in 0|1) ;; *) echo "PARAMS_AT_RUNTIME must be 0 or 1" >&2; exit 3 ;; esac
GO=""
if [ "$PARAMS_AT_RUNTIME" = 1 ]; then
    # The mode and the run parameters go to the firmware ("go", main.c
    # uart_go); only the remaining flags are compiled in.
    m=1; sw=0; smp=0
    case $MODE in *block*) m=2 ;; *dma*) m=3 ;; esac
    case $MODE in sweep2*) sw=2 ;; sweep*) sw=1 ;; esac
    case $MODE in *smp*) smp=1 ;; esac
    GO="go mode=$m sweep=$sw smp=$smp"
    EXTRA=""
    for tok in ${STRESS_PARAMS:-}; do
        case "$tok" in
            -DMAIN_SEED=*|-DISR_SEED=*|-DTIMER_PRESCALER=*|-DCACHE_ON=*|-DTRANSFERS=*|-DSWEEP_REPS=*)
                k=${tok#-D}; v=${k#*=}; k=${k%%=*}; v=${v%[uU]}
                case $k in MAIN_SEED) k=main_seed ;; ISR_SEED) k=isr_seed ;; TIMER_PRESCALER) k=prescaler ;;
                    CACHE_ON) k=cache ;; TRANSFERS) k=transfers ;; SWEEP_REPS) k=reps ;; esac
                GO="$GO $k=$v" ;;
            *) EXTRA="$EXTRA $tok" ;;
        esac
    done
    EXTRA=${EXTRA# }
else
    EXTRA="$EXTRA ${STRESS_PARAMS:-}"
fi
IMG_DEFAULT=one; [ "$PARAMS_AT_RUNTIME" = 1 ] && IMG_DEFAULT=per_lib
IMAGES=${IMAGES:-$IMG_DEFAULT}
case "$IMAGES" in one) ;; per_lib) [ "$PARAMS_AT_RUNTIME" = 1 ] || { echo "IMAGES=per_lib needs PARAMS_AT_RUNTIME=1" >&2; exit 3; } ;;
    combined) [ "$PARAMS_AT_RUNTIME" = 1 ] && [ -z "$EXTRA" ] && [ "$NORDIC" != 1 ] \
                  || { echo "IMAGES=combined needs PARAMS_AT_RUNTIME=1 and the default build (no build flags, no NORDIC)" >&2; exit 3; } ;;
    *) echo "IMAGES must be per_lib, combined or one" >&2; exit 3 ;; esac
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
case "$OPT" in -O0|-O1|-O2|-O3|-Os|-Og|-Oz) ;; *) echo "OPT must be one of -O0..-O3, -Os, -Og, -Oz" >&2; exit 3 ;; esac
OUTDIR=${OUTDIR:-$HOME/lab-runs}
strip() { sed 's/\x1b\[[0-9;]*m//g'; }

mkdir -p build "$OUTDIR"
libs=$(bash ../nrf5340-rb-bench/fetch-libs.sh)
if [ "$NORDIC" = 1 ]; then   # the nRF5 SDK files: from the zip (NRF5_SDK=path), checked against nrf5-sdk.lock
    if [ -n "${NRF5_SDK:-}" ]; then bash ../nrf5340-rb-bench/nrf5-sdk.sh "$NRF5_SDK" >/dev/null; fi
    [ "$(cat ../nrf5340-rb-bench/build/libs/nrf5-sdk/SHA256 2>/dev/null)" = "$(awk '$1 == "sha256" {print $2}' ../nrf5340-rb-bench/nrf5-sdk.lock)" ] \
        || { echo "NORDIC=1 needs the nRF5 SDK: NRF5_SDK=path/to/the/zip (nrf5-sdk.lock)" >&2; exit 3; }
    libs="$libs
nrf5-sdk $(awk '$1 == "version" {print $2}' ../nrf5340-rb-bench/nrf5-sdk.lock) sha256:$(cat ../nrf5340-rb-bench/build/libs/nrf5-sdk/SHA256)"
fi
# Build key: the toolchain image, the make arguments, the pinned libraries
# and every source file under firmware/ (build output excluded). The build is
# deterministic (verify-build.sh), so with the same key the image would come
# out the same: it is reused instead of rebuilt (with one image for every
# mode, the second and later modes of a check or campaign need no build).
# REBUILD=1 always builds.
MAKEARGS="BOARD=$BOARD CODE=$CODE OPT='$OPT' LTO=$LTO COMPILER=$COMPILER EXTRA='$EXTRA'"
[ "$NORDIC" = 1 ] && MAKEARGS="$MAKEARGS NORDIC=1"
key=$( { echo "$IMG|$MAKEARGS|$libs"
         ( cd .. && find . \( -name build -o -name target -o -name __pycache__ \) -prune -o -type f \
             \( -name '*.c' -o -name '*.cpp' -o -name '*.h' -o -name '*.hpp' -o -name '*.ld' -o -name '*.mk' \
                -o -name Makefile -o -name '*.rs' -o -name 'Cargo.*' -o -name bundle.py \) -print0 | sort -z | xargs -0 sha256sum ); } \
       | sha256sum | cut -d' ' -f1)
# build.key also holds the image's sha256, so an fw.elf made otherwise (a
# manual make) is never taken for the keyed one.
# IMAGES=per_lib: the bundle (bundle.json, which holds every image's sha256)
# takes fw.elf's place here.
key=$(echo "$key $IMAGES" | sha256sum | cut -d' ' -f1)
OUTF=build/fw.elf; [ "$IMAGES" != one ] && OUTF=build/bundle.json
SEL_OPT="--sel-symbol vl_select --sel-from-end 16"   # common/select.h: the last 16 bytes of RAM
[ "$BOARD" = rp2350 ] && SEL_OPT="--sel-addr 0x400D800C"   # common/rp2350/board_uart.h BOARD_SELECT_ADDR
if [ "${REBUILD:-0}" != 1 ] && [ -f $OUTF ] \
   && [ "$(cat build/build.key 2>/dev/null)" = "$key $(sha256sum $OUTF | cut -d' ' -f1)" ]; then
    echo "build: unchanged (build key), reusing $OUTF"
else
    rm -f build/build.key
    if [ "$IMAGES" = per_lib ]; then
        cmd="python3 -I ../common/bundle.py --libs 0-$((NL - 1)) $SEL_OPT -- $MAKEARGS"
    elif [ "$IMAGES" = combined ]; then
        # this test's images as with per_lib (the same, at the same places),
        # then the MP stress test's (../rb-mp-stress, selection indices 64..71,
        # its default build; its run.sh IMAGES=combined uses this bundle)
        MPARGS="BOARD=$BOARD CODE=$CODE OPT='$OPT' LTO=$LTO COMPILER=$COMPILER WITH_EXTRA=0 EXTRA=''"
        cmd="(cd ../rb-mp-stress && make clean >/dev/null); python3 -I ../common/bundle.py --libs 0-$((NL - 1)) $SEL_OPT --with ../rb-mp-stress 0-7 64 \"$MPARGS\" -- $MAKEARGS"
    else
        cmd="make $MAKEARGS"
    fi
    podman run --rm -v "$PWD/..":/work:Z -w /work/nrf5340-rb-stress "$IMG" \
        sh -c "make clean >/dev/null; $cmd" > build/make.log 2>&1 \
        || { echo "build failed, see build/make.log" >&2; exit 3; }
    echo "$key $(sha256sum $OUTF | cut -d' ' -f1)" > build/build.key
fi
toolchain=$(podman run --rm "$IMG" cat /etc/verified-libs/toolchain.json)
if [ "$PARAMS_AT_RUNTIME" = 1 ] && [ "$CONTROL" != uart ]; then
    echo "PARAMS_AT_RUNTIME=1 needs PER_LIB=1 and the board's serial port: built, not run" >&2; exit 3
fi
if [ "$PER_LIB" = 1 ] && [ "$IMAGES" = one ]; then
    # The selection words (common/select.h): symbol vl_select, the last 16
    # bytes of RAM; the results must still start at 0x20000000.
    read -r RES_ADDR SEL_SYM < <(podman run --rm -v "$PWD/..":/work:Z -w /work/nrf5340-rb-stress "$IMG" \
        arm-none-eabi-nm build/fw.elf | awk '$3 == "results" {r = $1} $3 == "vl_select" {v = $1} END {print r, v}')
    [ "$((16#$RES_ADDR))" = $((0x20000000)) ] || { echo "PER_LIB: results not at 0x20000000 ($RES_ADDR)" >&2; exit 3; }
    SEL_ADDR=0x$SEL_SYM
    [ "$BOARD" = rp2350 ] && SEL_ADDR=0x400D800C   # common/rp2350/board_uart.h BOARD_SELECT_ADDR
fi

if [ "$CONTROL" = uart ]; then
    :   # uart_host.py flashes the board itself, with the serial port open
else
# Every probe-rs call has a time limit, so a hung probe cannot block the run.
# --preverify: an image already on the board is not written again (flash
# wears out); not on the RP2350, where the download's own reset is the one
# the run relies on when probe-rs reset hangs (below)
PV=--preverify; [ "$BOARD" = rp2350 ] && PV=
timeout 180 probe-rs download $PR --allow-erase-all $PV build/fw.elf 2>&1 | strip | tail -n 1 \
    || { echo "probe failure: flashing failed" >&2; exit 2; }
if [ "$BOARD" = rp2350 ] && [ "$PER_LIB" = 1 ]; then
    :   # each library gets its own reset below (AIRCR); a probe-rs reset that
        # hangs here would leave the probe unusable for a while
elif [ "$BOARD" = rp2350 ]; then
    # probe-rs 0.32 "reset" hangs on the RP2350 while the stress firmware
    # runs (2026-11-11); the download has already reset the chip, and the
    # firmware clears "done" at start, so stale results cannot be read.
    timeout 20 probe-rs reset $PR >/dev/null 2>&1 \
        || echo "note: probe-rs reset timed out (RP2350); running from the download's reset"
else
    # Up to three tries: with several boards started at the same moment a
    # reset occasionally fails at once (2026-11-12, sweep runs started in
    # parallel); a short random pause separates the retries.
    ok=0
    for try in 1 2 3; do
        if timeout 60 probe-rs reset $PR 2>&1 | strip; then ok=1; break; fi
        echo "note: probe-rs reset failed (try $try)"; sleep $((2 + RANDOM % 5))
    done
    [ $ok = 1 ] || { echo "probe failure: reset failed" >&2; exit 2; }
fi
fi   # CONTROL != uart
# One library per reset (PER_LIB=1): see the header.
reset_board() {
    if [ "$BOARD" = rp2350 ]; then
        # probe-rs reset can hang on the RP2350 (see above): request a system
        # reset through the core's AIRCR instead.
        timeout 20 probe-rs write $PR b32 0xE000ED0C 0x05FA0004 >/dev/null 2>&1 || true
        return 0
    fi
    local try
    for try in 1 2 3; do
        timeout 60 probe-rs reset $PR >/dev/null 2>&1 && return 0
        sleep $((2 + RANDOM % 5))
    done
    return 1
}
if [ "$PER_LIB" = 1 ] && [ "$CONTROL" = uart ]; then
    rm -f build/words_*.txt build/go.txt
    rmode=probe; [ "$BOARD" = rp2350 ] && rmode=aircr
    UART_DUMP=${UART_DUMP:-1}
    unf=$(VLS_LIBS="$LIBS" VLS_GO="$GO" VLS_DUMP=$UART_DUMP python3 ../common/uart_host.py "$UART_TTY" $NL $NWORDS "${LIB_LIMIT:-1800}" build $rmode $OUTF -- $PR) || exit 2
    # a library not in LIBS: "-" (merge_words.py leaves its rows zero)
    python3 merge_words.py $NL build/words.txt $(for l in $(seq 0 $((NL - 1))); do
            if [ -z "$LIBS" ] || [[ ",$LIBS," == *",$l,"* ]]; then echo build/words_$l.txt; else echo -; fi; done) \
        || { echo "merging the result blocks failed" >&2; exit 2; }
    rread=debug_port; [ "$UART_DUMP" = 1 ] && rread=uart_dump
    notrun=$(for l in $(seq 0 $((NL - 1))); do [ -z "$LIBS" ] || [[ ",$LIBS," == *",$l,"* ]] || echo $l; done | jq -cs .)
    PER_LIB_JSON=$(jq -cn --argjson u "$unf" --argjson limit "${LIB_LIMIT:-1800}" --arg rr "$rread" --argjson nr "$notrun" \
        '{one_library_per_reset: true, control: "uart", results_read: $rr, limit_s: $limit, unfinished: $u, not_run: $nr}')
elif [ "$PER_LIB" = 1 ]; then
    unfinished=()
    rm -f build/words_*.txt
    for l in $(seq 0 $((NL - 1))); do
        ok=0; tl=$(date +%s)
        for try in 1 2 3; do
            # selection (and select_pad), then done = 0, so the previous
            # library's "done" cannot be taken for this one's; the write after
            # the selection also pushes it out of the H7's ECC write buffer
            timeout 30 probe-rs write $PR b32 "$SEL_ADDR" 0x564C5345 "$l" $(( ~l & 0xFFFFFFFF )) 0 >/dev/null 2>&1 \
                && timeout 30 probe-rs write $PR b32 0x20000008 0 >/dev/null 2>&1 \
                && { ok=1; break; }
            sleep $((2 + RANDOM % 5))
        done
        [ $ok = 1 ] || { echo "probe failure: selecting library $l failed" >&2; exit 2; }
        reset_board || { echo "probe failure: reset for library $l failed" >&2; exit 2; }
        # Started? The firmware clears the selection (and "done") when it
        # takes it; until then the block still holds the previous state.
        t0=$(date +%s); fails=0; hdr=""
        while :; do
            sel=$(timeout 30 probe-rs read $PR b32 "$SEL_ADDR" 1 2>/dev/null | strip | awk '{print $2}') || sel=""
            [ "$sel" = 00000000 ] && break
            [ $(( $(date +%s) - t0 )) -lt 60 ] || { echo "probe failure: library $l: the firmware did not take the selection (sel '$sel')" >&2; exit 2; }
            sleep 1
        done
        sleep "${LIB_POLL:-5}"
        while :; do
            if hdr=$(timeout 60 probe-rs read $PR b32 0x20000000 3 2>/dev/null | strip | awk '{print $2, $4}'); then
                fails=0
            else
                fails=$((fails + 1)); hdr=""
                [ $fails -lt 3 ] || { echo "probe failure: reading library $l failed" >&2; exit 2; }
            fi
            [ "$hdr" = "$HDR_DONE" ] && break
            [ $(( $(date +%s) - t0 )) -lt "${LIB_LIMIT:-1800}" ] || { unfinished+=("$l"); echo "library $l did not finish in ${LIB_LIMIT:-1800} s"; break; }
            sleep "${LIB_POLL:-5}"
        done
        timeout 60 probe-rs read $PR b32 0x20000000 $NWORDS 2>&1 | strip \
            | awk '{for (i = 2; i <= NF; i++) print $i}' > build/words_$l.txt \
            || { echo "probe failure: reading the results of library $l failed" >&2; exit 2; }
        echo "library $l: $(( $(date +%s) - tl )) s"
    done
    python3 merge_words.py $NL build/words.txt $(for l in $(seq 0 $((NL - 1))); do echo build/words_$l.txt; done) \
        || { echo "merging the result blocks failed" >&2; exit 2; }
    PER_LIB_JSON=$(printf '%s\n' "${unfinished[@]}" | jq -R 'select(length > 0) | tonumber' | jq -cs \
        --argjson limit "${LIB_LIMIT:-1800}" '{one_library_per_reset: true, control: "swd", limit_s: $limit, unfinished: .}')
else
PER_LIB_JSON=null
# A probe-rs attach can halt the core briefly; stay off the probe while the
# test runs (5-40 minutes depending on parameters), then poll slowly. The
# 8-bit timer recovers from any halt within its period.
sleep 120
hdr=""
for i in $(seq 1 "${POLL_TRIES:-600}"); do
    # A failed read (probe gone, board off) must not end the script under
    # set -e: it is retried, and the run ends with exit 2 if it never succeeds.
    hdr=$(timeout 60 probe-rs read $PR b32 0x20000000 3 2>/dev/null | strip | awk '{print $2, $4}') || hdr=""
    [ "$hdr" = "$HDR_DONE" ] && break
    sleep 15
done
if [ "$hdr" != "$HDR_DONE" ]; then
    # Hung, or only too slow for the limit? Two reads of the result block 20 s
    # apart: if the counters still move, the test is running (exit 4: a power
    # cycle and a retry would not help; use fewer transfers or more POLL_TRIES).
    a=$(timeout 60 probe-rs read $PR b32 0x20000000 $NWORDS 2>/dev/null | strip | cksum) || a=""
    sleep 20
    b=$(timeout 60 probe-rs read $PR b32 0x20000000 $NWORDS 2>/dev/null | strip | cksum) || b=""
    if [ -n "$a" ] && [ -n "$b" ] && [ "$a" != "$b" ] && [ "${hdr%% *}" = "${HDR_DONE%% *}" ]; then
        echo "stress test still running at the time limit (too slow for POLL_TRIES=${POLL_TRIES:-600}; header: $hdr)" >&2; exit 4
    fi
    echo "stress test did not finish (header: $hdr)" >&2; exit 2
fi
timeout 60 probe-rs read $PR b32 0x20000000 $NWORDS 2>&1 | strip \
    | awk '{for (i = 2; i <= NF; i++) print $i}' > build/words.txt \
    || { echo "probe failure: reading the results failed" >&2; exit 2; }
fi

# IMAGES=per_lib: fw_sha256 is bundle.json's; "images" has every library's
# image (sha256 of its ELF, slot address, bundle) and the bundles.
# IMAGES=combined: the same images of this test (kind "combined"), and the
# bundle holds the MP test's too (their entries in libs have "dir").
IMAGES_JSON=null
if [ "$IMAGES" != one ]; then
    kind=per_library; [ "$IMAGES" = combined ] && kind=combined
    IMAGES_JSON=$(jq -c --arg kind $kind '{kind: $kind, select_addr, align, boot_len,
        bundles: [.bundles[] | {bundle, sha256, boot_sha256, flash_bytes, libs}],
        libs: (.libs | with_entries(.value |= {sha256, base, bytes, bundle, dir}))}' build/bundle.json)
fi
jq -n --arg time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --arg fw_sha256 "$(sha256sum $OUTF | cut -d' ' -f1)" --argjson images "$IMAGES_JSON" \
      --arg source_commit "$(bash ../../lab/tools/source-commit.sh .)" \
      --arg probe_rs "$(probe-rs --version | head -1)" \
      --arg build_flags "$EXTRA" --arg code "$CODE" \
      --arg board "$BOARD_DESC" --arg core "$CORE" \
      --arg opt "$OPT" --argjson lto "$LTO" --arg compiler "$COMPILER" \
      --arg libs "$libs" --argjson toolchain "$toolchain" --arg img "$IMG" --argjson per_lib "$PER_LIB_JSON" \
      --argjson par "$PARAMS_AT_RUNTIME" --arg go "$GO" --arg goack "$(cat build/go.txt 2>/dev/null || true)" \
      '{time: $time, host: "lib-lab1", board: $board, core: $core, per_lib: $per_lib,
        params_at_runtime: ($par == 1), run_params: (if $par == 1 then $go else null end),
        run_params_confirmed: (if $par == 1 then $goack else null end),
        images: $images,
        build_flags: $build_flags, code_location: $code, opt: $opt, lto: ($lto == 1), compiler_libs: $compiler, fw_sha256: $fw_sha256, source_commit: $source_commit, probe_rs: $probe_rs,
        toolchain_image: $img, toolchain: $toolchain,
        libs_pinned: ($libs | split("\n"))}' > build/meta.json

# Record names: nrf5340-rb-stress-<mode>-... as before; other boards are
# prefixed with their own name.
prefix=nrf5340-rb-stress; [ "$BOARD" = nrf5340 ] || prefix=$BOARD-rb-stress
# NORDIC=1: a firmware of its own, its records kept apart from the campaigns
# (which collect *-rb-stress-*): nrf5340-rb-nordic-stress-<mode>-...
[ "$NORDIC" = 1 ] && prefix=nrf5340-rb-nordic-stress
out=$OUTDIR/$prefix-$MODE-$(date -u +%Y%m%dT%H%M%SZ).json
rc=0
if [ "$IMAGES" != one ]; then
    # each library's coverage from its own block and image
    for l in $(seq 0 $((NL - 1))); do
        if [ -f build/words_$l.txt ] && { [ -z "$LIBS" ] || [[ ",$LIBS," == *",$l,"* ]]; }; then
            echo "{\"$l\": {\"words\": \"build/words_$l.txt\", \"lst\": \"build/lib$l/fw.lst\", \"map\": \"build/lib$l/fw.map\"}}"
        fi
    done | jq -s 'add' > build/images.json
    python3 decode.py build/words.txt build/meta.json "$out" --images build/images.json || rc=$?
else
    python3 decode.py build/words.txt build/meta.json "$out" build/fw.lst build/fw.map || rc=$?
fi
echo "record: $out"
exit $rc
