/* Single-context variant: ETL etl::queue<uint8_t, 127> (plain queue, no
 * interrupt or thread protection), next to the benchmark's queue_spsc_isr /
 * queue_spsc_atomic. Placement new into static storage, as in
 * adapter_etl.cpp (no static destructor, no atexit). */
#include <new>
#include <stdint.h>
#include "etl/queue.h"
#include "bench.h"

/* RB_SLOTS - 1 usable, like the other adapters */
using Q = etl::queue<uint8_t, RB_SLOTS - 1>;
alignas(Q) static unsigned char q_mem[sizeof(Q)];
static Q *q;

extern "C" {

BENCH_ALIGN static void etlq_reset(void)
{
    if (!q) q = new (q_mem) Q();
    q->clear();
}
BENCH_ALIGN static uint32_t etlq_push(uintptr_t v, uintptr_t)
{
    if (q->full()) return 0;
    q->push(static_cast<uint8_t>(v));
    return 1;
}
BENCH_ALIGN static uint32_t etlq_pop(uintptr_t p, uintptr_t)
{
    if (q->empty()) return 0;
    *reinterpret_cast<uint8_t *>(p) = q->front();
    q->pop();
    return 1;
}
BENCH_DEFINE_LOOP_N(etlq)

const rb_adapter adapter_etl_queue = { etlq_reset, etlq_push, etlq_pop, etlq_push_n, etlq_pop_n, 0, 0 };

}
