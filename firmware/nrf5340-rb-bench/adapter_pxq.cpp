/* Adapter: pxq-dk/RingBuffer-Cortex, RingBuffer_PackedState, SPSC topology.
 * Since 1.4.0 the header's PrimaskLock is self-contained; versions before
 * 1.4.0 needed the CMSIS PRIMASK intrinsics declared before the include. */
#include <stdint.h>


#include "RingBuffer_PackedState.h"
#include "bench.h"

using Rb = RingBuffer_PackedState<uint8_t, RB_SLOTS, Topology::SPSC<>>;
static Rb rb;

extern "C" {

BENCH_ALIGN static void pxq_reset(void) { rb.clear(); }

BENCH_ALIGN static uint32_t pxq_push(uintptr_t v, uintptr_t)
{
    return rb.push(static_cast<uint8_t>(v)) ? 1u : 0u;
}

BENCH_ALIGN static uint32_t pxq_pop(uintptr_t p, uintptr_t)
{
    return rb.pop(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u;
}

BENCH_ALIGN static uint32_t pxq_push_n(uintptr_t p, uintptr_t n)
{
    return static_cast<uint32_t>(rb.push_n(reinterpret_cast<const uint8_t *>(p), n));
}

BENCH_ALIGN static uint32_t pxq_pop_n(uintptr_t p, uintptr_t n)
{
    return static_cast<uint32_t>(rb.pop_n(reinterpret_cast<uint8_t *>(p), n));
}

/* Zero-copy: get_contiguous_push_area / commit_push and
 * get_contiguous_pop_area / commit_pop. The areas are volatile-qualified for
 * the SPSC topology; a DMA engine writes them as plain memory. */
BENCH_ALIGN static uint32_t pxq_dma_wr_acquire(uintptr_t pp, uintptr_t max)
{
    auto area = rb.get_contiguous_push_area(max);
    *reinterpret_cast<uint8_t **>(pp) = const_cast<uint8_t *>(area.ptr);
    return static_cast<uint32_t>(area.count);
}
BENCH_ALIGN static uint32_t pxq_dma_wr_commit(uintptr_t n, uintptr_t) { rb.commit_push(n); return static_cast<uint32_t>(n); }
BENCH_ALIGN static uint32_t pxq_dma_rd_acquire(uintptr_t pp, uintptr_t max)
{
    auto area = rb.get_contiguous_pop_area(max);
    *reinterpret_cast<const uint8_t **>(pp) = const_cast<const uint8_t *>(area.ptr);
    return static_cast<uint32_t>(area.count);
}
BENCH_ALIGN static uint32_t pxq_dma_rd_release(uintptr_t n, uintptr_t) { rb.commit_pop(n); return static_cast<uint32_t>(n); }

const rb_adapter adapter_pxq = { pxq_reset, pxq_push, pxq_pop, pxq_push_n, pxq_pop_n, 0, 0,
                                 pxq_dma_wr_acquire, pxq_dma_wr_commit, pxq_dma_rd_acquire, pxq_dma_rd_release };

}
