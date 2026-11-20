/* Single-context variant: micoring in its default build
 * (MRING_CONCURRENCY_SINGLE_CONTEXT, the library's own mring_config.h, not
 * the generated SPSC one). mring.c is compiled here a second time, so its
 * public functions are renamed (mring_* -> mring_sc_*) to coexist with the
 * SPSC build; the library source itself is unchanged. */
#define mring_capacity      mring_sc_capacity
#define mring_clear         mring_sc_clear
#define mring_count         mring_sc_count
#define mring_element_size  mring_sc_element_size
#define mring_err_str       mring_sc_err_str
#define mring_free          mring_sc_free
#define mring_init          mring_sc_init
#define mring_is_empty      mring_sc_is_empty
#define mring_is_full       mring_sc_is_full
#define mring_peek          mring_sc_peek
#define mring_peek_at       mring_sc_peek_at
#define mring_pop           mring_sc_pop
#define mring_pop_many      mring_sc_pop_many
#define mring_push          mring_sc_push
#define mring_push_many     mring_sc_push_many
#define mring_push_overwrite mring_sc_push_overwrite
#include "mring.c"
#include "bench.h"

#if MRING_CONCURRENCY_MODE != MRING_CONCURRENCY_SINGLE_CONTEXT
#error "expected the default single-context configuration"
#endif

static mring_t ring;
static uint8_t storage[RB_SLOTS];

BENCH_ALIGN static void msc_reset(void) { mring_init(&ring, storage, sizeof storage, RB_SLOTS, 1); }
BENCH_ALIGN static uint32_t msc_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    uint8_t b = (uint8_t)v;
    return mring_push(&ring, &b) == MRING_OK;
}
BENCH_ALIGN static uint32_t msc_pop(uintptr_t p, uintptr_t u) { (void)u; return mring_pop(&ring, (void *)p) == MRING_OK; }
BENCH_ALIGN static uint32_t msc_push_n(uintptr_t p, uintptr_t n)
{
    size_t done = 0;
    mring_push_many(&ring, (const void *)p, n, &done);
    return (uint32_t)done;
}
BENCH_ALIGN static uint32_t msc_pop_n(uintptr_t p, uintptr_t n)
{
    size_t done = 0;
    mring_pop_many(&ring, (void *)p, n, &done);
    return (uint32_t)done;
}

const rb_adapter adapter_micoring_sc = { msc_reset, msc_push, msc_pop, msc_push_n, msc_pop_n, 0, 0 };
