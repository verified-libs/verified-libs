/*
 * GenMC model check: a C SPSC queue between two threads, same scheme as
 * lwrb_spsc.c and spsc_cxx.cpp. Library chosen with -DLIB_<NAME>.
 */
#include <assert.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <genmc.h>

#ifndef N
#define N 5
#endif
#define CAP 4

#if defined(LIB_KOSTYK)
/* lf_spsc copies items with memcpy and a run-time element size, which GenMC
 * cannot track; a byte loop with the same semantics replaces it (as for lwrb
 * in lwrb_spsc.c). string.h first, so its declaration keeps its name. */
#include <string.h>
static void *model_memcpy(void *dst, const void *src, size_t n)
{
    uint8_t *d = dst;
    const uint8_t *s = src;
    for (size_t i = 0; i < n; i++) d[i] = s[i];
    return dst;
}
#define memcpy model_memcpy
#include "lockfree.h"   /* header-only */
#undef memcpy
static lf_spsc_ring_t q;
static uint8_t storage[CAP];
static void q_init(void) { lf_spsc_init(&q, storage, CAP, 1); }
static bool q_push(uint8_t v) { return lf_spsc_push(&q, &v); }
static bool q_pop(uint8_t *v) { return lf_spsc_pop(&q, v); }

#elif defined(LIB_QP)
#include "ring_buf.h"
#include "ring_buf.c"   /* GenMC checks one translation unit */
static RingBuf q;
static RingBufElement sto[CAP];
static void q_init(void) { RingBuf_ctor(&q, sto, CAP); }
static bool q_push(uint8_t v) { return RingBuf_put(&q, (RingBufElement)v); }
static bool q_pop(uint8_t *v)
{
    RingBufElement e;
    if (!RingBuf_get(&q, &e)) return false;
    *v = (uint8_t)e;
    return true;
}

#elif defined(LIB_MICORING)
/* Built in its documented SPSC mode: the generated mring_config.h (see
 * fetch-libs.sh) selects MRING_CONCURRENCY_SPSC_ATOMIC, which uses the GCC
 * __atomic builtins with acquire/release. Items are copied with memcpy and
 * memmove and a run-time size: byte loops as for kostyk (memmove one handles
 * overlap in both directions). */
#include <string.h>
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
#define memcpy model_memcpy
#define memmove model_memmove
#include "mring.h"
#include "mring.c"   /* GenMC checks one translation unit */
#undef memcpy
#undef memmove
static mring_t q;
static uint8_t storage[CAP];
static void q_init(void) { mring_init(&q, storage, sizeof storage, CAP, 1); }
static bool q_push(uint8_t v) { return mring_push(&q, &v) == MRING_OK; }
static bool q_pop(uint8_t *v) { return mring_pop(&q, v) == MRING_OK; }

#elif defined(LIB_ZEPHYR)
/* Zephyr ring_buf (v4.5.0, header only) in its SMP configuration
 * (CONFIG_SMP=y, 2 CPUs: __atomic acquire/release on the indices); the
 * default single-core configuration uses plain accesses with compiler
 * barriers, a data race under C11 by definition, so it is not checked here.
 * Built with the minimal Zephyr header shims of the benchmark. */
#define CONFIG_SMP 1
#define CONFIG_MP_MAX_NUM_CPUS 2
/* ring_buf_put/get copy with memcpy and a run-time length, which GenMC
 * cannot track: a byte loop with the same semantics (as for kostyk). */
#include <string.h>
static void *model_memcpy(void *dst, const void *src, size_t n)
{
    uint8_t *d = dst;
    const uint8_t *s = src;
    for (size_t i = 0; i < n; i++) d[i] = s[i];
    return dst;
}
#define memcpy model_memcpy
#include <zephyr/sys/ring_buffer.h>
#undef memcpy
static struct ring_buf q;
static uint8_t storage[CAP];
static void q_init(void) { ring_buf_init(&q, CAP, storage); }
static bool q_push(uint8_t v) { return ring_buf_put(&q, &v, 1) == 1; }
static bool q_pop(uint8_t *v) { return ring_buf_get(&q, v, 1) == 1; }

#else
#error "define LIB_KOSTYK, LIB_QP, LIB_MICORING or LIB_ZEPHYR"
#endif

static void *producer(void *arg)
{
    (void)arg;
    for (uint8_t v = 1; v <= N; v++) {
        bool ok = q_push(v);
        if (!ok) ok = q_push(v);
        __VERIFIER_assume(ok);
    }
    return 0;
}

static void *consumer(void *arg)
{
    (void)arg;
    for (uint8_t expect = 1; expect <= N; expect++) {
        uint8_t v = 0;
        bool ok = q_pop(&v);
        if (!ok) ok = q_pop(&v);
        __VERIFIER_assume(ok);
        assert(v == expect);
    }
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
