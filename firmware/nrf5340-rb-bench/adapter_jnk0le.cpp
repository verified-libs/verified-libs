/* Adapter: jnk0le/Ring-Buffer (C++), Ringbuffer<uint8_t, RB_SLOTS>,
 * default template arguments (fake_tso = false: real acquire/release).
 * Unmasked indices, so all RB_SLOTS slots are usable. */
#include <stdint.h>
#include "ringbuffer.hpp"
#include "bench.h"

static jnk0le::Ringbuffer<uint8_t, RB_SLOTS> rb;

extern "C" {

BENCH_ALIGN static void jnk_reset(void) { rb.consumerClear(); }
BENCH_ALIGN static uint32_t jnk_push(uintptr_t v, uintptr_t) { return rb.insert(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t jnk_pop(uintptr_t p, uintptr_t) { return rb.remove(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t jnk_push_n(uintptr_t p, uintptr_t n)
{
    return static_cast<uint32_t>(rb.writeBuff(reinterpret_cast<const uint8_t *>(p), n));
}
BENCH_ALIGN static uint32_t jnk_pop_n(uintptr_t p, uintptr_t n)
{
    return static_cast<uint32_t>(rb.readBuff(reinterpret_cast<uint8_t *>(p), n));
}

const rb_adapter adapter_jnk0le = { jnk_reset, jnk_push, jnk_pop, jnk_push_n, jnk_pop_n, 0, 0 };

}
