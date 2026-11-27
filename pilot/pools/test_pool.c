/* Pilot: the first correctness test of the pool interface, on the host,
 * one context (no interrupts yet). README.md says what it is for: to show
 * that the interface is workable and that the test can fail. It makes no
 * claim about any library.
 *
 * For each adapter: SEQUENCES runs of STEPS random calls (xorshift32, fixed
 * seeds). The test keeps its own record of which blocks it holds and checks
 * after every call:
 *   - alloc returns a block if and only if fewer than POOL_BLOCKS are held
 *     ("capacity": a pool of N blocks must give the N-th, and must not give
 *     an (N+1)-th);
 *   - a block lies in the adapter's region, at the promised alignment, and
 *     is not one the test already holds ("no block twice");
 *   - the owner fills its block with a pattern of its own (owner, step);
 *     before the free the pattern must be intact ("no overlap": a block
 *     shared with another or with the pool's own bookkeeping shows);
 *   - after the run every block is freed, and then exactly POOL_BLOCKS
 *     allocations succeed ("no block lost").
 * Exit 0 if every adapter that is expected to pass passes and every
 * deliberately broken one fails; 1 otherwise. */
#include <stdio.h>
#include <string.h>
#include "pool.h"

#define SEQUENCES 64u
#define STEPS     20000u

extern const pool_adapter adapter_ref, adapter_broken_double, adapter_broken_lost;
#ifdef POOL_TEST_CMSIS_RTX
/* The pool pre-checks (../pools-prechecks): the reference, the two broken
 * pools and CMSIS-RTX's pool, without the pilot's three libraries. */
extern const pool_adapter adapter_cmsis_rtx;
#else
extern const pool_adapter adapter_etl_pool, adapter_riot_memarray, adapter_threadx_block;
#endif

static struct { const pool_adapter *ad; int expect_pass; } CASES[] = {
    { &adapter_ref, 1 },
    { &adapter_broken_double, 0 },
    { &adapter_broken_lost, 0 },
#ifdef POOL_TEST_CMSIS_RTX
    { &adapter_cmsis_rtx, 1 },
#else
    { &adapter_etl_pool, 1 },
    { &adapter_riot_memarray, 1 },
    { &adapter_threadx_block, 1 },
#endif
};

/* "Interrupts off" for the ThreadX port header: a flag, nothing more on
 * one context. Counted, so the output shows the pool used it. */
static unsigned irq_off, irq_sections;
unsigned pilot_irq_disable(void) { unsigned was = irq_off; irq_off = 1; irq_sections++; return was; }
void pilot_irq_restore(unsigned was) { irq_off = was; }

static uint32_t rng;
static uint32_t xs(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }

static uintptr_t held[POOL_BLOCKS + 1];
static uint32_t stamp[POOL_BLOCKS + 1];
static uint32_t nheld;

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

/* Returns NULL if the run passed, else the first violation. */
static const char *run(const pool_adapter *ad, uint32_t seed, uint32_t *at)
{
    uintptr_t lo, hi;
    ad->region(&lo, &hi);
    ad->init();
    nheld = 0;
    rng = seed;
    for (uint32_t step = 0; step < STEPS; step++) {
        *at = step;
        int do_alloc = nheld == 0 || (nheld < POOL_BLOCKS + 1 && (xs() & 1));
        if (do_alloc) {
            uintptr_t b = ad->alloc(0, 0);
            if (nheld < POOL_BLOCKS && !b) return "capacity: no block although fewer than POOL_BLOCKS are held";
            if (nheld >= POOL_BLOCKS && b) return "capacity: a block beyond POOL_BLOCKS";
            if (!b) continue;
            if (b < lo || b + POOL_BLOCK_SIZE > hi) return "a block outside the pool's region";
            if (b % ad->align) return "a block at a smaller alignment than promised";
            for (uint32_t i = 0; i < nheld; i++)
                if (held[i] == b) return "no block twice: a block handed out that the test holds";
            held[nheld] = b;
            stamp[nheld] = step + 1;
            fill(b, step + 1);
            nheld++;
        } else {
            uint32_t k = xs() % nheld;
            if (!intact(held[k], stamp[k])) return "no overlap: a held block was changed by someone else";
            if (!ad->free(held[k], 0)) return "free refused a block the pool handed out";
            held[k] = held[nheld - 1];
            stamp[k] = stamp[nheld - 1];
            nheld--;
        }
        for (uint32_t i = 0; i < nheld; i++)
            if (!intact(held[i], stamp[i])) return "no overlap: a held block was changed by someone else";
    }
    *at = STEPS;
    while (nheld) {
        nheld--;
        if (!intact(held[nheld], stamp[nheld])) return "no overlap: a held block was changed by someone else";
        if (!ad->free(held[nheld], 0)) return "free refused a block the pool handed out";
    }
    for (uint32_t i = 0; i < POOL_BLOCKS; i++) {
        uintptr_t b = ad->alloc(0, 0);
        if (!b) return "no block lost: fewer than POOL_BLOCKS blocks after every block was freed";
        for (uint32_t j = 0; j < i; j++)
            if (held[j] == b) return "no block twice: after the drain";
        held[i] = b;
    }
    if (ad->alloc(0, 0)) return "capacity: a block beyond POOL_BLOCKS after the drain";
    return NULL;
}

int main(void)
{
    int ok = 1;
    printf("pool pilot test: %u blocks of %u bytes, %u sequences of %u steps\n",
           POOL_BLOCKS, POOL_BLOCK_SIZE, SEQUENCES, STEPS);
    for (size_t c = 0; c < sizeof(CASES) / sizeof(CASES[0]); c++) {
        const pool_adapter *ad = CASES[c].ad;
        const char *why = NULL;
        uint32_t seq, at = 0;
        irq_sections = 0;
        for (seq = 0; seq < SEQUENCES && !why; seq++) why = run(ad, 0x9E3779B9u ^ (seq * 2654435761u), &at);
        int passed = why == NULL;
        int as_expected = passed == CASES[c].expect_pass;
        ok &= as_expected;
        if (passed)
            printf("%-34s pass   (expected %s)%s  interrupt-off sections: %u\n", ad->name,
                   CASES[c].expect_pass ? "pass" : "FAIL", as_expected ? "" : "  <-- NOT AS EXPECTED", irq_sections);
        else
            printf("%-34s FAIL   (expected %s)%s  sequence %u, step %u: %s\n", ad->name,
                   CASES[c].expect_pass ? "pass" : "FAIL", as_expected ? "" : "  <-- NOT AS EXPECTED", seq - 1, at, why);
    }
    printf("%s\n", ok ? "exit 0: every verdict as expected" : "exit 1: a verdict not as expected");
    return ok ? 0 : 1;
}
