/* RIOT memarray (sys/memarray, sys/include/memarray.h), pinned in
 * libs.lock. Its header documents nothing about threads or interrupts and
 * it has no lock; this adapter adds none. */
#include "pool.h"
#include "memarray.h"

typedef union { void *next; uint8_t bytes[POOL_BLOCK_SIZE]; } blk;
static blk store[POOL_BLOCKS];
static memarray_t mem;

static void riot_init(void) { memarray_init(&mem, store, sizeof(blk), POOL_BLOCKS); }
static uintptr_t riot_alloc(uintptr_t a, uintptr_t b) { (void)a; (void)b; return (uintptr_t)memarray_alloc(&mem); }
static uint32_t riot_free(uintptr_t a, uintptr_t b) { (void)b; memarray_free(&mem, (void *)a); return 1; }
static void riot_region(uintptr_t *lo, uintptr_t *hi) { *lo = (uintptr_t)&store[0]; *hi = (uintptr_t)&store[POOL_BLOCKS]; }

const pool_adapter adapter_riot_memarray = {
    "RIOT memarray (C)", riot_init, riot_alloc, riot_free, 0, 0, riot_region, sizeof(void *)
};
