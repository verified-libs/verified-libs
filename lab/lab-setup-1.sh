#!/bin/bash
# lib-lab1 base setup, step 1. Run with: sudo bash ~/lab-setup-1.sh
set -euo pipefail

echo "== 1/4 SSH key only (no passwords over the network)"
# Safety: stop if the user has no key, so we don't lock ourselves out
USER_HOME="$(getent passwd "${SUDO_USER:?Run with sudo from your own user}" | cut -d: -f6)"
grep -q '^ssh-ed25519 ' "$USER_HOME/.ssh/authorized_keys" || { echo "No key in authorized_keys - stopping"; exit 1; }
printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\n' > /etc/ssh/sshd_config.d/10-key-only.conf
sshd -t
systemctl restart ssh

echo "== 2/4 Run with the lid closed, never sleep"
mkdir -p /etc/systemd/logind.conf.d
printf '[Login]\nHandleLidSwitch=ignore\nHandleLidSwitchExternalPower=ignore\nHandleLidSwitchDocked=ignore\n' > /etc/systemd/logind.conf.d/10-lid.conf
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

echo "== 3/4 No graphical desktop at boot"
systemctl set-default multi-user.target

echo "== 4/4 Update"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y full-upgrade
apt-get -y install git build-essential lm-sensors linux-tools-common "linux-tools-$(uname -r)" || true

echo "== Done. Rebooting in 5 seconds."
sleep 5
reboot
