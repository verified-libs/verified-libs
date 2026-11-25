# Decisions

Short log of what was decided and why. Newest first.

## 2026-11-25: The CRC kind's results page shows ranges over the placements, cache on and off
Decided by the owner, on the proposal for the page
(`lab/plans/2026-11-25-crc-page-proposal.md`, with the reviewer's
recommendation), after the checks of the first series
([report, "The numbers, checked"](reports/2026-11-25-crc-first-series.md#the-numbers-checked-step-3)).
- **Every number is the range over the eight placements** (min–max, first
  pass); no placement is picked. With the cache off, placement 0 is the
  lowest or the highest of the eight in 75 of 120 rows
  (`site/crc_tables.py --edges --cache off`), and the series gives no reason
  to prefer one placement (check 7).
- **Cache off is a second table per board and CRC**, below the cache-on
  table, with ranges. It is where the placements spread most (check 7: up
  to 23 % on the NUCLEO-G474RE, 447 % on the NUCLEO-H723ZG) and where a
  table's memory matters most (check 6).
- **The NUCLEO-H723ZG is shown as measured**, with a sentence on its 7 wait
  states (the power-on default, which the 64 MHz build keeps; RM0468's
  Table 16 allows 0 or 1 at 64 MHz) directly above its cache-off tables
  (check 5). Changing them changes `firmware/common`, which version 2's
  records are held against. Running the H723 with the wait states a user
  would set is an item for the next version of the method.
- **The table copied to RAM is not measured before the first
  publication**; the method page says so under "What is not measured".
  Check 6 shows where it would matter.
- **The median beside the mean** is an item for the next version of the
  method. In the page's figures the first call adds at most 2.45 % to a
  mean (check 1); the calls themselves vary more in some scenarios.
- The 1-byte figures and a factor of the baseline are not shown (the
  proposal, first section).

## 2026-11-24: The CRC kind's records stand as long as their images do; its first publication is static pages
Decided by the owner, on the plan for the CRC kind after its first series
(`lab/plans/2026-11-24-crc-from-series-to-publication.md`, step 5 and
"Later").
- **The same-image rule (2026-11-22, below) holds for the CRC kind's
  records** (`records/crc`) as it does for version 2's: a record of a
  commit with other CRC test sources is exported if the ledger
  (`records/rebuilt.json`, made by `lab/tools/image-ledger.py` from the
  test sources of HEAD) says the tree builds its eight images byte for
  byte, at the same addresses, with the same fixed part, boot stub,
  toolchain image and layout. A change on the host side (the runner, the
  record writer, the version 2 programs the kind imports, the board
  table, the check of a record) is taken only as a recorded host fix
  (2026-11-23, below) of the runner, the record writer or the check of a
  record; any other host-side change means the series is measured again.
  The tools that repeat or compare runs without making or checking a
  record (`repeat.sh`, `crccompare.py`) are not test sources. Which files are on which side is listed in
  `lab/tools/public-export.py`.
- **The kind's first publication is static pages.** The comparison page
  and the data for the MCP server come later.

## 2026-11-23: Version 2 of the benchmark is published; its method is frozen
Decided by the owner, after a dry run of the publication
(`lab/plans/2026-11-23-ring-buffers-finish.md`, steps 7 and 8).
- The work of the branch `bench-per-lib` is on `main`, and the pages and
  the data show version 2.
- The method of version 2 is frozen at the tag `v2-method-freeze` (in the
  project's working repository; the records name the commit their images
  were built from). A record stands as long as the tree builds its
  images (2026-11-22, below); a change of the method is a new decision.
- Why the numbers of the three ST boards depend on the place of the code
  modulo 8 bytes stays "a likely reading" in the report
  (`reports/2026-11-23-bench-v2-placement-period.md`): good enough, no
  experiment for it.

## 2026-11-23: The pages show version 2 only; version 1 is archived
Decided by the owner. It replaces "version 1's numbers stay on the page
next to version 2's for a time" (2026-11-22, below).
- **When version 2 is published, the pages and the comparison show its
  numbers only.** Version 1 is not shown beside it.
- **Version 1 stays findable**: its records, its tag and the report of the
  differences are linked from a short note per board that says what
  changed from version 1 and why. The MCP server gives version 1 on
  request (`benchmark` argument).
- Why: the two series differed in two places, and in both the number of
  version 1 came from where the code happened to lie in a shared image
  and not from the library
  ([report](reports/2026-11-23-bench-v2-first-run.md)): the cost of a
  call on the Cortex-M7, and one configuration's block number on the
  Pico 2. Two tables would ask the reader to choose between a number
  and one that is known to carry the layout. The old numbers must still
  be there for whoever has seen them, and so that the change can be
  checked; one of the two concerns the owner's own library.

## 2026-11-23: Every library is measured with a far call
Decided by the owner after the difference between version 1 and version 2
on the Cortex-M7 was explained
([report](reports/2026-11-23-bench-v2-first-run.md)): a call to code about
4 KB or more away costs 6 to 10 cycles more there than a call to code
nearby, and with one small image per configuration every library lay next
to its caller.
- **In every image the library lies far from the adapter that calls it**:
  at least 6144 bytes (half as much again as the 4096 at which the full
  cost was measured), plus the placement of 0 to 28 bytes. So every
  library is measured under the same condition, and it is the condition
  of an application, where a library lies where the linker puts it. Near
  and far are not both measured: the second number says little more than
  that a call costs something.
- **The adapter stays next to the harness.** Code that the compiler puts
  into the adapter itself (a library of headers, a Rust generic) has no
  call and therefore pays none, as in an application; a function such a
  library keeps out of line lies behind the gap like any other library
  code. The pages say this, because it favours libraries of headers, the
  owner's among them.
- **What a far call costs on each board is stated once**, as a note, from
  the two series (the one with the library next to its adapter, 263
  records at `f2348f3a0c37`, was never published and is replaced; it stays
  in the repository's history).
- Not changed: the C library's memory functions lie in the fixed part,
  next to the adapter and so far from a library behind the gap. Where
  they should lie is still open (decision of 2026-11-22, "later").
- Cost: a new series, 48 flash writes on the six boards (26 before), as
  the images are 6 KB larger.

## 2026-11-23: A fix of the runner does not cost a new series
Decided by the owner after the first full run of benchmark version 2, in
which the runner stopped at a log line
([report](reports/2026-11-23-bench-v2-first-run.md)).
- **The test sources have two kinds of host-side files.** Those that an
  image is built from or by (the firmware sources, the pins, the build
  scripts, the slot table) and the decoder of the result words stay bound
  to the records as before: a change means the tree must still build the
  same image, or the series is measured again. Three files build nothing:
  the runner (`run-one.py`), the tool that collects run files into records
  (`onerecords.py`) and the one that rebuilds and compares
  (`oneverify.sh`). A fix of one of them is recorded in
  `records/host-fixes.json` (the file before and after, what changed, why
  no number can change, and the control run), and the records made before
  it stand.
- **A change of how numbers are read from the board or worked out is not
  such a fix**, in whichever file it is: the series is measured again.
- **After a fix of the runner one image per board is run again**, from the
  bundle that is on the board (no flash write), and must give the record's
  numbers.
- Why: every record is already tied to its image by the rebuild check
  (the bytes in flash), which no host-side fix can pass by; a series costs
  two hours and 32 flash writes, and a rule that makes small faults too
  dear to mend leaves them in.

## 2026-11-22: The benchmark of version 2: one image per configuration
Decided by the owner on
[lab/plans/2026-11-22-bench-image-per-library.md](lab/plans/2026-11-22-bench-image-per-library.md),
after the pilots on the nRF5340 and the SAM D20. It takes effect when the
new series is measured and published; until then version 1 stands.
- **The bytes in flash decide whether an image is the same.** The checksum
  of the ELF file is recorded next to it, and the sources are arranged so
  that both stay the same. Why: the bytes are what the chip runs; the ELF
  file also changes with debug information that touches no instruction
  (a line added elsewhere in a shared source file).
- **Slots of 4 KB units** (8 KB for most images, 16 KB for the two
  largest). Why: every library can double before it must move, and a full
  benchmark is 31 flash writes on the six boards against 145.
- **Version 1's numbers stay on the page next to version 2's** for a time
  (replaced 2026-11-23: the pages show version 2 only, see above).
  Why: on a chip with a cache the numbers of the new series are lower, and
  a reader should see both and the reason.
- **The cache-on number is the library in an image of its own**, with no
  other code on its cache lines, and the page says so. Why: it is the same
  kind of number for every library and no neighbour moves it; what a
  crowded cache costs depends on the application's layout. Placements that
  put other code on the same cache lines on purpose may be added later.

Added 2026-11-23, after the tools were made and tried on the six boards:
- **Version 1 is an archived series.** Its records stay as they are, are
  labelled "version 1", and are checked against their own commit, not
  against the tree at hand. Why: the tree of version 2 builds version 1's
  images byte for byte, but two host-side files that version 1 uses had to
  change for version 2; running version 1 again would cost 145 flash
  writes for a series that is being replaced.
- **`memcpy` stays at one fixed place** in every image. Whether its place
  becomes an axis of its own is looked at later.
- **A published run has two passes**, the second in reverse order.
- **The first full run of version 2 may be made now.** Nothing of it is
  published before the page data, the export check and the other tools
  are in place.

## 2026-11-22: A record stands as long as its image does
Decided by the owner on the proposal in
[lab/plans/2026-11-22-same-image-rule.md](lab/plans/2026-11-22-same-image-rule.md),
after the full re-run for lwrb v3.4.0.
- **A record may be shown if the published tree builds, byte for byte, the
  image it was measured from, and runs and judges it the same way.** This
  replaces "every record is made at the published sources" (2026-11-16,
  2026-11-19). Why: the reader's check is the same (the tree they have
  builds what was measured, by checksum), and the re-run showed what the
  old rule cost for nothing: one new library version made every record of
  every library unshowable, although most images had not changed and the
  unchanged ones gave the same numbers to the last digit.
- **What is measured again follows from the images.** A changed library:
  the benchmark set its image belongs to, its code size, its own stress
  images. A changed test firmware, run script or judge: everything that
  test produces. Rows of the comparison then carry the date and commit of
  their own records.
- **A changed library is stressed alone over the rotation entries the last
  full campaign reached on that board.** Why: its row then rests on the
  same runs as its neighbours', not on more.
- **Everything runs again at every method version, and otherwise twice a
  year.** Why: a checksum does not see the boards, the probes or the room.
- **One benchmark image per library is on the list for the version after
  1.** Why: the C and C++ single-producer libraries share one image, so a
  change in one still moves the others' numbers and costs eight writes per
  board. It changes the benchmark firmware, so it comes with a full re-run.
- **New library versions are tested as they come, for now.** Collecting
  them into one run a month may come later.
- **The ISR campaign script will take a list of libraries, and the change
  is made together with the first library update** (decided the same
  evening). Why: `overnight.sh` runs all libraries or none, so one library
  cannot be stressed alone today. Changing a run script means the ISR
  stress records are made once more by a full campaign; the first update
  needs that campaign anyway, so the change costs no extra flash writes.
  The other way, a second script that walks the same rotation, would leave
  the rotation in two places.
- **The tools follow in steps**, and until they are complete nothing is
  shown that the earlier, stricter rule would not allow: every record
  shown today meets both. The plan for the tools:
  [lab/plans/2026-11-22-same-image-tools.md](lab/plans/2026-11-22-same-image-tools.md).

## 2026-11-22: A new version of a library (lwrb v3.4.0)
- **lwrb is pinned at v3.4.0 and every test ran again at one commit**
  (`a7a206190337`; [report](reports/2026-11-22-lwrb-v3.4.0-rerun.md)).
  Why everything: the pin and the adapter are test sources, and a record
  must name sources the reader has (2026-11-16); with the tools as they
  are, that means new records for every library.
- **lwrb's single bytes are measured through `lwrb_write_byte` and
  `lwrb_read_byte`**, which v3.4.0 adds. Why: each library is measured
  through the call it offers for the job, as every other library with a
  call for one element is. Up to v3.3.0 lwrb had none, and one byte went
  through `lwrb_write` / `lwrb_read` with a length of 1. Blocks and
  zero-copy are measured as before. The numbers of v3.3.0 stay in the
  report of 2026-11-20 and in the report above, not on the comparison
  page: the page shows one version per library.
- **The model check covers both ways** (the byte functions and the block
  calls with a length of 1), each with its own controls
  ([verify/genmc](verify/genmc/README.md)).

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
