# Result records

The JSON records behind the [comparison page](../site/content/compare.html),
copied from the lab host by [`site/collect_records.py`](../site/collect_records.py).
How to check them: [Reproduce our results](../site/content/reproduce.md).

- `bench-v2/<board>/`: the speed benchmark the pages show (version 2): one
  record per configuration, holding its eight images (one per placement)
  and every run of each, with the baseline of the run.
  `firmware/nrf5340-rb-bench/oneverify.sh` rebuilds a record's images and
  compares them.
- `bench/`: the code and RAM record of each board (`-rb-size-`), which the
  page shows, and the records of benchmark version 1, an archived series
  (below): the SPSC set, `-rust-` the Rust libraries, `-mp-` the modes for
  more than one producer or consumer, and the placement records
  (`-shiftN-`).
- `stress/`: one run per board and mode of the ISR stress test
  (`-rb-stress-`) and of the two-interrupt stress test (`-rb-mp-stress-`;
  per mode one run with random and one with aimed interrupts), as a
  reference for a run on your own board: of each campaign the first run of
  the mode that passed. The page's stress counts come from the whole
  campaigns (8 to 42 runs per board of the ISR test and 25 to 89 of the
  two-interrupt test, see
  [the report](../reports/2026-11-22-lwrb-v3.4.0-rerun.md)); the other
  records are not in the repository because of their size, ask for them at
  contact@verified-libs.org.

- `crc/<board>/`: the CRC kind's benchmark, one record per configuration
  (below), shown on the [CRC results page](../site/content/results-crc.md).

- `campaign/`: per board a summary of the campaign the page's stress
  counts come from: per mode and library the valid runs, the runs with
  errors and the runs it did not finish, and how often each mutant was caught
  (made by `firmware/nrf5340-rb-stress/reference.py make`; `reference.py
  compare` and `repeat.sh` compare a run on your own board with it).

Each record names its source commit (`bench_commit` or `source_commit`),
toolchain image, flags, pinned library commits and, where a firmware ran,
its SHA-256 (`fw_sha256`).

`archived.json` lists the archived series: published records that are no
longer held against the tree at hand but against their own commit
([DECISIONS.md](../DECISIONS.md), 2026-11-23). "Version 1" is every record
here that names commit `a7a206190337`. To check one of them, clone the
public repository with its history and run
[`lab/tools/verify-build.sh`](../lab/tools/verify-build.sh) on it: the
sources are taken from the public commit the series was published as.
An entry with `paths` archives only its commit's records under those
prefixes: the nRF5340 DK's and the NUCLEO-H723ZG's records of benchmark
version 2 and of the two CRC series, as they were before method version 3
(DECISIONS.md, 2026-11-26). The records of method version 3 replaced them
in the same paths; the archived ones are in the public repository at the
entry's `public_commit`.

## Method version 3: `rb-bench/3` and `crc-bench/2`

The records made under method version 3 (DECISIONS.md, 2026-11-26; the
[method page](../site/content/method.md#method-version-3)) are of two new
record versions, made by the same programs
([`firmware/nrf5340-rb-bench/onerecords.py`](../firmware/nrf5340-rb-bench/onerecords.py)
and [`kinds/crc/bench/crcrecords.py`](../kinds/crc/bench/crcrecords.py)):
- `rb-bench/3` is `rb-bench/2` with one field more, `crc-bench/2` is
  `crc-bench/1` with the same field; every other field is unchanged.
- `option_registers`: the board's option registers, read through the debug
  probe without writing anything before the series and each of its jobs
  ([`lab/tools/read-options.py`](../lab/tools/read-options.py)). A list of
  readings, each distinct reading once, in time order. A reading
  (`board-options/1`) holds `board`, `chip`, `time`, `probe_rs` (the
  probe-rs version) and `regions`: per register or register block its
  `name`, `address`, `source` (the manual's section) and `words`.
- A record whose runs have no option registers is of the old version,
  written as before; a record whose runs have them is of the new one; a
  record of runs with and without them is not made.

The pages read both versions, and say per board which method version its
records are of ([`site/series_info.py`](../site/series_info.py)).

## The CRC records (`crc/`)

`crc/<board>/<adapter>.json`: the CRC kind's benchmark, one record per
board and configuration ([`kinds/crc`](../kinds/crc/README.md)),
made by [`kinds/crc/bench/crcrecords.py`](../kinds/crc/bench/crcrecords.py)
from the run files of `kinds/crc/bench/run-crc.py`. Schema `crc-bench/1`.
[`kinds/crc/bench/crcverify.sh`](../kinds/crc/bench/crcverify.sh) rebuilds
a record's eight images and compares them. The 221 records here are of two
series, six boards, two passes each, and of method version 3 on two boards:
- the first series, 120 records of the 20 configurations of step 2 (commit
  `6301058`, 2026-11-24 to 2026-11-25; the
  [report](../reports/2026-11-25-crc-first-series.md));
- the second series, 101 records of the 18 configurations of step 11 (the
  tables in RAM, and the board's CRC unit on the four boards that have
  one). Its commits are `04a2197` (NUCLEO-G474RE, the NUCLEO-G0B1RE's
  tables in RAM, SAM D20) and `40f1958` (the rest). The account is in the
  [report](../reports/2026-11-25-crc-second-series.md);
- method version 3, 73 records of commit `4032f80` (2026-11-26): every
  configuration of both series on the nRF5340 DK (35) and the
  NUCLEO-H723ZG (38), measured again (record version `crc-bench/2`,
  below). They replaced those boards' records of the two series, which
  are archived series now (`archived.json`).

Every record was rebuilt byte for byte from its commit. The records of
`4032f80` have this tree's CRC test sources; those of `6301058`, `04a2197`
and `40f1958` also rebuild from this tree's sources, and
[`rebuilt.json`](rebuilt.json) says so (`lab/tools/image-ledger.py`). Fields:

| Field | What it holds |
|---|---|
| `schema` | `crc-bench/1` |
| `board`, `core`, `board_id`, `board_decoded` | the board, its core, and the board as the image reported it |
| `code_location` | where the code ran from (`flash`) |
| `kind` | `crc` |
| `crc` | the CRC, by its catalogue name (`CRC-32/ISO-HDLC`, `CRC-16/IBM-3740`, `CRC-8/SMBUS`) |
| `adapter`, `lang`, `name` | the configuration (`kinds/crc/configs.txt`), its language and the name it carries |
| `bench_commit` | the commit the images were built from |
| `toolchain_image`, `toolchain` | the toolchain image and the compilers in it |
| `libs_pinned`, `crcany_generated_lock_sha256` | the libraries' pinned commits, and the checksum of crcany's generated sources |
| `result_version` | the version of the result block the image wrote |
| `clock_hz` | the core clock |
| `runs` | timed calls per scenario (256) |
| `lens`, `offsets` | the lengths (1, 4, 16, 64, 256, 1024 bytes) and the offsets from an 8-byte boundary (0, 1) |
| `overhead_subtracted` | the cycles of the cycle counter's read (the board's `BOARD_READ_OVERHEAD`, `firmware/common/<board>/board.h`), subtracted from every call |
| `empty_call_raw_min` | the shortest timed call of an empty function, before the subtraction; every run of the record must agree |
| `fixed_sha256`, `boot_image_sha256` | the fixed part (timing code, `main`, the reference) and the boot stub, the same in every image of a board |
| `far_bytes`, `layout` | the bytes between the adapter and the library, and the order of the parts of an image |
| `passes` | the passes of the series (2) |
| `images` | the eight images, one per placement (below) |

Per image: `place` (the placement, 0 to 28 bytes), `slot` (segment, offset
and size in the board's flash), `image_base`, `image_bytes`, `fw_sha256`
(the ELF file), `image_sha256` (the bytes in flash) and `runs`. Per run:
`time`, `host`, `probe_rs`, `pass`, `attempt` and `wait_s` (an attempt
read before the image had finished is repeated with a longer wait),
`seconds`, `run_number` (the host's number the image echoed),
`bundle` and `bundle_sha256` (the bundle written to the board), `errors`
and `baseline_errors` (calls whose result was not the reference's), and
`results` and `baseline`: per scenario
(`len<N>/offset<K>/cache_<off|on>`) `min`, `max`, `mean`, `first` and
`count` of the 256 calls, in cycles, for the configuration and for the
reference of its CRC in the same image.

A CRC record has test sources of its own (`CRC_TEST_SOURCES` in
[`lab/tools/public-export.py`](../lab/tools/public-export.py)); a change in
`kinds/crc` does not touch the ring-buffer records, a change elsewhere
under `firmware/` does not touch the CRC records, and a change under
`firmware/common` counts for both.
