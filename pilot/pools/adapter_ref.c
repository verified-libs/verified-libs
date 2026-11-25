/* Reference pool of our own: a singly linked free list in a static array,
 * no lock. It is the baseline of a board benchmark (the cheapest possible
 * pool) and the control of the host test. With POOL_BROKEN it is built as
 * one of two deliberately broken adapters, which the host test must
 * reject (README.md):
 *   POOL_BROKEN=1  "double": every fourth alloc() hands out the first
 *                  free block without unlinking it, so the next alloc()
 *                  hands out the same block again.
 *   POOL_BROKEN=2  "lost":   every fourth free() drops the block, so the
 *                  pool shrinks. */
#include "pool.h"

#ifndef POOL_BROKEN
#define POOL_BROKEN 0
#endif

#if POOL_BROKEN == 0
#define NAME "reference free list (ours)"
#define SYM adapter_ref
#elif POOL_BROKEN == 1
#define NAME "broken: block handed out twice"
#define SYM adapter_broken_double
#else
#define NAME "broken: block lost"
#define SYM adapter_broken_lost
#endif

typedef union blk { union blk *next; uint8_t bytes[POOL_BLOCK_SIZE]; } blk;
static blk store[POOL_BLOCKS];
static blk *head;
static uint32_t allocs, frees;

static void ref_init(void)
{
    head = 0;
    allocs = frees = 0;
    for (uint32_t i = POOL_BLOCKS; i-- > 0;) { store[i].next = head; head = &store[i]; }
}

static uintptr_t ref_alloc(uintptr_t a, uintptr_t b)
{
    (void)a; (void)b;
    blk *p = head;
    allocs++;
#if POOL_BROKEN == 1
    if (p && allocs % 4 == 0) return (uintptr_t)p;   /* not unlinked: the bug */
#endif
    if (p) head = p->next;
    return (uintptr_t)p;
}

static uint32_t ref_free(uintptr_t a, uintptr_t b)
{
    (void)b;
    blk *p = (blk *)a;
    frees++;
#if POOL_BROKEN == 2
    if (frees % 4 == 0) return 1;            /* dropped: the bug */
#endif
    p->next = head;
    head = p;
    return 1;
}

static void ref_region(uintptr_t *lo, uintptr_t *hi)
{
    *lo = (uintptr_t)&store[0];
    *hi = (uintptr_t)&store[POOL_BLOCKS];
}

const pool_adapter SYM = { NAME, ref_init, ref_alloc, ref_free, 0, 0, ref_region, sizeof(void *) };
