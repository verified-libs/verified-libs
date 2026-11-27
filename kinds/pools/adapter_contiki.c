/* Contiki-NG memb (os/lib/memb.c, os/lib/memb.h), pinned in libs.lock. A
 * flag per block and a linear search (memb_alloc takes the first free flag,
 * memb_free searches for the block's index). Its header documents nothing
 * about interrupts and it has no lock (Contiki's processes are cooperative).
 * The adapter fills struct memb as the MEMB() macro of memb.h does, inside
 * the guarded struct; memb_init() clears the flags and the blocks. */
#include <stdbool.h>
#include "pool.h"
#include "lib/memb.h"

typedef union { void *align; uint8_t bytes[POOL_BLOCK_SIZE]; } blk;
static POOL_GUARDED(struct memb m; bool used[POOL_BLOCKS]; blk mem[POOL_BLOCKS];) g;

static void contiki_init(void)
{
    g.m.size = sizeof(blk);
    g.m.num = POOL_BLOCKS;
    g.m.used = g.used;
    g.m.mem = g.mem;
    memb_init(&g.m);
}
static uintptr_t contiki_alloc(uintptr_t a, uintptr_t b) { (void)a; (void)b; return (uintptr_t)memb_alloc(&g.m); }
static uint32_t contiki_free(uintptr_t a, uintptr_t b) { (void)b; return memb_free(&g.m, (void *)a) == 0; }
static void contiki_region(uintptr_t *lo, uintptr_t *hi) { *lo = (uintptr_t)&g.mem[0]; *hi = (uintptr_t)&g.mem[POOL_BLOCKS]; }

/* The blocks are elements of the caller's array (MEMB() declares them as the
 * structure given), so their alignment is the element type's: here a pointer's. */
const pool_adapter adapter_contiki = {
    "Contiki-NG memb (C)", contiki_init, contiki_alloc, contiki_free, contiki_region, sizeof(void *), g.canary_lo, g.canary_hi
};
