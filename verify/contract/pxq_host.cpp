/* pxq RingBuffer_PackedState in its locking topologies for the host
 * contract check: the same configurations as ../../firmware/rb-mp-stress
 * (adapters_mp.cpp), with HostLock (host_irq.h) instead of PrimaskLock,
 * which exists only on Cortex-M. The SPSC configuration needs no lock and
 * is the benchmark's own adapter (adapter_pxq.cpp), built unchanged. */
#include <stdint.h>
#include "host_irq.h"
#include "RingBuffer_PackedState.h"
#include "bench.h"

using RbMpsc  = RingBuffer_PackedState<uint8_t, RB_SLOTS, Topology::MPSC<HostLock>>;
using RbSpmc  = RingBuffer_PackedState<uint8_t, RB_SLOTS, Topology::SPMC<HostLock>>;
using RbMpmc  = RingBuffer_PackedState<uint8_t, RB_SLOTS, Topology::MPMC<HostLock>>;
using RbMpscR = RingBuffer_PackedState<uint8_t, RB_SLOTS, Topology::MPSC<HostLock, 2>>;
static RbMpsc rb_mpsc;
static RbSpmc rb_spmc;
static RbMpmc rb_mpmc;
static RbMpscR rb_mpscr;

#define PXQ_ADAPTER(name, rb)                                                                  \
    static void name##_reset(void) { rb.clear(); }                                             \
    static uint32_t name##_push(uintptr_t v, uintptr_t) { return rb.push((uint8_t)v) ? 1u : 0u; } \
    static uint32_t name##_pop(uintptr_t p, uintptr_t) { return rb.pop(*(uint8_t *)p) ? 1u : 0u; } \
    static uint32_t name##_push_n(uintptr_t p, uintptr_t n) { return (uint32_t)rb.push_n((const uint8_t *)p, n); } \
    static uint32_t name##_pop_n(uintptr_t p, uintptr_t n) { return (uint32_t)rb.pop_n((uint8_t *)p, n); }

extern "C" {
PXQ_ADAPTER(h_mpsc, rb_mpsc)
PXQ_ADAPTER(h_spmc, rb_spmc)
PXQ_ADAPTER(h_mpmc, rb_mpmc)

/* 1.5.0 producer reservations: push = reserve(1), write, commit (an
 * interrupt can come between any two instructions of it) */
static void h_mpscr_reset(void) { rb_mpscr.clear(); }
static uint32_t h_mpscr_push(uintptr_t v, uintptr_t)
{
    auto r = rb_mpscr.reserve(1);
    if (!r.count) return 0u;
    r.ptr[0] = (uint8_t)v;
    rb_mpscr.commit(r);
    return 1u;
}
static uint32_t h_mpscr_pop(uintptr_t p, uintptr_t) { return rb_mpscr.pop(*(uint8_t *)p) ? 1u : 0u; }
/* a block through one reservation */
static uint32_t h_mpscr_push_n(uintptr_t p, uintptr_t n)
{
    auto r = rb_mpscr.reserve(n);
    for (uint32_t i = 0; i < r.count; i++) r.ptr[i] = ((const uint8_t *)p)[i];
    if (r.count) rb_mpscr.commit(r);
    return (uint32_t)r.count;
}
static uint32_t h_mpscr_pop_n(uintptr_t p, uintptr_t n) { return (uint32_t)rb_mpscr.pop_n((uint8_t *)p, n); }

extern const rb_adapter adapter_pxq_h_mpsc  = { h_mpsc_reset, h_mpsc_push, h_mpsc_pop, h_mpsc_push_n, h_mpsc_pop_n, 0, 0, 0, 0, 0, 0 };
extern const rb_adapter adapter_pxq_h_spmc  = { h_spmc_reset, h_spmc_push, h_spmc_pop, h_spmc_push_n, h_spmc_pop_n, 0, 0, 0, 0, 0, 0 };
extern const rb_adapter adapter_pxq_h_mpmc  = { h_mpmc_reset, h_mpmc_push, h_mpmc_pop, h_mpmc_push_n, h_mpmc_pop_n, 0, 0, 0, 0, 0, 0 };
extern const rb_adapter adapter_pxq_h_mpscr = { h_mpscr_reset, h_mpscr_push, h_mpscr_pop, h_mpscr_push_n, h_mpscr_pop_n, 0, 0, 0, 0, 0, 0 };
}
