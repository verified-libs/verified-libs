/* Adapter: RIOT-OS sys/tsrb ("thread-safe ring buffer"). Every operation
 * runs with interrupts disabled via RIOT's irq.h (shimmed with RIOT's
 * Cortex-M semantics, shims/riot/irq.h). Native block API: tsrb_add/tsrb_get. */
#include "tsrb.h"
#include "bench.h"

static tsrb_t rb;
static uint8_t buf[RB_SLOTS];

BENCH_ALIGN static void tsrb_bench_reset(void) { tsrb_init(&rb, buf, RB_SLOTS); }
BENCH_ALIGN static uint32_t tsrb_bench_push(uintptr_t v, uintptr_t u) { (void)u; return tsrb_add_one(&rb, (uint8_t)v) == 0; }

BENCH_ALIGN static uint32_t tsrb_bench_pop(uintptr_t p, uintptr_t u)
{
    (void)u;
    int c = tsrb_get_one(&rb);
    if (c < 0) return 0;
    *(uint8_t *)p = (uint8_t)c;
    return 1;
}

BENCH_ALIGN static uint32_t tsrb_bench_push_n(uintptr_t p, uintptr_t n) { return (uint32_t)tsrb_add(&rb, (const uint8_t *)p, n); }
BENCH_ALIGN static uint32_t tsrb_bench_pop_n(uintptr_t p, uintptr_t n) { return (uint32_t)tsrb_get(&rb, (uint8_t *)p, n); }

const rb_adapter adapter_riot_tsrb = {
    tsrb_bench_reset, tsrb_bench_push, tsrb_bench_pop, tsrb_bench_push_n, tsrb_bench_pop_n, 0, 0
};
