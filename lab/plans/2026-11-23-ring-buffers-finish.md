# Finishing the ring buffer tests

2026-11-23. What is left before the ring buffer part can be called done
and the registry can take up a second kind of library. The owner asked
for a plan that can be worked through without them; what needs their
word is collected at the end and nothing of it is done before.

Done means: a number on the page can stand without us. A reader can see
which code it came from and build that code again, and one library can
be measured again without touching the rest.

All work is on the branch `bench-per-lib`. Nothing is published, no
maintainer is written to, and no long campaign is started by this plan.

## Steps

1. **The series with the far call, finished.** Records of the six boards
   replace the records of the near series; every record is rebuilt and
   compared (`oneverify.sh`); the export check is clean. The report gets
   a table per board of what a call costs (near series against far
   series) and a check that the numbers on the Pico 2 did not move.
2. **The Pico 2 is written in parts.** A flash write that lasts longer
   than about a minute loses the board (the hub port is power-cycled;
   see the report). A tool writes a bundle for it in parts of about 1 MB
   before the runner starts (`lab/tools/pico2-write.py`; the runner is a
   source of the records and stays as it is); the flash holds the same
   bytes afterwards. Removed again
   when the board has a power-only cable.
3. **Page data and pages from version 2.** `gen_libdata` and the page
   build read the records of version 2; the pages show version 2 only
   (DECISIONS 2026-11-23). Texts: code the compiler inlines pays no
   call; what a call costs per board; a note per board on what changed
   from version 1 and why, with links to the archived records. The MCP
   data and its README line for the `benchmark` argument.
4. **The export check enforces the same-image rule for version 2**: a
   record whose image the tree no longer builds, or whose host-side
   sources changed without a recorded fix, stops the export.
5. **Run only what changed.** A ledger per image; a tool that names the
   configurations whose image differs from their record, and the
   bundles to write for them; `repeat.sh` for version 2. Tried without a
   board on a made-up change of one library.
6. **The known oddities, explained or stated.** The FreeRTOS stream
   buffer on the Cortex-M7: read from the images first; a board
   experiment only if reading cannot settle it, at most two flash
   writes. `memcpy` near for inlined code and far for code behind the
   gap: stated on the page (its placement stays "later").
7. **Repetition from outside, tried.** A dry run of the export into an
   empty directory; from that tree alone, following only the published
   instructions: build every image, compare with the records, and run
   one bundle on a board (the bundle is on the board already, so no
   flash write). Whatever the instructions lack is added.
8. **A dry run of the whole publication** for the owner to look at: the
   exported tree and the built pages in a directory, with a list of
   what differs from what is public today.

Order: 1 and 2 first (the run is ending), then 3 to 5, which the later
steps use, then 6 to 8. Each step is committed and pushed on its own.

Flash writes expected: none beyond the series that is running, except
step 6 (at most two).

## What steps 7 and 8 found (2026-11-23)

Step 7, from an exported tree in an empty directory, with nothing but
the toolchain image and the pages' instructions:

- All 265 records rebuilt: every image the same bytes at the same
  addresses, on all six boards (about two minutes per board).
- The nRF5340 DK's images cannot be built without Nordic's nRF5 SDK
  (which we may not redistribute). The tool said so, the Reproduce page
  did not: added.
- `repeat.sh` failed its first test in a fresh tree (a progress message
  ended up in a path) and passed from the second run on: fixed. Its
  quick level picked the board's own parts next to the libraries: it
  takes library configurations only now.
- `lab/tools/compare-records.py` is run as a command on the Reproduce
  page and was not executable: fixed.
- The quick level of `repeat.sh`, with the bundle each board held
  already (no flash write), on five boards: every image the same,
  every mean within 1 % of ours (160 to 768 means per board). The
  step-by-step commands of the Reproduce page on the sixth, the
  NUCLEO-G474RE: the same (384 means).
- Not tried: a machine other than ours, a second copy of a board, the
  full level, the stress part of `repeat.sh` (unchanged since version 1).

Step 8: the exported tree and the built pages were made in a directory
on the lab machine, with the checks of a publication (links, embargo
words, records against the tree) and a list of every file and page that
differs from what is public. Nothing was pushed.

## Not in this plan

More boards, more scenarios, the nRF5340's network core, experiments
with the place of `memcpy`, one Rust crate per library (unless step 5
needs it), notices for libraries that are merely in the comparison.

## For the owner, when the steps are done

- Go for the publication of version 2 (step 8 shows what would go out).
- The branch into `main`.
- A tag that freezes the method of version 2.
- Anything steps 6 and 7 turn up that changes a number or a text on a
  page that is public.
