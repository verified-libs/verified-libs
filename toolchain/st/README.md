# ST compilers (STM32CubeCLT) for the STM32 boards

A local image, `verified-libs/toolchain-st:cubeclt-1.22.0`, on top of
`verified-libs/toolchain:2026-11-05`, with two compilers from STM32CubeCLT
1.22.0 for Linux (Debian package):

| `COMPILER=` | Compiler | Version |
|---|---|---|
| `st-gcc` | GNU Tools for STM32 | arm-none-eabi-gcc 14.3.1 20250623 (14.3.rel1.20251027-0700) |
| `st-clang` | STMicroelectronics Arm Clang (`starm-clang`) | clang 21.1.1 (rel2.20260323-1806) |
| `st-clang-omax` | the same, with `--config=Omax.cfg` | (needs `OPT=-O3`) |

As with `COMPILER=clang` (see `firmware/common/compiler.mk`), only the
libraries under test and their adapters are built with the ST compiler; the
harness, startup and link stay the Debian arm-none-eabi-gcc 14.2.1 with its
newlib-nano, so the library code is the only thing that changes.
`st-gcc` uses its own headers; `st-clang` uses the same GNU headers and
flags as `clang` (ST's clang also ships newlib and libc++, not used here).
A third variant, `st-clang-omax`, adds ST's speed preset `--config=Omax.cfg`
(`-O3` plus LLVM inlining and unrolling options); the run scripts require
`OPT=-O3` with it. The size preset `Osize.cfg` (`-Oz` plus options) is not
wired up: the harness is built with the same `OPT` by gcc, which has no `-Oz`.

Results: [reports/2026-11-12-compilers-stm32.md](../../reports/2026-11-12-compilers-stm32.md).
In short, ST Arm Clang generates the same code as upstream clang 21.1 for
these libraries, and GNU Tools for STM32 measures as Arm GCC 14.2.

## Licence: why the image stays local
CubeCLT is under ST's SLA0048 (Rev5, October 2025; the GCC and clang parts
are also covered by their open-source licences). Two clauses matter here:
- Clause 4: the package "must be used and execute solely and exclusively on
  or in combination with a processing unit device manufactured by or for
  STMicroelectronics". The run scripts therefore refuse `st-gcc` and
  `st-clang` for any `BOARD` that is not `stm32*`.
- No redistribution of the binaries is set up here: the image is built
  locally and never pushed. The installer is not in the repository.
The agreement has no clause against publishing benchmark results. Clause 3
(no use of ST's name to endorse) is respected by naming the compiler only
as a fact.

## Build (on lib-lab1)
The owner downloads `stm32cubeclt_1.22-Lin-Deb-x86_64.sh.zip` from st.com
(login) to `~/downloads/st/`. The makeself installer is not run: its tar
payload is cut out (offset = the first 524 lines), checked against the
embedded MD5, and the main `.deb` is unpacked with `dpkg-deb -x` (no
install, no root):

```
cd ~/downloads/st && mkdir -p x && cd x
unzip ../stm32cubeclt_1.22-Lin-Deb-x86_64.sh.zip
f=stm32cubeclt_1.22.0_29188_20260626_1359-Lin-Deb-x86_64.sh
off=$(head -n 524 $f | wc -c)
tail -c +$((off+1)) $f | head -c 723865600 > payload.tar
md5sum payload.tar            # 26bf489709fce9338e66ec472938399a (MD5= in the header)
mkdir payload && tar -xf payload.tar -C payload && rm payload.tar
dpkg-deb -x payload/stm32cubeclt-1.22.0-29188-20260626-1359-x86_64.deb deb
podman build -t verified-libs/toolchain-st:cubeclt-1.22.0-base2026-11-13 \
    --build-arg CUBECLT_ZIP_SHA256=$(sha256sum ../stm32cubeclt_1.22-Lin-Deb-x86_64.sh.zip | cut -d' ' -f1) \
    -f ~/verified-libs/toolchain/st/Containerfile deb/opt/st/stm32cubeclt_1.22.0
```

Until 2026-11-13 the image was built on the 2026-11-05 base as
`toolchain-st:cubeclt-1.22.0` (still on the lab host, for the records made with it;
add `--build-arg BASE=localhost/verified-libs/toolchain:2026-11-05` to rebuild it).

Zip SHA-256 (2026-11-12): `4b863e7a68d35080e8ebefdb5723974f1df0678a2e220ff6943e3fe4e2064916`.
The image adds `st_cubeclt`, `st_cubeclt_zip_sha256`, `st_gcc` and
`st_clang` to `/etc/verified-libs/toolchain.json`, which every record embeds.
