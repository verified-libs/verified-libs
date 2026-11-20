/* Speed of the modes for more than one producer or consumer: pxq
 * RingBuffer_PackedState with Topology::MPSC<>, SPMC<> and MPMC<> (PRIMASK
 * guards around push, around pop, or both; one core). Timed like every
 * other adapter, from one context: the cost of the mode's own code, not of
 * contention. The stress test of these modes is ../rb-mp-stress. */
#include <stdint.h>


#include "RingBuffer_PackedState.h"
#include "bench.h"

#define PXQ_MP(tag, TOPO)                                                                         \
    static RingBuffer_PackedState<uint8_t, RB_SLOTS, Topology::TOPO<>> rb_##tag;                  \
    extern "C" {                                                                                  \
    BENCH_ALIGN static void pxq_##tag##_reset(void) { rb_##tag.clear(); }                         \
    BENCH_ALIGN static uint32_t pxq_##tag##_push(uintptr_t v, uintptr_t)                          \
    { return rb_##tag.push(static_cast<uint8_t>(v)) ? 1u : 0u; }                                  \
    BENCH_ALIGN static uint32_t pxq_##tag##_pop(uintptr_t p, uintptr_t)                           \
    { return rb_##tag.pop(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }                           \
    BENCH_ALIGN static uint32_t pxq_##tag##_push_n(uintptr_t p, uintptr_t n)                      \
    { return static_cast<uint32_t>(rb_##tag.push_n(reinterpret_cast<const uint8_t *>(p), n)); }   \
    BENCH_ALIGN static uint32_t pxq_##tag##_pop_n(uintptr_t p, uintptr_t n)                       \
    { return static_cast<uint32_t>(rb_##tag.pop_n(reinterpret_cast<uint8_t *>(p), n)); }          \
    extern const rb_adapter adapter_pxq_##tag = { pxq_##tag##_reset, pxq_##tag##_push,            \
        pxq_##tag##_pop, pxq_##tag##_push_n, pxq_##tag##_pop_n, 0, 0 };                           \
    }

PXQ_MP(mpsc, MPSC)
PXQ_MP(spmc, SPMC)
PXQ_MP(mpmc, MPMC)
