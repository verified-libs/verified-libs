/* The null configuration of the size measure (onepool.py sizes_of): a pool
 * that does nothing, linked once per board into an image that is never
 * flashed. A configuration's sizes are the symbols its image has and this
 * image has not (as ../sizes.py against the empty program), so the harness,
 * the reference, the start-up code and the C library count for neither.
 * Its own names begin with "nullpool_", so none meets a configuration's. */
#include "../pool.h"

static uint32_t nullpool_canary[2][POOL_CANARY_WORDS];

static void nullpool_init(void) {}
static uintptr_t nullpool_alloc(uintptr_t a, uintptr_t b) { (void)a; (void)b; return 0; }
static uint32_t nullpool_free(uintptr_t a, uintptr_t b) { (void)a; (void)b; return 1; }
static void nullpool_region(uintptr_t *lo, uintptr_t *hi) { *lo = *hi = 0; }

const pool_adapter adapter_null = {
    "null (size measure only)", nullpool_init, nullpool_alloc, nullpool_free, nullpool_region, 1,
    nullpool_canary[0], nullpool_canary[1]
};
