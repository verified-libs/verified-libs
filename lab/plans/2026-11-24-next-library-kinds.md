# Plan: the next kind of library (survey and choice)

Written 2026-11-23, after version 2 of the ring buffer benchmark was
published. The ring buffers are finished for now. No new boards come in
the near future, so the next kind must be one the six boards we have can
measure.

This plan is the work of one unattended night. It ends with a
recommendation for the owner, not with a decision, and with nothing
public.

## What the night must give

In the morning the owner can choose the next kind of library from facts:
what each kind would cost, what we could prove and measure for it, which
libraries it holds, and how much of what we built for ring buffers
carries over.

## Rules for this night

The standing rules of the lab apply (the memory index names them). The
ones that matter most here:

- **Nothing outward.** No publication, no mail, no draft, no issue, no
  post, no contact with any maintainer.
- **No board is used.** No flash write, no run. Cross-compiling in the
  toolchain image is fine.
- **Work on a branch** `next-kind`, in its own worktree
  (`git worktree add ~/vl-wt-next -b next-kind origin/main`), never on
  `main`. Commit and push the branch after each step. No attribution
  lines in commits.
- **The method of version 2 is frozen.** No file under `firmware`, and
  none of `lab/boards.conf`, `lab/tools/source-commit.sh`,
  `lab/tools/boardpower.sh`, `repeat.sh`, is changed. New files go in
  new directories.
- **Everything under `candidates`, `reports` and `lab/plans` becomes
  public** with the next publication. Write it as a text a maintainer may
  read: facts with a source, no judgement of a library we have not
  tested. What a project says about itself is "it documents" or "it
  claims", as in `candidates/ringbuffers-embedded.md`.
- **A possible defect in someone's library** is written in `lab/drafts`
  only (that directory is never exported), with how it was seen, and is
  named in the morning status. It is not mentioned anywhere else, and
  the work on that library stops there.
- **Downloaded code is untrusted**: each clone in its own directory
  outside the repository (`~/vl-next/<name>`), nothing from it is run on
  the host outside the toolchain container, Python that reads it runs
  with `-I`.
- **The owner's own libraries** (pxq) are marked ⚠ wherever they appear,
  and get no step of their own.
- A question only the owner can answer goes under "Questions for the
  owner" at the end of this file; the work goes on with another step.

## Steps

1. **What carries over.** Read the benchmark of version 2
   (`lab/plans/2026-11-22-bench-image-per-library.md`,
   `firmware/nrf5340-rb-bench`), the stress tests, the contract check
   (`verify/contract`), the model check (`verify/genmc`), the records,
   the page data (`site/gen_libdata.py`, `site/data/libs-meta.json`),
   the comparison page and the MCP server. Write
   `reports/2026-11-24-what-carries-over.md`: for each part, whether it
   is general (one image per configuration, placements, bundles, the
   runner, the same-image rule, the export, the page build), tied to
   ring buffers by name only (schema names, directory names), or tied to
   them by design (the adapter interface, the scenarios, the judges of
   the stress tests, the contract, the columns of the comparison). For
   the last group: what a second kind would need instead. No code is
   changed in this step.

2. **Survey of four kinds.** One file per kind,
   `candidates/<kind>-embedded.md`, in the form of the survey sections of
   `candidates/ringbuffers-embedded.md`:

   - **A. Fixed-block pools used from interrupts**: object and memory
     pools that claim to be safe between an interrupt and the main loop,
     lock-free or with a lock.
   - **B. Heap allocators for small microcontrollers**: allocators with
     a bounded or documented worst case, and the ones the RTOSes and C
     libraries ship.
   - **C. Queues with more than one producer or consumer** on the
     boards (MPSC, MPMC): an extension of the two-interrupt stress test
     we have; the Pico 2 and the nRF5340 DK have two cores.
   - **D. A kind without concurrency: CRC calculation in software**
     (the owner's proposal). Bitwise, small table, byte table and
     slicing implementations, and code generators; the boards' CRC
     hardware only as a point of comparison. Correctness can be shown
     in full against the catalogued check values and a reference; the
     measurement is cycles per byte against bytes of flash, per core.
     The survey proposes the few variants to start with (for example
     CRC-32, CRC-16/CCITT-FALSE, CRC-8) and says what a table in flash
     costs on the boards with wait states or a cache.

   If the reading turns up a further kind that fits the project well
   (PROJECT.md: "the hard cases"), it is named in the comparison of
   step 3 with a few lines, not surveyed.

   The owner added at the start of the night (2026-11-24): if one or
   two further kinds look better than A to D, they are surveyed too, in
   the same form (as E, F), after A to D.

   Per kind:
   - Who has the hard problem, and what goes wrong in practice (public
     sources only: documentation, public issues, papers; with links).
   - **At least ten candidates** in C, C++ and Rust: repository,
     licence as GitHub reports it, last push, the version or commit one
     would pin, what the project documents about interrupt and thread
     safety, and where it is used (an RTOS, a vendor SDK, a framework).
     The most deployed implementations first; then small ones with a
     licence. No licence found: listed apart, as in the ring buffer
     file.
   - **What could be proven** and with which tool (model check, a
     contract on a host model, differential test against a reference,
     sanitizers, Miri, loom), and what the tool we have would need.
   - **What could be measured** on the six boards: the operations, what a
     scenario is, what the baseline is, whether the placement method of
     version 2 applies as it is, and a first guess of images and flash
     writes for a first series.
   - **What a filter and a column would be** on the comparison page and
     in the MCP data (principle 2: the user's criteria decide).
   - The owner's own libraries of that kind, if any are public (⚠), and
     libraries of maintainers we already wrote to.
   - Effort: what is new work, in the terms of step 1.

3. **Comparison and recommendation.**
   `reports/2026-11-24-next-kind.md`: the four kinds side by side in one
   table (fit with PROJECT.md's audience, candidates found, what can be
   proven, what can be measured, new work, flash writes of a first
   series, risks), then one recommended kind with its reasons and what
   speaks against it, and the runner-up. Unknowns are named as unknowns.

4. **Only if steps 1 to 3 are finished and checked: a pilot on the host
   for the recommended kind.** In a new directory `pilot/<kind>` on the
   branch:
   - a draft of the common adapter interface (one header) and of the
     scenarios, with the reasons;
   - three candidates pinned (a lock file like `libs.lock`), with
     adapters, built for the host and cross-compiled for one board in
     the toolchain image (no board);
   - one first correctness test on the host that can fail: it is shown
     to catch a deliberately broken adapter;
   - a note on what the board benchmark and the stress test would look
     like, and what is still open.
   The pilot proves that the interface is workable. It produces no
   result about any library, and its text says so.

Order: 1, then 2 (A to D, each committed on its own), then 3, then 4.
Step 2 is the large one; if the night is too short, A and B get their
full depth before C and D, and the report says what was not done.

## Checks before the morning

- `python3 lab/tools/public-export.py --check` is clean on the branch.
- `python3 site/build.py <dir>` and `python3 site/check_links.py <dir> .`
  pass (new reports become pages).
- Every link in the new files was fetched once this night; a fact
  without a source is marked as such.
- The memory gets `open-items-2026-11-24.md` and its line in the index.

## For the owner, in the morning

A short status in Danish: what was done per step, the recommendation in
three lines, what was not done, and the questions below. Then the
owner's choices:

- Which kind is next.
- Whether the branch `next-kind` goes into `main` (the survey files
  would then be public with the next publication).
- Whether the pilot is continued towards a first series on the boards.

## Questions for the owner

Added during the night of 2026-11-24.

1. **Which kind is next.** Recommended: A (fixed-block pools used from
   interrupts); runner-up D (CRC in software); or D first to generalise
   the machinery with the least risk, then A
   ([report](../../reports/2026-11-24-next-kind.md)).
   **Answered 2026-11-24: D first, then A in a narrower form** (the
   report's "Review and decision"; plan for D:
   [2026-11-24-crc-kind.md](2026-11-24-crc-kind.md)).
2. **The export check and a second kind.** `public-export.py` holds all
   of `firmware/` as the test sources of every ring-buffer record: the
   first file of a second kind there stops the export of all 265 version
   2 records (tested in a throw-away clone,
   [step-1 report](../../reports/2026-11-24-what-carries-over.md)).
   Proposed: test sources per kind (a change of the export check, so a
   change of method for the export). Yes, or another way?
   **Open.** Not needed while the second kind lives outside `firmware/`
   and has no records; the CRC night writes the proposal
   ([plan](2026-11-24-crc-kind.md), step 6).
3. **Maintainers we already wrote to.** The plan asked the surveys to
   name their libraries; the contact policy says no public list of who
   was told. That list is therefore in `lab/drafts` (not exported), not
   in the survey files. Is that right?
   **Answered 2026-11-24: yes, it stays in `lab/drafts`.**
4. **Licences.** The plan asked for the licence "as GitHub reports it";
   the GitHub API was not used this night (a call was refused), so the
   licences are from each repository's licence file. Check them through
   the API in the daytime, or keep the licence file as the source (as
   `site/data/libs-meta.json` does)?
   **Answered 2026-11-24: the licence file is the source.** GitHub's
   field is derived from that file and can misread an unusual one. Each
   licence is read again when a library is pinned for the lab.
5. **The branch.** `next-kind` into `main` makes the six survey files and
   the two reports public with the next publication.
   **Answered 2026-11-24: merged after a review** (the report's "Review
   and decision"; in addition every quoted sentence of the six survey
   files was looked up in the clones, two quotes were made exact, and
   twelve licences were compared with their licence files). Publishing
   stays a step of its own.
