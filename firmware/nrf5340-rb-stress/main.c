/*
 * nrf5340-rb-stress: ISR <-> main loop stress test of SPSC ring buffers on
 * one Cortex-M33 core (the nRF5340 application core), i.e. exactly the use
 * case of an interrupt-driven UART, ADC or similar.
 *
 * For each library and both directions
 *   D0 isr_to_main: TIMER0 ISR pushes a byte sequence, main pops and checks
 *   D1 main_to_isr: main pushes a byte sequence, TIMER0 ISR pops and checks
 * the producer pushes 0,1,2,... (mod 256) and only advances on success; the
 * consumer checks that every popped byte is the next expected one. Any
 * mismatch is an error (lost, duplicated, reordered or torn data).
 *
 * The interrupt period is random (xorshift32, fixed seed) between
 * PERIOD_MIN and PERIOD_MIN + 127 timer ticks (16 MHz; 4 CPU cycles each),
 * so the interrupt lands at different instructions of the main-loop side.
 * The main loop alternates fast and slow phases (random busy waits), so the
 * buffer regularly runs full (D0) or empty (D1) and the full/empty paths are
 * exercised under preemption too.
 *
 * Libraries: the shared-buffer configurations of the benchmark, "broken" (negative
 * control with a producer-side ordering bug; it must fail), and four mutants
 * (mutants.c: other bug classes; they measure what each mode catches and do
 * not decide whether a run counts).
 * Results at 0x20000000, decoded on the host by decode.py.
 *
 * The board (clock, cache, the timer interrupt) comes from
 * common/<BOARD>/board.h; the directory name is historical. One timer tick
 * is 4 << prescaler core cycles on every board.
 *
 * smp (boards with a second core, BOARD_HAS_CORE1: the RP2350): the
 * interrupt side is replaced by a loop on core 1 that runs at the same time
 * as main on core 0, with random pauses of 0-63 loop turns between calls;
 * "irqs" then counts core-1 loop turns. No timer interrupt is used. This is
 * the multi-core case, which only some libraries document.
 *
 * sweep (all boards): instead of a free-running random timer, one
 * SysTick interrupt per call, armed d core cycles before main's push or pop,
 * for d = 1, 2, 3, ... until the interrupt has come after the call returned
 * SWEEP_TAIL times in a row. The interrupt does one call of the other side.
 * This is repeated with the buffer empty, holding one byte, half full, one
 * short of full and full, and from reps start positions (stream
 * position modulo 256), so the interrupt lands at every instruction of the
 * call in every fill state, deterministically. The handler records the
 * interrupted PC (from the exception frame) in a coverage bitmap, one bit per
 * halfword of code, which the host maps to the instructions of each function.
 * The data check is the same as in the random stress. "irqs" counts trials.
 * With smp as well (RP2350), core 1 instead of SysTick: core 0 starts a
 * trial with a flag, core 1 waits d cycles of its own counter after it sees
 * the flag and makes the other side's call, while core 0 makes its own call.
 * The start-flag latency between the cores varies by a few cycles, so the
 * steps are approximate; the start positions spread them. No coverage
 * bitmap in this mode (core 1 is not interrupting core 0).
 * sweep=2 (two interrupts per call; not with smp): the first interrupt at
 * delay d1 as above; if it came while the call was still running, its
 * handler arms SysTick again with g, so that a second interrupt (a second
 * call of the other side) comes about g cycles after the first handler
 * returned, for g = 1, 2, 3, ... until the second interrupt has come after
 * the call SWEEP_TAIL times in a row; then the next d1. Every pair of
 * interrupt points inside the call is so tried (the second no earlier than
 * one handler's length after the first): the other side makes two calls in
 * the middle of one of main's, e.g. a consumer that empties the buffer and
 * a producer that refills it between main's read and its write. "irqs"
 * counts trials, "overlapped" the trials with both interrupts inside the
 * call; both interrupted PCs go into the coverage bitmap.
 * After each delay sweep the buffer is drained one byte at a time (checked)
 * and the number of bytes must be exactly produced - consumed; a mismatch
 * (bytes lost or duplicated in any number, also a multiple of 256, which the
 * stream check modulo 256 cannot see) is counted in count_mismatch, with the
 * bytes lost and the bytes too many summed and the first mismatch kept; the
 * host adds it to the errors (errors and first_error_* in the firmware are
 * byte errors only).
 *
 * Modes: single bytes (default), blocks (push_n/pop_n) or zero-copy (the
 * zero-copy API: acquire a contiguous area, fill or check it in place, commit
 * or release; only libraries that have such an API, the others are skipped
 * and reported as n/a), each as random stress or interrupt sweep, and on a
 * board with a second core also with the other side on core 1.
 *
 * Run parameters (since 2026-11-15): one image holds every mode. The mode
 * and the run parameters (seeds, timer prescaler, cache, bytes per library,
 * sweep start positions) are chosen at run time: after a selected reset the
 * host sends them over the serial port ("go", see uart_go); without one the
 * build's defaults apply. The -D flags BLOCK_MODE, DMA_MODE, SMP_MODE,
 * SWEEP_MODE, MAIN_SEED, ISR_SEED, TIMER_PRESCALER, CACHE_ON, TRANSFERS and
 * SWEEP_REPS set only those defaults. Code location, compiler and
 * optimisation stay build-time choices.
 */
#include <stdint.h>
#include "board.h"
#include "bench.h"
/* UART to the debug probe's serial port (common/<board>/board_uart.h), used
 * only before and after the test, polled, never with an interrupt: the host
 * (run.sh PER_LIB=1) chooses the library and learns when it is done without
 * touching the debug port while a library runs. */
#if defined(__has_include)
#if __has_include("board_uart.h")
#include "board_uart.h"
#define HAVE_UART 1
#endif
#endif
#ifndef HAVE_UART
#define HAVE_UART 0
#endif

#ifndef TRANSFERS
#define TRANSFERS 300000u
#endif
#define PERIOD_MIN 40u
/* Build-time run parameters (the overnight runner varies them per run):
 *   MAIN_SEED, ISR_SEED  xorshift32 seeds (non-zero) for main-loop pauses and
 *                        interrupt periods
 *   TIMER_PRESCALER      0: 16 MHz timer (interrupt every 160-668 cycles),
 *                        2: 4 MHz (x4 slower), 4: 1 MHz (x16 slower)
 *   CACHE_ON             1: instruction cache on (normal), 0: off
 * They are reported back in the result block. */
#ifndef MAIN_SEED
#define MAIN_SEED 0x12345678u
#endif
#ifndef ISR_SEED
#define ISR_SEED 0xCAFEBABEu
#endif
#ifndef TIMER_PRESCALER
#define TIMER_PRESCALER 0u
#endif
#ifndef CACHE_ON
#define CACHE_ON 1u
#endif
/* Starvation cap: if one library/direction needs more than IRQ_CAP_PER_BYTE
 * interrupts per byte, the interrupt load leaves the main loop almost no CPU
 * time (e.g. a slow ISR with the cache off). Stop that part instead of
 * hanging the whole run; decode.py reports it as starved (transferred <
 * transfers), never as a pass. */
#ifndef IRQ_CAP_PER_BYTE
#define IRQ_CAP_PER_BYTE 60u
#endif
#define PHASE_LEN 4096u
#ifdef WITH_NORDIC   /* NORDIC=1, nRF5340 only: Nordic's nrf_ringbuf as library 40 */
#define NLIBS 41u
#else
#define NLIBS 40u
#endif
#define NDIRS 2u
#define RESULT_MAGIC 0x564C5331u /* "VLS1" */
#ifndef BLOCK_MODE
#define BLOCK_MODE 0             /* 1: push_n/pop_n with 1..16 bytes per call */
#endif
#ifndef DMA_MODE
#define DMA_MODE 0               /* 1: zero-copy API with 1..16 bytes per transfer */
#endif
#ifndef SMP_MODE
#define SMP_MODE 0               /* 1: the "ISR" side runs on core 1 instead */
#endif
#ifdef BOARD_HAS_CORE1
#define HAVE_SMP 1
#else
#define HAVE_SMP 0
#endif
#if SMP_MODE && !HAVE_SMP
#error "SMP_MODE needs a board with a second core (BOARD_HAS_CORE1)"
#endif
#if BLOCK_MODE && DMA_MODE
#error "BLOCK_MODE and DMA_MODE are exclusive"
#endif
#ifndef SWEEP_MODE
#define SWEEP_MODE 0             /* 1: deterministic interrupt sweep (SysTick one-shot), 2: two interrupts per call */
#endif
#if SMP_MODE && DMA_MODE
#error "SMP_MODE does not go with DMA_MODE"
#endif
/* SWEEP_MODE with SMP_MODE (RP2350): the other side runs on core 1, one call
 * per trial, d core-1 cycles after it sees the trial start (see sweep()). */
#ifndef SWEEP_REPS
#define SWEEP_REPS 16u           /* start positions per fill state (stream position mod 256) */
#endif
#define SWEEP_DMAX 4096u         /* longest delay tried, cycles */
#define SWEEP_TAIL 16u           /* stop after this many trials in a row with the interrupt after the call */
#ifndef SWEEP_SMP_LEAD
#define SWEEP_SMP_LEAD 96u   /* turns of a 3-4 cycle loop on core 0 before its call (SMP sweep) */
#endif
#define SWEEP_NFILL 5u
#define COV_WORDS 1024u          /* coverage bitmap: 1 bit per halfword, 64 KB of code */

extern const rb_adapter adapter_broken, adapter_broken_smp;   /* smp: wider window (broken.c) */
extern const rb_adapter adapter_mut_count_nolock, adapter_mut_count_poplock,
                        adapter_mut_full_nowrap, adapter_mut_drain_reread;

/* The libraries in result-block order (decode.py LIBS). */
#define LIB_TABLE(X) \
    X(adapter_pxq) X(adapter_lwrb) X(adapter_anders) X(adapter_jnk0le) \
    X(adapter_etl_isr) X(adapter_etl_atomic) \
    X(adapter_qp_lfrb) X(adapter_ea_cbuf) X(adapter_ece) X(adapter_micoring) \
    X(adapter_kostyk) X(adapter_diffstorm) X(adapter_riot_tsrb) X(adapter_contiki) \
    X(adapter_rigtorp) X(adapter_wizard97_plain) X(adapter_wizard97_primask) \
    X(adapter_polycratia) X(adapter_rtspsc) X(adapter_tinyusb) \
    X(adapter_zephyr) X(adapter_zephyr_smp) X(adapter_lockfree) X(adapter_etl_locked) \
    X(adapter_freertos_sb) X(adapter_nuttx_circbuf) X(adapter_arduino_plain) X(adapter_arduino_safe) \
    X(adapter_rtthread_plain) X(adapter_rtthread_locked) X(adapter_mbed_cb) X(adapter_moodycamel) \
    /* Rust (../rust-adapters) */ \
    X(adapter_heapless) X(adapter_bbqueue) X(adapter_embassy_pipe) \
    X(adapter_broken) \
    X(adapter_mut_count_nolock) X(adapter_mut_count_poplock) X(adapter_mut_full_nowrap) \
    X(adapter_mut_drain_reread) LIB_TABLE_NORDIC(X)
#ifdef WITH_NORDIC
extern const rb_adapter adapter_nrf_ringbuf;
#define LIB_TABLE_NORDIC(X) X(adapter_nrf_ringbuf)
#else
#define LIB_TABLE_NORDIC(X)
#endif
#define LIB_ENTRY(a) &a,
/* One firmware per library (ONLY_LIB=n, Makefile ONLY=n): only library n's
 * objects are linked. Every adapter is then a weak reference, so the others
 * are null in the table and are skipped; the image holds no code of theirs,
 * and a library that is added, changed or fails to build cannot change
 * another library's image. */
#ifdef ONLY_LIB
#define LIB_WEAK(a) extern const rb_adapter a __attribute__((weak));
LIB_TABLE(LIB_WEAK)
extern const rb_adapter adapter_broken_smp __attribute__((weak));
#endif

struct dirres {
    uint32_t transferred, errors, first_error_at, first_error_got, first_error_want;
    uint32_t full_events, empty_events, irqs;
};
struct results {
    uint32_t magic, version, done, transfers, nlibs, ndirs;
    struct dirres r[NLIBS][NDIRS];
    /* run parameters, appended so the layout above is unchanged */
    uint32_t main_seed, isr_seed, timer_prescaler, cache_on, code_in_sram;
    uint32_t board_id, clock_hz;
    /* sweep part: always in the block since 2026-11-15 (one image for every
     * mode), read only with version | 0x200 */
    uint32_t reps, cov_base, cov_words, cov_outside;
    uint32_t cap[NLIBS];                 /* bytes accepted when filling an empty buffer */
    uint32_t overlapped[NLIBS][NDIRS];   /* trials where the interrupt came during the call */
    uint32_t sweeps[NLIBS][NDIRS];       /* delay sweeps run */
    uint32_t dsum[NLIBS][NDIRS];         /* sum of the last delay of each sweep */
    uint32_t count_mismatch[NLIBS][NDIRS]; /* drains after a sweep with the wrong number of bytes */
    uint32_t count_lost[NLIBS][NDIRS];     /* bytes missing in those drains, summed */
    uint32_t count_extra[NLIBS][NDIRS];    /* bytes too many in those drains, summed */
    uint32_t count_first_want[NLIBS][NDIRS]; /* first mismatch: bytes expected ... */
    uint32_t count_first_got[NLIBS][NDIRS];  /* ... and bytes drained */
    uint32_t cov[COV_WORDS];
    /* Until 2026-11-17 the selection words; since then they have their own
     * fixed place (common/select.h) and these four words stay only to keep
     * the block's layout. select_pad is still written after a selection, as
     * one of the writes that push it out of the STM32H7 RAM ECC write
     * buffer. */
    uint32_t select_magic, select_index, select_check, select_pad;
};
/* One library per reset (run.sh PER_LIB=1): the host or this firmware
 * writes SELECT_MAGIC, the library's index and its complement into the
 * selection words (common/select.h) before a reset; they survive it. main()
 * runs only that library and clears them at once, so a later plain reset
 * runs all. */
#include "../common/select.h"
VL_SELECT_DEFINE
__attribute__((section(".results")))
volatile struct results results;

/* Run parameters (see the header): the build's defaults, or what the host
 * sent with "go". The names are those of the "go" line. */
enum { P_MODE, P_SWEEP, P_SMP, P_MAIN_SEED, P_ISR_SEED, P_PRESCALER, P_CACHE, P_TRANSFERS, P_REPS, NPRM };
static uint32_t prm[NPRM] = {
    DMA_MODE ? 3u : BLOCK_MODE ? 2u : 1u,   /* mode: 1 single, 2 blocks, 3 zero-copy */
    SWEEP_MODE, SMP_MODE, MAIN_SEED, ISR_SEED, TIMER_PRESCALER, CACHE_ON, TRANSFERS, SWEEP_REPS };
static __attribute__((unused)) const char *const prm_names[NPRM] = {
    "mode", "sweep", "smp", "main_seed", "isr_seed", "prescaler", "cache", "transfers", "reps" };
static uint32_t irq_cap;                 /* IRQ_CAP_PER_BYTE * transfers */
/* Mode 1..3, sweep 0..2, smp 0/1 (smp only with a second core, not with
 * zero-copy, not with the two-interrupt sweep), seeds not 0 (xorshift), prescaler 0..4 (the rates tested), cache
 * 0/1, transfers 1..2^26 (irq_cap must not overflow), reps 1..256. */
static int prm_valid(void)
{
    return prm[P_MODE] >= 1u && prm[P_MODE] <= 3u && prm[P_SWEEP] <= 2u && prm[P_SMP] <= (uint32_t)HAVE_SMP
        && !(prm[P_SMP] && prm[P_SWEEP] == 2u)
        && !(prm[P_SMP] && prm[P_MODE] == 3u) && prm[P_MAIN_SEED] && prm[P_ISR_SEED]
        && prm[P_PRESCALER] <= 4u && prm[P_CACHE] <= 1u
        && prm[P_TRANSFERS] >= 1u && prm[P_TRANSFERS] <= (1u << 26)
        && prm[P_REPS] >= 1u && prm[P_REPS] <= 256u;
}

#if HAVE_UART
/* The serial-port protocol (common/vls_uart.h) */
#define VLS_RESULTS results
#define VLS_NSEL NLIBS
#define VLS_ECC_WRITE() do { results.select_pad = 0; results.done = 0; results.version = results.version; } while (0)
#define VLS_ECC_READ() do { (void)results.select_pad; (void)results.done; } while (0)
#include "../common/vls_uart.h"
#endif

static uint32_t rng = MAIN_SEED;          /* main() sets the run's seed */
static inline uint32_t xorshift32(void)
{
    uint32_t x = rng;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    return rng = x;
}

/* State shared between ISR and main for the current run. The ISR uses the
 * adapter's ISR variants when it has them (ETL queue_spsc_isr). */
static const rb_adapter *volatile cur;
static volatile rb_op isr_push, isr_pop;
static volatile uint32_t dir;
static volatile struct dirres *res;
static volatile uint8_t isr_seq;      /* D0: next byte the ISR pushes */
static volatile uint8_t isr_expect;   /* D1: next byte the ISR expects */
static volatile uint32_t isr_rng = ISR_SEED;   /* main() sets the run's seed */

/* Transfer helpers, shared by ISR and main. In single mode one byte per
 * call (push/pop); in BLOCK_MODE a random length per call (push_n/pop_n):
 * 1..16 bytes in main, 1..4 in the ISR. The ISR moves less per interrupt so
 * that main can outpace it and the buffer also runs full (main -> ISR) and
 * empty (ISR -> main) under preemption. In DMA_MODE the same lengths, with
 * one zero-copy acquire + commit (or release) per call: the area is filled
 * or checked in place, as DMA hardware or a parser would. Return the number
 * of bytes moved. kind is the mode (prm[P_MODE]) as a constant: every
 * caller dispatches on the mode once and calls these with a literal, so
 * each mode gets its own code, as in the one-mode builds before 2026-11-15. */
#define ALWAYS_INLINE static inline __attribute__((always_inline))
#define MAIN_BLOCK_MASK 15u
#define ISR_BLOCK_MASK 3u
static uint8_t isr_blk[16], main_blk[16];

static inline void check(volatile struct dirres *r, uint8_t v, uint8_t *expect);

static inline uint32_t produce_dma(const rb_adapter *ad, uint8_t *seq, uint32_t rnd, uint32_t mask)
{
    uint8_t *p = 0;
    uint32_t len = ad->dma_wr_acquire((uintptr_t)&p, 1u + (rnd & mask));
    if (len == 0 || !p) return 0;
    for (uint32_t k = 0; k < len; k++) p[k] = (uint8_t)(*seq + k);
    uint32_t done = ad->dma_wr_commit(len, 0);
    *seq = (uint8_t)(*seq + done);
    return done;
}

static inline uint32_t consume_dma(const rb_adapter *ad, uint8_t *expect, volatile struct dirres *r,
                                   uint32_t rnd, uint32_t mask)
{
    const uint8_t *p = 0;
    uint32_t len = ad->dma_rd_acquire((uintptr_t)&p, 1u + (rnd & mask));
    if (len == 0 || !p) return 0;
    for (uint32_t k = 0; k < len; k++) check(r, p[k], expect);
    return ad->dma_rd_release(len, 0);
}

ALWAYS_INLINE uint32_t produce(rb_op push, rb_op push_n, uint8_t *blk, uint8_t *seq, uint32_t rnd,
                               uint32_t mask, uint32_t kind)
{
    if (kind == 3u)
        return produce_dma(cur, seq, rnd, mask);
    if (kind == 2u) {
        uint32_t n = 1u + (rnd & mask);
        for (uint32_t k = 0; k < n; k++) blk[k] = (uint8_t)(*seq + k);
        uint32_t done = push_n((uintptr_t)blk, n);
        *seq = (uint8_t)(*seq + done);
        return done;
    }
    if (!push(*seq, 0)) return 0;
    (*seq)++;
    return 1;
}

static inline void check(volatile struct dirres *r, uint8_t v, uint8_t *expect)
{
    if (v != *expect) {
        if (r->errors++ == 0) {
            r->first_error_at = r->transferred;
            r->first_error_got = v;
            r->first_error_want = *expect;
        }
        *expect = v;                     /* resync, keep counting new errors */
    }
    (*expect)++;
    r->transferred++;
}

ALWAYS_INLINE uint32_t consume(rb_op pop, rb_op pop_n, uint8_t *blk, uint8_t *expect,
                               volatile struct dirres *r, uint32_t rnd, uint32_t mask, uint32_t kind)
{
    if (kind == 3u)
        return consume_dma(cur, expect, r, rnd, mask);
    if (kind == 2u) {
        uint32_t n = 1u + (rnd & mask);
        uint32_t got = pop_n((uintptr_t)blk, n);
        for (uint32_t k = 0; k < got; k++) check(r, blk[k], expect);
        return got;
    }
    uint8_t v;
    if (!pop((uintptr_t)&v, 0)) return 0;
    check(r, v, expect);
    return 1;
}
/* produce/consume for the current mode (one dispatch per call): the sweep's
 * calls and its single steps, where a few cycles more do not matter (the
 * sweep tries every delay until the interrupt comes after the call). */
static uint32_t produce_cur(rb_op push, uint8_t *blk, uint8_t *seq, uint32_t rnd, uint32_t mask)
{
    switch (prm[P_MODE]) {
    case 3u: return produce(push, cur->push_n, blk, seq, rnd, mask, 3u);
    case 2u: return produce(push, cur->push_n, blk, seq, rnd, mask, 2u);
    default: return produce(push, cur->push_n, blk, seq, rnd, mask, 1u);
    }
}
static uint32_t consume_cur(rb_op pop, uint8_t *blk, uint8_t *expect, volatile struct dirres *r,
                            uint32_t rnd, uint32_t mask)
{
    switch (prm[P_MODE]) {
    case 3u: return consume(pop, cur->pop_n, blk, expect, r, rnd, mask, 3u);
    case 2u: return consume(pop, cur->pop_n, blk, expect, r, rnd, mask, 2u);
    default: return consume(pop, cur->pop_n, blk, expect, r, rnd, mask, 1u);
    }
}

/* The other side's transfer: one per interrupt, or per core-1 loop turn. */
ALWAYS_INLINE void other_side(uint32_t x, uint32_t kind)
{
    if (dir == 0) {                      /* ISR is the producer */
        uint8_t s = isr_seq;
        if (produce(isr_push, cur->push_n, isr_blk, &s, x >> 8, ISR_BLOCK_MASK, kind)) isr_seq = s;
        else res->full_events++;
    } else {                             /* ISR is the consumer */
        uint8_t e = isr_expect;
        if (!consume(isr_pop, cur->pop_n, isr_blk, &e, res, x >> 8, ISR_BLOCK_MASK, kind)) res->empty_events++;
        isr_expect = e;
    }
}

void BOARD_TIMER_IRQ_HANDLER(void)
{
    uint32_t x = isr_rng;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    isr_rng = x;
    board_timer_isr_ack(PERIOD_MIN + (x & 127u));
    /* Starvation cap, also here: if the interrupt load leaves the main loop
     * no time at all, main never reaches its own check (seen on the SAM D20
     * at 48 MHz, block mode, prescaler 0). Stop the timer; main then sees
     * irqs over the cap and ends this part as starved. */
    if (++res->irqs > irq_cap) {
        board_timer_stop();
        return;
    }
    switch (prm[P_MODE]) {
    case 3u: other_side(x, 3u); break;
    case 2u: other_side(x, 2u); break;
    default: other_side(x, 1u); break;
    }
    board_timer_isr_end();
}
#if HAVE_SMP
/* Core 1: the other side of the buffer, concurrently with main on core 0.
 * smp_run / smp_stop / smp_ack carry the part number; dmb orders them
 * against the shared state (cur, dir, res, isr_seq, ...). */
static volatile uint32_t smp_run, smp_stop, smp_ack;
static uint32_t core1_stack[1024];
static void core1_main(void)             /* random stress; the sweep has core1_sweep */
{
    uint32_t seen = 0;
    for (;;) {
        while (smp_run == seen) {}
        seen = smp_run;
        __asm volatile("dmb" ::: "memory");
        while (smp_stop != seen) {
            uint32_t x = isr_rng;
            x ^= x << 13; x ^= x >> 17; x ^= x << 5;
            isr_rng = x;
            res->irqs++;
            if (prm[P_MODE] == 2u) other_side(x, 2u); else other_side(x, 1u);   /* no zero-copy with smp */
            for (volatile uint32_t i = 0; i < (x & 63u); i++) {}
        }
        __asm volatile("dmb" ::: "memory");
        smp_ack = seen;
    }
}
#endif
/* The other side's start and stop: the timer interrupt, or core 1 (smp). */
static void timer_start(void)
{
#if HAVE_SMP
    if (prm[P_SMP]) {
        __asm volatile("dmb" ::: "memory");
        smp_run = smp_run + 1u;
        return;
    }
#endif
    board_timer_start(prm[P_PRESCALER], PERIOD_MIN + 64);
}
static void timer_stop(void)
{
#if HAVE_SMP
    if (prm[P_SMP]) {
        smp_stop = smp_run;
        while (smp_ack != smp_run) {}
        __asm volatile("dmb" ::: "memory");
        return;
    }
#endif
    board_timer_stop();
}

/* ---- Interrupt sweep (sweep=1) ----------------------------------------
 * SysTick (core registers, the same on every Cortex-M) as a one-shot: armed
 * with reload d, it counts the core clock down and interrupts about d cycles
 * later; the handler stops it at once. */
#define SW_SYST_CSR (*(volatile uint32_t *)0xE000E010u)
#define SW_SYST_RVR (*(volatile uint32_t *)0xE000E014u)
#define SW_SYST_CVR (*(volatile uint32_t *)0xE000E018u)
#define SW_ICSR     (*(volatile uint32_t *)0xE000ED04u)
#define SW_PENDSTCLR (1u << 25)
/* Stop SysTick and clear its pending bit: with a short reload the counter
 * can run out again between the exception entry and the stop, which left
 * a second, unplanned interrupt pending (an extra call of the other side;
 * found 2026-11-15 with the two-interrupt sweep, where trials saw three
 * interrupts). */
static inline void sw_systick_stop(void)
{
    SW_SYST_CSR = 0;
    __asm volatile("dsb" ::: "memory");
    SW_ICSR = SW_PENDSTCLR;
    __asm volatile("dsb\n isb" ::: "memory");
}
static volatile uint32_t sw_done, sw_fired, sw_overlap;
static volatile uint32_t sw_gap, sw_first;           /* sweep=2: second delay; first interrupt taken */
static volatile uint8_t sw_pseq, sw_cexp;           /* producer's next byte, consumer's expected byte */
static volatile uint32_t sw_produced, sw_consumed;   /* bytes in and out since reset */
static uintptr_t cov_base;
static uint32_t sw_target;                           /* fill state of the trials */

static uint32_t sw_produce(rb_op push, uint8_t *blk, uint32_t rnd, uint32_t mask)
{
    uint8_t s = sw_pseq;
    uint32_t n = produce_cur(push, blk, &s, rnd, mask);
    sw_pseq = s;
    sw_produced += n;
    return n;
}
static uint32_t sw_consume(rb_op pop, uint8_t *blk, uint32_t rnd, uint32_t mask)
{
    uint8_t e = sw_cexp;
    uint32_t n = consume_cur(pop, blk, &e, res, rnd, mask);
    sw_cexp = e;
    sw_consumed += n;
    return n;
}

/* Called from the naked SysTick handler with the exception frame (MSP;
 * everything here runs on MSP): frame[6] is the interrupted PC. */
/* The other side's one call of a trial (interrupt or core 1). */
static void sw_other_side(void)
{
    uint32_t x = isr_rng;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    isr_rng = x;
    if (dir == 0) { if (!sw_produce(isr_push, isr_blk, x >> 8, ISR_BLOCK_MASK)) res->full_events++; }
    else          { if (!sw_consume(isr_pop, isr_blk, x >> 8, ISR_BLOCK_MASK)) res->empty_events++; }
}
__attribute__((used)) void sweep_isr(const uint32_t *frame)
{
    sw_systick_stop();
    /* Defensive: an interrupt after the trial's last one does nothing (the
     * trial is over; main arms the next one only after stopping the timer
     * and clearing the pending bit itself). */
    if (sw_fired) return;
    uint32_t inside = !sw_done;
    uintptr_t off = ((frame[6] & ~1u) - cov_base) >> 1;
    if (off < COV_WORDS * 32u) results.cov[off >> 5] |= 1u << (off & 31u);
    else results.cov_outside++;
    sw_other_side();
    if (sw_gap && !sw_first) {
        /* sweep=2, first interrupt: a second one g cycles after this handler
         * (armed last, so the count starts as late as possible); none if
         * the call has already returned (sw_overlap 0 ends the trial) */
        sw_first = 1;
        sw_overlap = inside;
        if (inside) {
            SW_SYST_RVR = sw_gap;
            SW_SYST_CVR = 0;
            SW_SYST_CSR = 7u;
            return;
        }
    } else {
        sw_overlap = sw_gap ? sw_overlap + (inside << 1) : inside;   /* sweep=2: bit 1 = second inside */
    }
    sw_fired = 1;
}
#if HAVE_SMP
/* Core 1 in sweep mode: for each trial (sw_go changes), wait sw_delay steps
 * of about one cycle, note whether core 0's call is still running,
 * make the other side's call, report back. dmb orders the flags against
 * the buffer state (the two cores do not share a cache; the barrier keeps
 * the order of the accesses). */
static volatile uint32_t sw_go, sw_delay;
static void core1_sweep(void)
{
    uint32_t seen = 0;
    for (;;) {
        while (sw_go == seen) {}
        seen = sw_go;
        __asm volatile("dmb" ::: "memory");
        /* Delay in steps of about one cycle: d / 4 turns of a two-instruction
         * loop (3 to 4 cycles a turn) and then d % 4 NOPs, entered by a
         * computed jump. (A loop that polls the cycle counter moves the
         * call in steps of its own period, 5 or more cycles, and always in
         * the same phase: on 2026-11-13 that version missed every
         * single-byte race of the unsafe variants and the mutants.) */
        uint32_t turns = sw_delay >> 2, skip = (3u - (sw_delay & 3u)) << 1;
        __asm volatile("cbz   %0, 2f\n"
                       "1: subs %0, #1\n"
                       "bne   1b\n"
                       "2: add pc, %1\n"      /* pc reads as this + 4: skip 0..3 of the NOPs */
                       ".short 0xbf00\n"      /* never executed */
                       ".short 0xbf00\n"
                       ".short 0xbf00\n"
                       ".short 0xbf00\n"
                       : "+l"(turns) : "r"(skip) : "cc");
        sw_overlap = !sw_done;
        __asm volatile("dmb" ::: "memory");
        sw_other_side();
        __asm volatile("dmb" ::: "memory");
        sw_fired = 1;
    }
}
#endif
__attribute__((naked)) void SysTick_Handler(void)
{
    __asm volatile("mrs r0, msp\n"
                   "ldr r1, =sweep_isr\n"
                   "bx  r1\n"
                   ".ltorg\n");
}

/* Main-side single steps (no interrupt armed) to set the fill level. */
static uint32_t sw_fill(void) { return sw_produced - sw_consumed; }
static void sw_set_fill(uint32_t target)
{
    for (uint32_t guard = 0; guard < 1024u; guard++) {
        uint32_t f = sw_fill();
        if (f < target) { if (!sw_produce(cur->push, main_blk, 0, 0)) return; }
        else if (f > target) { if (!sw_consume(cur->pop, main_blk, 0, 0)) return; }
        else return;
    }
}

/* Drain the buffer one byte at a time (each byte checked) and compare the
 * count with produced - consumed. Then resynchronise the counters to the
 * empty buffer, so one fault is counted once. */
static void sw_audit(uint32_t l, uint32_t d0, volatile struct dirres *r)
{
    uint32_t want = sw_fill(), got = 0;
    sw_consumed = sw_produced;           /* the drain below must not change sw_fill() bookkeeping */
    uint8_t e = sw_cexp;
    while (got < 1024u && consume_cur(cur->pop, main_blk, &e, r, 0, 0)) got++;
    sw_cexp = sw_pseq;
    if (got != want) {                   /* decode.py adds the mismatches to errors */
        if (results.count_mismatch[l][d0]++ == 0) {
            results.count_first_want[l][d0] = want;
            results.count_first_got[l][d0] = got;
        }
        if (got < want) results.count_lost[l][d0] += want - got;
        else            results.count_extra[l][d0] += got - want;
    }
}

/* One trial: the buffer at the fill state, an interrupt armed dl cycles
 * before main's call (sweep=2 with g: and a second one g cycles after the
 * first handler), or core 1's call (smp). Returns the overlap: bit 0 the
 * (first) interrupt came during the call, bit 1 the second did too. */
static uint32_t sw_trial(const rb_adapter *ad, uint32_t l, uint32_t d0, volatile struct dirres *r,
                         uint32_t dl, uint32_t g)
{
    sw_set_fill(sw_target);
    uint32_t rnd = xorshift32();
    sw_done = 0;
    sw_fired = 0;
    sw_gap = g;
    sw_first = 0;
    sw_overlap = 0;
#if HAVE_SMP
    if (prm[P_SMP]) {
    sw_delay = dl - 1u;
    __asm volatile("dmb" ::: "memory");
    sw_go = sw_go + 1u;
    /* Lead: core 0 waits a fixed time before its call, so that
     * the sweep starts with core 1's call ahead of core 0's and
     * moves it through and past it. Without the lead core 1,
     * which has to notice sw_go first, is always the later one
     * and never meets the first instructions of core 0's call
     * (2026-11-13: no single-byte race was found that way). */
    { uint32_t lead = SWEEP_SMP_LEAD;
      __asm volatile("1: subs %0, #1\n" "bne 1b\n" : "+l"(lead) :: "cc"); }
    } else
#endif
    {
    sw_systick_stop();
    SW_SYST_RVR = dl;
    SW_SYST_CVR = 0;
    SW_SYST_CSR = 7u;            /* core clock, interrupt, enable */
    }
    uint32_t moved = (d0 == 0) ? sw_consume(ad->pop, main_blk, rnd, MAIN_BLOCK_MASK)
                               : sw_produce(ad->push, main_blk, rnd, MAIN_BLOCK_MASK);
    __asm volatile("dmb" ::: "memory");
    sw_done = 1;
    while (!sw_fired) {}
    __asm volatile("dmb" ::: "memory");
    if (!moved) { if (d0 == 0) r->empty_events++; else r->full_events++; }
    r->irqs++;
    uint32_t o = sw_overlap;
    if (g ? o == 3u : o) results.overlapped[l][d0]++;
    return o;
}

static void sweep(const rb_adapter *ad, uint32_t l, uint32_t d0, volatile struct dirres *r)
{
    if (prm[P_MODE] == 3u && !ad->dma_wr_acquire) return;   /* no zero-copy API: n/a */
    cur = ad;
    isr_push = ad->isr_push ? ad->isr_push : ad->push;
    isr_pop = ad->isr_pop ? ad->isr_pop : ad->pop;
    dir = d0;
    res = r;
    ad->reset();
    sw_pseq = sw_cexp = 0;
    sw_produced = sw_consumed = 0;
    /* capacity: fill an empty buffer one byte at a time, then drain it
     * (checked). At most 255: the stream check is modulo 256, so a buffer
     * that accepts more than it holds (the control's zero-copy write)
     * would lose a multiple of 256 bytes unseen at a larger limit. */
    uint32_t cap = 0;
    while (cap < 255u && sw_produce(ad->push, main_blk, 0, 0)) cap++;
    sw_set_fill(0);
    results.cap[l] = cap;
    if (cap == 0) return;
    const uint32_t fills[SWEEP_NFILL] = { 0, 1, cap / 2u, cap - 1u, cap };
    for (uint32_t f = 0; f < SWEEP_NFILL; f++)
        for (uint32_t rep = 0; rep < prm[P_REPS]; rep++) {
            /* start position: bytes produced = rep (mod 256), at fill f */
            sw_set_fill(fills[f] < cap ? fills[f] : cap - 1u);   /* room for one more */
            sw_target = fills[f];
            for (uint32_t g = 0; g < 512u && ((sw_produced - rep) & 255u) != 0; g++) {
                sw_produce(ad->push, main_blk, 0, 0);
                sw_consume(ad->pop, main_blk, 0, 0);
            }
            uint32_t tail = 0, dl;
            for (dl = 1; dl <= SWEEP_DMAX && tail < SWEEP_TAIL; dl++) {
                if (prm[P_SWEEP] != 2u) {
                    if (sw_trial(ad, l, d0, r, dl, 0)) tail = 0; else tail++;
                    continue;
                }
                /* two interrupts: every second delay while the first lands
                 * inside the call */
                uint32_t t2 = 0, first_inside = 0;
                for (uint32_t g = 1; g <= SWEEP_DMAX && t2 < SWEEP_TAIL; g++) {
                    uint32_t o = sw_trial(ad, l, d0, r, dl, g);
                    if (!(o & 1u)) break;        /* the first came after the call */
                    first_inside = 1;
                    if (o & 2u) t2 = 0; else t2++;
                }
                if (first_inside) tail = 0; else tail++;
            }
            results.sweeps[l][d0]++;
            results.dsum[l][d0] += dl - 1u;
            sw_audit(l, d0, r);
        }
    sw_set_fill(0);
}

static void slow_wait(uint32_t phase)
{
    if (phase & 1u) {                    /* slow phase: random pause */
        uint32_t n = xorshift32() & 1023u;
        for (volatile uint32_t i = 0; i < n; i++) {}
    }
}

/* The main loop of the random stress, for one mode (kind, a constant). */
ALWAYS_INLINE void run_loop(const rb_adapter *ad, uint32_t d, volatile struct dirres *r, uint32_t kind)
{
    const uint32_t transfers = prm[P_TRANSFERS], cap = irq_cap;
    uint8_t state = 0;                   /* main's expect (d == 0) or seq (d == 1) */
    uint32_t phase = 0, in_phase = 0;
    while (r->transferred < transfers && r->irqs < cap) {
        uint32_t moved = (d == 0)
            ? consume(ad->pop, ad->pop_n, main_blk, &state, r, xorshift32(), MAIN_BLOCK_MASK, kind)
            : produce(ad->push, ad->push_n, main_blk, &state, xorshift32(), MAIN_BLOCK_MASK, kind);
        if (!moved) {
            if (d == 0) r->empty_events++; else r->full_events++;
            continue;
        }
        in_phase += moved;
        if (in_phase >= PHASE_LEN) { in_phase = 0; phase++; }
        slow_wait(phase);
    }
}
static void run(const rb_adapter *ad, uint32_t d, volatile struct dirres *r)
{
    if (prm[P_MODE] == 3u && !ad->dma_wr_acquire) return;   /* no zero-copy API: n/a (transferred stays 0) */
    cur = ad;
    isr_push = ad->isr_push ? ad->isr_push : ad->push;
    isr_pop = ad->isr_pop ? ad->isr_pop : ad->pop;
    dir = d;
    res = r;
    isr_seq = 0;
    isr_expect = 0;
    ad->reset();
    timer_start();
    switch (prm[P_MODE]) {
    case 3u: run_loop(ad, d, r, 3u); break;
    case 2u: run_loop(ad, d, r, 2u); break;
    default: run_loop(ad, d, r, 1u); break;
    }
    timer_stop();
}
int main(void)
{
    board_init();

    /* One library per reset? (see struct results) */
    uint32_t only = NLIBS;
    if (SEL[0] == SELECT_MAGIC && SEL[1] < NLIBS && SEL[2] == ~SEL[1])
        only = SEL[1];
    results.done = 0;                    /* before the host sees the selection consumed */
    SEL[0] = SEL[2] = 0;
#if HAVE_UART
    uart_init();
    if (only == NLIBS) {
        /* No selection: announce, and give the host about a second to choose
         * a library; without a command all libraries run, as before. */
        uart_puts("VLS ready ");
        uart_putu(NLIBS);
        uart_putc('\n');
        uart_commands(board_clock_hz() / 16u);
    } else {
        uart_puts("VLS start ");
        uart_putu(only);
        uart_putc('\n');
#ifdef ONLY_LIB
        if (only != ONLY_LIB) {          /* not this image's library */
            uart_puts("VLS error not in image\n");
            uart_commands(0);
        }
#endif
        /* the run parameters ("go"; about a second, else the defaults) */
        if (!uart_go(board_clock_hz() / 16u)) uart_commands(0);   /* bad: not run */
        uart_flush();                    /* then silent until the library is done */
    }
#endif
    board_cache(prm[P_CACHE]);           /* normal operation: cache on */
    rng = prm[P_MAIN_SEED];
    isr_rng = prm[P_ISR_SEED];
    irq_cap = IRQ_CAP_PER_BYTE * prm[P_TRANSFERS];

    results.magic = RESULT_MAGIC;
    results.version = prm[P_MODE]                                /* 1 single, 2 blocks, 3 zero-copy */
                    | (prm[P_SMP] ? 0x100u : 0u)                  /* + 0x100: other side on core 1 */
                    | (prm[P_SWEEP] ? 0x200u : 0u)                /* + 0x200: interrupt sweep */
                    | (prm[P_SWEEP] == 2u ? 0x400u : 0u);         /* + 0x400: two interrupts per call */
#if HAVE_SMP
    if (prm[P_SMP])
        board_core1_launch(prm[P_SWEEP] ? core1_sweep : core1_main,
                           core1_stack + sizeof core1_stack / sizeof core1_stack[0]);
#endif
    results.board_id = BOARD_ID;
    results.clock_hz = board_clock_hz();
    results.done = 0;
    results.transfers = prm[P_SWEEP] ? 0u : prm[P_TRANSFERS];   /* sweep: no fixed byte count */
    results.nlibs = NLIBS;
    results.ndirs = NDIRS;
    results.main_seed = prm[P_MAIN_SEED];
    results.isr_seed = prm[P_ISR_SEED];
    results.timer_prescaler = prm[P_PRESCALER];
    results.cache_on = prm[P_CACHE];
    extern uint32_t _sramtext, _eramtext;
    results.code_in_sram = (&_eramtext != &_sramtext);
    /* the sweep part, also cleared in the other modes (it is in the block) */
    extern const void *const vectors[];
    cov_base = results.code_in_sram ? (uintptr_t)&_sramtext : (uintptr_t)vectors;
    results.reps = prm[P_REPS];
    results.cov_base = cov_base;
    results.cov_words = COV_WORDS;
    results.cov_outside = 0;
    for (uint32_t i = 0; i < COV_WORDS; i++) results.cov[i] = 0;
    for (uint32_t l = 0; l < NLIBS; l++) {
        results.cap[l] = 0;
        for (uint32_t d = 0; d < NDIRS; d++)
            results.overlapped[l][d] = results.sweeps[l][d] = results.dsum[l][d] = results.count_mismatch[l][d] =
            results.count_lost[l][d] = results.count_extra[l][d] =
            results.count_first_want[l][d] = results.count_first_got[l][d] = 0;
    }

    const rb_adapter *libs[NLIBS] = { LIB_TABLE(LIB_ENTRY) };
    for (uint32_t l = 0; l < NLIBS; l++)
        for (uint32_t d = 0; d < NDIRS; d++) {
            if (only != NLIBS && l != only) continue;
            volatile struct dirres *r = &results.r[l][d];
            r->transferred = r->errors = r->first_error_at = 0;
            r->first_error_got = r->first_error_want = 0;
            r->full_events = r->empty_events = r->irqs = 0;
            const rb_adapter *ad = libs[l];
            if (!ad) continue;           /* ONLY_LIB: not in this image */
            if (ad == &adapter_broken && prm[P_SMP]) ad = &adapter_broken_smp;
            if (prm[P_SWEEP]) sweep(ad, l, d, r);
            else run(ad, d, r);
        }

    results.done = 1;
#if HAVE_UART
    uart_puts("VLS done ");
    if (only == NLIBS) uart_puts("all"); else uart_putu(only);
    uart_putc('\n');
    uart_commands(0);
#endif
    board_idle();
}
