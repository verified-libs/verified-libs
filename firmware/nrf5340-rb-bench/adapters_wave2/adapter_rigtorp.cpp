/* Adapter: rigtorp/SPSCQueue, SPSCQueue<uint8_t> with capacity 128.
 * The slot array is allocated once through std::allocator (malloc, served by
 * bench_heap.c). The queue object itself is built with placement new in
 * static storage (no atexit destructor); reset drains it. No block API. */
#include <new>
#include <stdint.h>
#include "rigtorp/SPSCQueue.h"
#include "bench.h"

namespace {
using Q = rigtorp::SPSCQueue<uint8_t>;
alignas(Q) unsigned char q_mem[sizeof(Q)];
Q *q;
}

extern "C" {

BENCH_ALIGN static void rig_reset(void)
{
    if (!q) q = new (q_mem) Q(RB_SLOTS);
    while (q->front()) q->pop();
}
BENCH_ALIGN static uint32_t rig_push(uintptr_t v, uintptr_t) { return q->try_push(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t rig_pop(uintptr_t p, uintptr_t)
{
    uint8_t *f = q->front();
    if (!f) return 0;
    *reinterpret_cast<uint8_t *>(p) = *f;
    q->pop();
    return 1;
}
BENCH_DEFINE_LOOP_N(rig)

const rb_adapter adapter_rigtorp = { rig_reset, rig_push, rig_pop, rig_push_n, rig_pop_n, 0, 0 };

}
