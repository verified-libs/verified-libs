# MP stress test: one library per reset, validated against the old way (2026-11-17)

Plan step 5 (`lab/plans/2026-11-16-mp-bundle-and-open-areas.md`). The
two-interrupt (MP) stress test now runs one library per reset over the
serial port, from a bundle that also holds the ISR stress test's images
(`run.sh PER_LIB=1 IMAGES=combined`; RP2350 SMP: `IMAGES=per_lib`). Here it
is compared with the old way (one image with every library, parameters over
the debug port), with the same seeds and parameters.

**Setup.** All six boards; MPSC and SPMC at timer prescaler 1 and 3,
300000 values per library, fixed seeds per case; RP2350 also SMP-MPSC and
SMP-SPMC (roles on two cores). 26 cases x 2 ways, 52 records:
`~/lab-runs/mp-validate-20261117/` (lib-lab1). Firmware: commit 01351d3
(the records written before ~06:35 UTC name a stale `86d20e7ca721+dirty`,
see `SOURCE_COMMIT_NOTE.txt` there; reruns name `f844fa4`..`693b73b`,
which change only run.sh and uart_host.py, not the firmware).

## Result

| | Same verdict | Different |
|---|---|---|
| Libraries (every one, every case) | 161 of 161 | 0 |
| Control caught | 23 of 26 | 3 (all SPMC, prescaler 3) |

(Plus 8 library-cases not available on the core both ways: DNedic lockfree
on Cortex-M0+, which lacks compare-and-swap.)

- **Libraries.** Every library has the same verdict both ways in every case.
  The only faults are the single-core designs (pxq MPSC/MPMC/SPMC, RIOT
  tsrb, wizard97) on two cores in SMP mode, found both ways, and not in
  their documented mode there (not counted). pxq reserve/commit starves in
  SMP-MPSC both ways (not counted). No library in its documented mode had
  an error either way.
- **Load.** Interrupts per value agree within 0.1 in every case (e.g.
  15.5/15.4, 6.8/6.8, 1.3/1.3): one library per reset loads the board as
  the one image did.
- **Control.** At prescaler 3 in SPMC the second interrupt rarely lands
  inside a pop, and the control is caught or not by chance either way: old
  missed it on G474, H723, RP2350; new on G0B1, G474. Where it was caught
  only lost/duplicated counts show it (no order errors). Campaigns already
  count a run without a caught control as invalid.
- **Control error counts** where caught: same order both ways (e.g. H723
  MPSC p1 4707/4569, SAM D20 5742/5617, G474 MPSC p3 143/926 at the low
  rate).

## Found on the way (fixed)

- `probe-rs reset` hung right after a download that wrote flash, on four
  boards started together: MP run.sh now tries three times (f844fa4).
- The old way could record a run with the build defaults as if with the
  parameters sent (a firmware started by hand ran past its wait): run.sh
  now compares the header with the parameters (f1ae43d, 1c2c357). The one
  record it affected was rerun.
- A selection written over the debug port is lost to the STM32H7 RAM ECC
  write buffer unless more words follow (b2252e0), and a hanging
  `probe-rs write` there gave a traceback (693b73b).

## Conclusion

The new way gives the same results as the old one. Records of the two ways
stay apart (new method: names `-perlib`, field `per_lib`). Switching the
MP campaigns to the new way is the owner's call (plan step 5).
