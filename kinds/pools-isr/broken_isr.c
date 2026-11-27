/* Two broken interrupts-off builds of our reference free list, the controls of
 * the concurrency check (lab/plans/2026-11-27-pools-concurrency.md, 3.1): the
 * list of ../pools/adapter_ref.c with PRIMASK (pool_irq_disable/pool_irq_restore),
 * but with interrupts on again too early, so that an interrupt can come
 * between the read of the head and its write. Copied, not built from
 * adapter_ref.c, which is a test source of the first series and stays as it is.
 *   BROKEN_ISR=1  "early in alloc": the head is read with interrupts off; the
 *                 block's link is read and the new head written after they
 *                 are on again;
 *   BROKEN_ISR=2  "early in free":  the block's link is written with
 *                 interrupts off, the head after they are on again.
 * Each window holds more than the one instruction after the unmask: on the
 * Cortex-M4 and M33 an interrupt that is pending when PRIMASK is cleared was
 * taken only after that next instruction, as the architecture allows
 * (Armv7-M B5.2.3, MSR: a lower priority is guaranteed visible only after an
 * ISB, exception entry or exception return; Armv8-M B3.18, RKLWH: a pending
 * exception is taken "within finite time"), so a write right after the
 * unmask is never interrupted there. Until
 * 2026-11-27 the alloc build wrote the head right after the unmask, and the
 * boards with those cores did not catch it. */
#include "pool.h"

#if BROKEN_ISR == 1
#define NAME "broken: interrupts on too early in alloc"
#define SYM adapter_broken_isr_alloc
#else
#define NAME "broken: interrupts on too early in free"
#define SYM adapter_broken_isr_free
#endif

typedef union blk { union blk *next; uint8_t bytes[POOL_BLOCK_SIZE]; } blk;
static POOL_GUARDED(blk *volatile head; blk store[POOL_BLOCKS];) g;

static void b_init(void)
{
    g.head = 0;
    for (uint32_t i = POOL_BLOCKS; i-- > 0;) { g.store[i].next = g.head; g.head = &g.store[i]; }
}

static uintptr_t b_alloc(uintptr_t a, uintptr_t b)
{
    (void)a; (void)b;
    unsigned s = pool_irq_disable();
    blk *p = g.head;
#if BROKEN_ISR == 1
    pool_irq_restore(s);
    blk *n = p ? p->next : 0;
    if (p) g.head = n;
#else
    blk *n = p ? p->next : 0;
    if (p) g.head = n;
    pool_irq_restore(s);
#endif
    return (uintptr_t)p;
}

static uint32_t b_free(uintptr_t a, uintptr_t b)
{
    (void)b;
    blk *p = (blk *)a;
    unsigned s = pool_irq_disable();
    p->next = g.head;
#if BROKEN_ISR == 2
    pool_irq_restore(s);
    g.head = p;
#else
    g.head = p;
    pool_irq_restore(s);
#endif
    return 1;
}

static void b_region(uintptr_t *lo, uintptr_t *hi)
{
    *lo = (uintptr_t)&g.store[0];
    *hi = (uintptr_t)&g.store[POOL_BLOCKS];
}

const pool_adapter SYM = { NAME, b_init, b_alloc, b_free, b_region, sizeof(void *), g.canary_lo, g.canary_hi };
