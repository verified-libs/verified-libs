/* Adapter: Saikiran4255/rt-spsc, rtq::SpscQueue<uint8_t, 128> (header-only,
 * acquire/release indices, documented for ISR -> task). No block API. */
#include <stdint.h>
#include "rtq/spsc_queue.hpp"
#include "bench.h"

static rtq::SpscQueue<uint8_t, RB_SLOTS> q;

extern "C" {

BENCH_ALIGN static void rts_reset(void)
{
    uint8_t d;
    while (q.pop(d)) {}
}
BENCH_ALIGN static uint32_t rts_push(uintptr_t v, uintptr_t) { return q.push(static_cast<uint8_t>(v)) ? 1u : 0u; }
BENCH_ALIGN static uint32_t rts_pop(uintptr_t p, uintptr_t) { return q.pop(*reinterpret_cast<uint8_t *>(p)) ? 1u : 0u; }
BENCH_DEFINE_LOOP_N(rts)

const rb_adapter adapter_rtspsc = { rts_reset, rts_push, rts_pop, rts_push_n, rts_pop_n, 0, 0 };

}
