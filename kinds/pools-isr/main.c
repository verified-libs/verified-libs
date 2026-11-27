/* The board image of the pools concurrency series: the interrupt sweep and
 * the interrupts-off time (lab/plans/2026-11-27-pools-concurrency.md, 3.2 and
 * 3.3). One image per configuration (POOL_ISR_ADAPTER, an adapter of
 * ../pools/pool.h), all of a board in one bundle behind the first series'
 * boot stub, which starts the image the host selects (select.h), as the
 * first series' images are started; the host reads the result block at the
 * start of RAM.
 *
 * The sweep is the ring buffers' (firmware/nrf5340-rb-stress/main.c,
 * sweep=1), copied, not shared: SysTick (core registers, the same on every
 * Cortex-M) as a one-shot armed d core cycles before main's call, for d = 1,
 * 2, 3, ... until the interrupt has come after the call SWEEP_TAIL times in a
 * row (or d reaches SWEEP_DMAX). The handler makes the interrupt's calls and
 * records the interrupted PC in a coverage bitmap (one bit per halfword of
 * the first COV_WORDS * 64 bytes of the image), which the host maps to the
 * instructions of the configuration's functions. Each trial is judged by
 * verdict.h, the same code as the host check (contract.c): the start states,
 * main's calls and the interrupt's calls are the host check's, and the free
 * list's start is varied (SWEEP_REPS rotations of the scattered free order).
 * Every trial runs with the cache off and then on (board_cache, as the first
 * series).
 *
 * The interrupts-off time (3.3): main arms SysTick with reload d and, once
 * the count has started, sets the reload to 0xFFFFFF; when the count runs out
 * it starts again from 0xFFFFFF, so the handler's first read of the current
 * value gives the cycles since it ran out (0xFFFFFF - value). Its latency is
 * that figure; the largest latency of an image less the smallest of the
 * reference without a lock (which never masks; every image calibrates
 * with it first, in the same image, the cal[] fields) is the longest time
 * an interrupt waited because the configuration had interrupts off. Only trials
 * whose interrupt came during main's call count, and only figures below
 * 0x10000 (a count that ran out before the reload was set gives a nonsense
 * figure, which is dropped).
 */
#include <stdint.h>
#include <string.h>
#include "board.h"
#include "board_uart.h"   /* only for BOARD_SELECT_ADDR, on the board that has one (RP2350) */
#include "select.h"
#include "pool.h"
#include "verdict.h"
VL_SELECT_DEFINE

#ifndef POOL_ISR_ADAPTER
#error POOL_ISR_ADAPTER: the adapter of the configuration
#endif
#ifndef ADAPTER_CONST
#define ADAPTER_CONST const
#endif
#define RESULT_MAGIC 0x564C4931u   /* "VLI1" */
#define RESULT_VERSION 1u
#define SWEEP_TAIL 16u
#define SWEEP_DMAX 4096u
#define SWEEP_REPS 4u
#define COV_WORDS 1024u            /* 64 KB of code, a bit per halfword */
#define LAT_OK 0x10000u

extern const pool_adapter adapter_ref;            /* the calibration of the latency: never masks */
extern ADAPTER_CONST pool_adapter POOL_ISR_ADAPTER;

/* ---- the result block (the host reads it over the debug port) ---- */
struct cache_res {
    uint32_t trials, inside, before, after;  /* trials; the interrupt during, before, after main's call */
    uint32_t faults[NPF];                    /* per fault code (verdict.h) */
    uint32_t first_fault, first_case, first_d;   /* first_case: h << 16 | main op << 8 | interrupt seq << 4 | rotation */
    uint32_t lat_min, lat_max, lat_max_case, lat_max_d, lat_n;
};
struct results {
    uint32_t magic, version, done, clock_hz, board_id, image_base, nonce, faults_total;
    struct cache_res c[2];                   /* cache off, on */
    uint32_t cal_lat_min[2], cal_lat_n[2];   /* the reference's smallest latency, per cache state */
    uint32_t cov_outside;
    uint32_t cov[COV_WORDS];
};
__attribute__((section(".results")))
volatile struct results results;

static uint32_t get_primask(void)
{
    uint32_t p;
    __asm volatile("mrs %0, primask" : "=r"(p));
    return p;
}

/* ---- SysTick as a one-shot ---- */
#define SYST_CSR (*(volatile uint32_t *)0xE000E010u)
#define SYST_RVR (*(volatile uint32_t *)0xE000E014u)
#define SYST_CVR (*(volatile uint32_t *)0xE000E018u)
#define ICSR     (*(volatile uint32_t *)0xE000ED04u)
#define PENDSTCLR (1u << 25)
static inline void systick_stop(void)
{
    SYST_CSR = 0;
    __asm volatile("dsb" ::: "memory");
    ICSR = PENDSTCLR;
    __asm volatile("dsb\n isb" ::: "memory");
}

static volatile uint32_t phase;   /* 0 before main's call, 1 during, 2 after */
static volatile uint32_t fired, fired_phase, lat;
static uintptr_t cov_base;
static int cov_on;
static volatile struct cache_res *cur;

__attribute__((used)) void isr_sweep(const uint32_t *frame)
{
    uint32_t v = SYST_CVR;                 /* first: the cycles since the count ran out */
    uint32_t rvr = SYST_RVR;
    systick_stop();
    if (fired) return;                     /* defensive: one interrupt per trial */
    lat = rvr == 0xFFFFFFu ? 0xFFFFFFu - v : 0xFFFFFFFFu;
    fired_phase = phase;
    if (fired_phase == 1 && cov_on) {
        uintptr_t off = ((frame[6] & ~1u) - cov_base) >> 1;
        if (off < COV_WORDS * 32u) results.cov[off >> 5] |= 1u << (off & 31u);
        else results.cov_outside++;
    }
    uintptr_t got = 0;
    for (int i = 0; i < isr_seq->n; i++) {
        if (isr_seq->op[i] == OP_A) {
            got = isr_ret[i] = ad->alloc(0, 0);
            if (got && in_region(got)) fill(got);
        } else {
            uintptr_t b = i ? got : isr_blk;
            isr_arg[i] = b;
            isr_ret[i] = b ? ad->free(b, 0) : 1;
        }
        if (get_primask()) masked_after_isr = 1;
    }
    fired = 1;
}
__attribute__((naked)) void SysTick_Handler(void)
{
    __asm volatile("mrs r0, msp\n"
                   "ldr r1, =isr_sweep\n"
                   "bx  r1\n"
                   ".ltorg\n");
}

/* ---- one trial ---- */
static enum fault trial(uint32_t h, uint32_t r, int need_main, int need_isr, const seq *sq, uint32_t d)
{
    isr_seq = &NO_ISR;
    enum fault f = setup(h, r);
    if (f != PF_OK) return f;
    who_frees(need_main, need_isr);
    isr_seq = sq;
    masked_after_isr = masked_after_main = 0;
    isr_ret[0] = isr_ret[1] = isr_arg[0] = isr_arg[1] = 0;
    fired = 0; phase = 0;
    systick_stop();
    SYST_RVR = d;
    SYST_CVR = 0;
    SYST_CSR = 7u;                         /* core clock, interrupt, enable */
    while (SYST_CVR == 0 && !fired) {}     /* the count has started (or run out already, for a small d) */
    SYST_RVR = 0xFFFFFFu;
    phase = 1;
    __asm volatile("" ::: "memory");
    if (main_op == OP_A) main_ret = ad->alloc(0, 0);
    else main_ret = ad->free(main_blk, 0);
    __asm volatile("" ::: "memory");
    phase = 2;
    if (get_primask()) masked_after_main = 1;
    for (uint32_t guard = 0; !fired && guard < 4u * SWEEP_DMAX; guard++) {}
    if (!fired) { systick_stop(); fired_phase = 2; lat = 0xFFFFFFFFu; }
    if (main_op == OP_A && main_ret && in_region(main_ret)) fill(main_ret);
    return verdict();
}

static void sweep_one(volatile struct cache_res *c)
{
    c->lat_min = 0xFFFFFFFFu;
    cov_on = 1;
    for (uint32_t hi_ = 0; hi_ < NHELD; hi_++)
        for (int mop = OP_A; mop <= OP_F; mop++)
            for (uint32_t s = 0; s < NSEQ; s++) {
                const seq *sq = &ISR_SEQS[s];
                uint32_t h = HELD[hi_];
                int need_main = mop == OP_F, need_isr = sq->op[0] == OP_F;
                if (h < (uint32_t)(need_main + need_isr)) continue;
                main_op = mop;
                for (uint32_t r = 0; r < SWEEP_REPS; r++) {
                    uint32_t tail = 0;
                    for (uint32_t d = 1; d <= SWEEP_DMAX && tail < SWEEP_TAIL; d++) {
                        enum fault f = trial(h, r, need_main, need_isr, sq, d);
                        c->trials++;
                        uint32_t ph = fired_phase;
                        if (ph == 0) c->before++;
                        else if (ph == 1) c->inside++;
                        else c->after++;
                        tail = ph == 2 ? tail + 1 : 0;
                        uint32_t cs = h << 16 | (uint32_t)mop << 8 | s << 4 | r;
                        if (ph == 1 && lat < LAT_OK) {
                            c->lat_n++;
                            if (lat < c->lat_min) c->lat_min = lat;
                            if (lat > c->lat_max) { c->lat_max = lat; c->lat_max_case = cs; c->lat_max_d = d; }
                        }
                        if (f != PF_OK) {
                            if (c->faults[f]++ == 0 && !c->first_fault) { c->first_fault = f; c->first_case = cs; c->first_d = d; }
                            results.faults_total++;
                        }
                    }
                }
            }
}

/* The latency with interrupts never off: the reference without a lock, 16
 * blocks held, main's alloc and the interrupt's alloc, one rotation; only
 * the latencies count (the reference is a control and may fault here). */
static void calibrate(int cache)
{
    uint32_t mn = 0xFFFFFFFFu, n = 0;
    cov_on = 0;
    main_op = OP_A;
    for (uint32_t d = 1, tail = 0; d <= SWEEP_DMAX && tail < SWEEP_TAIL; d++) {
        (void)trial(16, 0, 0, 0, &ISR_SEQS[0], d);
        tail = fired_phase == 2 ? tail + 1 : 0;
        if (fired_phase == 1 && lat < LAT_OK) { n++; if (lat < mn) mn = lat; }
    }
    results.cal_lat_min[cache] = mn;
    results.cal_lat_n[cache] = n;
}

int main(void)
{
    board_init();
    memset((void *)&results, 0, sizeof results);
    results.magic = RESULT_MAGIC;
    results.version = RESULT_VERSION;
    results.clock_hz = board_clock_hz();
    results.board_id = BOARD_ID;
    results.image_base = *(volatile uint32_t *)0xE000ED08u;   /* VTOR */
    results.nonce = SEL[3];
    cov_base = results.image_base;
    for (int cache = 0; cache < 2; cache++) {
        board_cache(cache);
        ad = &adapter_ref;
        calibrate(cache);
        ad = (const pool_adapter *)&POOL_ISR_ADAPTER;
        ad->init();
        sweep_one(&results.c[cache]);
    }
    results.done = 1;
    board_idle();
    return 0;
}
