# rp2350-excl-check

Is a C11 atomic read-modify-write (LDREX/STREX on the Cortex-M33) atomic
between the RP2350's two cores? Both cores add 1 to the same SRAM word
10^6 times each with an LDREX/ADD/STREX loop (what `__atomic_fetch_add` and
`compare_exchange` compile to); the result must be 2 000 000.

```
PROBE=2e8a:000c:<serial> bash run.sh      # on lib-lab1, Pico 2 + Debug Probe
```

Result (2026-11-12, Pico 2, 150 MHz, run twice):

| Memory attributes of SRAM | Counter | Lost |
|---|---|---|
| MPU off: ARMv8-M default map, Normal **Non-shareable** | 1 000 002-1 000 005 | ~10^6 |
| MPU region over SRAM, Normal, **Inner Shareable** | 2 000 000 | 0 |
| MPU off again | 1 000 002 | ~10^6 |

With Non-shareable memory each core's exclusives use only its local
monitor, so a STREX succeeds even when the other core wrote the word in
between: almost every increment of one core is overwritten. Marked
Shareable, exclusives go through the global monitor and the counter is
exact.

Consequence for this repository: the SMP builds (stress `smp`, `smp-block`,
MP `smp-mpsc`, `smp-spmc`) must mark SRAM Shareable on both cores before a
library's CAS can be atomic. `board_core1_launch` in
`../common/rp2350/board.h` does that (`board_sram_shareable`) since
2026-11-12. Libraries that use only atomic loads and stores (the SPSC rings)
were not affected; the first SMP MP runs of the CAS-based queues on
2026-11-12 were, and were rerun:
lockfree `mpmc::Queue`.
