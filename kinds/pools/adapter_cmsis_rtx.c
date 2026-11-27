/* CMSIS-RTX's memory pool (Source/rtx_mempool.c of v5.9.1), pinned in
 * libs.lock, without the rest of the kernel.
 *
 * The kernel's pool object (osMemoryPoolNew/Alloc/Free) is an RTX object:
 * its public calls go through the SVC call or, from an ISR, through
 * isrRtxMemoryPoolAlloc/Free, which check the object and then call the three
 * functions this adapter calls directly: osRtxMemoryPoolInit, osRtxMemoryPoolAlloc
 * and osRtxMemoryPoolFree. Those three hold the whole of the pool's
 * algorithm: the free list, with interrupts off on Armv6-M (EXCLUSIVE_ACCESS
 * 0) and lock-free with LDREX/STREX on Armv7-M and Armv8-M (EXCLUSIVE_ACCESS
 * 1, atomic_link_get/atomic_link_put in rtx_core_cm.h). What the ISR call adds
 * and this adapter does not do: the object check (IsMemoryPoolPtrValid and the
 * id) and, after a free, osRtxPostProcess, which wakes a thread waiting for a
 * block (no thread waits here). The library file is compiled as it is; the
 * kernel's other functions in it are dropped by the linker (--gc-sections). */
#include "pool.h"
#include "rtx_lib.h"

/* RTX's own pool memory macro: block_count blocks of block_size bytes, in
 * 32-bit words (rtx_os.h, osRtxMemoryPoolMemSize). */
static POOL_GUARDED(os_mp_info_t info; uint32_t store[osRtxMemoryPoolMemSize(POOL_BLOCKS, POOL_BLOCK_SIZE) / 4u];) g;

static void rtx_init(void) { (void)osRtxMemoryPoolInit(&g.info, POOL_BLOCKS, POOL_BLOCK_SIZE, g.store); }
static uintptr_t rtx_alloc(uintptr_t a, uintptr_t b) { (void)a; (void)b; return (uintptr_t)osRtxMemoryPoolAlloc(&g.info); }
static uint32_t rtx_free(uintptr_t a, uintptr_t b) { (void)b; return osRtxMemoryPoolFree(&g.info, (void *)a) == osOK; }
static void rtx_region(uintptr_t *lo, uintptr_t *hi) { *lo = (uintptr_t)&g.store[0]; *hi = (uintptr_t)&g.store[sizeof g.store / 4u]; }

const pool_adapter adapter_cmsis_rtx = {
    "CMSIS-RTX osRtxMemoryPool (C)", rtx_init, rtx_alloc, rtx_free, rtx_region, 4, g.canary_lo, g.canary_hi
};
