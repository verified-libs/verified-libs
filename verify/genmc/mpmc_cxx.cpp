/*
 * GenMC model check: a multi-producer / multi-consumer queue with NP
 * producer and NC consumer threads (default 2 and 2; run.sh uses 2+1 and
 * 1+2, which together cover both sides of the lock at a state space GenMC
 * finishes: 2+2 did not finish in 20 minutes), in the mode the library
 * documents (threads, the queue's own mutex).
 *
 * Producer p pushes p*16+1 .. p*16+K (a full queue is retried up to RETRY
 * times); the consumers pop NP*K values between them, NP*K/NC each (an empty
 * queue is retried up to RETRY times). Executions that need more retries are pruned with
 * __VERIFIER_assume. After all threads are joined, main asserts that every
 * value arrived exactly once and that each consumer saw each producer's
 * values in increasing order (a mutex-protected FIFO must keep that).
 * Capacity CAP = 2 (4 for lockfree, which needs a power of 2 above 2) is
 * less than the NP*K values, so the queue runs full and empty. Reachability probes (run.sh expects them to FAIL): -DPROBE_FULL
 * asserts that no push finds the queue full, -DPROBE_EMPTY that no pop finds
 * it empty.
 *
 * -DLIB_ETL_MPMC: etl::queue_mpmc_mutex (lock: etl::mutex, a spin lock on
 * the GCC/Clang __sync builtins). The negative control swaps in a copy of
 * ETL whose mutex does not lock (run.sh); it must fail.
 *
 * -DLIB_LOCKFREE_MPMC: DNedic lockfree::mpmc::Queue (lock-free: CAS on the
 * counters, a sequence count per slot). Controls: release -> relaxed and
 * acquire -> relaxed copies of its queue_impl.hpp (run.sh); they must fail.
 */
#include <assert.h>
#include <pthread.h>
#include <stdint.h>
#include <genmc.h>

#ifndef K
#define K 2
#endif
#ifndef RETRY
#define RETRY 3
#endif
#ifndef NP
#define NP 2
#endif
#ifndef NC
#define NC 2
#endif
#define PER_C (NP * K / NC)
static_assert(NP * K % NC == 0, "values must split evenly between the consumers");
#ifndef CAP
#define CAP 2   /* lockfree::mpmc::Queue needs a power of 2 > 2: run.sh passes -DCAP=4 for it */
#endif

#if defined(LIB_ETL_MPMC)
#include <type_traits>
#include <new>
#include "etl/queue_mpmc_mutex.h"
#if !ETL_HAS_MUTEX
#error "ETL selected no mutex implementation"
#endif
/* Placement new: a static object with a destructor needs __dso_handle,
 * which GenMC does not provide (as in spsc_cxx.cpp). */
using Q = etl::queue_mpmc_mutex<uint8_t, CAP>;
alignas(Q) static unsigned char q_mem[sizeof(Q)];
static Q *q;
static void q_init() { q = new (q_mem) Q(); }
static bool q_push_lib(uint8_t v) { return q->push(v); }
static bool q_pop_lib(uint8_t *v) { return q->pop(*v); }
#elif defined(LIB_LOCKFREE_MPMC)
/* DNedic/lockfree 3.0.1 lockfree::mpmc::Queue (lock-free, CAS), with the
 * settings its README gives for embedded systems. */
#include <new>
#define LOCKFREE_CACHE_COHERENT false
#define LOCKFREE_CACHELINE_LENGTH 64
#include "lockfree/mpmc/queue.hpp"
using Q = lockfree::mpmc::Queue<uint8_t, CAP>;
alignas(Q) static unsigned char q_mem[sizeof(Q)];
static Q *q;
static void q_init() { q = new (q_mem) Q(); }
static bool q_push_lib(uint8_t v) { return q->Push(v); }
static bool q_pop_lib(uint8_t *v) { return q->Pop(*v); }
#else
#error "define LIB_ETL_MPMC or LIB_LOCKFREE_MPMC"
#endif

static bool q_push(uint8_t v)
{
    bool ok = q_push_lib(v);
#ifdef PROBE_FULL
    assert(ok);   /* reachable: the queue was full */
#endif
    return ok;
}
static bool q_pop(uint8_t *v)
{
    bool ok = q_pop_lib(v);
#ifdef PROBE_EMPTY
    assert(ok);   /* reachable: the queue was empty */
#endif
    return ok;
}

static uint8_t got[NC][PER_C];   /* per consumer, written by that thread only */

static void *producer(void *arg)
{
    uintptr_t p = (uintptr_t)arg;
    for (uint8_t i = 1; i <= K; i++) {
        uint8_t v = (uint8_t)(p * 16 + i);
        bool ok = false;
        for (int t = 0; t < RETRY && !ok; t++) ok = q_push(v);
        __VERIFIER_assume(ok);
    }
    return nullptr;
}

static void *consumer(void *arg)
{
    uintptr_t c = (uintptr_t)arg;
    for (int i = 0; i < PER_C; i++) {
        uint8_t v = 0;
        bool ok = false;
        for (int t = 0; t < RETRY && !ok; t++) ok = q_pop(&v);
        __VERIFIER_assume(ok);
        got[c][i] = v;
    }
    return nullptr;
}

int main()
{
    pthread_t pt[NP], ct[NC];
    q_init();
    for (uintptr_t i = 0; i < NP; i++) pthread_create(&pt[i], nullptr, producer, (void *)i);
    for (uintptr_t i = 0; i < NC; i++) pthread_create(&ct[i], nullptr, consumer, (void *)i);
    for (int i = 0; i < NP; i++) pthread_join(pt[i], nullptr);
    for (int i = 0; i < NC; i++) pthread_join(ct[i], nullptr);

    int seen[NP][K + 1] = {};
    for (int c = 0; c < NC; c++) {
        int last[NP] = {};
        for (int i = 0; i < PER_C; i++) {
            int v = got[c][i], p = v / 16, s = v % 16;
            assert(p >= 0 && p < NP && s >= 1 && s <= K);   /* a value that was pushed */
            assert(s > last[p]);                             /* per-producer order */
            last[p] = s;
            seen[p][s]++;
        }
    }
    for (int p = 0; p < NP; p++)
        for (int s = 1; s <= K; s++) assert(seen[p][s] == 1);   /* exactly once */
    return 0;
}
