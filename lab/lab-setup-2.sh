#!/bin/bash
# lib-lab1 setup, step 2: stable measurements.
# Run from the copied lab folder with: sudo bash ~/lab/lab-setup-2.sh
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
ISOL=12-15     # physical cores 6 and 7 (SMT pairs 12-13 and 14-15)
HOUSE=0-11     # everything else: OS, interrupts, housekeeping

echo "== 1/4 Fixed CPU frequency, boost off, at every boot"
install -m 0755 "$here/tools/lab-cpu-tune.sh" /usr/local/sbin/lab-cpu-tune
cat > /etc/systemd/system/lab-cpu-tune.service <<'EOF'
[Unit]
Description=lib-lab1: fixed CPU frequency for benchmarks

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/lab-cpu-tune
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
# Power-profile daemons would change governor/EPP behind our back.
for s in power-profiles-daemon tuned tuned-ppd; do
    if systemctl list-unit-files "$s.service" --no-legend | grep -q .; then
        systemctl disable --now "$s.service" || true
        systemctl mask "$s.service"
        echo "   disabled $s"
    fi
done
systemctl daemon-reload
systemctl enable --now lab-cpu-tune.service

echo "== 2/4 Isolate benchmark CPUs $ISOL from scheduler, timer ticks, RCU and IRQs"
cat > /etc/default/grub.d/90-lib-lab1.cfg <<EOF
GRUB_CMDLINE_LINUX_DEFAULT="\${GRUB_CMDLINE_LINUX_DEFAULT} isolcpus=managed_irq,domain,$ISOL nohz_full=$ISOL rcu_nocbs=$ISOL irqaffinity=$HOUSE"
EOF
update-grub

echo "== 3/4 Measurement tools: lab-env, lab-run"
install -m 0755 "$here/tools/lab-env.sh" /usr/local/bin/lab-env
install -m 0755 "$here/tools/lab-run.sh" /usr/local/bin/lab-run

echo "== 4/4 Done. Rebooting in 5 seconds."
sleep 5
reboot
