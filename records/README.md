# Result records

The JSON records behind the [comparison page](../site/content/compare.html),
copied from the lab host by [`site/collect_records.py`](../site/collect_records.py).
How to check them: [Reproduce our results](../site/content/reproduce.md).

- `bench/`: per board the benchmark records the page shows (the SPSC set,
  `-rust-` the Rust libraries, `-mp-` the modes for more than one producer
  or consumer), the placement records (`-shiftN-`) and the code and RAM
  record (`-rb-size-`).
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

- `campaign/`: per board a summary of the campaign the page's stress
  counts come from: per mode and library the valid runs, the runs with
  errors and the runs it did not finish, and how often each mutant was caught
  (made by `firmware/nrf5340-rb-stress/reference.py make`; `reference.py
  compare` and `repeat.sh` compare a run on your own board with it).

Each record names its source commit (`bench_commit` or `source_commit`),
toolchain image, flags, pinned library commits and, where a firmware ran,
its SHA-256 (`fw_sha256`).
