/* Adapter: kostyk348/lockfree, lf_spsc_ring_t (header-only, C11 atomics,
 * element size 1). No block API. */
#include <string.h>
#include "lockfree.h"
#include "bench.h"

static lf_spsc_ring_t ring;
static uint8_t storage[RB_SLOTS];

BENCH_ALIGN static void kostyk_reset(void) { lf_spsc_init(&ring, storage, RB_SLOTS, 1); }
BENCH_ALIGN static uint32_t kostyk_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    uint8_t b = (uint8_t)v;
    return (uint32_t)lf_spsc_push(&ring, &b);
}
BENCH_ALIGN static uint32_t kostyk_pop(uintptr_t p, uintptr_t u) { (void)u; return (uint32_t)lf_spsc_pop(&ring, (void *)p); }
BENCH_DEFINE_LOOP_N(kostyk)

const rb_adapter adapter_kostyk = { kostyk_reset, kostyk_push, kostyk_pop, kostyk_push_n, kostyk_pop_n, 0, 0 };
