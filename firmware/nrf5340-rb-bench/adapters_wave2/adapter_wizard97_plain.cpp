/* Adapter: wizard97/Embedded_RingBuf_CPP, RingBufCPP<uint8_t, 128>, AS
 * SHIPPED for a non-Arduino target: RB_ATOMIC_START/END expand to nothing,
 * and the header itself warns "Operations on the buffer in ISRs are not
 * safe! Implement RB_ATOMIC_START and RB_ATOMIC_END macros for safe ISR
 * operation!". Measured to show what that warning means in practice; see
 * adapter_wizard97_primask.cpp for the configuration the README asks for.
 * No block API. */
#include <stdint.h>
#include <stddef.h> /* RingBufCPP.h uses size_t but does not include it */
#include "RingBufCPP.h"
#include "bench.h"

static RingBufCPP<uint8_t, RB_SLOTS> rb;

extern "C" {

BENCH_ALIGN static void w97p_reset(void)
{
    uint8_t d;
    while (rb.pull(&d)) {}
}
BENCH_ALIGN static uint32_t w97p_push(uintptr_t v, uintptr_t)
{
    const uint8_t b = static_cast<uint8_t>(v);
    return rb.add(b) ? 1u : 0u;
}
BENCH_ALIGN static uint32_t w97p_pop(uintptr_t p, uintptr_t) { return rb.pull(reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }
BENCH_DEFINE_LOOP_N(w97p)

const rb_adapter adapter_wizard97_plain = { w97p_reset, w97p_push, w97p_pop, w97p_push_n, w97p_pop_n, 0, 0 };

}
