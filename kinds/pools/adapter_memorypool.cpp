/* bertmelis/MemoryPool, MemoryPool::Fixed (src/Fixed.h), pinned in libs.lock
 * at the head of its main branch, 5073178 (2024-05-15), not at its only
 * release v0.1.0 (c98ff35): v0.1.0 spaces the blocks of Fixed by the size of a
 * pointer whatever the block size, so blocks overlap, and it does not build
 * for arm-none-eabi (std::mutex); the author fixed both on main (PR #4, "Fix
 * Fixed Mempool blocksize", merged 2024-05-14, and "Disable mutex when not
 * available", 2024-05-15) and has made no release since (DECISIONS
 * 2026-11-26; README.md).
 * The lock: at the head the mutex is compiled only #if _GLIBCXX_HAS_GTHREADS,
 * with #warning "The memory pool is not thread safe" otherwise. On the boards
 * (arm-none-eabi, no threads) the pool therefore has no lock; on the host
 * (glibc's libstdc++ has threads) it takes its std::mutex in every call.
 * init() destroys the pool object and constructs it again in place (its
 * constructor threads the free list through the buffer). */
#include <new>
#include "pool.h"
#include "MemoryPool.h"

namespace {
typedef MemoryPool::Fixed<POOL_BLOCKS, POOL_BLOCK_SIZE> Pool;
POOL_GUARDED(alignas(Pool) unsigned char pool[sizeof(Pool)];) g;
Pool *pool() { return std::launder(reinterpret_cast<Pool *>(g.pool)); }
bool made = false;

void mp_init()
{
    if (made) pool()->~Pool();
    new (g.pool) Pool();
    made = true;
}
uintptr_t mp_alloc(uintptr_t, uintptr_t) { return reinterpret_cast<uintptr_t>(pool()->malloc()); }
uint32_t mp_free(uintptr_t a, uintptr_t)
{
    pool()->free(reinterpret_cast<void *>(a));
    return 1;
}
void mp_region(uintptr_t *lo, uintptr_t *hi)
{
    *lo = reinterpret_cast<uintptr_t>(g.pool);
    *hi = *lo + sizeof(g.pool);
}
}

/* The blocks are elements of an unsigned char buffer inside the object, spaced
 * by the block size (32): their alignment is the object's, which this adapter
 * gives as alignof(Pool) (a pointer's, from its _head member). */
extern "C" const pool_adapter adapter_memorypool = {
    "MemoryPool Fixed (C++)", mp_init, mp_alloc, mp_free, mp_region, alignof(Pool), g.canary_lo, g.canary_hi
};
