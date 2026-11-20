/*
 * Reachability probes for block_c.c / block_cxx.cpp.
 *
 * A pass only means something if the interesting states were explored. Each
 * probe turns one state into an assertion failure; run.sh expects every probe
 * to FAIL, which shows GenMC reached that state within the bounds:
 *   PROBE_FULL       a producer call moved nothing (buffer full)
 *   PROBE_PARTIAL_W  a producer call moved some but not all bytes
 *   PROBE_EMPTY      a consumer call moved nothing (buffer empty)
 *   PROBE_PARTIAL_R  a consumer call moved some but not all bytes
 *   PROBE_WRAP       (lwrb only, in block_c.c) a transfer crossed / ended at the wrap
 * Without a PROBE_ define these expand to nothing.
 */
#pragma once

#if defined(PROBE_FULL)
#define PROBE_PRODUCER(w, want) assert((w) != 0)
#elif defined(PROBE_PARTIAL_W)
#define PROBE_PRODUCER(w, want) assert(!((w) > 0 && (w) < (want)))
#else
#define PROBE_PRODUCER(w, want) ((void)0)
#endif

#if defined(PROBE_EMPTY)
#define PROBE_CONSUMER(r, want) assert((r) != 0)
#elif defined(PROBE_PARTIAL_R)
#define PROBE_CONSUMER(r, want) assert(!((r) > 0 && (r) < (want)))
#else
#define PROBE_CONSUMER(r, want) ((void)0)
#endif
