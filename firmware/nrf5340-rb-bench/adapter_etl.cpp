/* Adapters: ETLCPP/etl (C++), two SPSC queues.
 *
 * etl::queue_spsc_isr<uint8_t, RB_SLOTS, Access>: shares a size counter
 * between both sides. Calls from the main loop (push/pop) disable
 * interrupts around the operation via Access::lock/unlock; calls from the
 * interrupt use push_from_isr/pop_from_isr without locking. The adapter
 * exposes both, and the stress test uses the ISR variants in the ISR.
 *
 * etl::queue_spsc_atomic<uint8_t, RB_SLOTS>: lock-free, etl::atomic indices.
 *
 * Neither has a block API; push_n/pop_n loop over single operations, which
 * is what a user would write. Both hold RB_SLOTS elements. */
#include <stdint.h>
#include "etl/queue_spsc_isr.h"
#include "etl/queue_spsc_atomic.h"
#include "bench.h"

namespace {

/* Interrupt lock as recommended for queue_spsc_isr: save PRIMASK, disable
 * interrupts, restore. */
struct Access {
    static inline uint32_t saved;
    static void lock()
    {
        uint32_t p;
        __asm volatile("mrs %0, primask\n cpsid i" : "=r"(p) :: "memory");
        saved = p;
    }
    static void unlock() { __asm volatile("msr primask, %0" ::"r"(saved) : "memory"); }
};

/* The queues have non-trivial destructors; as plain statics they would
 * register atexit handlers (and pull in stdio). Construct them once with
 * placement new in static storage instead, as bare-metal firmware does. */
using QIsr = etl::queue_spsc_isr<uint8_t, RB_SLOTS, Access>;
using QAtomic = etl::queue_spsc_atomic<uint8_t, RB_SLOTS>;
alignas(QIsr) unsigned char q_isr_mem[sizeof(QIsr)];
alignas(QAtomic) unsigned char q_atomic_mem[sizeof(QAtomic)];
QIsr *q_isr_p;
QAtomic *q_atomic_p;

} // namespace

#include <new>
#define q_isr (*q_isr_p)
#define q_atomic (*q_atomic_p)

extern "C" {

/* --- queue_spsc_isr --- */
BENCH_ALIGN static void etl_isr_reset(void)
{
    if (!q_isr_p) q_isr_p = new (q_isr_mem) QIsr();
    q_isr.clear();
}
BENCH_ALIGN static uint32_t etl_isr_push(uintptr_t v, uintptr_t) { return q_isr.push(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t etl_isr_pop(uintptr_t p, uintptr_t) { return q_isr.pop(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t etl_isr_push_from_isr(uintptr_t v, uintptr_t)
{
    return q_isr.push_from_isr(static_cast<uint8_t>(v)) ? 1u : 0u;
}
BENCH_ALIGN static uint32_t etl_isr_pop_from_isr(uintptr_t p, uintptr_t)
{
    return q_isr.pop_from_isr(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u;
}
BENCH_ALIGN static uint32_t etl_isr_push_n(uintptr_t p, uintptr_t n)
{
    const uint8_t *s = reinterpret_cast<const uint8_t *>(p);
    uint32_t i = 0;
    while (i < n && q_isr.push(s[i])) i++;
    return i;
}
BENCH_ALIGN static uint32_t etl_isr_pop_n(uintptr_t p, uintptr_t n)
{
    uint8_t *d = reinterpret_cast<uint8_t *>(p);
    uint32_t i = 0;
    while (i < n && q_isr.pop(d[i])) i++;
    return i;
}

const rb_adapter adapter_etl_isr = {
    etl_isr_reset, etl_isr_push, etl_isr_pop, etl_isr_push_n, etl_isr_pop_n,
    etl_isr_push_from_isr, etl_isr_pop_from_isr
};

/* --- queue_spsc_atomic --- */
BENCH_ALIGN static void etl_at_reset(void)
{
    if (!q_atomic_p) q_atomic_p = new (q_atomic_mem) QAtomic();
    q_atomic.clear();
}
BENCH_ALIGN static uint32_t etl_at_push(uintptr_t v, uintptr_t) { return q_atomic.push(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t etl_at_pop(uintptr_t p, uintptr_t) { return q_atomic.pop(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t etl_at_push_n(uintptr_t p, uintptr_t n)
{
    const uint8_t *s = reinterpret_cast<const uint8_t *>(p);
    uint32_t i = 0;
    while (i < n && q_atomic.push(s[i])) i++;
    return i;
}
BENCH_ALIGN static uint32_t etl_at_pop_n(uintptr_t p, uintptr_t n)
{
    uint8_t *d = reinterpret_cast<uint8_t *>(p);
    uint32_t i = 0;
    while (i < n && q_atomic.pop(d[i])) i++;
    return i;
}

const rb_adapter adapter_etl_atomic = { etl_at_reset, etl_at_push, etl_at_pop, etl_at_push_n, etl_at_pop_n, 0, 0 };

}
