/* endurodave/C_Allocator, its fixed-block allocator (src/fb_allocator.c,
 * src/LockGuard.cpp), pinned in libs.lock.
 * - The lock: ALLOC_LOCK_NONE, the library's own default on a bare-metal
 *   toolchain without threads (arm-none-eabi; LockGuard.h and README.md:
 *   "there the default is no lock"). It is set explicitly, so that the host
 *   build (whose default would be std::mutex) is the same configuration.
 * - Exhaustion: the library treats an exhausted pool as a fault and calls
 *   FaultHandler() (README.md: "On a fault, such as an exhausted pool, the
 *   allocators call FaultHandler() ... define your own FaultHandler() to log
 *   or reset instead"). The library's default (src/Fault.cpp, a weak
 *   symbol) asserts and aborts. This adapter defines its own FaultHandler,
 *   which counts the call and returns; ALLOC_Alloc then returns NULL
 *   (GET_CLIENT_PTR(NULL) is NULL), the "none left" of the interface. The
 *   count is pool_c_allocator_faults.
 * - The allocator object and its memory are spelled out as ALLOC_DEFINE()
 *   (fb_allocator.h) makes them; the memory lies inside the guarded struct.
 *   init() puts the object's non-const fields back to ALLOC_DEFINE's values. */
#include "pool.h"
#include "fb_allocator.h"
#include "Fault.h"

static POOL_GUARDED(
    ALLOC_PoolAlign mem[(ALLOC_BLOCK_SIZE(POOL_BLOCK_SIZE) * POOL_BLOCKS + sizeof(ALLOC_PoolAlign) - 1) / sizeof(ALLOC_PoolAlign)];) g;
/* The allocator object has const members and is initialised where it is
 * defined, as ALLOC_DEFINE does; it lies outside the guarded memory. */
static ALLOC_Allocator obj = { "vl_pool", (const char *)g.mem, POOL_BLOCK_SIZE, ALLOC_BLOCK_SIZE(POOL_BLOCK_SIZE),
                               POOL_BLOCKS, NULL, 0, 0, 0, 0, 0 };

volatile uint32_t pool_c_allocator_faults;
void FaultHandler(const char *file, unsigned short line)
{
    (void)file; (void)line;
    pool_c_allocator_faults++;
}

static void cal_init(void)
{
    obj.pHead = NULL;
    obj.poolIndex = 0;
    obj.blocksInUse = obj.maxBlocksInUse = obj.allocations = obj.deallocations = 0;
    ALLOC_Init();
}
static uintptr_t cal_alloc(uintptr_t a, uintptr_t b) { (void)a; (void)b; return (uintptr_t)ALLOC_Alloc(&obj, POOL_BLOCK_SIZE); }
static uint32_t cal_free(uintptr_t a, uintptr_t b) { (void)b; ALLOC_Free(&obj, (void *)a); return 1; }
static void cal_region(uintptr_t *lo, uintptr_t *hi) { *lo = (uintptr_t)g.mem; *hi = (uintptr_t)g.mem + sizeof(g.mem); }

/* ALLOC_MEM_ALIGN, the pointer size by default (fb_allocator.h). */
const pool_adapter adapter_c_allocator = {
    "C_Allocator fb_allocator (C)", cal_init, cal_alloc, cal_free, cal_region, ALLOC_MEM_ALIGN, g.canary_lo, g.canary_hi
};
