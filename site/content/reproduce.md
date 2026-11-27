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
lab/tools/verify-build.sh records/stress/stm32g474-rb-stress-*.json
# the speed benchmark: one record per board and configuration, eight images each
bash firmware/nrf5340-rb-bench/oneverify.sh records/bench-v2/stm32g474/*.json
```

`verify-build.sh` takes the source of the record's commit, builds the
firmware with the record's settings in the image the record names, and
compares the SHA-256 of the result with the record's `fw_sha256`. It prints
`MATCH` or `DIFFERS` per record. It never touches a board: the build steps
are those of the lab's own run script, which is stopped before its first
probe access. `oneverify.sh` does the same for the records of the speed
benchmark: it builds every image of the board and compares, per record, the
bytes in flash of its eight images (`image_sha256`), the fixed part and the
boot stub. It takes about two minutes per board, the first one longer
(the pinned libraries are fetched). The images of the nRF5340 DK include
one of Nordic's nRF5 SDK, which we may not redistribute: download the zip
that `firmware/nrf5340-rb-bench/nrf5-sdk.lock` names and give it as
`NRF5_SDK=path/to/the/zip` in front of the command. The other five boards
need nothing but the tree and the image.

**An archived series** ([`records/archived.json`](../../records/README.md))
is checked at its own public commit, not against the tree at hand: clone
the public repository with its history, check out the entry's
`public_commit`, and run the same command there on the series' records.
The nRF5340 DK's and the NUCLEO-H723ZG's records from before method
version 3 are such series; the results pages link them under each board.

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
./repeat.sh                    # quick: a few benchmark configurations and two stress modes, 15-25 minutes
./repeat.sh --level full       # every benchmark configuration, twice, and every stress mode, 2-4 hours
```

`repeat.sh` recognises the board by its probe's USB identity (with several
connected, choose one with `--board`). For each stress test it takes the
source at the commit of our record of that test; the benchmark it builds
from the tree as it is, which builds the images of our records byte for
byte (level 1 checks that). So the firmware that runs on your board is the
one we ran. It builds in the toolchain image, runs, compares your record
with ours (the benchmark image by image and mean by mean, the stress test
library by library against our night campaign) and packs everything, with
the probe's firmware version, into one archive to send us (below). It needs
Linux, git, Podman, `jq`, Python 3, `probe-rs` 0.32 with its udev rules
(OpenOCD 0.12 for the SAM D20 Xplained Pro) and the toolchain image
(`./repeat.sh --build-image` builds it, about an hour).

Flash writes: each stress test writes the board's flash once. The benchmark
has one image per configuration and placement, packed into bundles that
fill the flash; one bundle is one flash write. The quick level runs up to
six configurations of one bundle (one write), the full level every bundle
of the board (nRF5340 DK 5, NUCLEO-G0B1RE 9, NUCLEO-G474RE 9, NUCLEO-H723ZG
5, SAM D20 Xplained Pro 18, Pico 2 2). `--only bench` or `--only stress`
runs one of the two. For the nRF5340 DK the benchmark also needs Nordic's
nRF5 SDK zip, which we may not redistribute:
`--nrf5-sdk PATH` (`firmware/nrf5340-rb-bench/nrf5-sdk.lock` names the file
and its checksum).

**The nRF5340 DK and a power-on.** The application core's debug port
opens only when UICR.APPROTECT is Unprotected and firmware writes
CTRL-AP.APPROTECT.DISABLE after each reset (nRF5340 Product Specification
v1.6, §8.2 "Access port protection").
- *Since method version 3* our boot stub (`firmware/common/benchboot.c`)
  copies UICR.APPROTECT and UICR.SECUREAPPROTECT into CTRL-AP at every
  boot, so that a board with a bundle of this tree on it stays reachable
  after a power-on. That was shown on our board on 2026-11-26: after a
  power cycle with only our boot stub run, the debug port was open and a
  run without a flash write measured as before
  ([report](../../reports/2026-11-26-method-version-3-reruns.md#the-watched-power-on-of-the-nrf5340-dk-passed)).
- *Bundles from before method version 3* (the archived series): their
  stub does not write CTRL-AP and starts no image after a power-on, so
  with one of them on the board the debug port is locked after any
  power-on, and a write or a run fails.

We recovered a locked board on 2026-11-25 with one command of probe-rs
0.32.0, which erases the application core (CTRL-AP ERASEALL; the network
core is not touched):

```sh
probe-rs read --chip nRF5340_xxAA_APPONLY --allow-erase-all b32 0x00FF8000 1
```

It erases the application core's flash and UICR, and probe-rs then writes
UICR.APPROTECT and UICR.SECUREAPPROTECT to 0x50FA50FA (Unprotected)
itself: the command reads back 0x50FA50FA. Then, with no reset and no
power-on in between, write the bundle and run as usual: each image opens
the port when it starts, and it stays open until the next power-on. The
erase removes everything on the application core, our bundles included.

Only these six board models give numbers that can be compared with ours:
the counts are cycles of a particular core, flash and bus. Results from other
boards are welcome too (below), but as a board of their own.

### Step by step

The boards are listed under [Method](../../site/content/method.md). You need
the board, `probe-rs` 0.32 (OpenOCD 0.12 for the SAM D20 Xplained Pro), `jq`
and the toolchain image.

```sh
cd firmware/nrf5340-rb-bench
BUNDLE=0 bash onebuild.sh table stm32g474            # the images of bundle 0 (fetches the pinned libraries, once)
python3 run-one.py stm32g474 $HOME/my-runs/g474 --bundle 0 --flash --passes 1 \
    --adapter adapter_lwrb,adapter_jnk0le            # one flash write, 16 runs, about 2 minutes
python3 onerecords.py --out $HOME/my-records $HOME/my-runs/g474
cd ../..
lab/tools/compare-records.py records/bench-v2/stm32g474 $HOME/my-records/stm32g474
```

With more than one probe connected, set `PROBE=VID:PID:SERIAL`. The board is
one of `nrf5340`, `stm32g0b1`, `stm32g474`, `stm32h723`, `samd20`, `rp2350`.
Without `BUNDLE` and `--bundle` every bundle of the board is built and run;
without `--adapter` every configuration of the bundles. The eight placements
of a configuration can lie in two bundles; `onerecords.py` makes a record
only of a whole configuration and names those it leaves out. Our records
hold two passes (`--passes 2`).

**Benchmark.** `compare-records.py` first says, image by image, whether your
firmware is the same as ours (the bytes in flash and the address), then
compares every mean of every placement. The counts are cycles of
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

## The CRC records

The records of the CRC kind (`records/crc/<board>/<adapter>.json`, one per
board and configuration, eight images each; [`records/`](../../records/README.md))
are checked the same two ways, with the kind's own tools. Both need the
toolchain image `verified-libs/toolchain:2026-11-13` and fetch the
libraries at their pins (`kinds/crc/libs.lock`).

**Rebuild, without a board.**

```sh
bash kinds/crc/bench/crcverify.sh records/crc/stm32g474/*.json
```

For each record it builds every image of the board from the sources of
the record's commit and compares, per image, the bytes in flash
(`image_sha256`), the address, the fixed part, the boot stub, the
toolchain and the layout of the image: `MATCH` or `DIFFERS`. In a tree
without git history it takes the sources from the tree if the record's
commit is in `EXPORTED_FROM` or in `SAME_SOURCES_CRC` (the commits whose
CRC test sources the export found to be those of the tree). A record of
another commit may still be published if this tree builds its images byte
for byte: `records/rebuilt.json` says so for each such record (the entries
named `crc/...`). Check that claim with `VL_TREE=1` in front of the
command, which builds from the tree at hand instead of from the record's
commit. Time: in our check of the 120 records (2026-11-25, on 6 CPUs)
16 s per board of 20 records, with the libraries already at hand. Without
`VL_LIBS_FROM` the script first fetches the libraries at their pins
(`kinds/crc/libs.lock`), once per board: from a tree exported from this
repository, with nothing at hand, it took 28 s per board of 20 records
(2026-11-25, all 120 records `MATCH`).

**Which commit each record needs.** The records are of two series and of
method version 3 (the [records' README](../../records/README.md)):
- The records of commit `4032f80` (method version 3: the nRF5340 DK and
  the NUCLEO-H723ZG) have the test sources of the published tree: the
  command above builds them from the tree.
- The records of `6301058` (the first series), `04a2197` (the second
  series on the NUCLEO-G474RE, SAM D20 and the NUCLEO-G0B1RE's tables in
  RAM) and `40f1958` (the second series on the Pico 2 and the
  NUCLEO-G0B1RE's CRC unit) are of earlier commits, and
  `records/rebuilt.json` lists them. Check them with `VL_TREE=1` in front
  of the command:

```sh
VL_TREE=1 bash kinds/crc/bench/crcverify.sh records/crc/samd20/*.json
```

- The second series' configurations build like the first's; a table in
  RAM is moved by the build itself (`kinds/crc/bench/onecrc.py`), and the
  board's CRC unit is built only for the boards that have one
  (`kinds/crc/boards.txt`).
- Time, in our check with the libraries at hand: all 168 records of
  `rebuilt.json` in 222 s (2026-11-25).

**Run it on your own board.**

```sh
kinds/crc/repeat.sh --check          # the tools, the image and the board
kinds/crc/repeat.sh                  # quick: up to three configurations of one bundle, two passes
kinds/crc/repeat.sh --level full     # every configuration of the board, two passes
kinds/crc/repeat.sh --board pico2    # choose the board when more than one is connected
```

It builds the images of this tree, writes a bundle to the board, runs its
images in two passes as our series did, makes records of your runs and
compares them with ours image by image, and packs everything into one
archive (below, "Send us your result"). Flash: the quick level writes one
bundle, the full level every bundle of the board (a bundle that is
already on the board is not written again). Time: the full level runs
what our series ran on one board; those runs, with the flash writes and
without the build, took from 33 minutes (NUCLEO-G474RE) to 3 h 40 min
(Raspberry Pi Pico 2) on 2026-11-24 (NUCLEO-G0B1RE 62 minutes, nRF5340 DK
88, NUCLEO-H723ZG 65, SAM D20 Xplained Pro 118; the
[series report](../../reports/2026-11-25-crc-first-series.md)); the quick
level on the Raspberry Pi Pico 2 took 34 minutes from a tree exported from
this repository (2026-11-25: fetching and building included, the bundle
already on the board, 48 runs; result "same as ours"). In such a tree (no
git history) it builds and runs in a copy of the sources under its result
directory (`src/<commit>`), so that its records name a commit that can be
rebuilt; your tree is not written to.

## The pools records

The records of the fixed-block memory pools (`records/pools/<board>/<adapter>.json`,
one per board and configuration, eight images each;
[`records/`](../../records/README.md)) are rebuilt with the kind's own
tool. It needs the toolchain image `verified-libs/toolchain:2026-11-13` and
fetches the libraries at their pins (`kinds/pools/libs.lock`).

**Rebuild, without a board.**

```sh
bash kinds/pools/bench/poolverify.sh records/pools/stm32g474/*.json
```

For each record it builds every image of the board from the sources of the
record's commit and compares, per image, the bytes in flash
(`image_sha256`), the address, the fixed part, the boot stub, the
toolchain, the layout of the image and the configuration's sizes: `MATCH`
or `DIFFERS`. In a tree without git history it takes the sources from the
tree if the record's commit is in `EXPORTED_FROM` or in
`SAME_SOURCES_POOLS`.

**Run it on your own board.**

```sh
kinds/pools/repeat.sh --check          # the tools, the image and the board
kinds/pools/repeat.sh                  # quick: up to three configurations of one bundle, two passes
kinds/pools/repeat.sh --level full     # every configuration of the board, two passes
kinds/pools/repeat.sh --board pico2    # choose the board when more than one is connected
kinds/pools/repeat.sh --bundle 101     # quick, with the configurations of that bundle, not of the first
```

It works as the CRC kind's script:
- it builds the images of this tree;
- it reads the board's option registers without writing anything, because
  every pools record carries them (method version 3);
- it writes a bundle to the board and runs its images in two passes, as our
  series did;
- it makes records of your runs and compares them with ours image by image
  (`kinds/pools/bench/poolscompare.py`);
- it packs everything into one archive (below, "Send us your result").

On the Raspberry Pi Pico 2 the XIP cache replaces at random (RP2350
datasheet 4.4.1.2), so with the cache on the number of calls that miss
changes from run to run and our own two passes differ too; there the
comparison judges a cache-on mean outside 1 % by its fastest call, and says
how many means it judged so.

Flash: the quick level writes one bundle, the full level every bundle of the
board: nRF5340 DK 2, NUCLEO-G0B1RE 3, NUCLEO-G474RE 3, NUCLEO-H723ZG 2,
SAM D20 Xplained Pro 5, Raspberry Pi Pico 2 1. A bundle that is already on the
board is not written again. Time: a run took about 5.6 s on every board, and
our series took 20 to 25 minutes per board on 2026-11-26
([series report](../../reports/2026-11-26-pools-first-series.md)). The quick
level runs 48 of those runs, after the build. In a tree exported from this
repository (no git history), the script builds and runs in a copy of the sources
under its result directory (`src/<commit>`), so that its records name a
commit that can be rebuilt; your tree is not written to. It was run from such a
tree on a Raspberry Pi Pico 2 on 2026-11-26 (quick level, one bundle that was
already on the board, no flash write); its build step is tested
(`lab/tools/test-pools-repeat-export.sh`).

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
