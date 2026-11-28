# Pools: the concurrency series (interrupts) (2026-11-27) (not published)

This plan is kept in the working repository. This file stands at its path
because files of the tests name it; earlier commits of this repository hold
the plan as it was.

It planned the series that tests the pools under interrupts: an interrupt
that calls alloc or free at every cycle of main's call, on the boards and on
the host. How it works: [method page](https://verified-libs.org/method-pools.html#use-from-interrupts);
what changed: [change log](https://verified-libs.org/method-pools.html#log-2026-11-27-isr).
