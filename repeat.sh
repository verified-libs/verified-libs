#!/bin/bash
# Repeat our results on your own board, with one command.
#
#   ./repeat.sh                 quick: up to six configurations of the benchmark and two
#                               stress modes, ~15-25 min
#   ./repeat.sh --level full    every configuration of the benchmark, twice, and
#                               every stress mode, ~2-4 h
#   ./repeat.sh --board pico2   choose a board when more than one is connected
#   ./repeat.sh --bundle N      quick level: the benchmark bundle to take the
#                               configurations from (default 0)
#   ./repeat.sh --only bench    the benchmark alone (or: --only stress)
#   ./repeat.sh --check         only check the tools and find the board
#
# Supported: the six boards of the lab, each through its own on-board debug
# probe and the serial port of that probe (one USB cable, no extra probe):
#   nrf5340dk      nRF5340 DK (J-Link OB)
#   nucleo-g0b1re  NUCLEO-G0B1RE (ST-LINK/V2-1)
#   nucleo-g474re  NUCLEO-G474RE (STLINK-V3E)
#   nucleo-h723zg  NUCLEO-H723ZG (STLINK-V3E)
#   sam-d20-xpro   SAM D20 Xplained Pro (EDBG; OpenOCD, not probe-rs)
#   pico2          Raspberry Pi Pico 2 with the Raspberry Pi Debug Probe
#
# What it does: finds the board by its probe's USB identity; for each test
# takes the source at the commit of OUR record of that test (a git worktree
# of it, or this tree itself if it was exported from that commit or from one
# with the same test sources, files EXPORTED_FROM and SAME_SOURCES), so your
# firmware is byte for byte the one we ran
# (fw_sha256 shows it); --out must then be outside any git clone;
# runs it; compares your record with ours (lab/tools/compare-records.py for
# the benchmark, firmware/nrf5340-rb-stress/reference.py against our night
# campaign, records/campaign, for the stress test);
# The benchmark (version 2, records/bench-v2) is built from this tree as it
# is: one image per configuration and placement, packed into bundles. The
# tree builds the images of our records byte for byte (bash
# firmware/nrf5340-rb-bench/oneverify.sh checks that without a board), and
# the comparison says for every image whether yours is the same.
# and packs everything into one archive to send us
# (site/content/reproduce.md, "Send us your result").
#
# Needs: Linux, git, podman, jq, python3,
# probe-rs 0.32 (OpenOCD 0.12 for the SAM D20) with the probe-rs udev rules,
# and the toolchain image verified-libs/toolchain:2026-11-13
# (toolchain/README.md; --build-image builds it, about an hour). The first
# run fetches the pinned libraries from their repositories (libs.lock).
# Flash: each stress test writes the board's flash once (images are verified
# first and not rewritten when unchanged). The benchmark writes one bundle
# at the quick level and every bundle of the board at the full level (nRF5340
# DK 5, NUCLEO-G0B1RE 9, NUCLEO-G474RE 9, NUCLEO-H723ZG 5, SAM D20 Xplained
# Pro 18, Pico 2 2); a bundle that is on the board already is not written.
# The nRF5340 DK also needs Nordic's nRF5 SDK zip, which we may not
# redistribute: --nrf5-sdk PATH (firmware/nrf5340-rb-bench/nrf5-sdk.lock
# names the file and its checksum).
set -uo pipefail
REPO=$(cd "$(dirname "$0")" && pwd)
IMG=verified-libs/toolchain:2026-11-13
LEVEL=quick; BOARD=; OUT=; CHECK_ONLY=0; BUILD_IMAGE=0; SDK=${NRF5_SDK:-}; QB=0; ONLY=
while [ $# -gt 0 ]; do
    case $1 in
        --level) LEVEL=$2; shift ;;
        --board) BOARD=$2; shift ;;
        --out) OUT=$2; shift ;;
        --nrf5-sdk) SDK=$2; shift ;;
        --bundle) QB=$2; shift ;;
        --only) ONLY=$2; shift ;;
        --check) CHECK_ONLY=1 ;;
        --build-image) BUILD_IMAGE=1 ;;
        -h|--help) sed -n '2,50p' "$0"; exit 0 ;;
        *) echo "unknown argument $1 (--help)" >&2; exit 2 ;;
    esac
    shift
done
case $LEVEL in quick|full) ;; *) echo "--level quick|full" >&2; exit 2 ;; esac
case $ONLY in ''|bench|stress) ;; *) echo "--only bench|stress" >&2; exit 2 ;; esac
case $QB in ''|*[!0-9]*) echo "--bundle N" >&2; exit 2 ;; esac
say() { printf '%s\n' "$*"; }
die() { printf 'repeat.sh: %s\n' "$*" >&2; exit 2; }

# ---- tools ----
miss=
for t in git podman jq python3; do command -v $t >/dev/null || miss="$miss $t"; done
[ -n "$miss" ] && die "missing:$miss"
if [ "$BUILD_IMAGE" = 1 ] && ! podman image exists "$IMG"; then
    tmp=$(mktemp -d)
    podman image exists verified-libs/toolchain:2026-11-05 || \
        podman build -t verified-libs/toolchain:2026-11-05 -f "$REPO/toolchain/Containerfile" "$REPO/toolchain" || die "image 2026-11-05 did not build"
    for a in $(sed -n 's/^ARG \(RUST_STD_V[A-Z0-9]*\)=\(.*\.tar\.xz\)$/\2/p' "$REPO/toolchain/rust-targets/Containerfile"); do
        curl -fsSL -o "$tmp/$a" "https://static.rust-lang.org/dist/2026-10-15/$a" || die "download of $a failed"
    done
    podman build -t "$IMG" -f "$REPO/toolchain/rust-targets/Containerfile" "$tmp" || die "image $IMG did not build"
    rm -rf "${tmp:?}"
fi
podman image exists "$IMG" || die "toolchain image $IMG not found: ./repeat.sh --build-image (about an hour), or toolchain/README.md"

# ---- board ----
# name, firmware board, how to recognise its probe
usbdevs() {   # vid:pid serial product
    local d
    for d in /sys/bus/usb/devices/*; do
        [ -f "$d/idVendor" ] || continue
        printf '%s:%s %s %s\n' "$(cat "$d/idVendor")" "$(cat "$d/idProduct")" "$(cat "$d/serial" 2>/dev/null || echo -)" \
            "$( { cat "$d/product" 2>/dev/null || echo -; } | tr ' ' '_')"
    done
}
stlink_board() {   # the ST-LINK's mass-storage volume is named after the Nucleo (NOD_G474RE ...)
    local sn=$1 l
    for l in /dev/disk/by-label/NOD_*; do
        [ -e "$l" ] || continue
        udevadm info --query=property --name="$l" 2>/dev/null | grep -qx "ID_SERIAL_SHORT=$sn" && { basename "$l"; return; }
    done
}
found=()
while read -r vp sn prod; do
    b=
    case $vp in
        1366:*) case $sn in 0009601*|9601*) b=nrf5340dk ;; esac ;;   # Nordic DK J-Link serials start with the board number (960: nRF5340 DK)
        0483:374b|0483:374e|0483:3753|0483:3754)
            case $(stlink_board "$sn") in
                NOD_G0B1RE) b=nucleo-g0b1re ;; NOD_G474RE) b=nucleo-g474re ;; NOD_H723ZG) b=nucleo-h723zg ;;
                *) say "note: ST-LINK $sn: not one of our Nucleo boards (or its USB drive is not visible)" ;;
            esac ;;
        03eb:2111) case $sn in ATML1873*) b=sam-d20-xpro ;; *) say "note: EDBG $sn: not a SAM D20 Xplained Pro" ;; esac ;;
        2e8a:000c) b=pico2 ;;   # the Debug Probe; the target must be a Pico 2 (RP2350)
    esac
    [ -n "$b" ] && found+=("$b $vp:$sn")
done < <(usbdevs)
[ ${#found[@]} -gt 0 ] || die "no supported board found (connect it by its debug USB port; --help lists the boards)"
if [ -n "$BOARD" ]; then
    sel=$(printf '%s\n' "${found[@]}" | awk -v b="$BOARD" '$1 == b' | head -1)
    [ -n "$sel" ] || die "board $BOARD not found; connected: $(printf '%s ' "${found[@]%% *}")"
elif [ ${#found[@]} -gt 1 ]; then
    die "more than one board connected ($(printf '%s ' "${found[@]%% *}")): choose one with --board"
else
    sel=${found[0]}
fi
BOARD=${sel%% *}; PROBE=${sel#* }
case $BOARD in
    nrf5340dk) FWB=nrf5340 ;; nucleo-g0b1re) FWB=stm32g0b1 ;; nucleo-g474re) FWB=stm32g474 ;;
    nucleo-h723zg) FWB=stm32h723 ;; sam-d20-xpro) FWB=samd20 ;; pico2) FWB=rp2350 ;;
esac
if [ "$FWB" = samd20 ]; then
    command -v openocd >/dev/null || die "the SAM D20 needs OpenOCD 0.12 (openocd not found)"
else
    command -v probe-rs >/dev/null || die "probe-rs 0.32 not found (https://probe.rs)"
    probe-rs --version 2>/dev/null | grep -q ' 0\.32\.' || say "note: probe-rs $(probe-rs --version 2>/dev/null | head -1): we use 0.32"
fi
ls /dev/serial/by-id/ 2>/dev/null | grep -q -- "${PROBE##*:}" || die "no serial port of probe ${PROBE##*:} in /dev/serial/by-id (the tests talk to the board over it)"
if [ "$FWB" = nrf5340 ] && [ "$ONLY" != stress ] && [ "$(cat "$REPO/firmware/nrf5340-rb-bench/build/libs/nrf5-sdk/SHA256" 2>/dev/null)" != "$(awk '$1 == "sha256" {print $2}' "$REPO/firmware/nrf5340-rb-bench/nrf5-sdk.lock")" ]; then
    [ -n "$SDK" ] && [ -f "$SDK" ] || die "the benchmark images of the nRF5340 DK need Nordic's nRF5 SDK zip (firmware/nrf5340-rb-bench/nrf5-sdk.lock): --nrf5-sdk PATH"
    SDK=$(cd "$(dirname "$SDK")" && pwd)/$(basename "$SDK")
fi
say "board: $BOARD (probe $PROBE), level $LEVEL"
[ "$CHECK_ONLY" = 1 ] && { say "tools and board OK"; exit 0; }

# ---- our records to repeat ----
LIBS_JSON=$REPO/site/data/libs.json
bj=$(jq -c --arg b "$BOARD" '.boards[] | select(.id == $b)' "$LIBS_JSON")
[ -n "$bj" ] || die "$BOARD not in site/data/libs.json"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=${OUT:-$HOME/verified-libs-repeat/$BOARD-$STAMP}
mkdir -p "$OUT/records" "$OUT/logs" "$OUT/src"
OUT=$(cd "$OUT" && pwd)
: > "$OUT/summary.txt"
note() { say "$*"; printf '%s\n' "$*" >> "$OUT/summary.txt"; }

src_at() {   # a worktree of the commit (made once), printed
    local c=$1 w=$OUT/src/$1
    if [ ! -d "$w" ]; then
        if git -C "$REPO" cat-file -e "$c^{commit}" 2>/dev/null; then
            git -C "$REPO" worktree add -q --detach "$w" "$c" || die "could not check out $c"
        elif { [ -f "$REPO/EXPORTED_FROM" ] && [ "$(cut -c1-12 "$REPO/EXPORTED_FROM")" = "${c:0:12}" ]; } \
             || { [ -f "$REPO/SAME_SOURCES" ] && grep -qx "${c:0:12}" "$REPO/SAME_SOURCES"; }; then
            # the public tree, exported from the commit of our record or from
            # one with the same test sources (SAME_SOURCES): a copy, with the
            # record's commit in COMMIT (lab/tools/source-commit.sh)
            mkdir -p "$w"; cp -a "$REPO/firmware" "$REPO/lab" "$w/"
            rm -rf "${w:?}/firmware/nrf5340-rb-bench/build"
            echo "$c" > "$w/COMMIT"
        else
            die "our record of this test was made at $c, which is neither in this clone nor a commit this tree has the sources of (EXPORTED_FROM, SAME_SOURCES): update the clone"
        fi
        # the pinned libraries: fetched once into this clone, then copied as
        # hard links (the build container sees only firmware/, so no symlink);
        # fetch-libs.sh in the worktree checks out that commit's pins
        if [ ! -d "$REPO/firmware/nrf5340-rb-bench/build/libs" ]; then
            say "fetching the pinned libraries (libs.lock), once ..." >&2   # stdout is the path
            bash "$REPO/firmware/nrf5340-rb-bench/fetch-libs.sh" > "$OUT/logs/fetch-libs.log" 2>&1 \
                || die "fetching the libraries failed (logs/fetch-libs.log)"
        fi
        mkdir -p "$w/firmware/nrf5340-rb-bench/build"
        cp -al "$REPO/firmware/nrf5340-rb-bench/build/libs" "$w/firmware/nrf5340-rb-bench/build/"
    fi
    echo "$w"
}
newest_after() {   # newest record matching glob, written after the marker
    find "$(dirname "$1")" -maxdepth 1 -name "$(basename "$1")" -newer "$2" -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-
}

bench() {   # benchmark version 2: one image per configuration and placement
    local c w dir sel= bundles=$QB passes=1 rc
    dir=$REPO/records/bench-v2/$FWB
    ls "$dir"/*.json >/dev/null 2>&1 || { note "benchmark: no records of ours for $BOARD, skipped"; return; }
    c=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || cat "$REPO/EXPORTED_FROM")
    w=$(src_at "$c") || exit 2
    if [ "$FWB" = nrf5340 ] && [ ! -f "$w/firmware/nrf5340-rb-bench/build/libs/nrf5-sdk/SHA256" ]; then
        if [ -f "$REPO/firmware/nrf5340-rb-bench/build/libs/nrf5-sdk/SHA256" ]; then
            cp -al "$REPO/firmware/nrf5340-rb-bench/build/libs/nrf5-sdk" "$w/firmware/nrf5340-rb-bench/build/libs/"
        else
            bash "$w/firmware/nrf5340-rb-bench/nrf5-sdk.sh" "$SDK" > "$OUT/logs/nrf5-sdk.log" 2>&1 || { note "benchmark: FAILED, the nRF5 SDK zip was not taken (logs/nrf5-sdk.log)"; return; }
        fi
    fi
    if [ "$LEVEL" = full ]; then bundles=; passes=2; fi
    say "benchmark, building the images${bundles:+ of bundle $bundles} ..."
    ( cd "$w/firmware/nrf5340-rb-bench" && BUNDLE=$bundles bash onebuild.sh table "$FWB" ) > "$OUT/logs/bench-build.log" 2>&1 \
        || { note "benchmark: FAILED, the build (logs/bench-build.log)"; return; }
    if [ "$LEVEL" = quick ]; then   # up to six configurations that lie wholly (eight placements) in the bundle
        sel=$(jq -r '[.images | group_by(.adapter)[] | select(length == 8) | .[0].adapter | select(startswith("adapter_"))] | .[0:6] | join(",")' \
            "$w/firmware/nrf5340-rb-bench/build/v2/$FWB/bundle$QB.json")
        [ -n "$sel" ] || { note "benchmark: FAILED, no whole configuration in bundle $QB (logs/bench-build.log)"; return; }
    fi
    say "benchmark, ${sel:+configurations $sel, }$passes pass(es); a bundle that is not on the board is written to it ..."
    ( cd "$w/firmware/nrf5340-rb-bench" && PROBE=$PROBE python3 run-one.py "$FWB" "$OUT/bench-runs" --flash --passes $passes \
        ${bundles:+--bundle $bundles} ${sel:+--adapter "$sel"} ) > "$OUT/logs/bench.log" 2>&1
    rc=$?
    python3 "$w/firmware/nrf5340-rb-bench/onerecords.py" --out "$OUT/records/bench-v2" "$OUT/bench-runs" > "$OUT/logs/bench-records.log" 2>&1
    if [ $rc -ne 0 ] || ! ls "$OUT/records/bench-v2/$FWB"/*.json >/dev/null 2>&1; then
        note "benchmark: FAILED (run-one.py exit $rc: 1 a run without a result, 2 probe or board; logs/bench.log, logs/bench-records.log)"; return
    fi
    note "benchmark: $(grep -o '[0-9]* runs, .* flash writes' "$OUT/bench-runs/run.log" | tail -n 1); $(tail -n 1 "$OUT/logs/bench-records.log")"
    python3 "$REPO/lab/tools/compare-records.py" "$dir" "$OUT/records/bench-v2/$FWB" > "$OUT/compare-bench.txt" 2>&1
    case $? in 0) note "benchmark: same as ours ($(sed -n 3p "$OUT/compare-bench.txt"))" ;;
               1) note "benchmark: DIFFERS from ours, see compare-bench.txt" ;;
               *) note "benchmark: could not be compared, see compare-bench.txt" ;; esac
}

stress() {   # MODE
    local mode=$1 c w m mine rc reps=16
    c=$(jq -r '.stress.commit // empty' <<< "$bj")
    [ -n "$c" ] || { note "stress $mode: no campaign of ours for $BOARD, skipped"; return; }
    w=$(src_at "$c") || exit 2
    m=$OUT/.mark-stress-$mode; touch "$m"
    say "stress $mode at $c ..."
    ( cd "$w/firmware/nrf5340-rb-stress" && \
      STRESS_PARAMS="-DTRANSFERS=20000u -DSWEEP_REPS=${reps}u" PER_LIB=1 OUTDIR="$OUT/records" \
      BOARD=$FWB PROBE=$PROBE bash run.sh "$mode" ) > "$OUT/logs/stress-$mode.log" 2>&1
    rc=$?
    case $rc in
        0) note "stress $mode: no errors in the libraries, negative control caught" ;;
        1) note "stress $mode: ERRORS or control not caught: $(grep -m1 'real libraries error-free' "$OUT/logs/stress-$mode.log")" ;;
        *) note "stress $mode: run failed (exit $rc: 2 board/probe, 3 build, 4 too slow), logs/stress-$mode.log"; return ;;
    esac
    # library by library against our night campaign (records/campaign)
    mine=$(newest_after "$OUT/records/$FWB-rb-stress-$mode-2*.json" "$m")
    [ -n "$mine" ] && [ -f "$REPO/records/campaign/$BOARD.json" ] || return
    python3 "$REPO/firmware/nrf5340-rb-stress/reference.py" compare "$REPO/records/campaign/$BOARD.json" "$mine" \
        > "$OUT/compare-stress-$mode.txt" 2>&1
    case $? in 0) note "  against our campaign: as ours (compare-stress-$mode.txt)" ;;
               1) note "  against our campaign: DIFFERS: $(tail -1 "$OUT/compare-stress-$mode.txt"), see compare-stress-$mode.txt" ;;
               *) note "  against our campaign: not compared: $(head -1 "$OUT/compare-stress-$mode.txt")" ;; esac
}

note "verified-libs repeat on $BOARD, level $LEVEL, $STAMP; repeat.sh from $(git -C "$REPO" rev-parse --short=12 HEAD 2>/dev/null || cut -c1-12 "$REPO/EXPORTED_FROM" 2>/dev/null || echo unknown)"
[ "$ONLY" = stress ] || bench
[ "$ONLY" = bench ] && stress() { :; }
stress single
stress sweep
if [ "$LEVEL" = full ]; then
    for m in block dma sweep-block sweep-dma; do stress $m; done
    [ "$FWB" = rp2350 ] && for m in smp sweep-smp; do stress $m; done
fi

# ---- the archive ----
probe_fw() {   # the probe's firmware version, read without writing anything
    local sn=${PROBE##*:} d bcd=
    for d in /sys/bus/usb/devices/*; do
        [ "$(cat "$d/serial" 2>/dev/null)" = "$sn" ] && { bcd=$(cat "$d/bcdDevice" 2>/dev/null); break; }
    done
    case $FWB in
        samd20)   # OpenOCD prints the EDBG's CMSIS-DAP firmware on init
            timeout 30 openocd -c "adapter driver cmsis-dap; cmsis_dap_vid_pid 0x03eb 0x2111; cmsis_dap_backend hid" \
                -f board/atmel_samd20_xplained_pro.cfg -c "init; shutdown" 2>&1 | sed -n 's/.*CMSIS-DAP: FW Version = /EDBG CMSIS-DAP /p' | head -1 ;;
        rp2350) ;;   # the Debug Probe gives its version as the USB device release (bcdDevice) only
        *)   # J-Link and ST-LINK: in probe-rs' log when it opens the probe
            RUST_LOG=probe_rs=debug timeout 40 probe-rs info --probe "$PROBE" --protocol swd 2>&1 \
                | sed 's/\x1b\[[0-9;]*m//g' \
                | sed -n -e 's/.*J-Link: Firmware version: //p' -e 's/.*STLink version: (\([0-9]*\), \([0-9]*\)).*/ST-LINK V\1J\2/p' | head -1 ;;
    esac
    echo "(USB device release ${bcd:-?})"
}
{
    echo "board: $BOARD ($FWB)"; echo "probe: $PROBE"
    echo "probe product: $(usbdevs | awk -v s="${PROBE##*:}" '$2 == s {print $3}')"
    echo "probe firmware: $(probe_fw | paste -sd' ')"
    echo "host: $(uname -srm)"; echo "podman: $(podman --version)"
    echo "image: $IMG $(podman image inspect --format '{{.Id}}' "$IMG" 2>/dev/null)"
    [ "$FWB" = samd20 ] && echo "openocd: $(openocd --version 2>&1 | head -1)" || echo "probe-rs: $(probe-rs --version 2>/dev/null | head -1)"
    echo "Fill in: board revision printed on the board, how the board was powered, anything changed:"
} > "$OUT/info.txt"
for c in "$OUT"/src/*; do
    [ -d "$c" ] || continue
    if [ -f "$c/COMMIT" ]; then rm -rf "${c:?}"; else git -C "$REPO" worktree remove --force "$c"; fi
done
rmdir "$OUT/src" 2>/dev/null; rm -f "$OUT"/.mark-*
tar -czf "$OUT.tar.gz" -C "$(dirname "$OUT")" "$(basename "$OUT")"
say ""
cat "$OUT/summary.txt"
say ""
say "Everything is in $OUT.tar.gz. Add the board revision to info.txt"
say "if you can, and send it to contact@verified-libs.org (site/content/reproduce.md)."
grep -q "FAILED\|ERRORS\|DIFFERS\|run failed" "$OUT/summary.txt" && exit 1
exit 0
