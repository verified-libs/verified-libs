#!/bin/bash
# Build, flash and run the DMA-producer stress test (main.c), one library per
# reset over the serial port, then decode. Exit 0 only if every library run
# is error-free, the control was caught and the transfers overlapped the
# reads; 1 if not; 2 if the run on the board failed; 3 if the build failed.
# Usage (on lib-lab1): bash run.sh
# Environment: BOARD (stm32g474, stm32h723; boards with common/<BOARD>/board_dma.h),
#   PROBE (vid:pid:serial, also used to find the serial port), UART_TTY,
#   DMA_PARAMS (TRANSFERS=, PRESCALER=, MAIN_SEED=, DMA_SEED=: the run
#   parameters, sent in the "go" line), LIBS (DMA library indices, default
#   0-7), LIB_LIMIT (seconds per library, default 1800), OPT, LTO, CODE,
#   OUTDIR (default ~/lab-runs), REBUILD=1,
#   DMA_CACHE (0 default, 1, 2: main.c; boards with a data cache), records
#   then -cache<n> and "dma_cache",
#   DMA_SNAP (an address: diagnostic build, main.c DIAG_SNAP; records then
#   -snap and "diag_snap").
# One image per library in a bundle (../common/bundle.py, selection indices
# 96..103); flashed only where an image changed (--preverify).
set -euo pipefail
cd "$(dirname "$0")"
export LC_ALL=C
IMG=verified-libs/toolchain:2026-11-13
BOARD=${BOARD:-stm32g474}
case $BOARD in
    stm32g474) CHIP=STM32G474RE; BOARD_DESC="NUCLEO-G474RE"; CORE="Cortex-M4F, 170 MHz" ;;
    stm32h723) CHIP=STM32H723ZG; BOARD_DESC="NUCLEO-H723ZG"; CORE="Cortex-M7, 64 MHz (reset clock); DMA area in AXI SRAM, not cached" ;;
    *) echo "rb-dma-stress: no DMA layer for BOARD $BOARD yet" >&2; exit 3 ;;
esac
PR="--chip $CHIP${PROBE:+ --probe $PROBE}"
CODE=${CODE:-flash}; OPT=${OPT:--O2}; LTO=${LTO:-0}
OUTDIR=${OUTDIR:-$HOME/lab-runs}
NL=8; NWORDS=$((12 + NL * 12))
LIBS=${LIBS:-$(seq -s, 0 $((NL - 1)))}
P_TR=300000; P_PRE=1; P_MAIN=0x12345678; P_DMA=0xCAFEBABE
for tok in ${DMA_PARAMS:-}; do
    v=${tok#*=}
    case "$tok" in TRANSFERS=*) P_TR=$v ;; PRESCALER=*) P_PRE=$v ;; MAIN_SEED=*) P_MAIN=$v ;; DMA_SEED=*) P_DMA=$v ;;
        *) echo "DMA_PARAMS: unknown $tok" >&2; exit 3 ;; esac
done
uart_tty() {
    [ -n "${PROBE:-}" ] || return 0
    local sn=${PROBE##*:} c
    c=$(ls /dev/serial/by-id/ 2>/dev/null | grep -- "$sn" || true)
    [ "$(echo "$c" | grep -c .)" = 1 ] && echo "/dev/serial/by-id/$c"
    return 0
}
UART_TTY=${UART_TTY:-$(uart_tty)}
[ -n "$UART_TTY" ] || { echo "rb-dma-stress needs the board's serial port (UART_TTY, PROBE)" >&2; exit 3; }

mkdir -p build "$OUTDIR"
libs=$(bash ../nrf5340-rb-bench/fetch-libs.sh)
DMA_CACHE=${DMA_CACHE:-0}
case "$DMA_CACHE" in 0|1|2) ;; *) echo "DMA_CACHE must be 0, 1 or 2" >&2; exit 3 ;; esac
CSUF=""; [ "$DMA_CACHE" = 0 ] || CSUF="-cache$DMA_CACHE"
# the record's core text must say how the DMA area is mapped (2026-11-17 cache records said "not cached")
case "$DMA_CACHE" in
    1) CORE=${CORE/not cached/cached, no maintenance} ;;
    2) CORE=${CORE/not cached/cached, clean+invalidate around each transfer} ;;
esac
DMA_SNAP=${DMA_SNAP:-}
case "$DMA_SNAP" in ""|0x[0-9A-Fa-f]*) ;; *) echo "DMA_SNAP must be a hex address (0x...)" >&2; exit 3 ;; esac
[ -z "$DMA_SNAP" ] || CSUF="$CSUF-snap"
MAKEARGS="BOARD=$BOARD CODE=$CODE OPT='$OPT' LTO=$LTO EXTRA='-DDMA_CACHE=$DMA_CACHE${DMA_SNAP:+ -DDIAG_SNAP=${DMA_SNAP}u}'"
OUTF=build/bundle.json
key=$( { echo "$IMG|$MAKEARGS|$libs|per_lib"
         ( cd .. && find . \( -name build -o -name target -o -name __pycache__ \) -prune -o -type f \
             \( -name '*.c' -o -name '*.cpp' -o -name '*.h' -o -name '*.hpp' -o -name '*.ld' -o -name '*.mk' \
                -o -name Makefile -o -name '*.rs' -o -name 'Cargo.*' -o -name bundle.py \) -print0 | sort -z | xargs -0 sha256sum ); } \
       | sha256sum | cut -d' ' -f1)
if [ "${REBUILD:-0}" != 1 ] && [ -f $OUTF ] \
   && [ "$(cat build/build.key 2>/dev/null)" = "$key $(sha256sum $OUTF | cut -d' ' -f1)" ]; then
    echo "build: unchanged (build key), reusing $OUTF"
else
    rm -f build/build.key
    podman run --rm -v "$PWD/..":/work:Z -w /work/rb-dma-stress "$IMG" \
        sh -c "make clean >/dev/null; python3 -I ../common/bundle.py --libs 0-$((NL - 1)) --index-base 96 --sel-symbol vl_select --sel-from-end 16 -- $MAKEARGS" \
        > build/make.log 2>&1 || { echo "build failed, see build/make.log" >&2; exit 3; }
    echo "$key $(sha256sum $OUTF | cut -d' ' -f1)" > build/build.key
fi
toolchain=$(podman run --rm "$IMG" cat /etc/verified-libs/toolchain.json)

rm -f build/words_*.txt build/go.txt
GO="go transfers=$P_TR prescaler=$P_PRE main_seed=$P_MAIN dma_seed=$P_DMA"
unf=$(VLS_SEL_BASE=96 VLS_LIBS="$LIBS" VLS_GO="$GO" python3 ../common/uart_host.py "$UART_TTY" $NL $NWORDS \
      "${LIB_LIMIT:-1800}" build probe $OUTF -- $PR) || exit 2
python3 ../rb-mp-stress/merge_mp.py --magic 0x564C4431 build/words.txt \
    $(echo "$LIBS" | tr ',' '\n' | sed 's|.*|build/words_&.txt|') || { echo "merging the result blocks failed" >&2; exit 2; }

jq -n --arg time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --arg fw_sha256 "$(sha256sum $OUTF | cut -d' ' -f1)" \
      --arg source_commit "$(bash ../../lab/tools/source-commit.sh .)" \
      --arg probe_rs "$(probe-rs --version | head -1)" \
      --arg go "$GO" --arg goack "$(cat build/go.txt 2>/dev/null || true)" \
      --arg code "$CODE" --arg opt "$OPT" --argjson lto "$LTO" \
      --arg board "$BOARD_DESC" --arg core "$CORE" --arg libs "$libs" --argjson toolchain "$toolchain" --arg img "$IMG" \
      --argjson unf "$unf" --arg libsrun "$LIBS" --argjson limit "${LIB_LIMIT:-1800}" --argjson dmacache "$DMA_CACHE" --arg snap "$DMA_SNAP" \
      '{time: $time, host: "lib-lab1", board: $board, core: $core, run_params: $go, run_params_confirmed: $goack,
        dma_cache: $dmacache, code_location: $code, opt: $opt, lto: ($lto == 1), fw_sha256: $fw_sha256, source_commit: $source_commit,
        probe_rs: $probe_rs, toolchain_image: $img, toolchain: $toolchain, libs_pinned: ($libs | split("\n")),
        per_lib: {one_library_per_reset: true, control: "uart", results_read: "uart_dump", images: "per_lib",
                  limit_s: $limit, libs_run: ($libsrun | split(",") | map(tonumber)), unfinished: $unf}}
       + (if $snap == "" then {} else {diag_snap: $snap} end)' > build/meta.json

out=$OUTDIR/$BOARD-rb-dma-stress$CSUF-$(date -u +%Y%m%dT%H%M%SZ).json
rc=0
python3 decode.py build/words.txt build/meta.json "$out" || rc=$?
echo "record: $out"
[ "$unf" = "[]" ] || { echo "unfinished libraries: $unf" >&2; rc=2; }
exit $rc
