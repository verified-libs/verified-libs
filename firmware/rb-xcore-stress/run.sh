#!/bin/bash
# Build, flash and run the cross-core SPSC test on the nRF5340 DK (main.c),
# one library per reset over the serial port, then decode. Exit 0 only if
# every library documented for several cores is error-free in both
# directions and the control was caught; 1 if not; 2 if the run on the board
# failed; 3 if the build failed.
# Environment: PROBE (vid:pid:serial), UART_TTY, XC_PARAMS (MODE=1|2,
#   TRANSFERS=, MAIN_SEED=, NET_SEED=), LIBS (indices 0-16, default all),
#   LIB_LIMIT (default 1800), OUTDIR (default ~/lab-runs), REBUILD=1,
#   NET_ERASE=1: write a changed network core image (probe-rs unlocks the
#   core by erasing both cores' flash; see below).
# The network core image is flashed first (probe-rs nRF5340_xxAA, the
# network flash at 0x01000000), then the application core image (at 0x0:
# it replaces a bundle there).
set -euo pipefail
cd "$(dirname "$0")"
export LC_ALL=C
IMG=verified-libs/toolchain:2026-11-13
PRA="--chip nRF5340_xxAA_APPONLY${PROBE:+ --probe $PROBE}"
PRN="--chip nRF5340_xxAA${PROBE:+ --probe $PROBE}"
OUTDIR=${OUTDIR:-$HOME/lab-runs}
NL=17; NWORDS=$((12 + NL * 16))
LIBS=${LIBS:-$(seq -s, 0 $((NL - 1)))}
P_MODE=1; P_TR=300000; P_MAIN=0x12345678; P_NET=0xCAFEBABE
for tok in ${XC_PARAMS:-}; do
    v=${tok#*=}
    case "$tok" in MODE=*) P_MODE=$v ;; TRANSFERS=*) P_TR=$v ;; MAIN_SEED=*) P_MAIN=$v ;; NET_SEED=*) P_NET=$v ;;
        *) echo "XC_PARAMS: unknown $tok" >&2; exit 3 ;; esac
done
uart_tty() {
    [ -n "${PROBE:-}" ] || return 0
    local sn=${PROBE##*:} c
    c=$(ls /dev/serial/by-id/ 2>/dev/null | grep -- "$sn" | grep -- "-if04\$" || true)   # the J-Link's UARTE0 port
    [ "$(echo "$c" | grep -c .)" = 1 ] && echo "/dev/serial/by-id/$c"
    return 0
}
UART_TTY=${UART_TTY:-$(uart_tty)}
[ -n "$UART_TTY" ] || { echo "rb-xcore-stress needs the board's serial port (UART_TTY, PROBE)" >&2; exit 3; }
strip() { sed 's/\x1b\[[0-9;]*m//g'; }

mkdir -p build "$OUTDIR"
libs=$(bash ../nrf5340-rb-bench/fetch-libs.sh)
key=$( { echo "$IMG|$libs"
         ( cd .. && find . \( -name build -o -name target -o -name __pycache__ \) -prune -o -type f \
             \( -name '*.c' -o -name '*.cpp' -o -name '*.h' -o -name '*.hpp' -o -name '*.ld' -o -name '*.mk' \
                -o -name Makefile -o -name '*.rs' -o -name 'Cargo.*' -o -name '*.py' \) -print0 | sort -z | xargs -0 sha256sum ); } \
       | sha256sum | cut -d' ' -f1)
if [ "${REBUILD:-0}" != 1 ] && [ -f build/app/fw.elf ] && [ -f build/net/fw.elf ] \
   && [ "$(cat build/build.key 2>/dev/null)" = "$key $(cat build/app/fw.elf build/net/fw.elf | sha256sum | cut -d' ' -f1)" ]; then
    echo "build: unchanged (build key)"
else
    rm -f build/build.key
    podman run --rm -v "$PWD/..":/work:Z -w /work/rb-xcore-stress "$IMG" sh -c "make clean >/dev/null; make" \
        > build/make.log 2>&1 || { echo "build failed, see build/make.log" >&2; exit 3; }
    echo "$key $(cat build/app/fw.elf build/net/fw.elf | sha256sum | cut -d' ' -f1)" > build/build.key
fi
toolchain=$(podman run --rm "$IMG" cat /etc/verified-libs/toolchain.json)

# The network core image is written only when it changed. After every
# reset of the application core the network core is held off and, once
# released, locked to the debugger until its firmware opens it again
# (hardened APPROTECT), so it cannot be read or written without an erase:
# probe-rs unlocks it by erasing both cores' flash (--allow-erase-all,
# NET_ERASE=1). The state file remembers which image the network flash
# holds (per probe); the application image is written by uart_host.py after.
NETSHA=$(sha256sum build/net/fw.elf | cut -d' ' -f1)
NETSTATE=$HOME/.cache/verified-libs/flash/nrf5340-net-${PROBE##*:}.sha256
if [ "$(cat "$NETSTATE" 2>/dev/null)" = "$NETSHA" ]; then
    echo "network core: image unchanged, not written"
else
    [ "${NET_ERASE:-0}" = 1 ] || { echo "the network core image changed: NET_ERASE=1 to write it (erases both cores' flash)" >&2; exit 2; }
    rm -f "$NETSTATE"
    timeout 300 probe-rs download $PRN --allow-erase-all build/net/fw.elf 2>&1 | strip | tail -n 2 \
        || { echo "probe failure: flashing the network core failed" >&2; exit 2; }
    mkdir -p "$(dirname "$NETSTATE")"; echo "$NETSHA" > "$NETSTATE"
    # the application flash was erased too: the state of its bundle is gone
    rm -f "$HOME/.cache/verified-libs/flash/"*.json 2>/dev/null || true
fi

rm -f build/words_*.txt build/go.txt
GO="go mode=$P_MODE transfers=$P_TR main_seed=$P_MAIN net_seed=$P_NET"
unf=$(VLS_SEL_BASE=128 VLS_LIBS="$LIBS" VLS_GO="$GO" python3 ../common/uart_host.py "$UART_TTY" $NL $NWORDS \
      "${LIB_LIMIT:-1800}" build probe build/app/fw.elf -- $PRA) || exit 2
python3 ../rb-mp-stress/merge_mp.py --magic 0x564C5831 --slot 16 build/words.txt \
    $(echo "$LIBS" | tr ',' '\n' | sed 's|.*|build/words_&.txt|') || { echo "merging the result blocks failed" >&2; exit 2; }

jq -n --arg time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --arg app_sha256 "$(sha256sum build/app/fw.elf | cut -d' ' -f1)" --arg net_sha256 "$(sha256sum build/net/fw.elf | cut -d' ' -f1)" \
      --arg source_commit "$(bash ../../lab/tools/source-commit.sh .)" --arg probe_rs "$(probe-rs --version | head -1)" \
      --arg go "$GO" --arg goack "$(cat build/go.txt 2>/dev/null || true)" \
      --arg libs "$libs" --argjson toolchain "$toolchain" --arg img "$IMG" \
      --argjson unf "$unf" --arg libsrun "$LIBS" --argjson limit "${LIB_LIMIT:-1800}" \
      '{time: $time, host: "lib-lab1", board: "nRF5340 DK", core: "application and network core (Cortex-M33 each)",
        run_params: $go, run_params_confirmed: $goack, fw_sha256: $app_sha256, net_fw_sha256: $net_sha256,
        source_commit: $source_commit, probe_rs: $probe_rs, toolchain_image: $img, toolchain: $toolchain,
        libs_pinned: ($libs | split("\n")),
        per_lib: {one_library_per_reset: true, control: "uart", results_read: "uart_dump", images: "one",
                  limit_s: $limit, libs_run: ($libsrun | split(",") | map(tonumber)), unfinished: $unf}}' > build/meta.json

out=$OUTDIR/nrf5340-rb-xcore-stress-mode$P_MODE-$(date -u +%Y%m%dT%H%M%SZ).json
rc=0
python3 decode.py build/words.txt build/meta.json "$out" || rc=$?
echo "record: $out"
[ "$unf" = "[]" ] || { echo "unfinished libraries: $unf" >&2; rc=2; }
exit $rc
