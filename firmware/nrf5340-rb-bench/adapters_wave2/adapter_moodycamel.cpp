/* Adapter: moodycamel ReaderWriterQueue (cameron314/readerwriterqueue
 * v1.0.7, readerwriterqueue.h): "a lock-free queue for a single-consumer,
 * single-producer architecture" (C++11 atomics, own atomicops.h). Its
 * blocks come from malloc (the bench heap, common/<board>/bench_heap.c) once,
 * in the constructor; try_enqueue never allocates. Capacity: constructed with
 * RB_SLOTS - 1 elements; the queue may round the block size up, so the
 * harness measures it (rb-size, sweep "capacity_bytes"). Exceptions are off
 * (-fno-exceptions), which the header detects (MOODYCAMEL_EXCEPTIONS_ENABLED
 * unset). Bare-metal build: atomicops.h stops with "Unsupported platform!
 * (No semaphore wrapper available)" unless an OS is selected, although only
 * the blocking queue uses semaphores; it is built through its FreeRTOS
 * branch with declaration-only stubs (../shims/moodycamel: any semaphore
 * use would fail to link). No block or zero-copy API: push_n/pop_n loop
 * over single bytes. */
#include <stdint.h>
#include "readerwriterqueue.h"
#include "bench.h"

namespace {
moodycamel::ReaderWriterQueue<uint8_t> *q;
alignas(moodycamel::ReaderWriterQueue<uint8_t>) unsigned char qmem[sizeof(moodycamel::ReaderWriterQueue<uint8_t>)];
}

extern "C" {

BENCH_ALIGN static void mc_reset(void)
{
    /* Built once (the bench heap never frees), then drained, as rigtorp. */
    if (!q) q = new (qmem) moodycamel::ReaderWriterQueue<uint8_t>(RB_SLOTS - 1);
    uint8_t d;
    while (q->try_dequeue(d)) {}
}
BENCH_ALIGN static uint32_t mc_push(uintptr_t v, uintptr_t)
{
    return q->try_enqueue(static_cast<uint8_t>(v)) ? 1u : 0u;
}
BENCH_ALIGN static uint32_t mc_pop(uintptr_t p, uintptr_t)
{
    return q->try_dequeue(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u;
}
BENCH_DEFINE_LOOP_N(mc)

const rb_adapter adapter_moodycamel = { mc_reset, mc_push, mc_pop, mc_push_n, mc_pop_n, 0, 0 };

}
