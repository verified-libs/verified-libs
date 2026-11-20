#!/bin/bash
# Switch a board's USB power through the monitor hubs and wait for its probe.
#
# Usage: boardpower.sh list
#        boardpower.sh status BOARD
#        boardpower.sh off|on BOARD
#        boardpower.sh cycle BOARD [OFF_SECONDS]   (default 3)
#
# Boards and ports come from lab/boards.conf (or $BOARDS_CONF). A port is
# switched only if it is also in SAFE_PORTS below: those are the ports tested
# to really cut VBUS. Everything else is refused, above all the cascade port
# (port 4 of the monitor hub) that feeds the second hub.
# Hubs are named by their USB serial number, not by their bus location: the
# location (e.g. 1-1 or 1-2) changes when the hub's cable moves to another
# port on the laptop, the serial does not. The location is looked up in sysfs
# at run time.
# "on" and "cycle" return 0 only when the probe with the board's serial number
# is back on USB (timeout $PROBE_TIMEOUT seconds, default 30).
# After every switch it waits $SWITCH_SETTLE seconds (default 1).
# Needs the udev rule from lab/lab-setup-6.sh (no sudo).
set -euo pipefail

# Dell U2415 #1, upstream TUSB8041 hub (0451:8142), serial 4B0708619185:
# ports 1-3 cut VBUS (tested 2026-11-07); port 4 is the cascade, never.
SAFE_PORTS="4B0708619185:1 4B0708619185:2 4B0708619185:3 9E0C0069B5FA:1 9E0C0069B5FA:2 9E0C0069B5FA:3"
here=$(cd "$(dirname "$0")" && pwd)
CONF=${BOARDS_CONF:-$here/../boards.conf}
PROBE_TIMEOUT=${PROBE_TIMEOUT:-30}

die() { echo "boardpower: $*" >&2; exit 2; }

board_line() {
    awk -v b="$1" '!/^#/ && NF >= 5 && $1 == b { print; exit }' "$CONF"
}

# Prints the sysfs name (e.g. 1-1.2) of the USB device with this vid:pid and serial.
find_probe() {
    local vidpid=$1 serial=$2 d
    for d in /sys/bus/usb/devices/*; do
        [ -f "$d/idVendor" ] && [ -f "$d/serial" ] || continue
        [ "$(cat "$d/idVendor"):$(cat "$d/idProduct")" = "$vidpid" ] || continue
        [ "$(cat "$d/serial")" = "$serial" ] && { basename "$d"; return 0; }
    done
    return 1
}

# Prints the sysfs location (e.g. 1-2) of the TUSB8041 hub with this serial.
find_hub() {
    local serial=$1 d found=""
    for d in /sys/bus/usb/devices/*; do
        [ -f "$d/idVendor" ] && [ -f "$d/serial" ] || continue
        [ "$(cat "$d/idVendor"):$(cat "$d/idProduct")" = "0451:8142" ] || continue
        [ "$(cat "$d/serial")" = "$serial" ] || continue
        [ -z "$found" ] || die "two hubs with serial $serial ($found, $(basename "$d"))"
        found=$(basename "$d")
    done
    [ -n "$found" ] || die "hub $serial not on USB (monitor off, or cable unplugged?)"
    echo "$found"
}

wait_probe() {
    local vidpid=$1 serial=$2 t=0 loc
    while [ "$t" -lt "$PROBE_TIMEOUT" ]; do
        if loc=$(find_probe "$vidpid" "$serial"); then
            echo "probe $serial back at $loc after ${t}s"
            return 0
        fi
        sleep 1; t=$((t + 1))
    done
    echo "boardpower: probe $serial not back after ${PROBE_TIMEOUT}s" >&2
    return 1
}

switch() {
    local hub=$1 port=$2 action=$3 loc
    case " $SAFE_PORTS " in
        *" $hub:$port "*) ;;
        *) die "refusing to switch hub $hub port $port: not in SAFE_PORTS ($SAFE_PORTS)" ;;
    esac
    loc=$(find_hub "$hub")
    uhubctl -l "$loc" -p "$port" -a "$action" >/dev/null
    # The hub and the board need a moment to settle after each switch.
    sleep "${SWITCH_SETTLE:-1}"
}

cmd=${1:-}
case "$cmd" in
    list)
        awk '!/^#/ && NF >= 5' "$CONF"
        exit 0 ;;
    status|off|on|cycle) ;;
    *) die "usage: boardpower.sh list | status|off|on|cycle BOARD [OFF_SECONDS]" ;;
esac

board=${2:-}
[ -n "$board" ] || die "missing BOARD"
line=$(board_line "$board")
[ -n "$line" ] || die "unknown board '$board' (see $CONF)"
read -r _ hub port vidpid serial _ probe_where _ <<< "$line"
# Optional 7th column "separate-probe": the debug probe has its own USB port
# (e.g. the Pico 2 and its Debug Probe), so it does not sit on the switched
# port and stays on USB while the board is off.
sep=0; [ "${probe_where:-}" = separate-probe ] && sep=1
hubloc=$(find_hub "$hub")

case "$cmd" in
    status)
        if loc=$(find_probe "$vidpid" "$serial"); then
            echo "$board: probe present at $loc (configured: hub $hub at $hubloc, port $port)"
            [ $sep = 1 ] || [ "$loc" = "$hubloc.$port" ] || echo "WARNING: $board is not on its configured port" >&2
        else
            echo "$board: probe absent (configured: hub $hub at $hubloc, port $port)"
        fi ;;
    off)
        switch "$hub" "$port" off
        echo "$board: hub $hub ($hubloc) port $port off" ;;
    on)
        switch "$hub" "$port" on
        wait_probe "$vidpid" "$serial" ;;
    cycle)
        off_s=${3:-3}
        loc=$(find_probe "$vidpid" "$serial" || true)
        [ $sep = 1 ] || [ -z "$loc" ] || [ "$loc" = "$hubloc.$port" ] \
            || die "$board's probe is at $loc, not at hub $hub ($hubloc) port $port: fix boards.conf first"
        switch "$hub" "$port" off
        sleep "$off_s"
        switch "$hub" "$port" on
        wait_probe "$vidpid" "$serial" ;;
esac
