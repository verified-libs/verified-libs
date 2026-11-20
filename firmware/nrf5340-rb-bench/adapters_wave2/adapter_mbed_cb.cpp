/* Adapter: Mbed OS CircularBuffer (platform/include/platform/CircularBuffer.h,
 * Mbed CE mbed-os-7.1.0; Arm's Mbed OS reached end of life in July 2026,
 * Mbed CE is the community continuation), built outside Mbed with the
 * minimal shims in ../shims/mbed. Every push/pop runs in Mbed's critical
 * section (interrupts off). push() overwrites the oldest data when the
 * buffer is full, so the adapter checks full()/size() first: only the
 * producer makes the buffer fuller, so the check cannot go stale.
 * BufferSize = RB_SLOTS - 1 (a _full flag, no reserved slot): the same
 * usable capacity as the other adapters. No zero-copy API. */
#include <stdint.h>
#include <algorithm>   /* CircularBuffer.h uses std::copy without including it */
#include <new>
#include "platform/CircularBuffer.h"
#include "bench.h"

extern "C" {
volatile uint32_t vl_mbed_cs_depth;
volatile bool vl_mbed_cs_irq_were_on;
}

namespace {
/* Placement new into static storage: CircularBuffer has a user-provided
 * destructor, so a global object would register an atexit destructor (and
 * pull in the C library's heap) on a bare-metal build. */
using CB = mbed::CircularBuffer<uint8_t, RB_SLOTS - 1, uint32_t>;
alignas(CB) unsigned char cb_mem[sizeof(CB)];
CB *cbp;
#define cb (*cbp)
}

extern "C" {

BENCH_ALIGN static void mbed_reset(void)
{
    if (!cbp) cbp = new (cb_mem) CB();
    cb.reset();
}
BENCH_ALIGN static uint32_t mbed_push(uintptr_t v, uintptr_t)
{
    if (cb.full()) return 0;
    cb.push(static_cast<uint8_t>(v));
    return 1;
}
BENCH_ALIGN static uint32_t mbed_pop(uintptr_t p, uintptr_t)
{
    uint8_t d;
    if (!cb.pop(d)) return 0;
    *reinterpret_cast<uint8_t *>(p) = d;
    return 1;
}
BENCH_ALIGN static uint32_t mbed_push_n(uintptr_t p, uintptr_t n)
{
    uint32_t space = (RB_SLOTS - 1) - cb.size();
    if (n > space) n = space;
    if (n) cb.push(reinterpret_cast<const uint8_t *>(p), static_cast<uint32_t>(n));
    return static_cast<uint32_t>(n);
}
BENCH_ALIGN static uint32_t mbed_pop_n(uintptr_t p, uintptr_t n)
{
    return cb.pop(reinterpret_cast<uint8_t *>(p), static_cast<uint32_t>(n));
}

const rb_adapter adapter_mbed_cb = { mbed_reset, mbed_push, mbed_pop, mbed_push_n, mbed_pop_n, 0, 0 };

}
