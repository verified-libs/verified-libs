#!/bin/bash
# lib-lab1 setup, step 4: debug probes for the embedded targets.
#  - probe-rs (pinned release, checksum verified) in /usr/local/bin
#  - udev rules so the lab user can use probes without root
#  - lab user in "dialout" for the probes' virtual serial ports
# Run from the copied lab folder with: sudo bash ~/lab/lab-setup-4.sh
set -euo pipefail

PROBE_RS_VERSION=0.32.0
PROBE_RS_SHA256=c2ccc46049e52a5d403ef212078cd637ecda55b662708327960558f83e851ff5
TARBALL=probe-rs-tools-x86_64-unknown-linux-gnu.tar.xz
URL=https://github.com/probe-rs/probe-rs/releases/download/v${PROBE_RS_VERSION}/${TARBALL}
LAB_USER=${SUDO_USER:?Run with sudo from your own user}

echo "== 1/3 probe-rs ${PROBE_RS_VERSION}"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y install curl xz-utils
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -sSfL -o "$tmp/$TARBALL" "$URL"
echo "${PROBE_RS_SHA256}  $tmp/$TARBALL" | sha256sum -c -
tar -xJf "$tmp/$TARBALL" -C "$tmp"
for bin in probe-rs cargo-flash cargo-embed; do
    install -m 0755 "$(find "$tmp" -type f -name "$bin" | head -1)" /usr/local/bin/
done
probe-rs --version

echo "== 2/3 udev rules for debug probes"
# Headless SSH sessions get no seat, so TAG+="uaccess" is not enough:
# grant access through the plugdev group instead.
cat > /etc/udev/rules.d/69-lib-lab1-probes.rules <<'EOF'
# SEGGER J-Link (incl. Nordic DK onboard probes)
SUBSYSTEM=="usb", ATTR{idVendor}=="1366", MODE="0660", GROUP="plugdev"
# ST-LINK (STM32 Nucleo/Discovery onboard probes)
SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="37[0-9a-f][0-9a-f]", MODE="0660", GROUP="plugdev"
# Microchip/Atmel EDBG (Xplained Pro boards)
SUBSYSTEM=="usb", ATTR{idVendor}=="03eb", ATTR{idProduct}=="2111", MODE="0660", GROUP="plugdev"
# Raspberry Pi debugprobe (CMSIS-DAP)
SUBSYSTEM=="usb", ATTR{idVendor}=="2e8a", ATTR{idProduct}=="000c", MODE="0660", GROUP="plugdev"
# CMSIS-DAP v1 probes use HID
KERNEL=="hidraw*", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="2111", MODE="0660", GROUP="plugdev"
KERNEL=="hidraw*", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="000c", MODE="0660", GROUP="plugdev"
EOF
udevadm control --reload-rules
udevadm trigger --subsystem-match=usb --subsystem-match=hidraw

echo "== 3/3 groups for ${LAB_USER}"
usermod -aG plugdev,dialout "$LAB_USER"
id "$LAB_USER"
echo "== Done. No reboot needed; new SSH sessions get the new groups."
