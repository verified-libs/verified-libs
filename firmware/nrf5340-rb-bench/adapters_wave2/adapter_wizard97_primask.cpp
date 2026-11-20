/* Adapter: wizard97/Embedded_RingBuf_CPP configured as its header asks for
 * non-AVR/ESP8266 targets: RB_ATOMIC_START/END implemented by the user, here
 * as save PRIMASK + disable interrupts / restore PRIMASK.
 * The element type is a one-byte struct, so this instantiation can never be
 * merged by the linker with the unprotected one in
 * adapter_wizard97_plain.cpp (different macro expansions). No block API. */
#include <stddef.h> /* RingBufCPP.h uses size_t but does not include it */
#include <stdint.h>
#include "RingBufHelpers.h"
#undef RB_ATOMIC_START
#undef RB_ATOMIC_END
#define RB_ATOMIC_START                                                          \
    {                                                                            \
        uint32_t rb_primask_;                                                    \
        __asm volatile("mrs %0, primask\n cpsid i" : "=r"(rb_primask_)::"memory");
#define RB_ATOMIC_END                                                            \
        __asm volatile("msr primask, %0" ::"r"(rb_primask_) : "memory");         \
    }
#include "RingBufCPP.h"
#include "bench.h"

namespace {
struct Byte { uint8_t v; };
RingBufCPP<Byte, RB_SLOTS> rb;
}

extern "C" {

BENCH_ALIGN static void w97m_reset(void)
{
    Byte d;
    while (rb.pull(&d)) {}
}
BENCH_ALIGN static uint32_t w97m_push(uintptr_t v, uintptr_t)
{
    const Byte b{ static_cast<uint8_t>(v) };
    return rb.add(b) ? 1u : 0u;
}
BENCH_ALIGN static uint32_t w97m_pop(uintptr_t p, uintptr_t)
{
    Byte d;
    if (!rb.pull(&d)) return 0;
    *reinterpret_cast<uint8_t *>(p) = d.v;
    return 1;
}
BENCH_DEFINE_LOOP_N(w97m)

const rb_adapter adapter_wizard97_primask = { w97m_reset, w97m_push, w97m_pop, w97m_push_n, w97m_pop_n, 0, 0 };

}
