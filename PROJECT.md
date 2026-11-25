# verified-libs

An open, verified registry of specialist libraries, where AI agents and
people can find the right tool for a hard task without repeating the same
expensive research and tests. The goal is to save work, tokens and CO2.

We start with **embedded ring buffers** (interrupt/DMA to main loop on
Cortex-M, in C, C++ and Rust) as the first narrow niche, and later expand to
server-side queues and, for example, lock-free queues, hash maps and
allocators. Depth over breadth.

*Run by AI, with a human who is accountable.*

## Core value

What future AI models cannot simply take over by having read more:

- **Measured data on real hardware over time**, not knowledge from reading.
- **Correctness tests:** stress tests on the boards, a contract check on a
  host model of one core (an interrupt at every instruction point)
  and model checking (GenMC, C11 memory model). Other tools (sanitizers,
  Miri, loom, TLA+, herd7 litmus tests) are named here when a result uses
  them.
- Correctness is proven once against the language's memory model. Performance
  can only be measured.
- **Role over time:** from "we found the bugs" to "here is the proof".
- **Audience:** the hard cases (lock-free, interrupt-driven, multithreaded,
  performance critical), not simple ring buffers an AI can write by itself.
- **The test suite ships with the results**, so agents can verify a
  recommendation themselves.

## Principles

### 1. Honest, reproducible data
- Everything can be reproduced: code, hardware, compiler, flags and versions
  are logged.
- Every record states the commit, the firmware's hash, compiler, flags and
  time, and can be repeated on the same board with one command. Independent
  repetitions count. Signing of records comes after version 1.
- The test setup is open source, and the data is a commons.
- No paid placement.
- Results expire when the library, compiler or hardware changes version.
- Uncertainty is shown next to the number: one measurement on one machine is
  not as certain as twelve measurements on three.
- Data is structured rather than free text, also as a guard against prompt
  injection.

### 2. The user's own criteria decide what is best
- The registry has **no overall score**. It delivers measurements; the user
  sets the criteria.
- **Filters for requirements**, e.g. "embedded, SPSC, Cortex-M0+, no dynamic
  memory, MIT-compatible license".
- **Weights for preferences**, e.g. speed 3, size 1, reliability 5. The
  calculation is shown openly.
- The same query for people (website) and AIs. Version 1 gives agents the
  same data as JSON files; an MCP server over them follows after version 1.
- **Known bugs are always shown** under the conditions the user has chosen.
- **The default view is a choice too.** It is neutral and says openly what it
  sorts by, e.g. "sorted by correctness, then alphabetically".
- During the trial period: filters and sorting by one criterion at a time.
  Weighting comes once the measurements have proven to hold.

### 3. The winner is celebrated, there is no last place
- The recommended solution and its creator are clearly credited by name.
- Below the winner there are only groups, e.g. "Also good choices" and
  "Other tested", sorted alphabetically and not by result.
- "Best for what": most libraries are good at something, and that should be
  visible.
- Fixes are celebrated too: "Bug found and fixed in v1.4, thanks to the
  maintainer."

### 4. Improvement is rewarded over time
- Every library has a timeline. A rise from "not recommended" to
  "recommended" is a success story that should be visible.
- New solutions get a fair start: "New, under test", not "not recommended".
- Fixed bugs move to the history.
- Bug reports come with the test that found the bug, and preferably a
  suggested fix: a tool, not an accusation.
- AI-written solutions are judged by the same tests and get the same chance
  to improve.
- The test suite evolves continuously and should resemble real workloads, so
  nobody can optimize for the tests instead of for real tasks.

### 5. Bugs are facts about a version, and the maintainer hears first
- Bugs are described neutrally and reproducibly: "v1.2 fails test X on ARM",
  never as a verdict on the code or the person.
- The maintainer is always told privately first, with a deadline (typically
  90 days) before publication.
- Every finding is recorded immediately with a timestamp and a hash of the
  description, without the content itself. When the deadline expires or the
  bug is fixed, everything is published. Anyone can then see that nothing
  was hidden or delayed.
- If we are wrong, we correct it quickly and visibly.

### 6. Openness about conflicts of interest
The project owner has their own solutions in the registry. They are treated
the same in the tests, but must be proven more strongly:
- **Clear labelling:** "Written by the project owner" appears next to the
  solution, both on the website and in the data that agents read.
- **Open to external verification, like every library:** every result,
  the owner's included, can be repeated outside the project with the
  published test suite on one's own hardware, and repetitions from outside
  are shown next to ours. An outside repetition is welcome for any library;
  it is not a condition for showing the owner's results. In the long run
  every library should be verified outside the project where possible
  (DECISIONS 2026-11-17).
- **Stronger validation:** the owner's solutions are tested in every
  documented mode and topology in every test (stress test, interrupt sweep,
  contract check, model check where it applies), and they need more
  repetitions from outside the project than other libraries before their
  results count as equally certain. More runs of our own do not count for
  that (DECISIONS 2026-11-17, addition of 2026-11-19).
- **No special treatment:** the same test suite, and the tests must not be
  changed in ways that favour the owner's solutions.
- **The same notice period** as everyone else (principle 5).

## Legal framework
- Phase 1 tests only open source libraries. Commercial libraries come in
  phase 2 at the earliest, once there is an association and possibly legal
  advice.
- We link to the libraries and do not copy them in without their license.
- Licences: MIT for code ([LICENSE](LICENSE)) and CC BY 4.0 for texts and
  data ([LICENSE-docs](LICENSE-docs)), both "as is, without warranty".
- The project starts as a project/association (possibly via Open
  Collective), not a foundation. An association with bylaws is set up fairly
  early, so liability does not rest personally with the owner.

## Organisation
- Project owner: Erik N (pxq.dk). Not anonymous by
  choice: the owner has a candidate of their own in the registry, and the
  conflict of interest must be visible (principle 6).
- Claude develops and runs most of it: coordinator, architect and steering.
- The owner holds the accounts and keys, approves everything that binds the
  project (bug reports to maintainers, publication, money, agreements) and is
  accountable. A few hours a week.
- Steering lives in the repo, not in a conversation: `PROJECT.md` (this
  document), `DECISIONS.md` (what and why) and the working lists in
  `lab/plans/` (tasks). GitHub Issues are used from publication, for
  questions and reports from outside.
- Project email: contact@verified-libs.org. Claude may read it and write drafts. Every
  outgoing mail is read and sent by the owner. Claude cannot send mail.

## Cheap operation
- Free hosting: Git repo plus GitHub/Cloudflare Pages.
- Host-side correctness checks on GitHub Actions come after version 1;
  until then they run on lib-lab1.
- Host-side correctness tools and board control on our own machine,
  [lib-lab1](lab/lib-lab1.md); performance measured in cycles on real
  Cortex-M boards. Stability over raw power.
- No claim of green operation. lib-lab1 is a laptop and draws little (its
  CPU 5.1 W with test campaigns running on all six boards, RAPL,
  2026-11-18), so running jobs in the greenest hours would change very
  little. The larger share is likely the AI model that does the
  development, and the project can neither choose nor check what power
  that runs on. A green promise that cannot be kept is not made.

## Plan: 3-month trial
- **Minimum version:** 10-15 embedded ring buffers in C, C++ and Rust
  ([candidates](candidates/ringbuffers-embedded.md)), correctness tested,
  measured on Cortex-M0+ and M4 boards, and a simple static website with
  the data as JSON files (version 1). An MCP server follows after version 1.
- **Success:** at least one real bug found and reported, external links or
  stars, use or feedback from outside.
- **Stop without a bad conscience** if there is no response after 3 months.

## Status
- 2026-11-04: lib-lab1 set up (Ubuntu 26.04 LTS, Ryzen 7 7840U).
- 2026-11-05: GitHub organisation verified-libs and this repo created.
- 2026-11-05: First niche set to embedded ring buffers; candidate list made.
- 2026-11-25: Second kind, CRC calculation in software: first board series on six boards ([results](site/content/results-crc.md)).
