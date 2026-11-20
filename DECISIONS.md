# Decisions

Short log of what was decided and why. Newest first.

## 2026-11-20: How version 1 is published
- **Commits in the public repository carry the project's name and
  address** (`verified-libs <contact@verified-libs.org>`), not a person's.
  Why: the public repository is the project's, and the private working
  address stays private.
- **The public tree goes to the branch `main`, the site built from that
  tree to the branch `gh-pages`**, which GitHub Pages serves at
  verified-libs.org (`lab/tools/publish.sh`). Why: no GitHub Actions
  before version 1, and the site is plain files. The script pushes only
  with `--go`, and that only on the owner's word each time.
- **verified-libs.org is verified for the organisation at GitHub** and
  points at GitHub Pages; the project mail stays where it was.

## 2026-11-19: Decisions for the publication of version 1
- **The publication re-run aims every multi-producer run at the two
  slowest interrupt rates** (prescaler 3 and 4; `campaign.sh`
  `AIM_SLOW=all`). Random interrupts are used at the two fastest rates
  only. Why: at the slow rates random runs often did not catch the control
  (on the Pico 2 never), so they were invalid and cost board time; aimed
  runs caught it in 210 of 210
  ([report](reports/2026-11-18-mp-campaign-coverage.md)).
- **`lab/plans` is public**, the critical review of 2026-11-18 included.
  Why: it fits the project's openness that its own weaknesses can be read.
- **Attribution lines in older commit messages stay.** Why: the public
  repository is made by an export without history, so they are never
  public, and removing them would need a rewrite of the history.
- **The site and the public repository live in the GitHub organisation
  `verified-libs`** (it exists since 2026-11-05), the site on GitHub Pages
  with verified-libs.org pointing there. Why: free, and the host-side
  checks on GitHub Actions (after version 1) need the repository there.
- **The method is frozen as soon as the PROJECT.md proposal and the
  conflict-of-interest texts are approved and applied**; the publication
  re-run then starts without asking again.
- **The public repository is `verified-libs/verified-libs`**: the same
  name as the organisation, as is usual for an organisation's main
  repository. Why: it holds the whole project (principles, method, test
  code, toolchain, site), and other kinds of libraries are to follow the
  ring buffers, so the name must not say "ring buffers"; "results" would
  cover too little. `verified-libs/project` stays the private working
  repository; the public one is made from it by the export, without
  history.
- **The green approach is dropped.** PROJECT.md no longer promises
  carbon-aware scheduling or a CO2 account per result, and the section is
  called "Cheap operation". Why: the lab draws so little that green hours
  would change almost nothing, and the larger share is likely the AI model
  that does the development; the project cannot choose or check what
  power that runs on, so it could not stand behind a green claim.
- **PROJECT.md aligned with what exists** (the rest of the proposal of
  2026-11-18 approved): the tests named are the ones the results use,
  records are not signed yet, JSON files in version 1 and the MCP server
  after it, MIT and CC BY 4.0, GitHub Actions after version 1.
- **Conflict of interest stated on the site** (approved): an item on the
  front page, a section on the method page that also says where pxq and
  the others are not treated evenly, the tag "written by the project
  owner" linking to it, note N7 in RESULTS.md with pxq's weaknesses, and a
  heading note on the report about pxq alone. With this the two drafts are
  applied and the method is frozen for the publication re-run.

## 2026-11-18: Version 1 first; the method is frozen until then
The next goal is to launch version 1: the site and the repository public
with what exists and holds today. Until then no new test types, boards,
modes or toolchains, and no long campaigns beyond the re-run that
publication needs. The MCP server comes after version 1. Working list:
[`lab/plans/2026-11-18-review-and-v1.md`](lab/plans/2026-11-18-review-and-v1.md).

Why:
- A review after two weeks showed the focus had drifted from the start
  goal: much depth in the test lab, nothing anyone outside can see, use or
  correct. The trial's success criteria need readers.
- Every new test type makes publication dearer, because everything shown
  must be re-run at the published commit.
- Once it is public, others can repeat the results and improve the tests.

Also decided: an observation that is useful to a maintainer and is not a
defect under embargo is sent when it is found, not held until publication
(first case: the bbqueue cache-line note), so that no maintainer hears
later than the project owner does about the owner's own library.

## 2026-11-17: The control is not made easier to catch; the test's reach is measured
At the slow interrupt rates the multi-producer stress test often does not
catch its control (a single-producer buffer used by two producers). The
control stays as it is. Instead the test records where its interrupts land
in each library's code, and half of the runs at those rates aim the
interrupts at the push and pop. The coverage numbers go into every
campaign report.

Why:
- A control tuned to fail hides the signal that the test is weak there.
- "0 errors" says little without knowing how often the code under test
  was interrupted, and where.

## 2026-11-17: pxq stays in the comparison, and the fairness must be visible
The owner's library stays in the tests and on the comparison page. A text
on the conflict of interest and an audit of the page and the reports for
anything that favours pxq are written before publication; the owner
approves both. At publication the other authors are invited to review the
adapters for their libraries.

Why: users gain from having it in the comparison, but only if they can
check that it got no better treatment than the rest.

## 2026-11-17: Development comes before campaigns
Long test campaigns run only when the boards are not needed for
development, and are stopped when they are. (From 2026-11-18: no long
campaigns before version 1, see above.)

Why: the 24-hour campaign of 2026-11-14 held all six boards during a
development phase; the owner stopped it after 16 hours.

## 2026-11-17: More boards after publication, as donations
More hardware (first more SAM D20 boards, so tests can run in parallel)
is sought once the site is public, as donations under the rules of
2026-11-12, not as purchases.

Why: the SAM D20 is the slowest board and needs several flash bundles;
one board per bundle means no rewrites when switching tests.

## 2026-11-17: Outside verification is a goal for every library, not a condition for pxq
In the long run every library's results should be repeated outside the
project, where that can be done. Until then no library, the owner's pxq
included, needs an outside repetition before its results are shown.

Why:
- The owner's words: outside verification is the long-term aim for all
  libraries; it is not something to do for pxq in particular.
- An early report (2026-11-08) said pxq's numbers "count only after an
  independent repetition"; that came from mixing up this goal with
  principle 6. Principle 6 already says an outside repetition is welcome
  for any library and not a condition.

Added 2026-11-18 (owner): once outside repetitions happen, pxq should get
more of them than the other libraries before it is seen as equally
certain (principle 6, stronger validation). That cannot be met before an
outside setup is in use, so it is not a step towards version 1.

Added 2026-11-19 (owner): more runs of pxq by the project itself add
nothing to this. In the long run the trust rests on people outside
repeating every library and getting results that match the site's. That
pxq needs more outside repetitions than the others for the same trust
follows from the owner having both a library and the comparison site.
Principle 6 in PROJECT.md said "more repetitions than others, e.g. twice
as many" without saying whose; it now says repetitions from outside.

## 2026-11-16: Outside repetition with one command, through the boards' own probes
`repeat.sh` lets anyone with one of the six boards repeat our records
with the probe that is on the board; no separate debug probe is needed.
Because the public tree has no history, every record shown at publication
must be made at the published commit: benchmarks, reference stress runs
and multi-producer runs are re-run there first.

Why: an outside repetition should cost a board and ten minutes, not a
lab; and a record can only be checked against a tree the reader can get.

## 2026-11-15: A changed method starts a new series
When the test method changes (run parameters at run time, one image per
library, the multi-producer bundle), records from before and after are
not pooled. Earlier reports keep their numbers and say which method they
used.

Why: pooled counts over different methods say more than was tested.

## 2026-11-15: Flash wear is a budget
The boards are to last for years and for other kinds of libraries. Test
firmware is built so that an unchanged image is never written again: one
image per library in a bundle, flashing with pre-verification, run
parameters sent at run time, campaign entries grouped by build
configuration. Experiments that need many images (placement series,
compiler matrices) run when their result is needed, not routinely. Writes
per board are counted and reported.

Why: flash is rated for about 10,000 erase cycles, and the owner pays for
the boards.

## 2026-11-15: The contributor agreement is a draft until a lawyer has read it
`CONTRIBUTING.md` holds the draft. It is not taken into use before a
lawyer has reviewed it, which must happen before the first outside
contribution is merged. Rights may pass on only to a verified-libs entity
or a non-profit that takes over the stewardship, not to any third party.

Why: an assignment of rights that does not hold in law protects neither
the contributors nor the project.

## 2026-11-14: A library that is held back or fails must not block the others
Code that is not in the public tree is never part of a firmware whose
records are shown: it is built only on request, and the default firmware
is byte-identical to a build of the public tree. Each library runs from
its own image after its own reset, so one that hangs or crashes cannot
spoil a run for the rest.

Why: the owner's words: a library that fails must not be able to block
results from the others. And a record must be rebuildable from the public
tree.

## 2026-11-14: The comparison uses the C library's memcpy for every library
Numbers measured with the Rust memcpy are not shown on the comparison
page. They are documented in `reports/2026-11-13-memcpy-rust.md`.

Why: one memcpy for all is the fairest common basis, and the records
already state which one was used.

## 2026-11-13: The comparison page does not rank
The page has no ranking of ours and no default order that favours a
library. Rows are grouped by test outcome (0 errors, not tested, errors);
the only preset filter hides single-context variants.

Why: the owner's own library is in the comparison.

## 2026-11-12: Embargoed findings stay out of everything public
A finding under embargo (notice not sent yet, or the notice period running
without the maintainer's agreement) is not mentioned anywhere public: not
on the site, not in a public repository, not in a public commit message.
Not even its existence or the library's results that would give it away.

- Work continues in the private repository, which keeps everything.
- The public repository is made by an export (`lab/tools/public-export.py`),
  never by making the private one public: a fresh tree without history
  (commit messages name findings), leaving out the paths in
  `site/embargo-paths.txt`, dropping markdown passages between
  `<!-- embargo -->` and `<!-- /embargo -->`, and refusing if any word from
  `site/embargo.txt` is left. `site/build.py` already refuses the same way.
- When an embargo ends, its words and paths are removed from the two lists
  and the next export includes it.
- Everything not under embargo can be published, but publication itself is
  still the owner's decision.

Why: the embargo protects users of the library until a fix exists; a
mention of "a finding in X" already points attackers at X.

## 2026-11-12: Donated hardware: welcome, and disclosed, not thanked
Donated boards (and probes) are welcome, to cover more cores and vendors.
Donors write to contact@verified-libs.org before sending anything.

- Every board's origin is recorded in the lab hardware list
  (`lab/lib-lab1.md`): `bought by the project` or `donated by <name>,
  <date>`. Name only: no logo, no link, no description, no sponsor page,
  nothing on the front page.
- If the donor makes or sells the board or its chip, the results for that
  board say so ("board donated by the vendor").
- A donor may stay anonymous; the list then says "donated" without a name.
- A donated board is used for every library in the same way; a donation
  does not buy placement or change a result.

As of 2026-11-12 every board and probe in the lab was bought by the project.

Why: a thank-you with the donor's name drifts towards advertising. Saying
where a board came from is the same kind of fact as compiler and flags:
it lets a reader judge the result, and it is needed when a vendor donates
the hardware its own chip is measured on.

## 2026-11-08: The project has its own domain
verified-libs.org, with contact@verified-libs.org for all project mail.
Notices to maintainers go out from there, not from the owner's pxq.dk
address; the owner still signs with name (principle 6).

Why: a defect notice to the maintainer of a competing ring buffer, sent
from pxq.dk, would make the project look like a part of pxq.

## 2026-11-06: Notice period for defects: 90 days from sending
When we find a defect, the maintainer is told first (principle 5). Nothing
about it is published until 90 days after the notice was **sent** (not
after it was found), or earlier if the maintainer has released a fix and
agrees. The send date and the resulting publication date are recorded in
the finding's README.

Why: 90 days is common practice and gives small, part-time maintainers
time to react. Counting from sending, not from finding, keeps the clock
honest when we take time to verify a finding before reporting it.

## 2026-11-06: Measurement method for embedded ring buffers (draft)
Decided while building the first harness on the nRF5340 DK. To be confirmed
before results are published.

- **Primary number: code in flash, instruction cache on**, cache-on mean and
  min of cycles per call. That is how firmware normally runs. Flash with the
  cache off and code in SRAM are reported as supplements.
  Why: on the nRF5340 the three differ by up to 3×, and SRAM is *slower*
  than flash with the cache on, so "flash vs RAM" must always be stated.
- **Every published "no errors" needs a negative control** that is caught
  by the same test: a deliberately broken variant (GenMC: atomics removed,
  release → relaxed; hardware: head published before the data). If the
  control passes, the test is broken and the run is rejected.
- **Timing in assembly, identical window for every operation and library**
  (`ldr CYCCNT ; blx op ; ldr CYCCNT`), plus a baseline row for the call
  cost. Why: with C timing code the compiler moved extra work into some
  windows and not others.
- **Runs are rejected if the cycle counter stalls.** Why: probe-rs clears
  `DEMCR.TRCENA` on attach/detach, which stops CYCCNT.
- **Libraries are fetched at pinned commits, never copied into the repo**,
  and used through a thin adapter that is documented per library (e.g.
  AndersKaloer: space check before queue, because queue overwrites when
  full; ETL queue_spsc_isr: `*_from_isr` in the interrupt).
- **Libraries are tested against their own contract.** A `volatile`-based
  buffer made for ISR ↔ main on one core is not judged by the C11 memory
  model alone (where it is a data race by definition); it gets a test of
  that contract (ISR stress on hardware) and, later, a matching model.

## 2026-11-06: The project owner is named
The project owner is named as Erik N (pxq.dk), instead of being
anonymous.

Why:
- The owner's own ring buffer is a candidate and has a commercial license. An
  anonymous tester with a competing candidate would undermine trust; a named
  one with clear labelling (principle 6) shows openness.
- Real anonymity would need an identity fully separate from the existing
  account and domain, which is not worth it.
- Bug reports from a named embedded developer carry more weight.

## 2026-11-05: No MCU energy measurements in the trial
The trial measures correctness, cycle counts and code size. Energy per
operation on the microcontroller is left out for now.

Why:
- Keeps the first harness small, so the trial can reach its main goal:
  finding real bugs and publishing verified results.
- Cycle counts at a fixed clock are already a strong proxy for energy on the
  same chip.
- Energy numbers are easily over-read (e.g. as "language X is greener"). Doing
  them well needs a method aligned with EEMBC ULPMark / MLPerf Tiny and, for
  absolute values, a calibrated instrument.

Likely to become an important parameter later; the registry has a clear gap
here. Not affected: RAPL energy on lib-lab1, which is used for the lab's own
CO2 account (green operation), not as a library metric.

## 2026-11-05: Correctness tools run in a pinned container
GenMC, CBMC, clang, arm-none-eabi GCC, Rust and Miri run in one Podman image
([toolchain/](toolchain/)), built on lib-lab1. Every input is pinned: base
image digest, Ubuntu snapshot date, GenMC commit, Rust versions.

Why:
- Principle 1: a published verdict must be reproducible by anyone, later. A
  versioned image makes "which tools said this" a fact, not a memory.
- Keeps the lab host clean, so the benchmark environment does not drift
  when tools are added.
- Rootless Podman needs no daemon and no root at run time.

Timing benchmarks on the host still run outside the container (via
`lab-run`), so container overhead never enters a measurement.

## 2026-11-05: First niche is embedded ring buffers
The 3-month trial is limited to embedded ring buffers: SPSC between an
interrupt (or DMA) and the main loop/task, on Cortex-M0+ and M4, in C, C++ and
Rust. The long-term vision stays broad.

Why:
- Server queues are already benchmarked widely; embedded ring buffers are
  rarely tested systematically, so the registry adds the most value there.
- Higher chance of finding real bugs (missing barriers, interrupt races,
  index wraparound), which is the trial's main success criterion.
- Cycle counts on a microcontroller are nearly deterministic, which suits
  reproducible measurements.
- The owner has the domain knowledge and the hardware (STM32 boards, ST-LINK,
  oscilloscope).

Consequences: lib-lab1 runs host-side correctness tools (TSan, GenMC, CBMC)
and drives the boards; performance is measured on the boards. Server-side
queues become a later niche. Candidates:
[candidates/ringbuffers-embedded.md](candidates/ringbuffers-embedded.md).

## 2026-11-05: C is included
C was added next to C++ and Rust. Many of the important embedded ring buffers
are written in C (lwrb, Zephyr, FreeRTOS, NuttX, TinyUSB), and the
correctness tools (sanitizers, GenMC, CBMC) support it well.

## 2026-11-05: English in the repo
Everything in the repos is written in English: documents, code, commits and
bug reports. Maintainers, contributors and AI agents are international.

## 2026-11-05: Organisation and first repo
GitHub organisation `verified-libs`, owned by the project owner's personal
account. The name covers more than ring buffers. `verified-libs/project` is
private until the principles are settled, then public.

## 2026-11-04: Benchmark machine is an existing laptop
lib-lab1 is an Acer Swift Edge 16 (Ryzen 7 7840U) on its own new NVMe disk,
instead of buying a used mini PC. Free, identical Zen 4 cores with SMT, and
the original Windows disk is kept untouched. Weak point: laptop cooling,
handled by locking the frequency and logging temperature per run.

## 2026-11-03: Principles
Honest, reproducible data; the user's own criteria decide what is best; the
winner is celebrated with no last place; improvement is rewarded over time;
bugs are facts about a version with private notice first; openness about
conflicts of interest, with a higher burden of proof for the owner's own
solutions but the same notice period. Details: [PROJECT.md](PROJECT.md).
