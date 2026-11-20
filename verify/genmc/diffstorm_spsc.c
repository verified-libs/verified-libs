/*
 * GenMC model check: diffstorm/cb as an SPSC queue between two threads.
 * Same shape as lwrb_spsc.c: the producer inserts bytes 1..N (cb_insert), the
 * consumer removes N bytes (cb_remove) and asserts order and value. Buffer of
 * 4 slots (3 usable), so indices wrap and the buffer runs full and empty.
 *
 * cb uses relaxed atomic loads/stores for its indices plus CB_MEMORY_BARRIER()
 * (a `dmb` on Cortex-M). GenMC cannot run inline assembly, so the barrier is
 * mapped to atomic_thread_fence(memory_order_seq_cst), the usual C11 mapping
 * of `dmb` (at least as strong for this purpose).
 *
 * Build define FIXED=1 selects a copy of cb.c with one extra barrier right
 * after the consumer reads the producer's index (made by run.sh with sed);
 * if only that variant passes, the missing ordering is located.
 */
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <genmc.h>

#define CB_MEMORY_BARRIER() atomic_thread_fence(memory_order_seq_cst)
#include "cb.c" /* GenMC checks one translation unit (fixed or original via -I) */

#ifndef N
#define N 4
#endif
#define BUF 4

static cb ring;
static CbItem storage[BUF];

static void *producer(void *arg)
{
    (void)arg;
    for (uint8_t v = 1; v <= N; v++) {
        bool ok = cb_insert(&ring, v);
        if (!ok) ok = cb_insert(&ring, v);
        __VERIFIER_assume(ok);
    }
    return 0;
}

static void *consumer(void *arg)
{
    (void)arg;
    for (uint8_t expect = 1; expect <= N; expect++) {
        CbItem v = 0;
        bool ok = cb_remove(&ring, &v);
        if (!ok) ok = cb_remove(&ring, &v);
        __VERIFIER_assume(ok);
        assert(v == expect);
    }
    return 0;
}

int main(void)
{
    pthread_t p, c;
    cb_init(&ring, storage, BUF);
    pthread_create(&p, 0, producer, 0);
    pthread_create(&c, 0, consumer, 0);
    pthread_join(p, 0);
    pthread_join(c, 0);
    return 0;
}
