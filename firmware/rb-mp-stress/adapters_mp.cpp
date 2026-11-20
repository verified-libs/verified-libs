/* Adapters for the multi-producer / multi-consumer stress test, in the
 * topologies the library itself offers: pxq RingBuffer_PackedState with
 * Topology::MPSC<> and Topology::MPMC<> (PRIMASK guards around push, resp.
 * push and pop; one core). The other libraries in this test use their benchmark
 * adapters (../nrf5340-rb-bench), which already are their documented
 * ISR-safe configuration. */
#include <stdint.h>


#include "RingBuffer_PackedState.h"
#include "bench.h"

using RbMpsc = RingBuffer_PackedState<uint8_t, RB_SLOTS, Topology::MPSC<>>;
using RbSpmc = RingBuffer_PackedState<uint8_t, RB_SLOTS, Topology::SPMC<>>;
using RbMpmc = RingBuffer_PackedState<uint8_t, RB_SLOTS, Topology::MPMC<>>;
/* 1.5.0: producer reservations, two open at a time (interrupt A, and B
 * preempting it between its reserve and its commit) */
using RbMpscR = RingBuffer_PackedState<uint8_t, RB_SLOTS, Topology::MPSC<PrimaskLock, 2>>;
static RbMpscR rb_mpsc_r;
static RbMpsc rb_mpsc;
static RbSpmc rb_spmc;
static RbMpmc rb_mpmc;

extern "C" {

BENCH_ALIGN static void pxq_mpsc_reset(void) { rb_mpsc.clear(); }
BENCH_ALIGN static uint32_t pxq_mpsc_push(uintptr_t v, uintptr_t) { return rb_mpsc.push(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t pxq_mpsc_pop(uintptr_t p, uintptr_t) { return rb_mpsc.pop(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }

BENCH_ALIGN static void pxq_spmc_reset(void) { rb_spmc.clear(); }
BENCH_ALIGN static uint32_t pxq_spmc_push(uintptr_t v, uintptr_t) { return rb_spmc.push(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t pxq_spmc_pop(uintptr_t p, uintptr_t) { return rb_spmc.pop(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }

BENCH_ALIGN static void pxq_mpmc_reset(void) { rb_mpmc.clear(); }
BENCH_ALIGN static uint32_t pxq_mpmc_push(uintptr_t v, uintptr_t) { return rb_mpmc.push(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t pxq_mpmc_pop(uintptr_t p, uintptr_t) { return rb_mpmc.pop(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }

/* push = reserve(1), write, a pause of 0-31 loop turns (taken from the
 * value, so no shared state), commit: the slow fill outside the lock that
 * reservations are made for, which leaves interrupt B time to reserve and
 * commit its own value in the middle. The consumer must see each producer's
 * values complete and in order (the test's per-producer sequence check);
 * a slot made visible before its commit would hold a stale value. */
BENCH_ALIGN static void pxq_mpscr_reset(void) { rb_mpsc_r.clear(); }
BENCH_ALIGN static uint32_t pxq_mpscr_push(uintptr_t v, uintptr_t)
{
    auto r = rb_mpsc_r.reserve(1);
    if (!r.count) return 0u;
    r.ptr[0] = static_cast<uint8_t>(v);
    for (volatile uint32_t i = 0; i < ((static_cast<uint32_t>(v) * 37u) & 31u); i++) {}
    rb_mpsc_r.commit(r);
    return 1u;
}
BENCH_ALIGN static uint32_t pxq_mpscr_pop(uintptr_t p, uintptr_t) { return rb_mpsc_r.pop(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }

extern const rb_adapter adapter_pxq_mpsc_resv = { pxq_mpscr_reset, pxq_mpscr_push, pxq_mpscr_pop, 0, 0, 0, 0 };
extern const rb_adapter adapter_pxq_mpsc = { pxq_mpsc_reset, pxq_mpsc_push, pxq_mpsc_pop, 0, 0, 0, 0 };
extern const rb_adapter adapter_pxq_spmc = { pxq_spmc_reset, pxq_spmc_push, pxq_spmc_pop, 0, 0, 0, 0 };
extern const rb_adapter adapter_pxq_mpmc = { pxq_mpmc_reset, pxq_mpmc_push, pxq_mpmc_pop, 0, 0, 0, 0 };

}
