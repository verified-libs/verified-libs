# Plan: the two-interrupt stress test in the bundle, and the areas not covered yet (2026-11-16) (not published)

This plan is kept in the working repository. This file stands at its path
because files of the tests name it; earlier commits of this repository hold
the plan as it was.

It put the two-interrupt (multi-producer) stress test into the same bundle as
the ISR stress test and listed the areas not covered yet. Its items were run
and reported: the DMA controller as a producer (item 2b,
[report](../../reports/2026-11-17-dma-producer.md)), the nRF5340's second core
(item 2a, [report](../../reports/2026-11-17-nrf5340-cross-core.md)) and the
check of every library in the bundle (step 5,
[report](../../reports/2026-11-17-mp-per-library-validation.md)).
