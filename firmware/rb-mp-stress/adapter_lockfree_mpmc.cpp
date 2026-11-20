/* Adapter: DNedic/lockfree 3.0.1, lockfree::mpmc::Queue<uint8_t, RB_SLOTS>
 * (lock-free multi-producer multi-consumer queue; "thread and interrupt
 * safe" in its use case, per the README). It needs compare-and-swap, which
 * ARMv6-M (Cortex-M0+) lacks: there the adapter is all zero and the library
 * is reported as not available (see main.c). */
#include "bench.h"

#if defined(__ARM_ARCH_6M__)
extern "C" const rb_adapter adapter_lockfree_mpmc = { 0, 0, 0, 0, 0, 0, 0 };
#else
#include <new>
#include "lockfree/mpmc/queue.hpp"

using LQ = lockfree::mpmc::Queue<uint8_t, RB_SLOTS>;
alignas(LQ) static unsigned char lq_mem[sizeof(LQ)];
static LQ *lq;

BENCH_ALIGN static void lfm_reset(void) { lq = new (lq_mem) LQ(); }
BENCH_ALIGN static uint32_t lfm_push(uintptr_t v, uintptr_t) { return lq->Push(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t lfm_pop(uintptr_t p, uintptr_t) { return lq->Pop(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }

extern "C" const rb_adapter adapter_lockfree_mpmc = { lfm_reset, lfm_push, lfm_pop, 0, 0, 0, 0 };
#endif
