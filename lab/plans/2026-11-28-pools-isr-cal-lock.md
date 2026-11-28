# Pools concurrency: C_Allocator with its interrupt-masking lock (2026-11-28) (not published)

This plan is kept in the working repository. This file stands at its path
because files of the tests name it; earlier commits of this repository hold
the plan as it was.

It planned a second C_Allocator row in the concurrency series, built with
the library's documented lock option `ALLOC_LOCK_CMSIS_RTOS2`, in a bundle
of its own with the three controls again. What changed:
[change log](https://verified-libs.org/method-pools.html#log-2026-11-28-cal-lock).
