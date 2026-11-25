/* ETL etl::pool (include/etl/pool.h), pinned in libs.lock. The header
 * documents nothing about threads or interrupts and has no lock; this
 * adapter adds none (a board benchmark would time it as shipped, the
 * stress test would need a lock of ours, as for wizard97). */
#include "pool.h"
#include <etl/pool.h>

namespace {
struct Block { uint8_t bytes[POOL_BLOCK_SIZE]; };
etl::pool<Block, POOL_BLOCKS> pool;

void etl_init() { pool.release_all(); }
uintptr_t etl_alloc(uintptr_t, uintptr_t) { return reinterpret_cast<uintptr_t>(pool.allocate()); }
uint32_t etl_free(uintptr_t a, uintptr_t)
{
    pool.release(reinterpret_cast<const Block *>(a));
    return 1;
}
/* The blocks lie inside the pool object (etl::generic_pool keeps its
 * buffer as a member), so the object's own extent bounds them. */
void etl_region(uintptr_t *lo, uintptr_t *hi)
{
    *lo = reinterpret_cast<uintptr_t>(&pool);
    *hi = *lo + sizeof(pool);
}
}

extern "C" const pool_adapter adapter_etl_pool = {
    "ETL etl::pool (C++)", etl_init, etl_alloc, etl_free, nullptr, nullptr, etl_region, alignof(Block)
};
