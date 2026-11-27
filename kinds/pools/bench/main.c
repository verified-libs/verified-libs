/* The pools kind's benchmark image (lab/plans/2026-11-26-pools-kind.md, section 2):
 * one configuration (BENCH_POOL, an adapter of ../pool.h) and the reference
 * free list (adapter_ref, ../adapter_ref.c, compiled as ref_pool.o into the
 * fixed part) as the baseline, timed by the board's time_call()
 * (firmware/common/<board>/board.h, unchanged), as the CRC kind's image
 * (kinds/crc/bench/main.c) does it. One context: no interrupts.
 *
 * Scenarios, each with the cache off and on, RUNS timed calls of each
 * operation (alloc and free) unless said otherwise:
 *   0 pair              alloc then free of the same block, the pool almost empty
 *   1 pair_full         the same with all but one block held
 *   2 fill_drain_lifo   POOL_BLOCKS allocs, then the frees in reverse order, RUNS/POOL_BLOCKS times
 *   3 fill_drain_fifo   the same, the frees in the order of the allocs
 *   4 mixed             a fixed-seed sequence of allocs and frees, the pool between 25 % and 75 % full
 *                       (2 * RUNS calls; the counts of alloc and free are in the stats)
 *   5 empty             alloc on an exhausted pool (RUNS allocs, no free)
 * and init once per cache state (struct stat init).
 *
 * Every call is checked outside the timed window (as the host test,
 * ../test_pool.c): alloc gives a block if and only if fewer than POOL_BLOCKS
 * are held; the block lies in the adapter's region at the promised alignment
 * and is not one already held; each holder writes a pattern into its block
 * and finds it intact at the free; the canaries around the adapter's memory
 * are intact after every call; all blocks come back at the end. A fault
 * counts in errors (the record must have 0).
 *
 * In a bundle (onepool.py, the slots of ../slots.txt): the boot stub of
 * version 2 starts the image the host named in the selection words; the image
 * records the address it runs from (VTOR) and the host's run number. The
 * placement bytes (BENCH_PLACE) lie between the fixed part and the adapter,
 * FAR bytes (BENCH_SHIFT) between the adapter and the library. */
#include <stdint.h>
#include <string.h>
#include "board.h"
#include "board_uart.h"   /* only for BOARD_SELECT_ADDR, on the board that has one (RP2350) */
#include "select.h"
VL_SELECT_DEFINE
#include "../pool.h"

#ifndef BENCH_POOL
#error BENCH_POOL: the adapter of the configuration
#endif
#define RUNS 256u
#define NSC 6u
#define NOP 2u            /* 0 alloc, 1 free */

#define RESULT_MAGIC 0x564C5031u   /* "VLP1" */
#define RESULT_VERSION 1u

struct stat { uint32_t min, max, sum, first, count; };
struct poolres { struct stat s[2][NSC][NOP]; struct stat init[2]; uint32_t errors; };   /* [cache][scenario][op] */
struct results {
    uint32_t magic, version, done, clock_hz, runs, nsc, nlibs, blocks, block_size;
    struct poolres lib[2];           /* 0 the reference (baseline), 1 the configuration */
    uint32_t dwt_stalls, board_id, read_overhead, empty_call_min;
    uint32_t image_base;             /* the vector table this image runs from (VTOR, set by the boot stub) */
    uint32_t nonce;                  /* the fourth selection word: the host's number for this start */
};
__attribute__((section(".results")))
volatile struct results results;

#define BENCH_HARNESS __attribute__((noinline, aligned(32), section(".text.bench_harness")))

#ifndef BENCH_PLACE
#define BENCH_PLACE 0
#endif
#if BENCH_PLACE > 0
__attribute__((section(".bench_place"), used, aligned(1)))
static const uint8_t bench_place[BENCH_PLACE] = {0};
#endif
#ifndef BENCH_SHIFT
#define BENCH_SHIFT 0
#endif
#if BENCH_SHIFT > 0
__attribute__((section(".bench_shift"), used, aligned(1)))
static const uint8_t bench_shift[BENCH_SHIFT] = {0};
#endif

/* "Interrupts off" of the PRIMASK row is PRIMASK itself on a board (pool.h); nothing to give here. */

static uint32_t empty_op(uintptr_t a, uintptr_t b) { (void)a; (void)b; return 0; }

BENCH_HARNESS static uint32_t empty_call_min(void)
{
    uint32_t ret, m = 0xFFFFFFFFu;
    for (uint32_t i = 0; i < 64; i++) {
        uint32_t c = time_call(empty_op, 0, 0, &ret);
        if (c < m) m = c;
    }
    return m;
}

BENCH_HARNESS static void stat_add(volatile struct stat *s, uint32_t c)
{
    if (c == 0) results.dwt_stalls++;
    if (s->count == 0) { s->min = s->max = s->sum = s->first = c; s->count = 1; return; }
    if (c < s->min) s->min = c;
    if (c > s->max) s->max = c;
    s->sum += c;
    s->count++;
}

/* The checker's record of the blocks held, as the host test's. */
static uintptr_t held[POOL_BLOCKS + 1];
static uint32_t stamp[POOL_BLOCKS + 1], nheld, nstamp;
static uintptr_t lo, hi;
static const pool_adapter *cur;
static volatile uint32_t *errs;

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
static void set_canaries(void)
{
    for (uint32_t i = 0; i < POOL_CANARY_WORDS; i++) cur->canary_lo[i] = cur->canary_hi[i] = POOL_CANARY ^ i;
}
static int canaries_ok(void)
{
    for (uint32_t i = 0; i < POOL_CANARY_WORDS; i++)
        if (cur->canary_lo[i] != (POOL_CANARY ^ i) || cur->canary_hi[i] != (POOL_CANARY ^ i)) return 0;
    return 1;
}

/* One alloc, timed into s (NULL: untimed), checked. */
BENCH_HARNESS static void take(volatile struct stat *s)
{
    uint32_t b, c = 0;
    if (s) { c = time_call((rb_op)cur->alloc, 0, 0, &b); stat_add(s, c); }
    else b = (uint32_t)cur->alloc(0, 0);
    if (!canaries_ok()) { (*errs)++; set_canaries(); }
    if (nheld < POOL_BLOCKS && !b) { (*errs)++; return; }
    if (nheld >= POOL_BLOCKS) { if (b) (*errs)++; return; }
    if (b < lo || b + POOL_BLOCK_SIZE > hi || b % cur->align) { (*errs)++; return; }
    for (uint32_t i = 0; i < nheld; i++) if (held[i] == b) { (*errs)++; return; }
    held[nheld] = b;
    stamp[nheld] = ++nstamp;
    fill(b, nstamp);
    nheld++;
}

/* Free the k-th held block, timed into s (NULL: untimed), checked. */
BENCH_HARNESS static void give(uint32_t k, volatile struct stat *s)
{
    uint32_t r, c;
    if (!intact(held[k], stamp[k])) (*errs)++;
    if (s) { c = time_call(cur->free, held[k], 0, &r); stat_add(s, c); }
    else r = cur->free(held[k], 0);
    if (!r) (*errs)++;
    if (!canaries_ok()) { (*errs)++; set_canaries(); }
    held[k] = held[nheld - 1];
    stamp[k] = stamp[nheld - 1];
    nheld--;
}

BENCH_HARNESS static void drain(void) { while (nheld) give(nheld - 1, 0); }

static uint32_t rng;
static uint32_t xs(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }

static uint32_t init_op(uintptr_t a, uintptr_t b) { (void)a; (void)b; cur->init(); return 0; }

BENCH_HARNESS static void run_all(const pool_adapter *ad, volatile struct poolres *r, int cache)
{
    volatile struct stat (*s)[NOP] = r->s[cache];
    uint32_t ret;
    cur = ad;
    errs = &r->errors;
    ad->region(&lo, &hi);
    stat_add(&r->init[cache], time_call(init_op, 0, 0, &ret));
    set_canaries();
    nheld = 0;
    for (uint32_t i = 0; i < RUNS; i++) { take(&s[0][0]); give(nheld - 1, &s[0][1]); }          /* pair */
    while (nheld < POOL_BLOCKS - 1) take(0);
    for (uint32_t i = 0; i < RUNS; i++) { take(&s[1][0]); give(nheld - 1, &s[1][1]); }          /* pair_full */
    drain();
    for (uint32_t r2 = 0; r2 < RUNS / POOL_BLOCKS; r2++) {                                     /* fill_drain_lifo */
        while (nheld < POOL_BLOCKS) take(&s[2][0]);
        while (nheld) give(nheld - 1, &s[2][1]);
    }
    for (uint32_t r2 = 0; r2 < RUNS / POOL_BLOCKS; r2++) {                                     /* fill_drain_fifo */
        while (nheld < POOL_BLOCKS) take(&s[3][0]);
        while (nheld) {
            give(0, &s[3][1]);
            if (nheld > 1) {                  /* give() moved the last block to slot 0: put the order back */
                uintptr_t b = held[0]; uint32_t t = stamp[0];
                memmove(&held[0], &held[1], (nheld - 1) * sizeof held[0]);
                memmove(&stamp[0], &stamp[1], (nheld - 1) * sizeof stamp[0]);
                held[nheld - 1] = b; stamp[nheld - 1] = t;
            }
        }
    }
    rng = 0x9E3779B9u;                                                                          /* mixed */
    while (nheld < POOL_BLOCKS / 2) take(0);
    for (uint32_t i = 0; i < 2 * RUNS; i++) {
        int a = nheld < POOL_BLOCKS / 4 ? 1 : nheld > 3 * POOL_BLOCKS / 4 ? 0 : (int)(xs() & 1);
        if (a) take(&s[4][0]); else give(xs() % nheld, &s[4][1]);
    }
    drain();
    while (nheld < POOL_BLOCKS) take(0);                                                       /* empty */
    for (uint32_t i = 0; i < RUNS; i++) take(&s[5][0]);
    drain();
    for (uint32_t i = 0; i < POOL_BLOCKS; i++) take(0);                                        /* all back */
    if (nheld != POOL_BLOCKS) r->errors++;
    drain();
}

extern const pool_adapter adapter_ref;
extern ADAPTER_CONST pool_adapter BENCH_POOL;

int main(void)
{
    board_init();
    memset((void *)&results, 0, sizeof results);
    results.magic = RESULT_MAGIC;
    results.version = RESULT_VERSION;
    results.clock_hz = board_clock_hz();
    results.runs = RUNS;
    results.nsc = NSC;
    results.nlibs = 2;
    results.blocks = POOL_BLOCKS;
    results.block_size = POOL_BLOCK_SIZE;
    results.board_id = BOARD_ID;
    results.read_overhead = BOARD_READ_OVERHEAD;
    results.dwt_stalls = board_counter_running() ? 0u : 0xFFFFFFFFu;
    results.image_base = *(volatile uint32_t *)0xE000ED08u;   /* VTOR */
    results.nonce = SEL[3];
    results.empty_call_min = empty_call_min();
    const pool_adapter *libs[2] = { &adapter_ref, (const pool_adapter *)&BENCH_POOL };
    for (int k = 0; k < 2; k++) {
        board_cache(0);
        run_all(libs[k], &results.lib[k], 0);
        board_cache(1);
        run_all(libs[k], &results.lib[k], 1);
    }
    results.done = 1;
    board_idle();
    return 0;
}
