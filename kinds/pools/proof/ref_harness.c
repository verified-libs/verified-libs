/* CBMC on the reference pool (../adapter_ref.c), the reference of the host
 * test and the baseline of the board images (site/content/method-pools.md,
 * "The reference, and our row"). For a pool of POOL_BLOCKS = 4 blocks and every sequence of OPS
 * calls (each call nondeterministically an alloc, or a free of a
 * nondeterministically chosen held block), after every call:
 *   - the free list starts at head, follows next, and ends after exactly
 *     POOL_BLOCKS - held blocks;
 *   - every block on it is an element of store, and none twice;
 *   - no held block is on it (so free list and held blocks partition store);
 *   - alloc gives a block if and only if the list was not empty, and that
 *     block is an element of store, pointer-aligned, and was not held.
 * Run by run.sh (make proof); --unwinding-assertions makes the bounds part of
 * the proof. */
#include <stdbool.h>
#include "../adapter_ref.c"

#ifndef OPS
#define OPS 8
#endif

unsigned nondet_unsigned(void);
bool nondet_bool(void);
/* "Interrupts off" is not used by this build (POOL_PRIMASK 0). */
unsigned pool_irq_disable(void) { return 0; }
void pool_irq_restore(unsigned was) { (void)was; }

static bool held[POOL_BLOCKS];
static unsigned nheld;

static unsigned index_of(blk *p)
{
    __CPROVER_assert(p >= &g.store[0] && p < &g.store[POOL_BLOCKS], "a block of the pool");
    return (unsigned)(p - &g.store[0]);
}

static void check_list(void)
{
    bool seen[POOL_BLOCKS] = { false };
    unsigned n = 0;
    for (blk *p = g.head; p; p = p->next) {
        __CPROVER_assert(n < POOL_BLOCKS, "the free list ends");
        unsigned i = index_of(p);
        __CPROVER_assert(!seen[i], "no block twice on the free list");
        __CPROVER_assert(!held[i], "no held block on the free list");
        seen[i] = true;
        n++;
    }
    __CPROVER_assert(n == POOL_BLOCKS - nheld, "the free list holds every block not held");
}

int main(void)
{
    SYM.init();
    check_list();
    for (unsigned op = 0; op < OPS; op++) {
        if (nheld == 0 || nondet_bool()) {
            uintptr_t b = SYM.alloc(0, 0);
            if (nheld == POOL_BLOCKS) {
                __CPROVER_assert(b == 0, "no block from an exhausted pool");
            } else {
                __CPROVER_assert(b != 0, "a block while one is free");
                __CPROVER_assert(b % sizeof(void *) == 0, "pointer-aligned");
                unsigned i = index_of((blk *)b);
                __CPROVER_assert(!held[i], "not a held block");
                held[i] = true;
                nheld++;
            }
        } else {
            unsigned i = nondet_unsigned() % POOL_BLOCKS;
            __CPROVER_assume(held[i]);
            __CPROVER_assert(SYM.free((uintptr_t)&g.store[i], 0) == 1, "free takes a held block");
            held[i] = false;
            nheld--;
        }
        check_list();
    }
    return 0;
}
