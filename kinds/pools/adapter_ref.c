/* The reference pool of our own (lab/plans/2026-11-26-pools-kind.md, section
 * 3): a singly linked free list threaded through the free blocks, LIFO, no
 * lock. It is the reference of the host test, the baseline of every board
 * image (timed in the same image, as the CRC kind's bitwise reference) and,
 * built with POOL_BROKEN, the controls the host test must reject:
 *   POOL_BROKEN=1  "double":     every fourth alloc() hands out the first free
 *                                block without unlinking it, so the next
 *                                alloc() hands it out again;
 *   POOL_BROKEN=2  "lost":       every fourth free() drops the block, so the
 *                                pool shrinks;
 *   POOL_BROKEN=3  "overrun":    every fourth free() also writes the word just
 *                                past the pool's memory (the first canary word
 *                                behind it);
 *   POOL_BROKEN=4  "misaligned": every fourth alloc() returns the block plus
 *                                one byte (and free() takes it back).
 * POOL_PRIMASK=1 builds the same list with interrupts off around each call
 * (pool_irq_disable/pool_irq_restore, pool.h): the row of ours that gives the
 * price of the simplest lock on each core, labelled "not a library". */
#include "pool.h"

#ifndef POOL_BROKEN
#define POOL_BROKEN 0
#endif
#ifndef POOL_PRIMASK
#define POOL_PRIMASK 0
#endif

#if POOL_PRIMASK
#define NAME "reference free list, interrupts off (ours)"
#define SYM adapter_ref_primask
#elif POOL_BROKEN == 0
#define NAME "reference free list (ours)"
#define SYM adapter_ref
#elif POOL_BROKEN == 1
#define NAME "broken: block handed out twice"
#define SYM adapter_broken_double
#elif POOL_BROKEN == 2
#define NAME "broken: block lost"
#define SYM adapter_broken_lost
#elif POOL_BROKEN == 3
#define NAME "broken: write outside the pool"
#define SYM adapter_broken_overrun
#else
#define NAME "broken: block misaligned"
#define SYM adapter_broken_misaligned
#endif

#if POOL_PRIMASK
#define LOCK()   unsigned s_ = pool_irq_disable()
#define UNLOCK() pool_irq_restore(s_)
#else
#define LOCK()   do {} while (0)
#define UNLOCK() do {} while (0)
#endif

typedef union blk { union blk *next; uint8_t bytes[POOL_BLOCK_SIZE]; } blk;
static POOL_GUARDED(blk *head; uint32_t allocs, frees; blk store[POOL_BLOCKS];) g;

static void ref_init(void)
{
    g.head = 0;
    g.allocs = g.frees = 0;
    for (uint32_t i = POOL_BLOCKS; i-- > 0;) { g.store[i].next = g.head; g.head = &g.store[i]; }
}

static uintptr_t ref_alloc(uintptr_t a, uintptr_t b)
{
    (void)a; (void)b;
    LOCK();
    blk *p = g.head;
#if POOL_BROKEN == 1
    if (p && ++g.allocs % 4 == 0) { UNLOCK(); return (uintptr_t)p; }   /* not unlinked: the bug */
#endif
    if (p) g.head = p->next;
    UNLOCK();
#if POOL_BROKEN == 4
    if (p && ++g.allocs % 4 == 0) return (uintptr_t)p + 1;             /* misaligned: the bug */
#endif
    return (uintptr_t)p;
}

static uint32_t ref_free(uintptr_t a, uintptr_t b)
{
    (void)b;
#if POOL_BROKEN == 4
    a &= ~(uintptr_t)(sizeof(void *) - 1);
#endif
    blk *p = (blk *)a;
#if POOL_BROKEN == 2
    if (++g.frees % 4 == 0) return 1;                                  /* dropped: the bug */
#endif
#if POOL_BROKEN == 3
    if (++g.frees % 4 == 0) ((volatile uint32_t *)g.canary_hi)[0] = 0; /* outside the pool: the bug */
#endif
    LOCK();
    p->next = g.head;
    g.head = p;
    UNLOCK();
    return 1;
}

static void ref_region(uintptr_t *lo, uintptr_t *hi)
{
    *lo = (uintptr_t)&g.store[0];
    *hi = (uintptr_t)&g.store[POOL_BLOCKS];
}

const pool_adapter SYM = { NAME, ref_init, ref_alloc, ref_free, ref_region, sizeof(void *), g.canary_lo, g.canary_hi };
