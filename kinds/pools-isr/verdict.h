/* The verdict of one trial of the concurrency check, the same on the host
 * (contract.c) and on the boards (main.c): the start state, the calls, and
 * what their answers must be (lab/plans/2026-11-27-pools-concurrency.md,
 * 3.1 and 3.2). One file, so that the host check and the board sweep judge
 * with the same code; included once by each, after pool.h.
 *
 * The including file provides:
 *   POOL_IS_MASKED()   1 while interrupts are off (the host's flag, PRIMASK)
 * and sets main_ret, isr_ret, isr_arg, masked_after_main, masked_after_isr
 * while it runs a trial. */
#ifndef POOLS_ISR_VERDICT_H
#define POOLS_ISR_VERDICT_H
#include <stdint.h>
#include <string.h>

/* ---- the calls and the start states ---- */
enum { OP_A = 1, OP_F = 2 };
typedef struct { int n; int op[2]; const char *text; } seq;
static const seq ISR_SEQS[] = {
    { 1, { OP_A, 0 }, "alloc" }, { 1, { OP_F, 0 }, "free" }, { 2, { OP_A, OP_F }, "alloc, free it" },
    { 2, { OP_F, OP_A }, "free, alloc" }, { 2, { OP_A, OP_A }, "alloc, alloc" },
};
#define NSEQ (sizeof ISR_SEQS / sizeof ISR_SEQS[0])
static const seq NO_ISR = { 0, { 0, 0 }, "" };
static const uint32_t HELD[] = { 0, 1, 2, 16, 30, 31, 32 };
#define NHELD (sizeof HELD / sizeof HELD[0])

/* ---- what went wrong: a code, the same on host and board ---- */
enum fault {
    PF_OK, PF_SETUP, PF_MASK_MAIN, PF_MASK_ISR, PF_REGION, PF_CANARY, PF_TWICE, PF_NONE_FREE, PF_FULL, PF_FREE_ANSWER,
    PF_PATTERN, PF_GIVEBACK, PF_AFTER_TWICE, PF_AFTER_LOST, PF_AFTER_MORE, PF_AFTER_CANARY, PF_CRASH, NPF
};
static const char *const FAULT_TEXT[NPF] = {
    "ok",
    "setup: the pool did not give 32 blocks after init, or refused a free",
    "interrupts off after main's call",
    "interrupts off after an interrupt's call",
    "a block outside the region or misaligned",
    "a canary around the pool's memory changed",
    "no order of the calls gives these answers: a block handed out while it is held (a block twice)",
    "no order of the calls gives these answers: an alloc gave no block while fewer than 32 were held",
    "no order of the calls gives these answers: an alloc gave a block while all 32 were held",
    "a free did not answer 1",
    "a held block's pattern changed: a block shared",
    "a free refused when giving every block back",
    "afterwards a block given twice",
    "afterwards fewer than 32 blocks: blocks lost",
    "afterwards more than 32 blocks",
    "a canary changed while giving every block back",
    "the program crashed: a call followed the pool's corrupted state outside memory",
};

/* ---- the trial's state ---- */
static const pool_adapter *ad;
static uintptr_t lo, hi;
static uintptr_t held[POOL_BLOCKS];      /* blocks held at the start */
static uint32_t nheld;
static uintptr_t main_blk, isr_blk;      /* the block main / the interrupt frees */
static int main_op;
static const seq *isr_seq;
static volatile uintptr_t main_ret, isr_ret[2], isr_arg[2];
static volatile int masked_after_isr, masked_after_main;

static void set_canaries(void)
{
    for (uint32_t i = 0; i < POOL_CANARY_WORDS; i++) ad->canary_lo[i] = ad->canary_hi[i] = POOL_CANARY ^ i;
}
static int canaries_ok(void)
{
    for (uint32_t i = 0; i < POOL_CANARY_WORDS; i++)
        if (ad->canary_lo[i] != (POOL_CANARY ^ i) || ad->canary_hi[i] != (POOL_CANARY ^ i)) return 0;
    return 1;
}
static uint8_t stamp_of(uintptr_t b) { return (uint8_t)(((uint32_t)b * 2654435761u) >> 24) | 1u; }
static void fill(uintptr_t b)
{
    uint8_t *p = (uint8_t *)b, s = stamp_of(b);
    for (uint32_t i = 0; i < POOL_BLOCK_SIZE; i++) p[i] = (uint8_t)(s + i);
}
static int intact(uintptr_t b)
{
    const uint8_t *p = (const uint8_t *)b;
    uint8_t s = stamp_of(b);
    for (uint32_t i = 0; i < POOL_BLOCK_SIZE; i++) if (p[i] != (uint8_t)(s + i)) return 0;
    return 1;
}
static int in_region(uintptr_t b) { return b >= lo && b < hi; }

/* The start state with h blocks held, the free list in a scattered order
 * starting at r (r = 0 on the host; the board sweep varies it): init, all 32
 * allocated, the ones not held freed in the order (k * 7 + r) mod 32. */
static enum fault setup(uint32_t h, uint32_t r)
{
    uintptr_t all[POOL_BLOCKS];
    ad->init();
    ad->region(&lo, &hi);
    set_canaries();
    for (uint32_t i = 0; i < POOL_BLOCKS; i++)
        if (!(all[i] = ad->alloc(0, 0)) || !in_region(all[i])) return PF_SETUP;
    nheld = 0;
    for (uint32_t k = 0; k < POOL_BLOCKS; k++) {
        uintptr_t b = all[(k * 7u + r) % POOL_BLOCKS];
        if (k < h) { held[nheld++] = b; fill(b); }
        else if (ad->free(b, 0) != 1) return PF_SETUP;
    }
    return PF_OK;
}
/* who frees which block: main its first held block, the interrupt the next */
static void who_frees(int need_main, int need_isr)
{
    main_blk = need_main ? held[0] : 0;
    isr_blk = need_isr ? held[need_main] : 0;
}

static int in(const uintptr_t *s, uint32_t n, uintptr_t b)
{
    for (uint32_t i = 0; i < n; i++) if (s[i] == b) return 1;
    return 0;
}
static void del(uintptr_t *s, uint32_t *n, uintptr_t b)
{
    for (uint32_t i = 0; i < *n; i++) if (s[i] == b) { s[i] = s[--*n]; return; }
}

/* The calls in one order: main's after the first s of the interrupt's.
 * PF_OK if every answer fits; the blocks held after them in out. */
static enum fault order_fits(int s, uintptr_t *out, uint32_t *nout)
{
    uintptr_t H[POOL_BLOCKS + 4];
    uint32_t n = nheld;
    memcpy(H, held, nheld * sizeof H[0]);
    int order[3], k = 0;
    for (int j = 0; j <= isr_seq->n; j++) {
        if (j == s) order[k++] = -1;              /* main */
        if (j < isr_seq->n) order[k++] = j;       /* the interrupt's j-th call */
    }
    for (int i = 0; i < k; i++) {
        int is_main = order[i] < 0, idx = order[i];
        int op = is_main ? main_op : isr_seq->op[idx];
        uintptr_t r = is_main ? main_ret : isr_ret[idx];
        if (op == OP_A) {
            if (!r) {
                if (n < POOL_BLOCKS) return PF_NONE_FREE;
            } else {
                if (n >= POOL_BLOCKS) return PF_FULL;
                if (in(H, n, r)) return PF_TWICE;
                H[n++] = r;
            }
        } else {
            uintptr_t b = is_main ? main_blk : isr_arg[idx];
            if (!b) continue;
            if (r != 1) return PF_FREE_ANSWER;
            del(H, &n, b);
        }
    }
    memcpy(out, H, n * sizeof H[0]);
    *nout = n;
    return PF_OK;
}

/* The verdict of a trial; it gives every block back. */
static enum fault verdict(void)
{
    if (masked_after_main) return PF_MASK_MAIN;
    if (masked_after_isr) return PF_MASK_ISR;
    uintptr_t rs[3] = { main_op == OP_A ? main_ret : 0, 0, 0 };
    for (int i = 0; i < isr_seq->n; i++) if (isr_seq->op[i] == OP_A) rs[1 + i] = isr_ret[i];
    for (int i = 0; i < 3; i++)
        if (rs[i] && (!in_region(rs[i]) || rs[i] % ad->align)) return PF_REGION;
    if (!canaries_ok()) return PF_CANARY;
    uintptr_t H[POOL_BLOCKS + 4];
    uint32_t n = 0;
    enum fault first = PF_OK, f = PF_SETUP;
    for (int s = 0; s <= isr_seq->n && f != PF_OK; s++) {
        f = order_fits(s, H, &n);
        if (f != PF_OK && first == PF_OK) first = f;
    }
    if (f != PF_OK) return first;
    for (uint32_t i = 0; i < n; i++) if (!intact(H[i])) return PF_PATTERN;
    /* every block back, then exactly 32 different ones */
    for (uint32_t i = 0; i < n; i++) if (ad->free(H[i], 0) != 1) return PF_GIVEBACK;
    uintptr_t all[POOL_BLOCKS + 1];
    uint32_t got = 0;
    while (got <= POOL_BLOCKS) {
        uintptr_t b = ad->alloc(0, 0);
        if (!b) break;
        if (in(all, got, b) || !in_region(b)) {
            for (uint32_t i = 0; i < got; i++) ad->free(all[i], 0);
            return PF_AFTER_TWICE;
        }
        all[got++] = b;
    }
    for (uint32_t i = 0; i < got; i++) ad->free(all[i], 0);
    if (got != POOL_BLOCKS) return got < POOL_BLOCKS ? PF_AFTER_LOST : PF_AFTER_MORE;
    if (!canaries_ok()) return PF_AFTER_CANARY;
    return PF_OK;
}
#endif
