/* Adapter: embeddedartistry/embedded-resources, examples/c/circular_buffer,
 * the "no_modulo_threadsafe" implementation (the variant documented as safe
 * for one producer and one consumer). circular_buf_init() allocates the
 * handle with malloc (served by bench_heap.c, once). No block API. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h> /* circular_buffer.h uses these types but does not include them */
#include "circular_buffer.h"
#include "bench.h"

static cbuf_handle_t cb;
static uint8_t data[RB_SLOTS];

BENCH_ALIGN static void ea_reset(void)
{
    if (!cb) cb = circular_buf_init(data, sizeof data);
    circular_buf_reset(cb);
}
BENCH_ALIGN static uint32_t ea_push(uintptr_t v, uintptr_t u) { (void)u; return circular_buf_try_put(cb, (uint8_t)v) == 0; }
BENCH_ALIGN static uint32_t ea_pop(uintptr_t p, uintptr_t u) { (void)u; return circular_buf_get(cb, (uint8_t *)p) == 0; }
BENCH_DEFINE_LOOP_N(ea)

const rb_adapter adapter_ea_cbuf = { ea_reset, ea_push, ea_pop, ea_push_n, ea_pop_n, 0, 0 };
