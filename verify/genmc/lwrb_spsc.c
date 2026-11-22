/*
 * GenMC model check: lwrb as an SPSC queue between two threads.
 *
 * The producer writes the bytes 1..N (one lwrb_write call per byte, retrying
 * while full); the consumer reads N bytes (one lwrb_read call per byte,
 * retrying while empty) and asserts they arrive in order and intact.
 * GenMC explores every execution allowed by the C11 memory model (RC11), so
 * a missing acquire/release or a torn index shows up as an assertion failure
 * or a data race on the buffer.
 *
 * Small sizes keep the state space finite: buffer of 4 bytes (3 usable),
 * N bytes in total, so the indices wrap. Each call may fail once (full /
 * empty) and is retried once; executions needing more retries are pruned
 * with __VERIFIER_assume. This bounds the search, it does not hide states:
 * the full and empty states are still reached (-DPROBE_FULL / -DPROBE_EMPTY
 * assert that they are not, and must fail).
 */
#include <assert.h>
#include <pthread.h>
#include <stdint.h>
#include <genmc.h>
#include "lwrb/lwrb.h"

/* GenMC cannot track memcpy with a run-time length, so the buffer accesses
 * would be invisible to the race check. Replace it with a byte loop (same
 * semantics) for the library code only. */
static void *model_memcpy(void *dst, const void *src, size_t n)
{
    uint8_t *d = dst;
    const uint8_t *s = src;
    for (size_t i = 0; i < n; i++) d[i] = s[i];
    return dst;
}
/* lwrb_init (from v3.4.0) clears the whole structure with memset, which
 * GenMC cannot model over atomic objects ("Invalid call to memset()"). The
 * structure here is a static object, zero from the start, and lwrb_init runs
 * before the threads exist: clearing it to zero changes nothing, so the model
 * leaves the write out and only checks that zero is the value asked for. */
static void *model_memset(void *dst, int c, size_t n)
{
    (void)n;
    assert(c == 0);
    return dst;
}
#define memcpy model_memcpy
#define memset model_memset
#include "lwrb/lwrb.c" /* GenMC checks one translation unit */
#undef memcpy
#undef memset

#ifndef N
#define N 5
#endif
#define BUF 4

static lwrb_t rb;
static uint8_t data[BUF];

/* One byte per call: lwrb_write / lwrb_read with a length of 1, or with
 * -DBYTE_API the functions for one byte (lwrb_write_byte / lwrb_read_byte,
 * from v3.4.0). */
#ifdef BYTE_API
#define Q_WRITE(v) lwrb_write_byte(&rb, (v))
#define Q_READ(v)  lwrb_read_byte(&rb, &(v))
#else
#define Q_WRITE(v) lwrb_write(&rb, &(v), 1)
#define Q_READ(v)  lwrb_read(&rb, &(v), 1)
#endif

static void *producer(void *arg)
{
    (void)arg;
    for (uint8_t v = 1; v <= N; v++) {
        /* retry while full (bounded: one failed attempt, then it must fit) */
        lwrb_sz_t w = Q_WRITE(v);
#ifdef PROBE_FULL
        assert(w != 0);                 /* reachable: a write found the buffer full */
#endif
        if (w == 0) w = Q_WRITE(v);
        __VERIFIER_assume(w == 1);
    }
    return 0;
}

static void *consumer(void *arg)
{
    (void)arg;
    for (uint8_t expect = 1; expect <= N; expect++) {
        uint8_t v = 0;
        /* retry while empty (bounded: one failed attempt, then data must be there) */
        lwrb_sz_t r = Q_READ(v);
#ifdef PROBE_EMPTY
        assert(r != 0);                 /* reachable: a read found the buffer empty */
#endif
        if (r == 0) r = Q_READ(v);
        __VERIFIER_assume(r == 1);
        assert(v == expect);
    }
    return 0;
}

int main(void)
{
    pthread_t p, c;
    lwrb_init(&rb, data, BUF);
    pthread_create(&p, 0, producer, 0);
    pthread_create(&c, 0, consumer, 0);
    pthread_join(p, 0);
    pthread_join(c, 0);
    return 0;
}
