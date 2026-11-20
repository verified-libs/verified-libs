# lib-lab1 – setup notes

Created 2026-11-04.

## Hardware
- Acer Swift Edge 16 (SFE16-43)
- AMD Ryzen 7 7840U, 8 cores / 16 threads (Zen 4, identical cores, SMT)
- 14 GB RAM (soldered), Kingston NV3 500 GB NVMe (new disk)
- Original Windows disk removed and stored (BitLocker key saved)
- Frequency control: amd-pstate-epp, see "Measurement setup" below

## Software
- Ubuntu Desktop 26.04.1 LTS, boots to text mode (multi-user.target)
- Installed: git, build-essential, lm-sensors, linux-tools (perf)
- Podman 5.7 (rootless) for the pinned toolchain image, see
  [../toolchain/](../toolchain/README.md). Script: [lab-setup-3.sh](lab-setup-3.sh)

## Settings
- SSH key only: /etc/ssh/sshd_config.d/10-key-only.conf
- Closed lid ignored: /etc/systemd/logind.conf.d/10-lid.conf
- Sleep disabled: sleep/suspend/hibernate/hybrid-sleep masked
- Script: [lab-setup-1.sh](lab-setup-1.sh)

## Measurement setup (step 2, 2026-11-05)
Script: [lab-setup-2.sh](lab-setup-2.sh).
- **Fixed frequency 3.0 GHz on all cores, boost off,** governor `performance`.
  3.0 GHz is just below the 3.3 GHz base clock so the thin laptop can hold it
  without thermal throttling. Applied at every boot by `lab-cpu-tune.service`
  ([lab-cpu-tune.sh](tools/lab-cpu-tune.sh)).
- `power-profiles-daemon` masked, so nothing changes governor/EPP behind our back.
- **Benchmark CPUs 12-15** (physical cores 6 and 7, SMT pairs 12-13 and
  14-15): `isolcpus=managed_irq,domain,12-15 nohz_full=12-15 rcu_nocbs=12-15
  irqaffinity=0-11` via `/etc/default/grub.d/90-lib-lab1.cfg`.
  CPUs 0-11 run the OS, interrupts and housekeeping. The only IRQs left on
  12-15 are NVMe queues 9-12 (managed IRQs), which only fire if a process on
  those CPUs does disk I/O.
- RAPL package energy readable without root (dedicated lab machine).

### Tools
- `lab-env` ([source](tools/lab-env.sh)): the measurement environment as JSON
  (kernel, cmdline, CPU, microcode, frequency settings, isolated CPUs, AC
  power, temperatures, compiler).
- `lab-run [-c CPUS] [-o FILE] -- cmd` ([source](tools/lab-run.sh)): runs a
  command on the isolated CPUs and records environment, wall time, package
  energy (RAPL) and temperature before/after as JSON (`~/lab-runs/` by
  default). Energy covers the whole package, not only the isolated cores.

### Stability check (2026-11-05)
A fixed single-threaded compute loop (xorshift, 4·10^8 iterations), 15 runs
each via `lab-run`:

| CPU | Mean | Min–max spread | CV |
|---|---|---|---|
| 12 (isolated) | 0.801508 s | 0.007 % | 0.0022 % |
| 2 (normal) | 0.803752 s | 0.017 % | 0.0048 % |

Package energy per run ≈ 3.4 J; Tctl stayed at 42 °C. Our rejection limit for
a series is CV > 5 %, so there is ample margin for real benchmarks, which
will be noisier than a pure compute loop.

## Access
- From the development PC: `ssh liblab1` (via lib-lab1.local / mDNS, key in ssh-agent)
- `~/.ssh/config`: `HostName lib-lab1.local`, `HostKeyAlias lib-lab1`, `User <user>`
- IP currently 192.168.0.138 (not reserved in the router yet)

## Known problems during installation
- Ubuntu Server installer: Wi-Fi blocked by rfkill (airplane mode). Fixed with the airplane-mode key.
- Server autoinstall failed with an unexplained Python traceback. Switched to the Desktop installer.

- Step 2: the kernel rejects per-policy `boost` writes once global boost is
  off; `lab-cpu-tune` ignores that error.
- The system locale is Danish: tools that parse numbers (awk, sort -g)
  must run with `LC_ALL=C`, or `0.8015` is read as 0.
- Step 4: Ubuntu Desktop has no `curl` by default; the script installs it.
- A USB-A to micro-USB cable turned out to contain its own chip (WCH
  `1a86:e010` "HID To Serial", present even with nothing on the other end).
  It passed power, so the board's LED lit, but no data. Use plain data
  cables only; `lsusb` must show the board's own probe.
- An erased nRF5340 re-enables APPROTECT at every reset, so probe-rs reports
  "Core 1 is locked" and erases again on each connect. Expected until our own
  firmware opens the debug port.
- J-Link OB firmware of the nRF5340 DK: updated 2026-11-14 by J-Link
  Commander on the owner's PC to `J-Link OB-K22-NordicSemi compiled Oct 30
  2023`. With the firmware it shipped with, the virtual COM port stopped
  passing data after a few hundred kB until a USB reset or power cycle
  (firmware/nrf5340-rb-stress/README.md, one library per reset).

## Debug probes (step 4, 2026-11-06)
Script: [lab-setup-4.sh](lab-setup-4.sh).
- probe-rs 0.32.0 in `/usr/local/bin` (release tarball, SHA-256 checked).
- udev rules `/etc/udev/rules.d/69-lib-lab1-probes.rules`: J-Link, ST-LINK,
  Microchip EDBG and Raspberry Pi debugprobe via group `plugdev` (headless
  SSH sessions get no seat, so `uaccess` does not apply).
- Lab user in `dialout` for the probes' virtual serial ports.

Connected:
| Board | Probe | USB id | Serial ports |
|---|---|---|---|
| nRF5340 DK | onboard J-Link (J2) | `1366:1065` (1055 before 2026-11-15), serial 000960122443 | `/dev/ttyACM0..2` |

nRF5340 DK: original firmware erased on both cores (2026-11-06,
`probe-rs erase --chip nRF5340_xxAA --allow-erase-all`).

## Limited passwordless sudo (step 5, 2026-11-06)
Script: [lab-setup-5.sh](lab-setup-5.sh). The lab user (and so Claude, via
SSH) may run only these as root without a password:
- `systemctl restart lab-cpu-tune.service`, `reboot` (no arguments)
- `udevadm control --reload-rules`, `udevadm trigger --subsystem-match=usb --subsystem-match=hidraw`
- `lab-install PKG...`: installs only packages listed in
  `/etc/lib-lab1/allowed-packages`, logged to `/var/log/lab-install.log`

Everything else still needs the owner's password. The script, the list and
the sudoers file are root-owned and not writable by the lab user. Adding a
package to the list is an owner decision. Tested: allowed commands work;
`lab-install vim`, option injection, `systemctl stop ssh`, `reboot --force`
and `sudo id` are refused.

## Unattended runs (2026-11-06)
- **User linger is on** (`loginctl enable-linger erik`, allowed without
  sudo for one's own user): the user's systemd instance and
  `/run/user/1000` stay up after logout, which rootless Podman needs.
  Long campaigns are started detached
  (`nohup setsid bash overnight.sh 8 > /dev/null 2>&1 < /dev/null &`) and
  survive the SSH session.
- Working copy on lib-lab1: `~/vl/` mirrors the repo's `firmware/` and
  `verify/` folders (copied with scp; lib-lab1 has no GitHub access). Do not
  update the copy of a folder while a campaign runs from it: bash reads
  scripts as it goes, and every run rebuilds from those sources.

## Embedded target hardware
Boards are connected to lib-lab1 over USB (onboard ST-LINK or SWD probe) and
driven headless. Prices are rough estimates in DKK.

**Origin** (DECISIONS 2026-11-12): every board and probe listed here was
bought by the project (as of 2026-11-12). A donated board gets `donated by
<name>, <date>` (or just `donated`) in its entry.

**Available now**
- STM32G071 and STM32G051 boards (Cortex-M0+). No DWT cycle counter on M0+:
  timing via SysTick.
- SAM D20 Xplained Pro and SAM L21 Xplained Pro (Cortex-M0+, Microchip,
  onboard EDBG CMSIS-DAP probe). Planned as a second-vendor M0+ cross-check
  once the G0B1RE runs. Not connected.
- **NUCLEO-G0B1RE: connected 2026-11-11** to hub `4B0708619185` port 2
  (`lab/boards.conf`: `nucleo-g0b1re`). Onboard ST-LINK/V2-1 `0483:374b`,
  serial `0673FF565382515067232957`, factory jumpers. probe-rs 0.32 attaches
  with `--chip STM32G0B1RETx` (auto-detect fails); DBGMCU_IDCODE
  `0x10016467` (DEV_ID 0x467, rev 0x1001), flash 512 KB. Power cycling
  tested: with the port off the probe leaves the bus, with it on it returns.
- **NUCLEO-G474RE: connected 2026-11-11** to hub `4B0708619185` port 3
  (`nucleo-g474re`). Onboard STLINK-V3 `0483:374e`, serial
  `002100483335510133383531`. probe-rs attaches with `--chip STM32G474RETx`;
  DBGMCU_IDCODE `0x20036469` (DEV_ID 0x469, rev 0x2003), flash 512 KB,
  DWT_CTRL `0x40000000` (NOCYCCNT = 0: `CYCCNT` available). Power cycling
  tested. With this, all three switchable ports of monitor #1 are in use.
- **NUCLEO-H723ZG: connected 2026-11-11, temporarily** to the downstream hub
  `3B0708619185` port 1 (`nucleo-h723zg`), which switches data only: no
  power cycling, and `boardpower.sh` refuses to switch it (tested). Not for
  unattended campaigns until it moves to a switchable port (monitor #2,
  once its chain cable is found; port 1 is meant for that cable). Onboard
  STLINK-V3 `0483:374e`, serial `0042001E3335511835383531`. probe-rs attaches
  with `--chip STM32H723ZGTx`; DBGMCU_IDCODE `0x10016483` (DEV_ID 0x483,
  rev 0x1001), flash 1 MB, CPUID `0x411FC272` (Cortex-M7 r1p2). DWT_CTRL
  reads 0 before `DEMCR.TRCENA` is set; to check when the firmware enables it.
- **Monitor #2 (2026-11-11)**, chained from `3B0708619185` port 2. Its
  upstream hub `9E0C0069B5FA` cuts VBUS on ports 2 and 3 (RAM-marker test),
  now in `SAFE_PORTS`: NUCLEO-H723ZG on port 2, Pico 2 on port 3. SAM D20 on
  port 1 (power cut not verified). **Both monitors must stay in standby and
  never be switched off with their power button**: their hubs power the
  boards (switching monitor #2 off briefly on 2026-11-11 dropped all its
  boards from USB).
- **Pico 2 H (RP2350): connected 2026-11-11** on `9E0C0069B5FA` port 3,
  debugged by the Raspberry Pi Debug Probe on the data-only hub
  `EE0C0869B5FA` port 1 (`boards.conf`: `pico2 ... separate-probe`). The
  probe's firmware was too old for probe-rs 0.32 (needs >= 2.2.0); updated
  with `debugprobe.uf2` from github.com/raspberrypi/debugprobe (latest
  release, 2026-11-11) after a faulty USB cable had made it look dead (USB
  error -71). probe-rs attaches with `--chip RP235x`; CHIP_ID `0x20004927`
  (RP2350). No firmware board layer yet.
- **SAM D20 Xplained Pro: connected 2026-11-11, temporarily** to the
  downstream hub `3B0708619185` port 2 (`sam-d20-xpro`; no power cycling).
  Onboard EDBG `03eb:2111` (CMSIS-DAP v1 over HID), serial
  `ATML1873040200009960`; udev gives `plugdev` access. **Not usable with
  probe-rs 0.32 yet:** it has no SAM D20 target (only SAM D21), and even the
  generic `Cortex-M0+` target fails with "Could not determine a suitable
  packet size for this probe" (EDBG HID). OpenOCD supports both EDBG and the
  SAM D20 flash (`at91samd` driver). **OpenOCD 0.12.0 installed 2026-11-11**
  (`lab-install openocd`) and works: `openocd -f
  board/atmel_samd20_xplained_pro.cfg` finds EDBG firmware 01.0F.00DB, SWD
  DPIDR `0x0bc11477`, Cortex-M0+ r0p1, SAMD20J18A (256 KB flash, 32 KB RAM).
  The failed probe-rs attempts left the EDBG unresponsive (`CMD_INFO
  failed`) until it was replugged by hand: do not point probe-rs at it.

**Purchase list (ordered at DigiKey 2026-11-07, delivered by 2026-11-11)**
All items are listed under the manufacturer part numbers below.
| # | Item | Mfr. part no. | Why | Approx. |
|---|---|---|---|---|
| 1 | NUCLEO-G0B1RE (Cortex-M0+, 64 MHz) | `NUCLEO-G0B1RE` | pxq's home family. No atomic instructions on M0+, so atomics-based libraries change. 144 KB RAM leaves room for the code-in-SRAM variant, which the G071's 36 KB probably does not. Own G071 boards serve as a cross-check | ~100 |
| 2 | NUCLEO-G474RE (Cortex-M4F, 170 MHz) | `NUCLEO-G474RE` | Most common Cortex-M class; DWT `CYCCNT`. Code in CCM SRAM as a third variant; ART accelerator on/off like the nRF5340 cache. Largest part of the G4 series | 150–200 |
| 3 | NUCLEO-H723ZG (Cortex-M7, caches) | `NUCLEO-H723ZG` | Dual-issue core and caches change cycle rankings; real DMA with a data cache tests zero-copy APIs for cache coherency | 250–300 |
| 4 | Raspberry Pi Pico 2 H (RP2350, with headers) | `SC1632` | Cross-core SPSC on two identical Cortex-M33 cores with shared SRAM; the same chip has RISC-V cores (needs a decision in [DECISIONS.md](../DECISIONS.md) before use). One is enough | ~50 |
| 5 | Raspberry Pi Debug Probe | `SC0889` | SWD probe for the Pico 2 (no onboard probe); CMSIS-DAP, supported by probe-rs. Comes with cables for the 3-pin debug connector and for pin headers | ~100 |
| 6 | USB-A male to Micro-B male data cables, 0.5–1 m, 5–6 pcs | – | One per new board (3 Nucleo ST-LINKs, Pico 2) plus spares; the Debug Probe comes with its own. Data-capable, not charge-only (see the J-Link note above). The monitor hub ports are USB-A | – |

Prices are rough estimates, not checked against shops. Dropped from earlier
plans: a USB hub with power switching (the monitor hubs do it, see below),
NUCLEO-G071RB (replaced by the G0B1RE), a second Pico 2.

USB ports: five boards need power cycling (nRF5340 DK, three Nucleos, Pico
2) but monitor #1 has three switchable ports. Chain monitor #2 into port 1
of the downstream hub (`3B0708619185`) when the fourth board is connected. The Debug Probe can use a
port that does not switch VBUS.

**Power switching per board (in place since 2026-11-07)**
lib-lab1 power-cycles a hung board with `uhubctl` (Ubuntu package
`uhubctl` 2.6.0) through the USB hubs built into two Dell U2415 monitors.
No separate hub was bought.
- Each monitor has two TI TUSB8041 hubs (`0451:8142`) in cascade; both report
  per-port power switching (`ppps`). Connected over USB 2.0 only.
- The hubs are identified by USB serial number, not by bus location: the
  location (`1-1`, `1-2`, ...) depends on which laptop port the monitor's
  cable is in. It changed from `1-1` to `1-2` on 2026-11-08 when the cable was moved.
  [`tools/boardpower.sh`](tools/boardpower.sh) looks it up at run time.
- Tested on the first monitor with the nRF5340 DK (LEDs and `lsusb`). In
  the upstream hub, serial `4B0708619185`:
  - the three ports side by side (ports 1–3) really cut VBUS: usable;
  - port 4 links to the downstream hub (`3B0708619185`): never switch it off.
  In the downstream hub, the separate port 1–2 cm away (port 1) and the port
  on the back (port 2) only cut the data lines. VBUS stays on, so they are
  not usable for power cycling.
- The monitor's power button cuts the whole hub. Standby (no video signal)
  keeps USB powered. **Never turn a monitor off with its power button while a
  campaign runs.**
- The second monitor is assumed to behave the same; test each port
  before relying on it.
- After power-on the scripts must wait for the probe to re-enumerate before
  calling probe-rs. A benchmark through the hub gave the same numbers as a
  direct connection.
- Switching needs root until a udev rule gives `dialout` access to the hub's
  port `disable` files (kernel ≥ 6.0).

Fallback if the monitors are not enough: Plugable USBC-HUB7BC (on the uhubctl
list, 6 of 7 ports switch).

**Later, if the scope grows**
- Energy per operation on the MCU is left out of the trial (see
  [DECISIONS.md](../DECISIONS.md)). When it is added: Nordic Power Profiler
  Kit II (≈ 800 DKK, relative comparisons) or a calibrated analyser such as
  Joulescope JS320 (≈ 1,000 USD, publishable absolute values).
- RISC-V: the Pico 2's RP2350 has RISC-V cores; a separate board (e.g.
  ESP32-C3) only if that is not enough. Either needs a decision in
  [DECISIONS.md](../DECISIONS.md) first.
- nRF52840 DK: only if Zephyr candidates should run on their reference platform.

## Next steps
- ~~Toolchains for the trial~~: done, in the toolchain image (2026-11-05)
- Connect a Cortex-M0+ board (ST-LINK) and measure cycle counts via DWT/SysTick
- Nightly runs via a systemd timer, scheduled by the CO2 forecast
