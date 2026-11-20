/* Adapter: ETL 20.49.0 etl::queue_spsc_locked<uint8_t, RB_SLOTS>. The main
 * loop's calls (push/pop) run under user-supplied lock/unlock functions;
 * here, as ETL's documentation suggests for interrupts, they save PRIMASK
 * and disable interrupts. The interrupt side uses push_from_unlocked /
 * pop_from_unlocked. No block API; push_n/pop_n loop over single calls (as
 * the other ETL adapters). */
#include <new>
#include "etl/queue_spsc_locked.h"
#include "etl/function.h"
#include "bench.h"

static uint32_t saved_primask;
static void lock()
{
    uint32_t p;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(p) :: "memory");
    saved_primask = p;
}
static void unlock() { __asm volatile("msr primask, %0" :: "r"(saved_primask) : "memory"); }
/* The function objects and the queue have non-trivial destructors; as
 * plain statics they would need __dso_handle, so they are created with
 * placement new in static storage (as in ../adapter_etl.cpp). */
using LockFn = etl::function_fv<lock>;
using UnlockFn = etl::function_fv<unlock>;
alignas(LockFn) static unsigned char lock_mem[sizeof(LockFn)];
alignas(UnlockFn) static unsigned char unlock_mem[sizeof(UnlockFn)];

using QLocked = etl::queue_spsc_locked<uint8_t, RB_SLOTS>;
alignas(QLocked) static unsigned char q_mem[sizeof(QLocked)];
static QLocked *q_p;
#define q (*q_p)

BENCH_ALIGN static void etl_lk_reset(void)
{
    if (!q_p) {
        LockFn *l = new (lock_mem) LockFn();
        UnlockFn *u = new (unlock_mem) UnlockFn();
        q_p = new (q_mem) QLocked(*l, *u);
    }
    q.clear();
}
BENCH_ALIGN static uint32_t etl_lk_push(uintptr_t v, uintptr_t) { return q.push(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t etl_lk_pop(uintptr_t p, uintptr_t) { return q.pop(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t etl_lk_isr_push(uintptr_t v, uintptr_t) { return q.push_from_unlocked(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t etl_lk_isr_pop(uintptr_t p, uintptr_t) { return q.pop_from_unlocked(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t etl_lk_push_n(uintptr_t p, uintptr_t n)
{
    const uint8_t *s = reinterpret_cast<const uint8_t *>(p);
    uintptr_t i = 0;
    while (i < n && q.push(s[i])) i++;
    return static_cast<uint32_t>(i);
}
BENCH_ALIGN static uint32_t etl_lk_pop_n(uintptr_t p, uintptr_t n)
{
    uint8_t *d = reinterpret_cast<uint8_t *>(p);
    uintptr_t i = 0;
    while (i < n && q.pop(d[i])) i++;
    return static_cast<uint32_t>(i);
}

extern "C" const rb_adapter adapter_etl_locked = {
    etl_lk_reset, etl_lk_push, etl_lk_pop, etl_lk_push_n, etl_lk_pop_n, etl_lk_isr_push, etl_lk_isr_pop
};
