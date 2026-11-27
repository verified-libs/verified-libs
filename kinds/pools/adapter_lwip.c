/* lwIP memp (src/core/memp.c), pinned in libs.lock, alone without the stack:
 * one private pool, used through memp_init_pool, memp_malloc_pool and
 * memp_free_pool, as include/lwip/memp.h documents for a private pool
 * (LWIP_MEMPOOL_DECLARE / _INIT / _ALLOC / _FREE; options:
 * shims/lwip/lwipopts.h). Its free list is guarded by SYS_ARCH_PROTECT, the
 * port's interrupts off (shims/lwip/sys_arch.c). LWIP_MEMPOOL_DECLARE declares
 * the pool's memory, its list head and its descriptor as objects of their own;
 * here they are declared as the macro declares them, inside the guarded
 * struct. */
#include "pool.h"
#include "lwip/memp.h"

static POOL_GUARDED(
    u8_t base[LWIP_MEM_ALIGN_BUFFER((POOL_BLOCKS) * (MEMP_SIZE + MEMP_ALIGN_SIZE(POOL_BLOCK_SIZE)))];
    struct memp *tab;
    struct memp_desc desc;) g;

/* The descriptor is filled here with the values LWIP_MEMPOOL_DECLARE gives it
 * (memp.h; no description and no statistics with these options), so that the
 * pool's memory stays in .bss, as the macro's does. */
static void lwip_init_(void)
{
    g.desc.size = LWIP_MEM_ALIGN_SIZE(POOL_BLOCK_SIZE);
    g.desc.num = POOL_BLOCKS;
    g.desc.base = g.base;
    g.desc.tab = &g.tab;
    memp_init_pool(&g.desc);
}
static uintptr_t lwip_alloc(uintptr_t a, uintptr_t b) { (void)a; (void)b; return (uintptr_t)memp_malloc_pool(&g.desc); }
static uint32_t lwip_free(uintptr_t a, uintptr_t b) { (void)b; memp_free_pool(&g.desc, (void *)a); return 1; }
static void lwip_region(uintptr_t *lo, uintptr_t *hi) { *lo = (uintptr_t)g.base; *hi = (uintptr_t)g.base + sizeof(g.base); }

/* MEM_ALIGNMENT of the options (4): memp_init_pool aligns the base and every
 * element size to it (memp.c, LWIP_MEM_ALIGN, MEMP_ALIGN_SIZE). */
const pool_adapter adapter_lwip = {
    "lwIP memp (C)", lwip_init_, lwip_alloc, lwip_free, lwip_region, MEM_ALIGNMENT, g.canary_lo, g.canary_hi
};
