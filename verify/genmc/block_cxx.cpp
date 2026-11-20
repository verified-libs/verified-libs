/*
 * GenMC model check: block and zero-copy APIs of C++ SPSC queues between two
 * threads. Same scheme as block_c.c (producer sends 1..N in chunks of up to
 * PCHUNK, consumer receives in chunks of up to CCHUNK and asserts order and
 * value; partial transfers allowed; at most MAXCALLS calls per thread, more
 * are pruned). Library setup as in spsc_cxx.cpp.
 *
 * The variant is chosen with -DLIB_<NAME>:
 *   JNK0LE_BUFF      jnk0le writeBuff / readBuff
 *   JNK0LE_PEEK      consumer: peek() (pointer into the buffer), read in place,
 *                    then remove()
 *   POLYCRATIA_N     polycratia try_push_n / try_pop_n
 *   ETL_FRONT        consumer: front(value) (checked peek), then pop()
 *   ETL_FRONT_REF    consumer: !empty(), then the reference front() (unchecked,
 *                    in place), then pop()
 */
#include <assert.h>
#include <pthread.h>
#include <stddef.h>
#include <stdint.h>
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
/* Single-element consumers need one call per byte. run.sh rejects a pass
 * with 0 complete executions (bound too tight, nothing checked). */
#ifndef MAXCALLS
#if defined(LIB_JNK0LE_PEEK) || defined(LIB_ETL_FRONT) || defined(LIB_ETL_FRONT_REF)
#define MAXCALLS (N + 1)
#else
#define MAXCALLS 4
#endif
#endif
#define CAP 4

#if defined(LIB_JNK0LE_BUFF) || defined(LIB_JNK0LE_PEEK)
#include "ringbuffer.hpp"
static jnk0le::Ringbuffer<uint8_t, CAP> q;
static void q_init() {}
static size_t q_write(const uint8_t *src, size_t n) { return q.writeBuff(src, n); }
#if defined(LIB_JNK0LE_BUFF)
static size_t q_read(uint8_t *dst, size_t n) { return q.readBuff(dst, n); }
#else
static size_t q_read(uint8_t *dst, size_t)
{
    uint8_t *p = q.peek();
    if (!p) return 0;
    dst[0] = *p;          /* read in place */
    bool ok = q.remove();
    assert(ok);
    return 1;
}
#endif

#elif defined(LIB_POLYCRATIA_N)
#include <new>
#include "spscring/spscring.hpp"
using R = spscring::ring<uint8_t, CAP>;
alignas(R) static unsigned char q_mem[sizeof(R)];
static R *q;
static void q_init() { q = new (q_mem) R(); }
static size_t q_write(const uint8_t *src, size_t n) { return q->try_push_n(src, n); }
static size_t q_read(uint8_t *dst, size_t n) { return q->try_pop_n(dst, n); }

#elif defined(LIB_ETL_FRONT) || defined(LIB_ETL_FRONT_REF)
#include <type_traits>
#include <new>
#include "etl/queue_spsc_atomic.h"
using Q = etl::queue_spsc_atomic<uint8_t, CAP>;
alignas(Q) static unsigned char q_mem[sizeof(Q)];
static Q *q;
static void q_init() { q = new (q_mem) Q(); }
static size_t q_write(const uint8_t *src, size_t) { return q->push(src[0]) ? 1 : 0; }
static size_t q_read(uint8_t *dst, size_t)
{
#if defined(LIB_ETL_FRONT)
    if (!q->front(dst[0])) return 0;
#else
    if (q->empty()) return 0;
    dst[0] = q->front();  /* unchecked reference, read in place */
#endif
    bool ok = q->pop();
    assert(ok);
    return 1;
}

#elif defined(LIB_LOCKFREE_BULK)
/* DNedic/lockfree 3.0.1 spsc::RingBuf bulk Write/Read (all or nothing), as
 * the benchmark adapter uses it: ask GetFree/GetAvailable, move what fits. */
#include <new>
#include <cstring>
static void *model_memcpy(void *dst, const void *src, size_t n)
{
    auto *d = static_cast<uint8_t *>(dst);
    auto *s = static_cast<const uint8_t *>(src);
    for (size_t i = 0; i < n; i++) d[i] = s[i];
    return dst;
}
#define LOCKFREE_CACHE_COHERENT false
#define LOCKFREE_CACHELINE_LENGTH 64
#define memcpy model_memcpy
#include "lockfree/spsc/ring_buf.hpp"
#undef memcpy
using LQ = lockfree::spsc::RingBuf<uint8_t, CAP>;
alignas(LQ) static unsigned char q_mem[sizeof(LQ)];
static LQ *q;
static void q_init() { q = new (q_mem) LQ(); }
static size_t q_write(const uint8_t *src, size_t n)
{
    size_t k = q->GetFree();
    if (k > n) k = n;
    return (k && q->Write(src, k)) ? k : 0;
}
static size_t q_read(uint8_t *dst, size_t n)
{
    size_t k = q->GetAvailable();
    if (k > n) k = n;
    return (k && q->Read(dst, k)) ? k : 0;
}
#else
#error "define LIB_JNK0LE_BUFF, LIB_JNK0LE_PEEK, LIB_POLYCRATIA_N, LIB_ETL_FRONT, LIB_ETL_FRONT_REF or LIB_LOCKFREE_BULK"
#endif

#include "block_probe.h"

static void *producer(void *)
{
    uint8_t src[N];
    for (size_t i = 0; i < N; i++) src[i] = (uint8_t)(i + 1);
    size_t sent = 0;
    for (int k = 0; k < MAXCALLS && sent < N; k++) {
        size_t want = N - sent < PCHUNK ? N - sent : PCHUNK;
        size_t w = q_write(src + sent, want);
        assert(w <= want);
        PROBE_PRODUCER(w, want);
        sent += w;
    }
    __VERIFIER_assume(sent == N);
    return nullptr;
}

static void *consumer(void *)
{
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
    return nullptr;
}

int main()
{
    pthread_t p, c;
    q_init();
    pthread_create(&p, nullptr, producer, nullptr);
    pthread_create(&c, nullptr, consumer, nullptr);
    pthread_join(p, nullptr);
    pthread_join(c, nullptr);
    return 0;
}
