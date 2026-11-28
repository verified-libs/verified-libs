/* The host test of the pools kind (site/content/method-pools.md,
 * "Checked on the host"), grown out of a pilot's (not published). One
 * context: no interrupts (the first series measures one context,
 * method-pools.html#log-2026-11-26-first).
 *
 * For each adapter, SEQUENCES runs of STEPS random calls (xorshift32, fixed
 * seeds), each after a fresh init(), and then the fixed patterns of the board
 * scenarios (fill and drain in reverse and in the same order, pairs). The
 * test keeps its own record of the blocks it holds and checks after every
 * call:
 *   capacity     alloc gives a block if and only if fewer than POOL_BLOCKS
 *                are held: the N-th is given, an (N+1)-th is not (the
 *                reference's answer, since the reference is an N-block pool);
 *   region       a block lies in the adapter's region, at the promised
 *                alignment;
 *   no block twice  a block given is not one the test holds;
 *   no overlap   each holder writes a pattern of its own into its block and
 *                finds it intact at its free (and every held block every 16
 *                steps): a block shared with another, or with the pool's own
 *                bookkeeping, shows;
 *   no write outside  the canary words around the adapter's memory
 *                (POOL_GUARDED, pool.h) are intact;
 *   interrupts   a pool that turns "interrupts" off turns them on again
 *                before it returns;
 *   reuse        after a free the block can be handed out again (the random
 *                runs and the patterns reuse every block);
 *   no block lost  after the run every block is freed, and then exactly
 *                POOL_BLOCKS allocations succeed; then every block is given
 *                back (atomic-pool has no reset, so the next init finds an
 *                empty pool only this way).
 * Exit 0 if every adapter expected to pass passes and every deliberately
 * broken one fails; 1 otherwise. */
#include <stdio.h>
#include <string.h>
#include "pool.h"

#define SEQUENCES 64u
#define STEPS     20000u

extern const pool_adapter adapter_ref, adapter_ref_primask, adapter_broken_double, adapter_broken_lost,
    adapter_broken_overrun, adapter_broken_misaligned;
extern const pool_adapter adapter_etl, adapter_riot, adapter_threadx, adapter_cmsis_rtx, adapter_contiki,
    adapter_c_allocator, adapter_memorypool;
#ifdef POOL_WITH_RUST
extern pool_adapter adapter_heapless, adapter_atomic_pool;   /* filled in by their init (adapter_rust.c) */
#endif
#ifdef POOL_WITH_ZEPHYR
extern const pool_adapter adapter_zephyr;
#endif
#ifdef POOL_WITH_LWIP
extern const pool_adapter adapter_lwip;
#endif

static const struct { const pool_adapter *ad; int expect_pass; } CASES[] = {
    { &adapter_ref, 1 },
    { &adapter_ref_primask, 1 },
    { &adapter_broken_double, 0 },
    { &adapter_broken_lost, 0 },
    { &adapter_broken_overrun, 0 },
    { &adapter_broken_misaligned, 0 },
    { &adapter_etl, 1 },
    { &adapter_riot, 1 },
    { &adapter_threadx, 1 },
    { &adapter_cmsis_rtx, 1 },
    { &adapter_contiki, 1 },
    { &adapter_c_allocator, 1 },
    { &adapter_memorypool, 1 },
#ifdef POOL_WITH_RUST
    { &adapter_heapless, 1 },
    { &adapter_atomic_pool, 1 },
#endif
#ifdef POOL_WITH_ZEPHYR
    { &adapter_zephyr, 1 },
#endif
#ifdef POOL_WITH_LWIP
    { &adapter_lwip, 1 },
#endif
};

/* "Interrupts off" on the host (pool.h): a flag, counted. */
static unsigned irq_off, irq_sections;
unsigned pool_irq_disable(void) { unsigned was = irq_off; irq_off = 1; irq_sections++; return was; }
void pool_irq_restore(unsigned was) { irq_off = was; }

static uint32_t rng;
static uint32_t xs(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }

static uintptr_t held[POOL_BLOCKS + 1];
static uint32_t stamp[POOL_BLOCKS + 1];
static uint32_t nheld, nstamp;
static uintptr_t lo, hi;

static void fill(uintptr_t b, uint32_t s)
{
    uint8_t *p = (uint8_t *)b;
    for (uint32_t i = 0; i < POOL_BLOCK_SIZE; i++) p[i] = (uint8_t)(s * 31u + i);
}
static int intact(uintptr_t b, uint32_t s)
{
    const uint8_t *p = (const uint8_t *)b;
    for (uint32_t i = 0; i < POOL_BLOCK_SIZE; i++) if (p[i] != (uint8_t)(s * 31u + i)) return 0;
    return 1;
}
static void set_canaries(const pool_adapter *ad)
{
    for (uint32_t i = 0; i < POOL_CANARY_WORDS; i++) ad->canary_lo[i] = ad->canary_hi[i] = POOL_CANARY ^ i;
}
static int canaries_ok(const pool_adapter *ad)
{
    for (uint32_t i = 0; i < POOL_CANARY_WORDS; i++)
        if (ad->canary_lo[i] != (POOL_CANARY ^ i) || ad->canary_hi[i] != (POOL_CANARY ^ i)) return 0;
    return 1;
}

/* One alloc, with every check; NULL if it passed. */
static const char *take(const pool_adapter *ad)
{
    uintptr_t b = ad->alloc(0, 0);
    if (irq_off) return "interrupts: alloc returned with interrupts off";
    if (!canaries_ok(ad)) return "no write outside: a canary around the pool's memory was changed (alloc)";
    if (nheld < POOL_BLOCKS && !b) return "capacity: no block although fewer than POOL_BLOCKS are held";
    if (nheld >= POOL_BLOCKS && b) return "capacity: a block beyond POOL_BLOCKS";
    if (!b) return NULL;
    if (b < lo || b + POOL_BLOCK_SIZE > hi) return "region: a block outside the pool's region";
    if (b % ad->align) return "region: a block at a smaller alignment than promised";
    for (uint32_t i = 0; i < nheld; i++)
        if (held[i] == b) return "no block twice: a block handed out that the test holds";
    held[nheld] = b;
    stamp[nheld] = ++nstamp;
    fill(b, nstamp);
    nheld++;
    return NULL;
}

/* Free the k-th held block, with every check; NULL if it passed. */
static const char *give(const pool_adapter *ad, uint32_t k)
{
    if (!intact(held[k], stamp[k])) return "no overlap: a held block was changed by someone else";
    if (!ad->free(held[k], 0)) return "free refused a block the pool handed out";
    if (irq_off) return "interrupts: free returned with interrupts off";
    if (!canaries_ok(ad)) return "no write outside: a canary around the pool's memory was changed (free)";
    held[k] = held[nheld - 1];
    stamp[k] = stamp[nheld - 1];
    nheld--;
    return NULL;
}

static const char *all_intact(void)
{
    for (uint32_t i = 0; i < nheld; i++)
        if (!intact(held[i], stamp[i])) return "no overlap: a held block was changed by someone else";
    return NULL;
}

static void start(const pool_adapter *ad)
{
    ad->region(&lo, &hi);
    ad->init();
    set_canaries(ad);
    nheld = 0;
}

/* Every block freed, then exactly POOL_BLOCKS allocations succeed and one more does not. */
static const char *drain_and_count(const pool_adapter *ad)
{
    const char *why;
    while (nheld)
        if ((why = give(ad, nheld - 1))) return why;
    for (uint32_t i = 0; i < POOL_BLOCKS; i++) {
        uint32_t before = nheld;
        if ((why = take(ad))) return why;
        if (nheld == before) return "no block lost: fewer than POOL_BLOCKS blocks after every block was freed";
    }
    if ((why = take(ad))) return why;   /* must give none: capacity is checked inside */
    while (nheld)                        /* every block back, for the next init of a pool without a reset */
        if ((why = give(ad, nheld - 1))) return why;
    return NULL;
}

/* The random runs. NULL if the run passed, else the first violation. */
static const char *run_random(const pool_adapter *ad, uint32_t seed, uint32_t *at)
{
    const char *why;
    start(ad);
    rng = seed;
    for (uint32_t step = 0; step < STEPS; step++) {
        *at = step;
        int do_alloc = nheld == 0 || (nheld < POOL_BLOCKS + 1 && (xs() & 1));
        if (do_alloc) { if ((why = take(ad))) return why; }
        else if ((why = give(ad, xs() % nheld))) return why;
        if (step % 16 == 0 && (why = all_intact())) return why;
    }
    *at = STEPS;
    return drain_and_count(ad);
}

/* The fixed patterns of the board scenarios (section 2 of the plan): pairs on an
 * almost empty and an almost full pool, fill and drain in reverse and in the same
 * order, and alloc on an exhausted pool. */
static const char *run_patterns(const pool_adapter *ad, uint32_t *at)
{
    const char *why;
    start(ad);
    for (uint32_t r = 0; r < 4; r++) {
        *at = r;
        for (uint32_t i = 0; i < 256; i++) {                         /* pair */
            if ((why = take(ad))) return why;
            if ((why = give(ad, nheld - 1))) return why;
        }
        while (nheld < POOL_BLOCKS - 1) if ((why = take(ad))) return why;
        for (uint32_t i = 0; i < 256; i++) {                         /* pair_full */
            if ((why = take(ad))) return why;
            if ((why = give(ad, nheld - 1))) return why;
        }
        if ((why = take(ad))) return why;                             /* full */
        for (uint32_t i = 0; i < 16; i++) if ((why = take(ad))) return why;   /* empty: none */
        while (nheld) if ((why = give(ad, nheld - 1))) return why;   /* drain, reverse order */
        while (nheld < POOL_BLOCKS) if ((why = take(ad))) return why; /* fill */
        while (nheld) {                                               /* drain, same order */
            if ((why = give(ad, 0))) return why;
            /* give() moved the last held block to slot 0; put the order back */
            if (nheld > 1) {
                uintptr_t b = held[0]; uint32_t s = stamp[0];
                memmove(&held[0], &held[1], (nheld - 1) * sizeof held[0]);
                memmove(&stamp[0], &stamp[1], (nheld - 1) * sizeof stamp[0]);
                held[nheld - 1] = b; stamp[nheld - 1] = s;
            }
        }
    }
    return drain_and_count(ad);
}

int main(void)
{
    int ok = 1;
    printf("pools host test: %u blocks of %u bytes, %u random sequences of %u steps and the board patterns\n",
           POOL_BLOCKS, POOL_BLOCK_SIZE, SEQUENCES, STEPS);
    for (size_t c = 0; c < sizeof(CASES) / sizeof(CASES[0]); c++) {
        const pool_adapter *ad = CASES[c].ad;
        const char *why = NULL, *where = "random";
        uint32_t seq, at = 0;
        irq_sections = 0;
        irq_off = 0;
        for (seq = 0; seq < SEQUENCES && !why; seq++) why = run_random(ad, 0x9E3779B9u ^ (seq * 2654435761u), &at);
        if (!why) { where = "patterns"; seq = 1; why = run_patterns(ad, &at); }
        int passed = why == NULL;
        int as_expected = passed == CASES[c].expect_pass;
        ok &= as_expected;
        if (passed)
            printf("%-44s pass   (expected %s)%s  interrupt-off sections: %u\n", ad->name,
                   CASES[c].expect_pass ? "pass" : "FAIL", as_expected ? "" : "  <-- NOT AS EXPECTED", irq_sections);
        else
            printf("%-44s FAIL   (expected %s)%s  %s %u, step %u: %s\n", ad->name,
                   CASES[c].expect_pass ? "pass" : "FAIL", as_expected ? "" : "  <-- NOT AS EXPECTED",
                   where, seq - 1, at, why);
    }
    printf("%s\n", ok ? "exit 0: every verdict as expected" : "exit 1: a verdict not as expected");
    return ok ? 0 : 1;
}
