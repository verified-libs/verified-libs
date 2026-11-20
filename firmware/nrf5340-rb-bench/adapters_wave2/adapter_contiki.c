/* Adapter: Contiki-NG os/lib/ringbuf (byte ring, 8-bit indices, documented
 * as safe for one interrupt producer and one consumer; uses Contiki's
 * CC_ACCESS_NOW, i.e. volatile accesses). No block API. */
#include "lib/ringbuf.h"
#include "bench.h"

static struct ringbuf rb;
static uint8_t data[RB_SLOTS];

BENCH_ALIGN static void ck_reset(void) { ringbuf_init(&rb, data, RB_SLOTS); }
BENCH_ALIGN static uint32_t ck_push(uintptr_t v, uintptr_t u) { (void)u; return ringbuf_put(&rb, (uint8_t)v) != 0; }

BENCH_ALIGN static uint32_t ck_pop(uintptr_t p, uintptr_t u)
{
    (void)u;
    int c = ringbuf_get(&rb);
    if (c < 0) return 0;
    *(uint8_t *)p = (uint8_t)c;
    return 1;
}
BENCH_DEFINE_LOOP_N(ck)

const rb_adapter adapter_contiki = { ck_reset, ck_push, ck_pop, ck_push_n, ck_pop_n, 0, 0 };
