/* Adapter: polycratia/spscring, spscring::ring<uint8_t, 128>.
 * The header uses try/catch in its batch functions, so this file must be
 * compiled with exceptions enabled (see libs.mk); with the usual embedded
 * -fno-exceptions it does not compile. Native block API: try_push_n /
 * try_pop_n. Built with placement new (no atexit destructor). */
#include <new>
#include <stdint.h>
#include "spscring/spscring.hpp"
#include "bench.h"

namespace {
using R = spscring::ring<uint8_t, RB_SLOTS>;
alignas(R) unsigned char r_mem[sizeof(R)];
R *r;
}

extern "C" {

BENCH_ALIGN static void poly_reset(void)
{
    if (!r) r = new (r_mem) R();
    while (r->try_pop()) {}
}
BENCH_ALIGN static uint32_t poly_push(uintptr_t v, uintptr_t) { return r->try_push(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t poly_pop(uintptr_t p, uintptr_t)
{
    auto v = r->try_pop();
    if (!v) return 0;
    *reinterpret_cast<uint8_t *>(p) = *v;
    return 1;
}
BENCH_ALIGN static uint32_t poly_push_n(uintptr_t p, uintptr_t n)
{
    return static_cast<uint32_t>(r->try_push_n(reinterpret_cast<const uint8_t *>(p), n));
}
BENCH_ALIGN static uint32_t poly_pop_n(uintptr_t p, uintptr_t n)
{
    return static_cast<uint32_t>(r->try_pop_n(reinterpret_cast<uint8_t *>(p), n));
}

const rb_adapter adapter_polycratia = { poly_reset, poly_push, poly_pop, poly_push_n, poly_pop_n, 0, 0 };

}
