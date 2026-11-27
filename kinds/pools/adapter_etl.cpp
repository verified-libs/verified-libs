/* ETL etl::pool (include/etl/pool.h), pinned in libs.lock. The header
 * documents nothing about threads or interrupts and has no lock; this
 * adapter adds none. The blocks lie inside the pool object (etl::generic_pool
 * keeps its buffer as a member), so the object's own extent bounds them.
 * The pool has a non-trivial destructor; as a plain static it would need
 * __dso_handle on the boards (no start files), so it is constructed with
 * placement new in static storage, as version 2's ETL adapters do
 * (firmware/nrf5340-rb-bench/adapters_wave2/adapter_etl_locked.cpp): once,
 * then init() gives every block back with release_all(). */
#include <new>
#include "pool.h"
#include <etl/pool.h>

namespace {
struct Block { uint8_t bytes[POOL_BLOCK_SIZE]; };
typedef etl::pool<Block, POOL_BLOCKS> Pool;
POOL_GUARDED(alignas(Pool) unsigned char pool[sizeof(Pool)];) g;
Pool *pool() { return std::launder(reinterpret_cast<Pool *>(g.pool)); }
bool made = false;

void etl_init()
{
    if (!made) { new (g.pool) Pool(); made = true; }
    pool()->release_all();
}
uintptr_t etl_alloc(uintptr_t, uintptr_t) { return reinterpret_cast<uintptr_t>(pool()->allocate()); }
uint32_t etl_free(uintptr_t a, uintptr_t)
{
    pool()->release(reinterpret_cast<const Block *>(a));
    return 1;
}
void etl_region(uintptr_t *lo, uintptr_t *hi)
{
    *lo = reinterpret_cast<uintptr_t>(g.pool);
    *hi = *lo + sizeof(g.pool);
}
}

extern "C" const pool_adapter adapter_etl = {
    "ETL etl::pool (C++)", etl_init, etl_alloc, etl_free, etl_region, alignof(Block), g.canary_lo, g.canary_hi
};
