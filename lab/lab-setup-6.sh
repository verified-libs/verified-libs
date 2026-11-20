#!/bin/bash
# lib-lab1 setup, step 6: let the lab user switch USB port power on the
# monitor hubs (Dell U2415, TI TUSB8041 0451:8142) with uhubctl, without sudo.
#
# Only hubs with this vendor:product id are affected. Access goes to the
# dialout group. On kernel >= 6.0 uhubctl switches power through the port
# "disable" files in sysfs; it reads the hub descriptor through /dev/bus/usb.
# The rule makes both of these group-writable for dialout.
#
# Which ports may be switched is decided by lab/tools/boardpower.sh, not here:
# with this rule the lab user can technically switch any port on these hubs,
# including the cascade port that feeds the second hub.
#
# Run from the copied lab folder with: sudo bash ~/lab/lab-setup-6.sh
set -euo pipefail
LAB_USER=${SUDO_USER:?Run with sudo from your own user}

echo "== 1/3 uhubctl installed?"
command -v uhubctl >/dev/null || apt-get install -y --no-install-recommends uhubctl
uhubctl -v

echo "== 2/3 udev rule /etc/udev/rules.d/52-usb-hub-power.rules"
cat > /etc/udev/rules.d/52-usb-hub-power.rules <<'EOF'
# lib-lab1 (lab-setup-6.sh): per-port power switching on the Dell U2415
# monitor hubs (TI TUSB8041, 0451:8142) for the dialout group, used by uhubctl.
# Hub device node (descriptor access):
SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTR{idVendor}=="0451", ATTR{idProduct}=="8142", MODE="0664", GROUP="dialout"
# Port power control files (kernel >= 6.0), created when the hub driver binds:
SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_interface", DRIVER=="hub", ATTRS{idVendor}=="0451", ATTRS{idProduct}=="8142", RUN+="/bin/sh -c 'chown -f root:dialout $sys$devpath/*-port*/disable; chmod -f 0664 $sys$devpath/*-port*/disable'"
EOF
chmod 0644 /etc/udev/rules.d/52-usb-hub-power.rules
udevadm control --reload-rules
udevadm trigger --subsystem-match=usb
udevadm settle

echo "== 3/3 Check"
id -nG "$LAB_USER" | grep -qw dialout || echo "WARNING: $LAB_USER is not in dialout"
# The hub's bus location (1-1, 1-2, ...) depends on the laptop port; check them all.
ls -l /sys/bus/usb/devices/*/*:1.0/*-port*/disable 2>/dev/null | grep dialout || echo "no TUSB8041 hub present"
echo "== Done. Test as $LAB_USER (no sudo): uhubctl  (lists the hubs and their locations)"
