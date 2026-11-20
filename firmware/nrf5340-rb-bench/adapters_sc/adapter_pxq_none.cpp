/* Single-context variant: pxq RingBuffer_PackedState with Topology::None<>,
 * the template's default ("single context, no concurrency": no volatile, no
 * interrupt masking). Same operations as adapter_pxq.cpp (SPSC topology). */
#include <stdint.h>


#include "RingBuffer_PackedState.h"
#include "bench.h"

using RbNone = RingBuffer_PackedState<uint8_t, RB_SLOTS, Topology::None<>>;
static RbNone rbn;

extern "C" {

BENCH_ALIGN static void pxqn_reset(void) { rbn.clear(); }
BENCH_ALIGN static uint32_t pxqn_push(uintptr_t v, uintptr_t) { return rbn.push(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t pxqn_pop(uintptr_t p, uintptr_t) { return rbn.pop(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t pxqn_push_n(uintptr_t p, uintptr_t n)
{
    return static_cast<uint32_t>(rbn.push_n(reinterpret_cast<const uint8_t *>(p), n));
}
BENCH_ALIGN static uint32_t pxqn_pop_n(uintptr_t p, uintptr_t n)
{
    return static_cast<uint32_t>(rbn.pop_n(reinterpret_cast<uint8_t *>(p), n));
}
BENCH_ALIGN static uint32_t pxqn_dma_wr_acquire(uintptr_t pp, uintptr_t max)
{
    auto area = rbn.get_contiguous_push_area(max);
    *reinterpret_cast<uint8_t **>(pp) = const_cast<uint8_t *>(area.ptr);
    return static_cast<uint32_t>(area.count);
}
BENCH_ALIGN static uint32_t pxqn_dma_wr_commit(uintptr_t n, uintptr_t) { rbn.commit_push(n); return static_cast<uint32_t>(n); }
BENCH_ALIGN static uint32_t pxqn_dma_rd_acquire(uintptr_t pp, uintptr_t max)
{
    auto area = rbn.get_contiguous_pop_area(max);
    *reinterpret_cast<const uint8_t **>(pp) = const_cast<const uint8_t *>(area.ptr);
    return static_cast<uint32_t>(area.count);
}
BENCH_ALIGN static uint32_t pxqn_dma_rd_release(uintptr_t n, uintptr_t) { rbn.commit_pop(n); return static_cast<uint32_t>(n); }

const rb_adapter adapter_pxq_none = { pxqn_reset, pxqn_push, pxqn_pop, pxqn_push_n, pxqn_pop_n, 0, 0,
                                      pxqn_dma_wr_acquire, pxqn_dma_wr_commit, pxqn_dma_rd_acquire, pxqn_dma_rd_release };

}
