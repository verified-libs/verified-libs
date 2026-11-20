/*
 * GenMC model check: a C++ SPSC queue between two threads, same scheme as
 * lwrb_spsc.c. The producer pushes the bytes 1..N one at a time, the
 * consumer pops N bytes and asserts they arrive in order and intact. GenMC
 * explores every execution allowed by the C11/C++11 memory model (RC11), so
 * a missing acquire/release shows up as an assertion failure or as a data
 * race on the (non-atomic) buffer slots.
 *
 * The library is chosen with -DLIB_<NAME>. Capacity CAP is small (indices
 * wrap with N > CAP). Each push/pop may fail once (full/empty) and is
 * retried once; executions needing more retries are pruned with
 * __VERIFIER_assume. That bounds the search; full and empty are still
 * reached.
 */
#include <assert.h>
#include <pthread.h>
#include <stdint.h>
#include <genmc.h>

#ifndef N
#define N 5
#endif
#define CAP 4

#if defined(LIB_JNK0LE)
#include "ringbuffer.hpp"
#ifndef JNK_FAKE_TSO
#define JNK_FAKE_TSO false
#endif
/* default template arguments except for the size; fake_tso is the library's
 * own switch to relaxed index accesses (meant for single-core use) */
static jnk0le::Ringbuffer<uint8_t, CAP, JNK_FAKE_TSO> q;
static void q_init() {}
static bool q_push(uint8_t v) { return q.insert(v); }
static bool q_pop(uint8_t *v) { return q.remove(*v); }

#elif defined(LIB_RIGTORP)
#include <new>
#include "rigtorp/SPSCQueue.h"
/* The queue object is over-aligned (alignas cache line); plain "new" would
 * call the aligned operator new, which GenMC does not provide. Placement new
 * into aligned static storage instead, as in the firmware adapter. The
 * queue's slot array is still allocated by the library itself. */
using Q = rigtorp::SPSCQueue<uint8_t>;
alignas(Q) static unsigned char q_mem[sizeof(Q)];
static Q *q;
static void q_init() { q = new (q_mem) Q(CAP); }
static bool q_push(uint8_t v) { return q->try_push(v); }
static bool q_pop(uint8_t *v)
{
    uint8_t *f = q->front();
    if (!f) return false;
    *v = *f;
    q->pop();
    return true;
}

#elif defined(LIB_ETL)
/* ETL derives its traits from the STL here but expects <type_traits> to be
 * included already (the firmware build gets it through other headers). */
#include <type_traits>
#include <new>
#include "etl/queue_spsc_atomic.h"
/* Placement new: a static object with a destructor needs __dso_handle,
 * which GenMC does not provide (as in the firmware adapter). */
using Q = etl::queue_spsc_atomic<uint8_t, CAP>;
alignas(Q) static unsigned char q_mem[sizeof(Q)];
static Q *q;
static void q_init() { q = new (q_mem) Q(); }
static bool q_push(uint8_t v) { return q->push(v); }
static bool q_pop(uint8_t *v) { return q->pop(*v); }

#elif defined(LIB_POLYCRATIA)
#include <new>
#include "spscring/spscring.hpp"
/* Placement new into static storage: a static object with a destructor
 * would need __cxa_atexit/__dso_handle, which GenMC does not provide (same
 * as in the firmware adapter). */
using R = spscring::ring<uint8_t, CAP>;
alignas(R) static unsigned char q_mem[sizeof(R)];
static R *q;
static void q_init() { q = new (q_mem) R(); }
static bool q_push(uint8_t v) { return q->try_push(v); }
static bool q_pop(uint8_t *v)
{
    auto r = q->try_pop();
    if (!r) return false;
    *v = *r;
    return true;
}

#elif defined(LIB_RTSPSC)
#include "rtq/spsc_queue.hpp"
static rtq::SpscQueue<uint8_t, CAP> q;
static void q_init() {}
static bool q_push(uint8_t v) { return q.push(v); }
static bool q_pop(uint8_t *v) { return q.pop(*v); }

#elif defined(LIB_LOCKFREE)
/* DNedic/lockfree 3.0.1, lockfree::spsc::RingBuf (as the benchmark adapter),
 * with the settings its README gives for embedded systems. */
#define LOCKFREE_CACHE_COHERENT false
#define LOCKFREE_CACHELINE_LENGTH 64
#include <new>
/* Write/Read copy with memcpy and a run-time length, which GenMC cannot
 * track: a byte loop with the same semantics (as for kostyk in spsc_c.c). */
#include <cstring>
static void *model_memcpy(void *dst, const void *src, size_t n)
{
    auto *d = static_cast<uint8_t *>(dst);
    auto *s = static_cast<const uint8_t *>(src);
    for (size_t i = 0; i < n; i++) d[i] = s[i];
    return dst;
}
#define memcpy model_memcpy
#include "lockfree/spsc/ring_buf.hpp"
#undef memcpy
static lockfree::spsc::RingBuf<uint8_t, CAP> *q;
alignas(lockfree::spsc::RingBuf<uint8_t, CAP>) static unsigned char q_mem[sizeof(lockfree::spsc::RingBuf<uint8_t, CAP>)];
static void q_init() { q = new (q_mem) lockfree::spsc::RingBuf<uint8_t, CAP>(); }
static bool q_push(uint8_t v) { return q->Write(&v, 1); }
static bool q_pop(uint8_t *v) { return q->Read(v, 1); }
#else
#error "define one of LIB_JNK0LE, LIB_RIGTORP, LIB_ETL, LIB_POLYCRATIA, LIB_RTSPSC, LIB_LOCKFREE"
#endif

static void *producer(void *)
{
    for (uint8_t v = 1; v <= N; v++) {
        bool ok = q_push(v);
        if (!ok) ok = q_push(v);
        __VERIFIER_assume(ok);
    }
    return nullptr;
}

static void *consumer(void *)
{
    for (uint8_t expect = 1; expect <= N; expect++) {
        uint8_t v = 0;
        bool ok = q_pop(&v);
        if (!ok) ok = q_pop(&v);
        __VERIFIER_assume(ok);
        assert(v == expect);
    }
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
