/* Adapter: diffstorm/cb, default configuration (uint8_t items, relaxed
 * atomic indices + memory barriers chosen by its detection headers,
 * overwrite off). No block API. */
#include "cb.h"
#include "bench.h"

static cb ring;
static CbItem storage[RB_SLOTS];

BENCH_ALIGN static void ds_reset(void) { cb_init(&ring, storage, RB_SLOTS); }
BENCH_ALIGN static uint32_t ds_push(uintptr_t v, uintptr_t u) { (void)u; return cb_insert(&ring, (CbItem)v); }
BENCH_ALIGN static uint32_t ds_pop(uintptr_t p, uintptr_t u) { (void)u; return cb_remove(&ring, (CbItem *)p); }
BENCH_DEFINE_LOOP_N(ds)

const rb_adapter adapter_diffstorm = { ds_reset, ds_push, ds_pop, ds_push_n, ds_pop_n, 0, 0 };
