# GenMC model checks

Model checking of ring buffers as SPSC queues between two threads, with
GenMC (pinned in the toolchain image) under the RC11 memory model. GenMC
explores every execution the C11 memory model allows, so a missing
acquire/release or a data race on the buffer is found, not just made
likely.

## Run
On lib-lab1:
```sh
bash run.sh
```
Uses the library commits pinned in
[`../../firmware/nrf5340-rb-bench/libs.lock`](../../firmware/nrf5340-rb-bench/libs.lock).

## lwrb SPSC ([`lwrb_spsc.c`](lwrb_spsc.c))
Producer thread writes bytes 1..5 with `lwrb_write` (1 byte per call);
consumer thread reads 5 bytes with `lwrb_read` and asserts order and value.
Buffer of 4 bytes (3 usable), so the indices wrap and the buffer runs full
and empty. Each call may fail once and is retried once; executions needing
more retries are pruned (bounds the search, the full/empty states are still
reached).

lwrb's `memcpy` is replaced by a byte loop in the test only: GenMC cannot
track `memcpy` with a run-time length, which would hide the buffer accesses
from the race check.

### Negative controls
A pass only means something if the check can fail. `run.sh` therefore also
runs deliberately broken variants that must fail; if one passes, the run
fails.

| Run (2026-11-06) | Expected | Result | Executions |
|---|---|---|---|
| lwrb v3.3.0, default (C11 atomics) | pass | **pass** | 7118 (3.4 s) |
| control: `-DLWRB_DISABLE_ATOMIC` | fail | fail: non-atomic race | – |
| control: every `memory_order_release` → `relaxed` | fail | fail: non-atomic race | – |

Reading: lwrb v3.3.0 in its default configuration is a correct SPSC queue
under the C11 memory model, for this test's bounds. With
`LWRB_DISABLE_ATOMIC` it is not, under the C11 model; whether that matters
on a single-core MCU (ISR ↔ main) is a separate question, see below.

### lwrb v3.4.0 (2026-11-22)
The pin moved to v3.4.0, which adds functions for one byte,
`lwrb_write_byte` and `lwrb_read_byte`. The same test runs twice: with
`lwrb_write` / `lwrb_read` and a length of 1 as before, and with the byte
functions (`-DBYTE_API`). The byte functions have their own controls and
two probes: an assertion that the first write (first read) never fails,
which must itself fail, so the full (empty) buffer is reached.

| Run (2026-11-22), lwrb v3.4.0 | Expected | Result | Executions |
|---|---|---|---|
| `lwrb_write` / `lwrb_read`, 1 byte per call | pass | **pass** | 7118 |
| control: `-DLWRB_DISABLE_ATOMIC` | fail | fail: non-atomic race | – |
| control: every `memory_order_release` → `relaxed` | fail | fail: non-atomic race | – |
| `lwrb_write_byte` / `lwrb_read_byte` | pass | **pass** | 7118 |
| control: byte functions, `-DLWRB_DISABLE_ATOMIC` | fail | fail: non-atomic race | – |
| control: byte functions, release → `relaxed` | fail | fail: non-atomic race | – |
| control: byte functions, acquire → `relaxed` | fail | fail: non-atomic race | – |
| probe: byte functions, buffer full reached | fail | fail: assertion | – |
| probe: byte functions, buffer empty reached | fail | fail: assertion | – |

The block and zero-copy checks further down give the same results with
v3.4.0 as with v3.3.0 (730 and 8988 executions; mutants fail, probes
reached).

One change to the model: from v3.4.0 `lwrb_init` clears its whole structure
with `memset`, and GenMC stops at a `memset` over atomic objects ("Invalid
call to memset()"). The structure in the test is a static object, zero from
the start, and `lwrb_init` runs before the threads exist, so the test
replaces that `memset` with a function that writes nothing and asserts that
zero is the value asked for.

`run.sh` exited 0 with all 136 checks as expected.

## diffstorm/cb SPSC ([`diffstorm_spsc.c`](diffstorm_spsc.c))
Same shape as the lwrb check (4 items, 4 slots). `CB_MEMORY_BARRIER()` is
mapped to `atomic_thread_fence(memory_order_seq_cst)` (GenMC cannot run
inline assembly). Results 2026-11-06, all as expected:

| Variant | Expected | Result |
|---|---|---|
| diffstorm `547d0812` as is | fail | fail: mixed-size access (32-bit load of a 1-byte flag) |
| overwrite-flag load made 1-byte (library's own `CB_ATOMIC_LOAD_OW`) | fail | fail: non-atomic race on the buffer |
| + one barrier after the consumer's index loads | pass | pass, 686 executions |

Two defects, documented in
[`../findings/diffstorm-cb-overwrite-padding`](../findings/diffstorm-cb-overwrite-padding/README.md).
**Reported to the maintainer on 2026-11-08; fixed upstream the same day
(`91ae20b`); the maintainer agreed to earlier publication on 2026-11-09.**

## Atomics-based SPSC libraries ([`spsc_c.c`](spsc_c.c), [`spsc_cxx.cpp`](spsc_cxx.cpp))
The eight other libraries of the benchmark that use atomics (C11/C++11, or
GCC `__atomic` builtins in micoring's SPSC mode), in
the same shape as the lwrb check: producer pushes bytes 1..5 one at a
time, consumer pops 5 and asserts order and value, capacity 4, one retry
per call. The library is chosen with `-DLIB_<NAME>`; the C++ libraries are
checked as C++ (GenMC compiles C++ with clang).

Each library has two negative controls made from copies of its source:
every `memory_order_release` / `__ATOMIC_RELEASE` becomes relaxed (the
producer publishes without release), or every acquire becomes relaxed (the
consumer reads the index without acquire). Both must fail. For jnk0le the
library's own `fake_tso = true` switch (relaxed index accesses, documented
for single-core use) is an extra control and must fail too.

| Library (pinned) | Result | Executions | release → relaxed | acquire → relaxed |
|---|---|---|---|---|
| jnk0le Ringbuffer `9efa07ff` | **pass** | 6132 | fail: race | fail: race |
| rigtorp SPSCQueue `59a6a938` | **pass** | 5096 | fail: read of an unwritten slot | fail: read of an unwritten slot |
| ETL queue_spsc_atomic 20.49.0 | **pass** | 6132 | fail: race | fail: race |
| polycratia spscring `9d2445a5` | **pass** | 6132 | fail: race | fail: race |
| rt-spsc `5454de55` | **pass** | 6132 | fail: race | fail: race |
| kostyk348 lf_spsc `38649b8f` | **pass** | 6132 | fail: race | fail: race |
| QuantumLeaps LFRB `0d6354a1` | **pass** | 7118 | fail: race | fail: race |
| micoring `a6f91ee2`, SPSC mode | **pass** | 6132 | fail: race | fail: race |

jnk0le with `fake_tso = true`: fail (race), as expected for a mode meant
for one core. Results 2026-11-07, `run.sh` exit 0 (every outcome as
expected).

Reading: within these bounds, all eight are correct SPSC queues under the
C11 memory model, i.e. also between two cores, and each check is shown to
be able to fail on exactly the ordering it relies on.

Test-only adaptations, none of which changes the code under test:
- kostyk and micoring copy items with `memcpy`/`memmove` and a run-time
  size; replaced by byte loops as for lwrb.
- polycratia, rigtorp and ETL: the queue object is created with placement
  new in static storage (as in the firmware adapters). A static object with
  a destructor needs `__dso_handle`, and rigtorp's over-aligned object needs
  the aligned `operator new`; GenMC provides neither.
- [`shims/`](shims/) comes first on the C++ include path. GenMC replaces
  `<pthread.h>` and `<stdio.h>` with minimal versions of its own, which
  libstdc++ does not expect: `bits/gthr-default.h` selects libstdc++'s
  single-threaded internal lock layer (the queues use `std::atomic` only),
  `bits/pthreadtypes.h` gives glibc the same pthread types as GenMC, and
  `cstdio` declares the stdio names libstdc++ re-exports (never called).
- ETL: `<type_traits>` is included before ETL, which derives its traits
  from the STL but expects that header to be included already.

## Block and zero-copy APIs ([`block_c.c`](block_c.c), [`block_cxx.cpp`](block_cxx.cpp))
The single-byte checks above leave out the paths where ordering bugs hide most
easily: the length check, the split at the wrap, and, for zero-copy, data
written or read in place, with the index updated later. Here the producer sends the bytes
1..N in calls of up to 3 bytes. The consumer receives in calls of up to 2
bytes and asserts order and value. A call may move fewer bytes than asked (full, empty, or the
linear block ends at the wrap), and the rest goes in a later call. Capacity is 4. Each thread
makes at most a bounded number of calls, and executions that need more are pruned.

Bounds: N = 7 bytes and 6 calls per thread for lwrb, jnk0le and polycratia. For the others, N = 5 and 4 calls,
or N + 1 calls for single-element consumers: micoring `push_many` takes over 10 minutes at N = 7, because each element is
a separate atomic push.

Every variant has the two mutants of the single-byte checks: release becomes relaxed, or
acquire becomes relaxed. Both must fail. For the multi-byte APIs, four **reachability probes**
must also fail: buffer full, partial write, buffer empty and partial read
([`block_probe.h`](block_probe.h)). For lwrb, a fifth probe checks that one call crossed
the wrap (`lwrb_write`) or that the linear block ended at the wrap (zero-copy). A
probe failing shows GenMC explored that state, so the pass covers it.
`run.sh` also rejects any pass with 0 complete executions: if the bounds are too tight,
every execution is pruned and nothing is checked.

| API (pinned commit as above) | Result | Executions | release → relaxed | acquire → relaxed | Probes reached |
|---|---|---|---|---|---|
| lwrb `lwrb_write`/`lwrb_read`, several bytes per call | **pass** | 730 | fail: race | fail: race | full, partial w, empty, partial r, wrap split |
| lwrb zero-copy: `get_linear_block_*` + in-place copy + `lwrb_advance`/`lwrb_skip` | **pass** | 8988 | fail: race | fail: race | full, partial w, empty, partial r, block ends at wrap |
| jnk0le `writeBuff`/`readBuff` | **pass** | 11547 | fail: race | fail: race | full, partial w, empty, partial r |
| jnk0le `peek()` (read in place) + `remove()` | **pass** | 16063 | fail: race | fail: race | – |
| polycratia `try_push_n`/`try_pop_n` | **pass** | 1124 | fail: race | fail: race | full, partial w, empty, partial r |
| micoring `mring_push_many`/`mring_pop_many` (SPSC mode) | **pass** | 5133 | fail: race | fail: race | full, partial w, empty, partial r |
| micoring `mring_peek` + `mring_pop(NULL)` | **pass** | 10820 | fail: race | fail: race | – |
| ETL `front(value)` + `pop()` | **pass** | 10820 | fail: race | fail: race | – |
| ETL `empty()` + `front()` reference + `pop()` | **pass** | 10820 | fail: race | fail: race | – |

These ran on 2026-11-08, and `run.sh` exited 0 with all 84 checks as expected (92 with the MPMC section below). rigtorp's zero-copy read
(`front()` + `pop()`) is already what the single-byte check uses. kostyk, QP LFRB and
rt-spsc have no block or zero-copy API.

Reading: within these bounds, the block and zero-copy APIs of these six
libraries are correct SPSC queues under the C11 memory model. Each check is shown to
reach the full, empty, partial and wrap states, and to fail on the ordering it relies on.
Test-only adaptations are as above: `memcpy`/`memmove` become byte loops, and objects are created with placement new.


## MPMC with a mutex: ETL `queue_mpmc_mutex` ([`mpmc_cxx.cpp`](mpmc_cxx.cpp))
This queue's documented mode is threads. It locks with `etl::mutex`, which
without an OS is a spin lock on the GCC/Clang `__sync` builtins
(`-DETL_NO_STD_MUTEX` selects it here, as on bare metal). An interrupt that
spins on a lock held by the code it preempted never returns on one core. So
the queue is not for interrupt contexts, and it is not in the on-board
interrupt stress test.

The check: producer p pushes p·16+1 .. p·16+K, and the consumers pop all the
values between them. After all threads are joined, main asserts that every
value arrived exactly once, and that each consumer saw each producer's values
in increasing order. Capacity is 2, so the queue runs full and empty, and the
probes show both states were reached. Two producers plus two consumers did
not finish in 20 minutes, so two cases cover the two sides of the lock:

| Run (2026-11-08), ETL 20.49.0 | Result | Executions | Control: a mutex that does not lock | Probes full / empty |
|---|---|---|---|---|
| 2 producers + 1 consumer, K = 2 | **pass** | 5952 | fail (assertion) | reached / reached |
| 1 producer + 2 consumers, K = 4 | **pass** | 39268 | fail (assertion) | reached / reached |

`run.sh` exited 0 with all 92 checks as expected (about 5 minutes).
On 2026-11-09 a check of diffstorm `11e05d60` (fixed upstream; expect pass,
636 executions) was added; the findings checks use the old pin
`diffstorm-cb-547d0812`. All 93 checks as expected.
2026-11-12: Zephyr ring_buf v4.5.0 in its CONFIG_SMP code (pass, 34 927
executions) and DNedic/lockfree 3.0.1 spsc::RingBuf (pass, 7 118), each
with release and acquire mutants that fail; their block and zero-copy
APIs (Zephyr put/get and put_ptr/commit, get_ptr/consume; lockfree bulk
Write/Read) pass with mutants failing and all four probes reached.

## MPMC lock-free: DNedic/lockfree 3.0.1 `mpmc::Queue` ([`mpmc_cxx.cpp`](mpmc_cxx.cpp))
The same check as for ETL above, with the queue's own lock-free algorithm
(CAS on the read and write counters, a sequence count per slot). Its
capacity must be a power of 2 above 2, so CAP = 4, and K is chosen so the
6 values still overrun it. Push also returns false while another producer
is between its CAS and its slot store (not only when full); the bounded
retries cover that. With 3 retries per operation the runs did not finish in
40 minutes; with 2 they do:

| Run (2026-11-12), lockfree 3.0.1, CAP 4, RETRY 2 | Result | Executions | release -> relaxed | acquire -> relaxed | Probes full / empty |
|---|---|---|---|---|---|
| 2 producers + 1 consumer, K = 3 | **pass** | 63 488 | fail (race) | fail (race) | reached / reached |
| 1 producer + 2 consumers, K = 6 | **pass** | 83 968 | fail (race) | fail (race) | reached / reached |

`run.sh` with this section: all 130 checks as expected (2026-11-12).

## Not covered yet
(The one-core contract of the libraries below is checked instead by
[`../contract`](../contract/README.md) since 2026-11-15: every instruction
point, every start state of a small buffer, linearisability.)
- **pxq RingBuffer_PackedState** uses `volatile` instead of C/C++ atomics.
  Its stated contract is ISR ↔ main loop on one Cortex-M core. Under the
  C/C++ memory model any concurrent non-atomic access is a data race, so
  GenMC would flag it regardless of whether it is correct for that
  contract. Checking it fairly needs a model of the contract (preemption on
  one core, sequential consistency), not two free-running threads. To be
  designed; the same applies to lwrb with `LWRB_DISABLE_ATOMIC`.
- `lwrb_peek`; larger bounds than above, such as several wraps or larger capacities.
- The libraries without atomics (Contiki, RIOT tsrb, AndersKaloer,
  Embedded Artistry, ece-mohammad, wizard97, ETL queue_spsc_isr):
  like pxq they rely on one core (volatile or interrupt locks) and need the
  contract model.
