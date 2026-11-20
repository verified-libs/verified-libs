# Reproduce our results

Every number on this site comes from a result record: a JSON file that names
the source commit, the toolchain image, the compiler flags, the pinned
library commits and the SHA-256 of the firmware that ran (`fw_sha256`). The
records behind the [comparison](../../site/content/compare.html) are in
[`records/`](../../records/README.md). You can check them at three levels,
and each level needs less trust in us than the one before.

| Level | What you need | What it shows |
|---|---|---|
| 1. Rebuild the firmware | Linux, Podman, no board | The firmware we ran is what the named commit builds |
| 2. Run it on your own board | One of the six boards | Your board gives the same cycle counts and the same test verdicts |
| 3. Rebuild the toolchain image | Podman, an hour | The compilers are what the recipe says, not something we changed |

## 1. Rebuild the firmware, without a board

```sh
podman build -t verified-libs/toolchain:2026-11-05 -f toolchain/Containerfile toolchain
# records that name image 2026-11-13 (Rust and multi-producer sets, stress tests)
# need the second image too: toolchain/README.md, "2026-11-13"
lab/tools/verify-build.sh records/bench/stm32g474-rb-bench-flash-*.json
```

`verify-build.sh` takes the source of the record's commit, builds the
firmware with the record's settings in the image the record names, and
compares the SHA-256 of the result with the record's `fw_sha256`. It prints
`MATCH` or `DIFFERS` per record. It never touches a board: the build steps
are those of the lab's own run script, which is stopped before its first
probe access.

A tree without git history (the public repository, a release archive)
carries its commit in the file `EXPORTED_FROM`. The records are committed
after the commit they were made at, so they name an earlier one: the file
`SAME_SOURCES` lists those commits, checked at the export to have the same
`firmware/` directory, byte for byte, as the tree you have. Records of the
commits in the two files can be checked from the tree. For records of other
commits you need the git history.

What cannot be checked this way: a record whose commit is `unknown` or ends
in `+dirty` (made from uncommitted changes). The comparison page uses no
such record; the generator warns if one slips in. Records made with ST's
compilers (`COMPILER=st-gcc`, `st-clang`) need ST's own installer, which we
may not redistribute; those records are not on the comparison page.

## 2. Run it on your own board

### With one command

Connect one of the six boards by its debug USB port: the board's own debug
probe and its serial port are all the tests need (the Pico 2 through the
Raspberry Pi Debug Probe), no extra probe. Then, in a clone of the
repository:

```sh
./repeat.sh --check            # the tools, the image and the board
./repeat.sh                    # quick: the benchmark and two stress modes, 15-25 minutes
./repeat.sh --level full       # every benchmark set and stress mode, 1-2 hours
```

`repeat.sh` recognises the board by its probe's USB identity (with several
connected, choose one with `--board`). For each test it takes the source at
the commit of our record of that test, so the firmware that runs on your
board is byte for byte the one we ran, builds it in the toolchain image,
runs it, compares your record with ours (the benchmark mean by mean, the
stress test library by library against our night campaign) and packs
everything, with the probe's firmware version, into one archive to send us
(below). It needs Linux, git, Podman, `jq`, Python 3,
`probe-rs` 0.32 with its udev rules (OpenOCD 0.12 for the SAM D20 Xplained
Pro) and the toolchain image (`./repeat.sh --build-image` builds it, about
an hour). Each test writes the board's flash once.

Only these six board models give numbers that can be compared with ours:
the counts are cycles of a particular core, flash and bus. Results from other
boards are welcome too (below), but as a board of their own.

### Step by step

The boards are listed under [Method](../../site/content/method.md). You need
the board, `probe-rs` 0.32 (OpenOCD 0.12 for the SAM D20 Xplained Pro), `jq`
and the toolchain image.

```sh
git checkout <the record's commit>
cd firmware/nrf5340-rb-bench
BOARD=stm32g474 OUTDIR=$HOME/my-runs bash run.sh flash      # about 3 minutes
cd ../..
lab/tools/compare-records.py records/bench/stm32g474-rb-bench-flash-<time>.json \
    $HOME/my-runs/stm32g474-rb-bench-flash-<time>.json
```

With more than one probe connected, set `PROBE=VID:PID:SERIAL`. `BOARD` is
one of `nrf5340`, `stm32g0b1`, `stm32g474`, `stm32h723`, `samd20`, `rp2350`.
`SET=rust` and `SET=mp` run the other two benchmark sets.

**Benchmark.** `compare-records.py` first says whether the two firmwares are
the same (`fw_sha256`), then compares every mean. The counts are cycles of
the core, so your board's clock does not enter. In our lab the same firmware
on the same board gives the same means run after run, so the tolerance is
1 % (`--tol` changes it). We have one specimen of each board; whether a
second specimen agrees to 1 % is exactly what we would like to learn from
you. If your firmware differs (another commit, compiler or flag), the tool
says so first, and then a difference in speed says nothing about the lab:
moving code by a few bytes can change a mean by several percent
([placement](../../site/content/compare.html)).

**Stress test.**

```sh
cd firmware/nrf5340-rb-stress
BOARD=stm32g474 OUTDIR=$HOME/my-runs bash run.sh single     # also: block, dma, sweep, sweep-block, sweep-dma
cd ../rb-mp-stress                                         # two interrupts: several producers or consumers
BOARD=stm32g474 OUTDIR=$HOME/my-runs bash run.sh mpsc       # also: spmc; smp-mpsc, smp-spmc on the Pico 2
```

A stress run is random in its timing, so counts are not compared. What must
agree is the verdict per configuration: the negative control and the
mutants must show errors, and a library that showed none in our record
should show none in yours. `run.sh` exits 0 only if that holds, and
`compare-records.py` lists every configuration where the two records
disagree. A short run can miss a rare defect, so compare runs of similar
length. Short reference runs of both stress tests, one per board and mode,
are in [`records/stress/`](../../records/README.md), and `verify-build.sh`
rebuilds their firmware like the benchmark's.

The comparison page's stress counts come from night campaigns of many runs.
[`records/campaign/`](../../records/README.md) has them per board, mode and
library (valid runs, runs with errors), and `reference.py` compares one run
of yours with them:

```sh
python3 firmware/nrf5340-rb-stress/reference.py compare \
    records/campaign/nucleo-g474re.json $HOME/my-runs/stm32g474-rb-stress-single-<time>.json
```

It marks a library NEW if it showed errors, or did not finish, where none of
our runs of that mode did; errors that our runs showed too are listed, not
counted against the run.

## 3. Rebuild the toolchain image

The image is built from [`toolchain/Containerfile`](../../toolchain/README.md):
a base image pinned by digest, Ubuntu packages from a dated snapshot, GenMC
at a pinned commit, and Rust archives checked against SHA-256 sums. On
2026-11-13 we rebuilt both images from the recipes with no cache, under
another name, and rebuilt the firmware of nine records in the rebuilt images
(benchmark, Rust set, multi-producer set and stress tests, on six boards):
all nine were byte-identical to the firmware that had run. The tool versions
the rebuilt image reports were the same as the original's.

## Send us your result

If you have run a benchmark or a stress test on your own board, we would
like the record, whether it agrees with ours or not. `repeat.sh` packs all
of the following except what only you know (it asks for that in `info.txt`).
Mail it to contact@verified-libs.org with:

- the JSON record, unchanged (it carries the commit, flags and firmware hash);
- the output of `compare-records.py` (and, for a stress run, of
  `reference.py compare`) against our record;
- the board's name and the revision printed on it, and the debug probe and
  its firmware version;
- how the board was powered, and anything you changed (solder bridges,
  external clock, another probe).

A record from a board model we do not have is welcome too, if you add the
board layer (`firmware/common/<board>`) it was built with. We publish what
we receive only with your consent, and a result that disagrees with ours is
looked into before anything else. Results received are listed on
[Repeated by others](../../site/content/repeats.md).
