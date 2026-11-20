# Critical review after two weeks, and the way to version 1 (2026-11-18)

Asked for by the owner before the day's work. The owner agreed with the
review the same morning: the focus has drifted from the start goal, and
the next goal is to launch version 1, so that others can see the results
and improve on them. This file is the working list towards that.

## Findings

1. **Nothing is public.** 13 working days, 250 commits, six boards, 13
   test firmwares, 17 reports; no site, no public repository. The trial's
   success criteria in PROJECT.md (links, use or feedback from outside)
   cannot be met while that is so. The third criterion, a real defect
   found and reported, is met.

2. **The stress campaigns do not find defects.** None of the three
   findings in `verify/findings/` came from a campaign: they came from
   model checking, and from reading code with a bounded check to confirm.
   Night after night of campaigns confirms "0 errors" for libraries used
   as documented. Meanwhile the GenMC table in RESULTS.md still has ten
   libraries. The coverage work of 2026-11-17 was the right question (could
   the test have caught it?), and its answer points the same way:
   campaigns are a regression check, not the discovery tool.

3. **The method changes faster than the results.** Three changes of the
   kind "new method, do not pool with earlier records" in ten days
   (runtime parameters, one image per library, MP per library with
   coverage). RESULTS.md says "Updated 2026-11-14": its MP table is from
   2026-11-08 with pxq 1.4.0, the model-checking table says pxq "not yet"
   (the contract check passed it on 2026-11-16), and "Not covered yet"
   lists the contract model, the network core, DMA as producer, other C
   libraries and nrf_ringbuf, all done since.
   Every new test type also makes publication dearer: the public tree has
   no history, so everything shown must be re-run at the export commit.

4. **PROJECT.md promises things that do not exist.**

   | Promise | State | Proposal |
   |---|---|---|
   | MCP server ("minimum version"; AI agents are the stated purpose) | nothing | after v1 (owner 2026-11-18); v1 ships the same data as JSON files, which the server will read |
   | Results signed and timestamped | no | after v1; say so |
   | Correctness tests on GitHub Actions | no workflow | after v1; say so |
   | Heavy jobs in the greenest hours, a CO2 account per result | not done | see finding 7 |
   | Sanitizers, loom, TLA+, herd7 | toolchain has some; none in results | list only what a result uses |
   | Licence "proposed Apache 2.0, not decided" | README and LICENSE say MIT | align PROJECT.md with the licence files |
   | Tasks in GitHub Issues | not used | drop, or start using them at v1 |

5. **The owner's library weighs more than a disclosure text covers.**
   Each point can be defended; together they read as a tilt.
   - The multi-producer test has pxq in 4 of its 8 rows.
   - Much development followed pxq: the re-runs for 1.5.0, reserve/commit
     as a new test row, the contract check (asked for as "GenMC is missing
     for pxq").
   - The owner hears what the lab finds about pxq at once; other
     maintainers hear at publication. First correction: the bbqueue note
     goes out now (`lab/drafts/2026-11-18-bbqueue-cache-note.md`).
   - Principle 6 was eased on 2026-11-16/17 (an outside repetition is no
     longer a condition for showing pxq).
   Proposal: an outside reader for the pxq adapters at launch, as already
   planned. *Corrected 2026-11-18:* this list first proposed one outside
   repetition of pxq before v1. That contradicts the owner's decision of
   2026-11-17: outside repetition is a goal for every library, not a step
   for pxq alone. The owner's view: pxq should in time have more outside
   repetitions than the others before it is seen as equally certain
   (principle 6); that needs an outside setup that people use, which v1
   is the start of, so it is not a step towards v1.

6. **Steering lives with the assistant, not in the repository.**
   DECISIONS.md has 15 entries; several times that many owner decisions
   (comparison page neutrality, which memcpy is shown, campaign policy,
   wear budget, held-back libraries) are only in the assistant's notes on
   lib-lab1. PROJECT.md says steering lives in the repository.

7. **Green operation: the promise is larger than the thing.** lib-lab1's
   CPU package drew 5.1 W with campaigns running on all six boards
   (RAPL, 10 s, 2026-11-18 07:00); the whole laptop with boards is not
   measured at the wall, likely 15-25 W. At 20 W that is about 0.5 kWh a
   day. Moving jobs to green hours could save a fraction of very little,
   and would cost schedule freedom. The scheduler and the per-result CO2
   account were never built. Not measured at all: the energy of the AI
   model that does the development, likely the larger share.
   Proposal: PROJECT.md states the measured draw and drops the green-hours
   scheduling and the per-result CO2 account as promises (owner's wording).

## Version 1

**In** (what exists and holds): speed on six boards (SPSC and
multi-producer), ISR stress test, multi-producer stress test with
coverage, contract check, GenMC, code size and placement, the comparison
page, method, reproduce and repeat pages, the published finding, the
reports as they are (DMA, cross-core, compilers and C libraries as "first
results" on the boards they ran on).

**Frozen until v1:** no new test types, boards, modes or toolchains. Not
before v1: DMA on the G0B1 and Pico 2, the 128 MHz cross-core run, the
aim window per library.

**Campaigns until v1:** the publication re-run, and short checks
(`check.sh`) after code changes. No more long campaigns for their own sake.

**Steps**

| # | Step | Who |
|---|---|---|
| 1 | Evaluate the night campaigns of 2026-11-17/18 (the last long ones before v1) | lab |
| 2 | RESULTS.md and the site brought up to date with what is done | lab |
| 3 | Owner decisions moved from the assistant's notes into DECISIONS.md | lab |
| 4 | PROJECT.md aligned with reality (finding 4 and 7): a diff for the owner | lab drafts, owner approves |
| 5 | Conflict-of-interest text and the audit of the comparison page (`lab/drafts/2026-11-17-pxq-conflict-of-interest.md`) | lab drafts, owner approves |
| 6 | `repeat.sh` and the Repeats page checked at the export commit, so outside repetitions of any library can start at launch (replaces "one outside repetition of pxq", see finding 5) | lab |
| 7 | Method freeze: the commit everything is re-run at. Owner 2026-11-19: freeze as soon as steps 4 and 5 are approved and applied, then start step 8 without asking again | lab |
| 8 | Publication re-run at that commit (benchmarks, reference stress, MP), records collected, site built, export dry run with the embargo check | lab |
| 9 | Notes to maintainers whose results look negative, a week before (`outreach/`) | owner sends |
| 10 | Publish site and repository; notes to the other maintainers | owner |

State 2026-11-19, evening: steps 1-5 done (4 and 5 approved by the owner
and applied the same day; DECISIONS 2026-11-19); step 6 pre-checked
(`repeat.sh --check` passes on all six boards). Step 7: the method is
frozen at the commit tagged `v1-method-freeze-2`. (`v1-method-freeze`, one
commit earlier, had a code-size script that failed on every board: it read
the benchmark's library table by position and took the Nordic set for the
SPSC set. The re-run started at that commit was stopped after four minutes;
its records are not used. The fix changes the script only, no firmware.)
Step 8 started at the second tag the same evening: `lab/tools/publication-rerun.sh 5 5` on all six
boards (code size, the three benchmark sets at eight placement shifts,
5 h ISR stress with -O2 as the reference campaign of 2026-11-15, 5 h
multi-producer stress with every slow-rate run aimed). Until the export,
no file under `firmware/` and no campaign script in `lab/tools/` changes.

State 2026-11-20, morning: the re-run finished on all six boards (the last
at 06:44 UTC), no step failed. ISR test 108 runs, all valid; two-interrupt
test 324 runs, 322 valid (on the nRF5340 random interrupts missed the
control twice); no errors in any real library. Report:
`reports/2026-11-20-publication-rerun.md`. Records collected
(`records/`), site data regenerated, RESULTS.md and the method page
brought up to the re-run, site built. `public-export.py`,
`verify-build.sh` and `repeat.sh` accept a record whose commit differs
from the exported one when the test sources are the same (`SAME_SOURCES`;
the records are committed after the commit they were made at, so the two
can never be equal). What the five hours did not reach (zero-copy ISR
runs on the nRF5340, the G0B1 and the SAM D20) is in the report and under
"Not covered yet" in RESULTS.md.

The freeze of `firmware/` and the campaign scripts stays until the public
export: a change there would break `SAME_SOURCES` for every record of the
night.

Left: steps 9 and 10, both the owner's (`outreach/maintainers.md` has the
state: nobody with a negative-looking result has a private channel, so the
early notes of step 9 have no addressee as planned).

The public repository will be `verified-libs/verified-libs` (DECISIONS
2026-11-19).

Open with the owner only: the contributor agreement (lawyer, who the Holder is; v1
can launch with it marked "draft, not in use"), and the association.

## After version 1

- MCP server over the published JSON (owner 2026-11-18).
- Model checking and the contract check for more libraries: where the
  findings came from.
- Signed records, CI for the host-side checks.
- Outside repetitions shown next to ours.
- The frozen items above; more boards.
