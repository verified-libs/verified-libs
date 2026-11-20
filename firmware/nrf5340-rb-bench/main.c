/*
 * nrf5340-rb-bench: cycles per call for push/pop of single bytes and of
 * blocks, per library, with the instruction cache off and on. Results go to
 * 0x20000000 and are decoded on the host by decode.py.
 *
 * Every call is timed by time_call(), written in assembly so the timed
 * window is exactly
 *     ldr t0, CYCCNT ; blx op ; <op> ; ldr t1, CYCCNT
 * for every operation and library alike. Every popped byte is checked.
 *
 * Scenarios (same order as SCENARIOS in decode.py):
 *   0 single    1024 x (push 1 byte, pop 1 byte)        buffer holds 0..1
 *   1 burst16   64 x (16 pushes, then 16 pops)           buffer holds 0..16
 *   2 block4    1024 x (push_n 4, pop_n 4)
 *   3 block16   1024 x (push_n 16, pop_n 16)
 *   4 block64   1024 x (push_n 64, pop_n 64)
 *   5 dma16     1024 x (zero-copy write 16 bytes, zero-copy read 16 bytes)
 *   6 dma64     1024 x (zero-copy write 64 bytes, zero-copy read 64 bytes)
 * DMA scenarios use the library's zero-copy API (only libraries that have
 * one): get the contiguous write area, fill it (untimed: the DMA hardware's
 * job), commit; get the read area, check it in place (untimed), release.
 * A transfer split at the wrap needs two acquire/commit pairs. The stat per
 * transfer is the sum of the timed library calls, i.e. the CPU cost of the
 * bookkeeping for N bytes, without moving the data.
 * Block scenarios start one slot into the buffer, so with 128 slots some
 * transfers are split at the wrap and some are not, as in real use.
 * Per library: all scenarios with the cache off, then the cache is
 * invalidated and enabled and all scenarios run again. "first" is a cold
 * run only for the first cache-on scenario (single).
 * The "baseline" adapter is the cheapest possible implementation (one store
 * and one load, or one memcpy each way), timed the same way.
 * Raw counts include the counter read overhead (BOARD_READ_OVERHEAD: 1 cycle
 * for CYCCNT on the M33); decode.py subtracts it.
 *
 * The board (clock, cycle counter, cache control, time_call itself) comes
 * from common/<BOARD>/board.h; the directory name is historical.
 */
#include <stdint.h>
#include <string.h>
#include "board.h"
#include "bench.h"

#define RUNS 1024u
#ifdef BENCH_ONLY   /* size.sh: a firmware with one configuration, to measure what it adds; never run */
#define NLIBS 1u
extern const rb_adapter adapter_none;   /* size_none.c: no library at all */
#elif defined(BENCH_MP)   /* SET=mp: the modes for more than one producer or consumer */
#define NLIBS 10u
#elif defined(BENCH_RUST)   /* SET=rust: the Rust libraries (../rust-adapters) */
#define NLIBS 5u
#elif defined(BENCH_NORDIC)   /* SET=nordic: nrf_ringbuf, nRF5340 only (Nordic's licence) */
#define NLIBS 6u
extern const rb_adapter adapter_nrf_ringbuf, part_nrf_atomics, part_memcpy1, part_nrf_len0;
#else
#define NLIBS 37u
#endif
#define NSCEN 7u
#define RESULT_MAGIC 0x564C4235u /* "VLB5" */
#define RESULT_VERSION 6u        /* 6: clock_hz, board_id, overhead, empty call */

struct stat { uint32_t min, max, sum, first, count; };
struct series { struct stat push, pop; };
struct libres { struct series s[2][NSCEN]; uint32_t errors; }; /* [cache][scen] */

struct results {
    uint32_t magic, version, done, clock_hz, runs, nlibs, nscen;
    struct libres lib[NLIBS];
    uint32_t dwt_stalls;   /* timed calls where the cycle counter did not advance */
    uint32_t board_id, read_overhead;
    uint32_t empty_call_min; /* raw cycles of an empty call (calibration) */
};
__attribute__((section(".results")))
volatile struct results results;

/* Baseline: the cheapest possible implementation. */
static uint8_t baseline_store[RB_SLOTS];
BENCH_ALIGN static void baseline_reset(void) {}
BENCH_ALIGN static uint32_t baseline_push(uintptr_t v, uintptr_t b) { (void)b; baseline_store[0] = (uint8_t)v; return 1; }
BENCH_ALIGN static uint32_t baseline_pop(uintptr_t p, uintptr_t b) { (void)b; *(uint8_t *)p = baseline_store[0]; return 1; }
BENCH_ALIGN static uint32_t baseline_push_n(uintptr_t p, uintptr_t n) { memcpy(baseline_store, (const void *)p, n); return n; }
BENCH_ALIGN static uint32_t baseline_pop_n(uintptr_t p, uintptr_t n) { memcpy((void *)p, baseline_store, n); return n; }
static const rb_adapter adapter_baseline = {
    baseline_reset, baseline_push, baseline_pop, baseline_push_n, baseline_pop_n, 0, 0
};

/* Placement (2026-11-13). The harness functions that run around the timed
 * calls are in their own section, which every linker script puts first in
 * .text (with time_call, then .bench_shift, then all other code), each
 * function aligned to 32 bytes: a change in a library, an adapter or
 * another set does not move them, so it cannot change the timings through
 * them. (Before, two lines added to scen_block and main shifted the harness
 * by a few bytes, and some means moved by up to 15 % with the libraries
 * byte-identical: NUCLEO-G474RE, lwrb.)
 * BENCH_SHIFT=N (placement experiment, run.sh SHIFT=N): N bytes after the
 * harness, so every library function lies N bytes further on, as if
 * another library had grown by N bytes; the spread over N is the
 * measurement's sensitivity to code placement. Adapters stay 32-byte
 * aligned (BENCH_ALIGN); the library code they call moves. */
#define BENCH_HARNESS __attribute__((noinline, aligned(32), section(".text.bench_harness")))
#ifndef BENCH_SHIFT
#define BENCH_SHIFT 0
#endif
#if BENCH_SHIFT > 0
__attribute__((section(".bench_shift"), used, aligned(1)))
static const uint8_t bench_shift[BENCH_SHIFT] = {0};
#endif

/* Calibration: a call that does nothing (movs r0, #0; bx lr). */
BENCH_ALIGN static uint32_t empty_op(uintptr_t a, uintptr_t b) { (void)a; (void)b; return 0; }

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
    if (s->count == 0) { s->min = s->max = s->sum = s->first = c; s->count = 1; return; }
    if (c < s->min) s->min = c;
    if (c > s->max) s->max = c;
    s->sum += c;
    s->count++;
}

static volatile uint32_t *errors;

BENCH_HARNESS static uint32_t timed(volatile struct stat *s, rb_op op, uintptr_t a, uintptr_t b)
{
    uint32_t ret;
    uint32_t c = time_call(op, a, b, &ret);
    if (c == 0) results.dwt_stalls++;
    stat_add(s, c);
    return ret;
}

BENCH_HARNESS static void scen_single(const rb_adapter *ad, volatile struct series *s)
{
    for (uint32_t i = 0; i < RUNS; i++) {
        uint8_t in = (uint8_t)i, out = 0;
        uint32_t ok1 = timed(&s->push, ad->push, in, 0);
        uint32_t ok2 = timed(&s->pop, ad->pop, (uintptr_t)&out, 0);
        if (!ok1 || !ok2 || out != in) (*errors)++;
    }
}

BENCH_HARNESS static void scen_burst16(const rb_adapter *ad, volatile struct series *s)
{
    for (uint32_t r = 0; r < RUNS / 16; r++) {
        for (uint32_t k = 0; k < 16; k++)
            if (!timed(&s->push, ad->push, (uint8_t)(r + k), 0)) (*errors)++;
        for (uint32_t k = 0; k < 16; k++) {
            uint8_t out = 0;
            if (!timed(&s->pop, ad->pop, (uintptr_t)&out, 0) || out != (uint8_t)(r + k)) (*errors)++;
        }
    }
}

static uint8_t src[64], dst[64];

BENCH_HARNESS static void scen_block(const rb_adapter *ad, volatile struct series *s, uint32_t n)
{
    if (!ad->push_n) return;           /* no block API: count stays 0 (n/a) */
    uint8_t one = 0;
    ad->push(0x5A, 0);                 /* start one slot in (untimed) */
    ad->pop((uintptr_t)&one, 0);
    for (uint32_t i = 0; i < RUNS; i++) {
        for (uint32_t k = 0; k < n; k++) { src[k] = (uint8_t)(i * 7 + k); dst[k] = 0; }
        uint32_t pushed = timed(&s->push, ad->push_n, (uintptr_t)src, n);
        uint32_t popped = timed(&s->pop, ad->pop_n, (uintptr_t)dst, n);
        if (pushed != n || popped != n || memcmp(src, dst, n) != 0) (*errors)++;
    }
}

/* Sum of the timed calls of one transfer goes into the stat as one value. */
BENCH_HARNESS static uint32_t tc(rb_op op, uintptr_t a, uintptr_t b, uint32_t *sum)
{
    uint32_t ret, c = time_call(op, a, b, &ret);
    if (c == 0) results.dwt_stalls++;
    *sum += c;
    return ret;
}

BENCH_HARNESS static void scen_dma(const rb_adapter *ad, volatile struct series *s, uint32_t n)
{
    if (!ad->dma_wr_acquire) return;   /* no zero-copy API: count stays 0 (n/a) */
    uint8_t one = 0;
    ad->push(0x5A, 0);                 /* start one slot in (untimed) */
    ad->pop((uintptr_t)&one, 0);
    for (uint32_t i = 0; i < RUNS; i++) {
        uint32_t wr = 0, rd = 0, done = 0;
        while (done < n) {             /* producer: like a DMA completion */
            uint8_t *p = 0;
            uint32_t len = tc(ad->dma_wr_acquire, (uintptr_t)&p, n - done, &wr);
            if (len == 0 || !p) { (*errors)++; break; }
            for (uint32_t k = 0; k < len; k++) p[k] = (uint8_t)(i * 7 + done + k);
            if (tc(ad->dma_wr_commit, len, 0, &wr) != len) (*errors)++;
            done += len;
        }
        uint32_t got = 0;
        while (got < n) {              /* consumer: process in place */
            const uint8_t *p = 0;
            uint32_t len = tc(ad->dma_rd_acquire, (uintptr_t)&p, n - got, &rd);
            if (len == 0 || !p) { (*errors)++; break; }
            for (uint32_t k = 0; k < len; k++)
                if (p[k] != (uint8_t)(i * 7 + got + k)) (*errors)++;
            if (tc(ad->dma_rd_release, len, 0, &rd) != len) (*errors)++;
            got += len;
        }
        stat_add(&s->push, wr);
        stat_add(&s->pop, rd);
    }
}

BENCH_HARNESS static void run_all(const rb_adapter *ad, volatile struct series *s)
{
    ad->reset(); scen_single(ad, &s[0]);
    ad->reset(); scen_burst16(ad, &s[1]);
    ad->reset(); scen_block(ad, &s[2], 4);
    ad->reset(); scen_block(ad, &s[3], 16);
    ad->reset(); scen_block(ad, &s[4], 64);
    ad->reset(); scen_dma(ad, &s[5], 16);
    ad->reset(); scen_dma(ad, &s[6], 64);
}

int main(void)
{
    board_init();

    results.magic = RESULT_MAGIC;
    results.version = RESULT_VERSION;
    results.done = 0;
    results.clock_hz = board_clock_hz();
    results.runs = RUNS;
    results.nlibs = NLIBS;
    results.nscen = NSCEN;
    results.board_id = BOARD_ID;
    results.read_overhead = BOARD_READ_OVERHEAD;
    results.dwt_stalls = board_counter_running() ? 0u : 0xFFFFFFFFu;
    board_cache(1);
    results.empty_call_min = empty_call_min();

    const rb_adapter *libs[NLIBS] = {
#ifdef BENCH_ONLY
        &BENCH_ONLY };
#elif defined(BENCH_MP)
        /* each mode next to the library's SPSC configuration, timed in the
         * same firmware; tsrb and wizard97 + PRIMASK are the same code in
         * every mode (stress test of the modes: ../rb-mp-stress) */
        &adapter_baseline, &adapter_pxq, &adapter_pxq_mpsc, &adapter_pxq_spmc, &adapter_pxq_mpmc,
        &adapter_lockfree, &adapter_lockfree_mpmc, &adapter_riot_tsrb, &adapter_wizard97_primask,
        &adapter_heapless_mpmc };
#elif defined(BENCH_RUST)
        /* a firmware of their own: the SPSC set fills the SAM D20's RAM;
         * baseline and pxq as a reference against that set */
        &adapter_baseline, &adapter_pxq, &adapter_heapless, &adapter_bbqueue, &adapter_embassy_pipe };
#elif defined(BENCH_NORDIC)
        /* a firmware of its own, for the nRF5340 only; baseline and pxq as
         * a reference against the SPSC set */
        &adapter_baseline, &adapter_pxq, &adapter_nrf_ringbuf,
        /* where nrf_ringbuf's single-byte cycles go (adapters_nordic/parts_nrf_ringbuf.c) */
        &part_nrf_atomics, &part_memcpy1, &part_nrf_len0 };
#else
        &adapter_baseline, &adapter_pxq, &adapter_lwrb, &adapter_anders,
        &adapter_jnk0le, &adapter_etl_isr, &adapter_etl_atomic,
        &adapter_qp_lfrb, &adapter_ea_cbuf, &adapter_ece, &adapter_micoring,
        &adapter_kostyk, &adapter_diffstorm, &adapter_riot_tsrb, &adapter_contiki,
        &adapter_rigtorp, &adapter_wizard97_plain, &adapter_wizard97_primask,
        &adapter_polycratia, &adapter_rtspsc, &adapter_tinyusb,
        &adapter_zephyr, &adapter_zephyr_smp, &adapter_lockfree, &adapter_etl_locked,
        &adapter_freertos_sb, &adapter_nuttx_circbuf, &adapter_arduino_plain, &adapter_arduino_safe,
        &adapter_rtthread_plain, &adapter_rtthread_locked, &adapter_mbed_cb, &adapter_moodycamel,
        /* single-context variants */
        &adapter_pxq_none, &adapter_micoring_sc, &adapter_ea_cbuf_plain, &adapter_etl_queue };
#endif
    for (uint32_t l = 0; l < NLIBS; l++) {
        memset((void *)&results.lib[l], 0, sizeof results.lib[l]);
        errors = &results.lib[l].errors;
        if (!libs[l]->reset) continue;   /* not available on this core: all counts stay 0 */

        board_cache(0);
        run_all(libs[l], results.lib[l].s[0]);

        board_cache(1);   /* invalidated, then on */
        run_all(libs[l], results.lib[l].s[1]);
    }

    results.done = 1;
    board_idle();
}
