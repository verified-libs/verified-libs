/*
 * GenMC model check: block and zero-copy APIs of C SPSC queues between two
 * threads. Same scheme as spsc_c.c, but the data moves in chunks:
 *
 *   producer: sends the bytes 1..N in calls of up to PCHUNK bytes;
 *   consumer: receives in calls of up to CCHUNK bytes and asserts every byte
 *             arrives in order and intact.
 *
 * A call may move fewer bytes than asked (buffer full/empty, or the linear
 * block ends at the wrap); the rest goes in a later call. Each thread makes
 * at most MAXCALLS calls; executions that need more are pruned with
 * __VERIFIER_assume (this bounds the search; full, empty, partial transfers
 * and the split at the wrap are all still reached with CAP = 4 and N = 5).
 *
 * The variant is chosen with -DLIB_<NAME>:
 *   LWRB_BLOCK     lwrb_write / lwrb_read with several bytes per call
 *   LWRB_ZC        zero-copy: lwrb_get_linear_block_{write,read}_{address,length},
 *                  data written/read in place, then lwrb_advance / lwrb_skip
 *   MICORING_MANY  mring_push_many / mring_pop_many (SPSC mode)
 *   MICORING_PEEK  consumer: mring_peek, then mring_pop(ring, NULL) to discard
 *   ZEPHYR_BLOCK   Zephyr ring_buf_put / ring_buf_get, CONFIG_SMP code
 *   ZEPHYR_ZC      Zephyr zero-copy: ring_buf_put_ptr / ring_buf_commit and
 *                  ring_buf_get_ptr / ring_buf_consume, CONFIG_SMP code
 */
#include <assert.h>
#include <pthread.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <genmc.h>

#ifndef N
#define N 5
#endif
#ifndef PCHUNK
#define PCHUNK 3
#endif
#ifndef CCHUNK
#define CCHUNK 2
#endif
/* Enough calls to finish with some failed (full/empty) attempts in between.
 * The single-element peek variant moves one byte per call, so it needs more.
 * run.sh rejects a pass with 0 complete executions (bound too tight: every
 * execution pruned, nothing checked). */
#ifndef MAXCALLS
#if defined(LIB_MICORING_PEEK)
#define MAXCALLS (N + 1)
#else
#define MAXCALLS 4
#endif
#endif
#define CAP 4

/* GenMC cannot track memcpy/memmove with a run-time length, which would hide
 * the buffer accesses from the race check; byte loops with the same semantics
 * replace them in the library code (as in lwrb_spsc.c and spsc_c.c). */
static void *model_memcpy(void *dst, const void *src, size_t n)
{
    uint8_t *d = dst;
    const uint8_t *s = src;
    for (size_t i = 0; i < n; i++) d[i] = s[i];
    return dst;
}
static void *model_memmove(void *dst, const void *src, size_t n)
{
    uint8_t *d = dst;
    const uint8_t *s = src;
    if (d < s) for (size_t i = 0; i < n; i++) d[i] = s[i];
    else for (size_t i = n; i-- > 0;) d[i] = s[i];
    return dst;
}

#if defined(LIB_LWRB_BLOCK) || defined(LIB_LWRB_ZC)
#include "lwrb/lwrb.h"
#define memcpy model_memcpy
#include "lwrb/lwrb.c" /* GenMC checks one translation unit */
#undef memcpy
static lwrb_t rb;
static uint8_t storage[CAP];
static void q_init(void) { lwrb_init(&rb, storage, CAP); }

#if defined(LIB_LWRB_BLOCK)
static size_t q_write(const uint8_t *src, size_t n) { return lwrb_write(&rb, src, n); }
static size_t q_read(uint8_t *dst, size_t n) { return lwrb_read(&rb, dst, n); }
#else
/* The DMA pattern: ask for the linear block, fill/drain it in place, then
 * publish with lwrb_advance / release with lwrb_skip. */
static size_t q_write(const uint8_t *src, size_t n)
{
    uint8_t *a = lwrb_get_linear_block_write_address(&rb);
    size_t len = lwrb_get_linear_block_write_length(&rb);
    if (len > n) len = n;
    for (size_t i = 0; i < len; i++) a[i] = src[i];
    return lwrb_advance(&rb, len);
}
static size_t q_read(uint8_t *dst, size_t n)
{
    const uint8_t *a = lwrb_get_linear_block_read_address(&rb);
    size_t len = lwrb_get_linear_block_read_length(&rb);
    if (len > n) len = n;
    for (size_t i = 0; i < len; i++) dst[i] = a[i];
    return lwrb_skip(&rb, len);
}
#endif

#elif defined(LIB_ZEPHYR_BLOCK) || defined(LIB_ZEPHYR_ZC)
/* Zephyr ring_buf v4.5.0 in its CONFIG_SMP code (see spsc_c.c). Capacity
 * CAP (Zephyr reserves no slot). */
#define CONFIG_SMP 1
#define CONFIG_MP_MAX_NUM_CPUS 2
#define memcpy model_memcpy
#include <zephyr/sys/ring_buffer.h>
#undef memcpy
static struct ring_buf rb;
static uint8_t storage[CAP];
static void q_init(void) { ring_buf_init(&rb, CAP, storage); }
#if defined(LIB_ZEPHYR_BLOCK)
static size_t q_write(const uint8_t *src, size_t n) { return ring_buf_put(&rb, src, (uint32_t)n); }
static size_t q_read(uint8_t *dst, size_t n) { return ring_buf_get(&rb, dst, (uint32_t)n); }
#else
static size_t q_write(const uint8_t *src, size_t n)
{
    uint8_t *a;
    size_t len = ring_buf_put_ptr(&rb, &a, 0);
    if (len > n) len = n;
    for (size_t i = 0; i < len; i++) a[i] = src[i];
    ring_buf_commit(&rb, len);
    return len;
}
static size_t q_read(uint8_t *dst, size_t n)
{
    uint8_t *a;
    size_t len = ring_buf_get_ptr(&rb, &a, 0);
    if (len > n) len = n;
    for (size_t i = 0; i < len; i++) dst[i] = a[i];
    ring_buf_consume(&rb, len);
    return len;
}
#endif

#elif defined(LIB_MICORING_MANY) || defined(LIB_MICORING_PEEK)
/* Built in its documented SPSC mode (generated mring_config.h, see
 * fetch-libs.sh), as in spsc_c.c. */
#define memcpy model_memcpy
#define memmove model_memmove
#include "mring.h"
#include "mring.c" /* GenMC checks one translation unit */
#undef memcpy
#undef memmove
static mring_t q;
static uint8_t storage[CAP];
static void q_init(void) { mring_init(&q, storage, sizeof storage, CAP, 1); }

#if defined(LIB_MICORING_MANY)
static size_t q_write(const uint8_t *src, size_t n)
{
    size_t done = 0;
    mring_err_t e = mring_push_many(&q, src, n, &done);
    assert(e == MRING_OK);
    return done;
}
static size_t q_read(uint8_t *dst, size_t n)
{
    size_t done = 0;
    mring_err_t e = mring_pop_many(&q, dst, n, &done);
    assert(e == MRING_OK);
    return done;
}
#else
static size_t q_write(const uint8_t *src, size_t n)
{
    (void)n;
    return mring_push(&q, src) == MRING_OK ? 1 : 0;
}
static size_t q_read(uint8_t *dst, size_t n)
{
    (void)n;
    if (mring_peek(&q, dst) != MRING_OK) return 0;
    mring_err_t e = mring_pop(&q, NULL);   /* discard the peeked element */
    assert(e == MRING_OK);
    return 1;
}
#endif

#else
#error "define LIB_LWRB_BLOCK, LIB_LWRB_ZC, LIB_MICORING_MANY or LIB_MICORING_PEEK"
#endif

#include "block_probe.h"

static void *producer(void *arg)
{
    (void)arg;
    uint8_t src[N];
    for (size_t i = 0; i < N; i++) src[i] = (uint8_t)(i + 1);
    size_t sent = 0;
    for (int k = 0; k < MAXCALLS && sent < N; k++) {
        size_t want = N - sent < PCHUNK ? N - sent : PCHUNK;
#if defined(PROBE_WRAP) && (defined(LIB_LWRB_BLOCK) || defined(LIB_LWRB_ZC))
        /* w_ptr is producer-owned: a relaxed read of it is not a race */
        size_t wp = atomic_load_explicit(&rb.w_ptr, memory_order_relaxed);
#endif
        size_t w = q_write(src + sent, want);
        assert(w <= want);
        PROBE_PRODUCER(w, want);
#if defined(PROBE_WRAP) && defined(LIB_LWRB_BLOCK)
        assert(!(wp + w > CAP));        /* reachable: one lwrb_write split at the wrap */
#elif defined(PROBE_WRAP) && defined(LIB_LWRB_ZC)
        assert(!(w > 0 && w < want && wp + w == CAP)); /* reachable: linear block ended at the wrap */
#endif
        sent += w;
    }
    __VERIFIER_assume(sent == N);
    return 0;
}

static void *consumer(void *arg)
{
    (void)arg;
    uint8_t dst[CCHUNK];
    size_t got = 0;
    for (int k = 0; k < MAXCALLS && got < N; k++) {
        size_t want = N - got < CCHUNK ? N - got : CCHUNK;
        size_t r = q_read(dst, want);
        assert(r <= want);
        PROBE_CONSUMER(r, want);
        for (size_t i = 0; i < r; i++) assert(dst[i] == (uint8_t)(got + i + 1));
        got += r;
    }
    __VERIFIER_assume(got == N);
    return 0;
}

int main(void)
{
    pthread_t p, c;
    q_init();
    pthread_create(&p, 0, producer, 0);
    pthread_create(&c, 0, consumer, 0);
    pthread_join(p, 0);
    pthread_join(c, 0);
    return 0;
}
