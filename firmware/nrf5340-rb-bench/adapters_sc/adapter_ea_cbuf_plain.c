/* Single-context variant: Embedded Artistry circular_buffer.c, the basic
 * implementation (not the "no_modulo_threadsafe" one in the benchmark's
 * SPSC set). It is compiled here next to the threadsafe one, so its public
 * functions are renamed (circular_buf_* -> ea_plain_*); the library source
 * is unchanged. circular_buf_init() allocates the handle with malloc
 * (bench_heap.c, once). try_put = put that fails when full, as in the
 * threadsafe adapter. */
#define circular_buf_capacity ea_plain_capacity
#define circular_buf_empty    ea_plain_empty
#define circular_buf_free     ea_plain_free
#define circular_buf_full     ea_plain_full
#define circular_buf_get      ea_plain_get
#define circular_buf_init     ea_plain_init
#define circular_buf_peek     ea_plain_peek
#define circular_buf_put      ea_plain_put
#define circular_buf_reset    ea_plain_reset
#define circular_buf_size     ea_plain_size
#define circular_buf_try_put  ea_plain_try_put
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h> /* circular_buffer.h uses these types but does not include them */
#include "circular_buffer.c"
#include "bench.h"

static cbuf_handle_t cb;
static uint8_t data[RB_SLOTS];

BENCH_ALIGN static void eap_reset(void)
{
    if (!cb) cb = circular_buf_init(data, sizeof data);
    circular_buf_reset(cb);
}
BENCH_ALIGN static uint32_t eap_push(uintptr_t v, uintptr_t u) { (void)u; return circular_buf_try_put(cb, (uint8_t)v) == 0; }
BENCH_ALIGN static uint32_t eap_pop(uintptr_t p, uintptr_t u) { (void)u; return circular_buf_get(cb, (uint8_t *)p) == 0; }
BENCH_DEFINE_LOOP_N(eap)

const rb_adapter adapter_ea_cbuf_plain = { eap_reset, eap_push, eap_pop, eap_push_n, eap_pop_n, 0, 0 };
