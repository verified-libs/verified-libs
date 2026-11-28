# Pilot: fixed-block pools (host only) (not published)

The pilot is kept in the working repository. This file stands at its path
because files of the tests name it; earlier commits of this repository hold
the pilot as it was.

It showed, on the host only, that a common interface for fixed-block pools
is workable: libraries fit it, the same adapters build for the host and for
a Cortex-M4, and a first host test can fail. It gave no result about any
library. Its `pool.h` and `libs.lock` are kept here, as the kind's files name
them. Its result is the pools kind: [`kinds/pools`](../../kinds/pools/README.md)
and the [pools method page](https://verified-libs.org/method-pools.html).
