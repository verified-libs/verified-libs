/* Adapter: Vanderhell/micoring, built in its documented SPSC mode
 * (MRING_CONCURRENCY_SPSC_ATOMIC): the config header is generated at build
 * time from the library's own mring_config.h (see libs.mk). The default
 * single-context mode is documented as not safe for ISR sharing.
 * Native block API: mring_push_many/mring_pop_many. */
#include "mring.h"
#include "bench.h"

#if MRING_CONCURRENCY_MODE != MRING_CONCURRENCY_SPSC_ATOMIC
#error "micoring is not in its SPSC mode: build/gen/micoring/mring_config.h missing or wrong (run fetch-libs.sh)"
#endif

static mring_t ring;
static uint8_t storage[RB_SLOTS];

BENCH_ALIGN static void mring_bench_reset(void) { mring_init(&ring, storage, sizeof storage, RB_SLOTS, 1); }

BENCH_ALIGN static uint32_t mring_bench_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    uint8_t b = (uint8_t)v;
    return mring_push(&ring, &b) == MRING_OK;
}

BENCH_ALIGN static uint32_t mring_bench_pop(uintptr_t p, uintptr_t u)
{
    (void)u;
    return mring_pop(&ring, (void *)p) == MRING_OK;
}

BENCH_ALIGN static uint32_t mring_bench_push_n(uintptr_t p, uintptr_t n)
{
    size_t done = 0;
    mring_push_many(&ring, (const void *)p, n, &done);
    return (uint32_t)done;
}

BENCH_ALIGN static uint32_t mring_bench_pop_n(uintptr_t p, uintptr_t n)
{
    size_t done = 0;
    mring_pop_many(&ring, (void *)p, n, &done);
    return (uint32_t)done;
}

const rb_adapter adapter_micoring = {
    mring_bench_reset, mring_bench_push, mring_bench_pop, mring_bench_push_n, mring_bench_pop_n, 0, 0
};
