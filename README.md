# verified-libs / project

An open registry of specialist libraries, verified on real hardware:
measured, stress-tested and model-checked, every number with its record and
source. Two kinds of library so far, both for microcontrollers on six
boards:

- embedded ring buffer (FIFO) libraries: speed, code size, interrupt stress
  tests and model checks ([results](https://verified-libs.org/results.html) ·
  [method](https://verified-libs.org/method.html) ·
  [compare the libraries](https://verified-libs.org/compare.html));
- CRC calculation in software: cycles per call and per byte
  ([results](https://verified-libs.org/results-crc.html) ·
  [method](https://verified-libs.org/method-crc.html)).

**Website: [verified-libs.org](https://verified-libs.org)** ·
[all results](https://verified-libs.org/kinds.html)

Shared project repo for verified-libs: purpose, principles and the test lab.
The libraries themselves each live in their own repo under the organisation.

## Contents
- [`RESULTS.md`](RESULTS.md) – **all results in one place** (speed, ISR stress, GenMC, findings)
- [`PROJECT.md`](PROJECT.md) – purpose, principles and plan
- [`DECISIONS.md`](DECISIONS.md) – what was decided and why
- [`candidates/ringbuffers-embedded.md`](candidates/ringbuffers-embedded.md) – candidates for the 3-month trial
- [`reports/2026-11-06-first-harness.md`](reports/2026-11-06-first-harness.md) – summary of the first harness results
- [`reports/2026-11-07-overnight-campaign.md`](reports/2026-11-07-overnight-campaign.md) – first 8-hour stress campaign
- [`lab/lib-lab1.md`](lab/lib-lab1.md) – setup of the benchmark machine lib-lab1
- [`lab/lab-setup-1.sh`](lab/lab-setup-1.sh) – base setup of lib-lab1 (run with `sudo bash`)
- [`lab/lab-setup-2.sh`](lab/lab-setup-2.sh) – stable measurements: fixed frequency, isolated cores, `lab-env`/`lab-run`
- [`lab/lab-setup-3.sh`](lab/lab-setup-3.sh) – rootless Podman for the toolchain image
- [`lab/lab-setup-4.sh`](lab/lab-setup-4.sh) – debug probes: probe-rs, udev rules, serial port access
- [`lab/lab-setup-5.sh`](lab/lab-setup-5.sh) – limited passwordless sudo for routine lab tasks
- [`firmware/nrf5340-cyccnt/`](firmware/nrf5340-cyccnt/README.md) – first cycle-count measurement on the nRF5340 DK
- [`firmware/nrf5340-rb-bench/`](firmware/nrf5340-rb-bench/README.md) – first ring buffer benchmark: push/pop cycles per library
- [`firmware/nrf5340-rb-stress/`](firmware/nrf5340-rb-stress/README.md) – ISR <-> main stress test with negative control
- [`verify/genmc/`](verify/genmc/README.md) – GenMC model checks with negative controls (lwrb, diffstorm)
- [`verify/findings/`](verify/findings/) – defects found, each with reproducer and status (maintainer first)
- [`toolchain/`](toolchain/README.md) – pinned container with GenMC, CBMC, clang, arm-none-eabi GCC, Rust and Miri
- [`mcp-server/`](mcp-server/README.md) – MCP server: the comparison as tools for AI agents, the same answers as the website

## Suggest a library
Do you think a library belongs on the test list, your own or one you use?
Write to contact@verified-libs.org with a link, the version, and what it
promises (for example "one producer and one consumer, interrupt-safe
without locks"). The libraries are chosen by how widely they are used and
by what they claim ([candidates](candidates/ringbuffers-embedded.md)); a
suggestion is welcome but not a promise to test it. Every library tested
goes through the same tests, and the results are published as they come
out. If we find a defect, the maintainer hears about it first.

## Donated hardware is welcome
The lab runs six boards today (nRF5340 DK, NUCLEO-G0B1RE, NUCLEO-G474RE,
NUCLEO-H723ZG, SAM D20 Xplained Pro, Raspberry Pi Pico 2). More cores and
vendors make the results more useful, for example RISC-V or Cortex-M cores
that are not in the lab yet. If you can give a board (with a debug probe, if
it needs one), please write to contact@verified-libs.org first, before you
send anything, so we can check that it fits the lab and is not a duplicate.
A donated board is used for every library in the same way: a donation does
not buy placement or change a result. Instead of a thank-you, the lab's
hardware list ([`lab/lib-lab1.md`](lab/lib-lab1.md)) says where each board
came from ("donated by" and your name, or just "donated" if you prefer), and if a
vendor donates its own board, the results for that board say so. Today
every board in the lab was bought by the project (see
[DECISIONS](DECISIONS.md), 2026-11-12).

## Licence
Code (scripts, firmware harness, adapters, build and configuration files):
[MIT](LICENSE). Texts and results (the Markdown documents, the website's
texts, `records/` and `site/data/`): [CC BY 4.0](LICENSE-docs); you may
reuse and republish them, also commercially, if you credit verified-libs
and link the licence. The libraries that are tested are not in this
repository and keep their own licences.

The copyright is held by Erik N (pxq.dk) for the verified-libs project,
to be moved to a verified-libs association or company if one is set up.
Contributions to the repository are accepted under the contributor
agreement in [CONTRIBUTING.md](CONTRIBUTING.md) (draft, not yet in use);
contributors are named in [AUTHORS](AUTHORS).

Neither licence gives a right to use the name "verified-libs" to suggest
that the project approves, certifies or recommends a library or product.
Citing our results with credit, as above, is welcome.
