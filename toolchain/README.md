# Pinned toolchain

One container image with the correctness and build tools for the trial.
Recipe: [`Containerfile`](Containerfile). Built and run on lib-lab1 with
rootless Podman ([`../lab/lab-setup-3.sh`](../lab/lab-setup-3.sh)).

## Pinned inputs
| Input | Pin |
|---|---|
| Base image | `ubuntu:26.04@sha256:157dc3d6…6725` |
| Ubuntu packages | snapshot.ubuntu.com, `20261105T000000Z` |
| GenMC | commit `fab5bba7d9efaf76990227c2f59d62c11c7ea2a3` |
| Rust stable | `1.99.1` (+ `thumbv6m-none-eabi`, `thumbv7em-none-eabihf`) |
| Rust nightly | `nightly-2026-11-05` (Miri) |

## Contents of `2026-11-05`
From `/etc/verified-libs/toolchain.json` in the image:

| Tool | Version |
|---|---|
| clang | 21.1.8 |
| gcc | 15.2.0 |
| arm-none-eabi-gcc | 14.2.1 (14.2.rel1) |
| CBMC | 6.6.0 |
| GenMC | commit fab5bba |
| rustc | 1.99.1 |
| rustc nightly / Miri | 1.101.0-nightly (2026-11-04) |

## `2026-11-13`: Rust soft-float targets
[`rust-targets/Containerfile`](rust-targets/Containerfile) builds
`verified-libs/toolchain:2026-11-13` on top of `2026-11-05`: it adds the Rust
standard library for `thumbv7em-none-eabi` (Cortex-M4/M7) and
`thumbv8m.main-none-eabi` (Cortex-M33). The firmware's C code is built with
`-mfloat-abi=soft` on every board, so Rust code linked into it needs these
soft-float targets (the base image has `thumbv6m-none-eabi`, and only the
hard-float `thumbv7em-none-eabihf`). The archives are rust-lang.org's for
rustc 1.99.1 (channel 2026-10-15), checked against the SHA-256 in that
channel's manifest, which the base image keeps in its sysroot. Nothing else
changes; the default image of the run scripts is still `2026-11-05`.
Checked 2026-11-13: a `no_std` staticlib builds for all three targets, and
links into an arm-none-eabi-gcc soft-float Cortex-M33 program.

Its build context is a directory with the two archives the Containerfile
names (`ARG RUST_STD_V7EM`, `RUST_STD_V8MM`):
```sh
curl -fsSL -o DIR/<name> https://static.rust-lang.org/dist/2026-10-15/<name>    # both archives
podman build -t verified-libs/toolchain:2026-11-13 -f rust-targets/Containerfile DIR
```

## `2026-11-16`: two more compilers for the libraries
[`variants/Containerfile`](variants/Containerfile) builds
`verified-libs/toolchain:2026-11-16` on top of `2026-11-13`, nothing else
changed: Arm Toolchain for Embedded 23.1.0 (`/opt/atfe`, clang 23; GitHub
arm/arm-toolchain, release-23.1.0-ATfE) and the Zephyr SDK 1.0.1's
arm-zephyr-eabi GCC 14.3.0 (`/opt/zephyr-sdk`; GitHub
zephyrproject-rtos/sdk-ng v1.0.1). Both archives are checked against their
published SHA-256 in the Containerfile; the build downloads nothing.
`toolchain.json` gains `atfe_clang`, `atfe_release`, `zephyr_gcc`,
`zephyr_sdk`. The run scripts use this image only for `COMPILER=atfe` and
`COMPILER=zephyr-gcc` ([`../firmware/common/compiler.mk`](../firmware/common/compiler.mk)):
the libraries and their adapters built with that compiler, the test harness
and the link unchanged (arm-none-eabi-gcc, newlib-nano). ATfE uses the same
GNU headers as `COMPILER=clang`, so only the compiler differs; the Zephyr
GCC uses its own headers, as a Zephyr application does.
```sh
# DIR: the two archives, from the GitHub release pages
podman build -t verified-libs/toolchain:2026-11-16 -f variants/Containerfile DIR
```
Checked 2026-11-16: the stress (one image and per-library bundle), benchmark
(SET=spsc) and multi-producer firmwares build with both on Cortex-M0+, M4,
M7 and M33.

## Build
```sh
podman build -t verified-libs/toolchain:2026-11-05 -f Containerfile .
```
The tag is the snapshot date. To update, change the pins, use a new date tag
and keep the old image until results made with it are re-checked.

## Rebuilt from the recipe (2026-11-13)
Both images were built again from these recipes with `--no-cache`, under
another name (`verified-libs/toolchain-rebuild`), eight days after the first
build of `2026-11-05`. The rebuilt base image reports the same
`toolchain.json`. The firmware of nine result records was then rebuilt in
the rebuilt images (the record's commit, the lab's own `run.sh`, as
[`lab/tools/verify-build.sh`](../lab/tools/verify-build.sh) does): benchmark
SPSC, Rust and multi-producer sets on the NUCLEO-G474RE, SPSC on the SAM D20,
Rust on the nRF5340 and NUCLEO-H723ZG, multi-producer on the Pico 2, and two
stress firmwares (G474 sweep, G0B1 single). All nine have the `fw_sha256` of
the firmware that ran. So the pins (base image digest, package snapshot,
GenMC commit, Rust archives by SHA-256) are enough to get the same compilers.

## Use
```sh
podman run --rm -v "$PWD":/work:Z verified-libs/toolchain:2026-11-05 genmc test.c
```
Every result should record the image tag and the contents of
`/etc/verified-libs/toolchain.json`.

## Smoke test (2026-11-05)
- GenMC finds the bug in message passing with a relaxed flag and reports no
  errors with release/acquire.
- arm-none-eabi-gcc builds for `-mcpu=cortex-m0plus`.
- Rust has both Cortex-M targets installed.

## Notes
- The base image has no CA certificates, and the snapshot service is HTTPS
  only. The build bootstraps `ca-certificates` from the regular signed
  archive, then reinstalls the snapshot version.
- The Miri sysroot is built for root (`/root/.cache/miri`). Run the
  container as its default user; with rootless Podman that is your own user
  on the host.
