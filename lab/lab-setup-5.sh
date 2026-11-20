#!/bin/bash
# lib-lab1 setup, step 5: limited passwordless sudo for routine lab tasks.
#
# The lab user may run ONLY the commands below without a password. Everything
# else (new setup scripts, config changes) still needs the owner's password.
# All files involved are owned by root and not writable by the lab user;
# otherwise the allowlist could be edited and would equal full sudo.
#
# Run from the copied lab folder with: sudo bash ~/lab/lab-setup-5.sh
set -euo pipefail
LAB_USER=${SUDO_USER:?Run with sudo from your own user}

echo "== 1/3 Package allowlist /etc/lib-lab1/allowed-packages"
install -d -m 0755 -o root -g root /etc/lib-lab1
cat > /etc/lib-lab1/allowed-packages <<'EOF'
# Packages lab-install may install without a password. One per line.
# Edit only as root; adding a package here is an owner decision.
jq
bc
picocom
usbutils
uhubctl
openocd
python3-venv
hyperfine
stress-ng
EOF
chmod 0644 /etc/lib-lab1/allowed-packages

echo "== 2/3 /usr/local/sbin/lab-install"
cat > /usr/local/sbin/lab-install <<'EOF'
#!/bin/bash
# Install packages from /etc/lib-lab1/allowed-packages only.
# Usage: sudo lab-install PKG...
set -euo pipefail
LIST=/etc/lib-lab1/allowed-packages
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
[ $# -gt 0 ] || { echo "usage: lab-install PKG..." >&2; exit 2; }
for p in "$@"; do
    [[ "$p" =~ ^[a-z0-9][a-z0-9+.-]*$ ]] || { echo "invalid package name: $p" >&2; exit 2; }
    grep -qxF -- "$p" <(grep -v '^#' "$LIST") || { echo "not in $LIST: $p" >&2; exit 3; }
done
export DEBIAN_FRONTEND=noninteractive
echo "$(date -Is) ${SUDO_USER:-root}: $*" >> /var/log/lab-install.log
apt-get update -q
apt-get install -y --no-install-recommends -- "$@"
EOF
chown root:root /usr/local/sbin/lab-install
chmod 0755 /usr/local/sbin/lab-install

echo "== 3/3 sudoers rule /etc/sudoers.d/90-lib-lab1"
SYSTEMCTL=$(command -v systemctl)
UDEVADM=$(command -v udevadm)
REBOOT=$(command -v reboot)
tmp=$(mktemp)
cat > "$tmp" <<EOF
# lib-lab1: routine lab tasks without a password (lab-setup-5.sh).
# Exact arguments are listed; "" means no arguments allowed.
$LAB_USER ALL=(root) NOPASSWD: \\
    $SYSTEMCTL restart lab-cpu-tune.service, \\
    $REBOOT "", \\
    $UDEVADM control --reload-rules, \\
    $UDEVADM trigger --subsystem-match=usb --subsystem-match=hidraw, \\
    /usr/local/sbin/lab-install
EOF
visudo -cf "$tmp"
install -m 0440 -o root -g root "$tmp" /etc/sudoers.d/90-lib-lab1
rm -f "$tmp"
visudo -c >/dev/null

echo "== Allowed without password for $LAB_USER:"
sudo -l -U "$LAB_USER" | sed -n '/NOPASSWD/,$p'
echo "== Done."
