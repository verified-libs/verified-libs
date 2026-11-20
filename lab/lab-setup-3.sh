#!/bin/bash
# lib-lab1 setup, step 3: rootless container engine for the pinned toolchain.
# Run from the copied lab folder with: sudo bash ~/lab/lab-setup-3.sh
set -euo pipefail

echo "== 1/2 Install Podman (rootless, no daemon)"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y install podman uidmap passt

echo "== 2/2 Check rootless setup for ${SUDO_USER:?Run with sudo from your own user}"
grep -q "^$SUDO_USER:" /etc/subuid && grep -q "^$SUDO_USER:" /etc/subgid \
    || { echo "No subuid/subgid range for $SUDO_USER - rootless containers will not work"; exit 1; }
sudo -u "$SUDO_USER" podman --version
echo "== Done. No reboot needed."
