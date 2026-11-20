/* Adapter: DNedic/lockfree 3.0.1, lockfree::spsc::RingBuf<uint8_t, RB_SLOTS>
 * (header only, C++11 atomics). The README: "thread and interrupt safe for
 * concurrent use without having to use mutual exclusion mechanisms" in each
 * structure's use case (SPSC here). Write/Read move all bytes or none, so
 * push_n/pop_n first ask GetFree/GetAvailable and move what fits, which is
 * what the other adapters' block calls do. Usable capacity RB_SLOTS - 1,
 * like the others (one slot kept free inside the library). */
#include <new>
#include "lockfree/lockfree.hpp"
#include "bench.h"

static lockfree::spsc::RingBuf<uint8_t, RB_SLOTS> lrb;

BENCH_ALIGN static void lf_reset(void) { new (&lrb) lockfree::spsc::RingBuf<uint8_t, RB_SLOTS>(); }
BENCH_ALIGN static uint32_t lf_push(uintptr_t v, uintptr_t)
{
    uint8_t b = static_cast<uint8_t>(v);
    return lrb.Write(&b, 1) ? 1u : 0u;
}
BENCH_ALIGN static uint32_t lf_pop(uintptr_t p, uintptr_t) { return lrb.Read(reinterpret_cast<uint8_t *>(p), 1) ? 1u : 0u; }
BENCH_ALIGN static uint32_t lf_push_n(uintptr_t p, uintptr_t n)
{
    size_t k = lrb.GetFree();
    if (k > n) k = n;
    return (k && lrb.Write(reinterpret_cast<const uint8_t *>(p), k)) ? static_cast<uint32_t>(k) : 0u;
}
BENCH_ALIGN static uint32_t lf_pop_n(uintptr_t p, uintptr_t n)
{
    size_t k = lrb.GetAvailable();
    if (k > n) k = n;
    return (k && lrb.Read(reinterpret_cast<uint8_t *>(p), k)) ? static_cast<uint32_t>(k) : 0u;
}

extern "C" const rb_adapter adapter_lockfree = { lf_reset, lf_push, lf_pop, lf_push_n, lf_pop_n, 0, 0 };
