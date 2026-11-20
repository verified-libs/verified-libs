/*
 * rb-dma-stress: a DMA controller as the producer of a ring buffer (plan 2b,
 * lab/plans/2026-11-16-mp-bundle-and-open-areas.md). The core does not
 * write the data: a DMA channel copies it, one byte per timer request, into
 * the area the library handed out (zero-copy API), while the main loop
 * consumes. Only libraries with the zero-copy API take part.
 *
 * Producer (interrupt context, one priority for both interrupts, so they do
 * not preempt each other):
 *   - DMA transfer complete: dma_wr_commit(len) of the transfer that just
 *     finished, then the next one: dma_wr_acquire(&p, 1..16), and the DMA
 *     copies len bytes of the sequence from a source table pat[] (pat[i] =
 *     i & 0xff) into p, one byte per period of a timer (random period);
 *   - the stress timer (TIM2 on the STM32s): if no transfer is in flight
 *     (the buffer was full), try again.
 * Consumer (main loop): dma_rd_acquire(&p, 1..16), check every byte of the
 * sequence, dma_rd_release; fast and slow phases, as the ISR stress test.
 * A transfer is in flight for many main-loop turns: a library that showed
 * the area before its commit, or handed out an area the consumer still
 * reads, gives sequence errors.
 *
 * Negative control: the same library (lwrb) with the commit moved to before
 * the transfer: the consumer can then read bytes the DMA has not written.
 * It must be caught in every valid run.
 *
 * One library per reset over the serial port (common/vls_uart.h, host
 * common/uart_host.py), selection indices from 96 (VLS_SEL_BASE), images in
 * the bundle shared with the other stress tests (common/bundle.py --with).
 * Results at 0x20000000 (struct results), decoded by decode.py.
 */
#include <stdint.h>
#include "board.h"
#include "bench.h"
#if defined(__has_include)
#if __has_include("board_uart.h")
#include "board_uart.h"
#define HAVE_UART 1
#endif
#if __has_include("board_dma.h")
#include "board_dma.h"
#endif
#endif
#ifndef HAVE_UART
#error "rb-dma-stress needs the board's serial port (board_uart.h)"
#endif
#ifndef BOARD_HAS_DMA
#error "rb-dma-stress needs a DMA layer for this board (board_dma.h)"
#endif

/* DMA_CACHE (build flag; boards with a data cache, the H723):
 *   0  the DMA area is not cached (board_dma_mem_init: MPU), the usual way
 *   1  cached, no maintenance: shows that something is needed (not a test
 *      of the libraries; expected to fail on the H723)
 *   2  cached, with the maintenance an application does through the
 *      zero-copy API: clean + invalidate the acquired area before the
 *      transfer, invalidate it after, before the commit (whole 32-byte
 *      lines: a library that keeps its own state in the lines of the data
 *      area loses writes or reads stale state, which this finds) */
#ifndef DMA_CACHE
#define DMA_CACHE 0
#endif
#ifndef TRANSFERS
#define TRANSFERS 300000u
#endif
#define RESULT_MAGIC 0x564C4431u   /* "VLD1" */
#define NOT_AVAILABLE 0xFFFFFFFFu  /* transferred: library has no zero-copy API */
#define NOT_IN_IMAGE  0xFFFFFFFEu  /* transferred: not selected / not in this image */
#define PHASE_LEN 2048u
#define STALL_TURNS 20000000u      /* main-loop turns without a byte: stop (starved) */

/* DMA library index (Makefile LIB_<n>, ONLY=n); selection index 96 + n. */
extern const rb_adapter adapter_pxq, adapter_lwrb, adapter_zephyr, adapter_tinyusb, adapter_ece,
    adapter_nuttx_circbuf, adapter_bbqueue;
#ifdef ONLY_LIB
extern const rb_adapter adapter_pxq __attribute__((weak)), adapter_lwrb __attribute__((weak)),
    adapter_zephyr __attribute__((weak)), adapter_tinyusb __attribute__((weak)),
    adapter_ece __attribute__((weak)), adapter_nuttx_circbuf __attribute__((weak)),
    adapter_bbqueue __attribute__((weak));
#endif
#define NLIBS 8u
#define CONTROL 7u                 /* lwrb, commit before the transfer */

struct libres {
    uint32_t transferred, errors, first_error_at, first_error_got, first_error_want;
    uint32_t full_events;          /* acquire found no space */
    uint32_t dma_transfers;        /* transfers started */
    uint32_t overlaps;             /* consumer reads while a transfer was in flight */
    uint32_t retries;              /* timer interrupts that started a transfer */
    uint32_t mismatch;             /* after the drain: |committed - consumed| */
    uint32_t dma_irqs, stalled;
};
struct results {
    uint32_t magic, version, done, transfers, nlibs, board_id, clock_hz, prescaler;
    uint32_t main_seed, dma_seed, code_in_sram, reserved;
    struct libres lib[NLIBS];
};
__attribute__((section(".results")))
volatile struct results results;
#include "../common/select.h"
VL_SELECT_DEFINE

enum { P_TRANSFERS, P_PRESCALER, P_MAIN_SEED, P_DMA_SEED, NPRM };
static uint32_t prm[NPRM] = { TRANSFERS, 0u, 0x12345678u, 0xCAFEBABEu };
static const char *const prm_names[NPRM] = { "transfers", "prescaler", "main_seed", "dma_seed" };
/* transfers 1..2^26, prescaler 0..4, seeds not 0 (xorshift) */
static int prm_valid(void)
{
    return prm[P_TRANSFERS] >= 1u && prm[P_TRANSFERS] <= (1u << 26) && prm[P_PRESCALER] <= 4u
        && prm[P_MAIN_SEED] && prm[P_DMA_SEED];
}
#define VLS_RESULTS results
#define VLS_NSEL NLIBS
#define VLS_SEL_BASE 96u
#define VLS_SEL_LIMIT 256u
#define VLS_ECC_WRITE() do { results.done = 0; results.lib[NLIBS - 1].stalled = results.lib[NLIBS - 1].stalled; } while (0)
#define VLS_ECC_READ() do { (void)results.done; (void)results.lib[NLIBS - 1].stalled; } while (0)
#include "../common/vls_uart.h"

static inline uint32_t xs(uint32_t x) { x ^= x << 13; x ^= x >> 17; x ^= x << 5; return x; }

/* The source of every transfer: the sequence, so a transfer of len bytes
 * starting at sequence number s copies pat[s .. s + len - 1]. */
static const uint8_t pat[256 + 16] = {
#define P4(n) (n), (n) + 1, (n) + 2, (n) + 3
#define P16(n) P4(n), P4((n) + 4), P4((n) + 8), P4((n) + 12)
#define P64(n) P16(n), P16((n) + 16), P16((n) + 32), P16((n) + 48)
    P64(0), P64(64), P64(128), P64(192), P16(0)
};

/* The harness's own state in .data: on the H723 (stm32h723_dma.ld) that
 * is DTCM, apart from the libraries' data in AXI SRAM, so DMA_CACHE=2's
 * line maintenance cannot hit it; elsewhere it changes nothing. */
#define HARNESS __attribute__((section(".data.harness")))
HARNESS static const rb_adapter *volatile cur;
HARNESS static volatile struct libres *res;
HARNESS static volatile uint32_t early;  /* control: commit before the transfer */
HARNESS static volatile uint32_t stop;   /* no new transfers */
HARNESS static volatile uint32_t inflight;   /* bytes of the transfer in flight, 0: none */
HARNESS static volatile uint8_t prod_seq;    /* sequence number of the next transfer's first byte */
HARNESS static volatile uint32_t committed;  /* bytes committed */
HARNESS static volatile uint32_t dma_rng;
HARNESS static uint8_t *volatile inflight_p; /* area of the transfer in flight */
HARNESS static uint32_t rng_main;
#ifdef DIAG_SNAP
/* Diagnostic build (run.sh DMA_SNAP=<address>): when a run stalls, keep the
 * 32 bytes at that address as the core sees them, i.e. through the cache
 * (a read over the debug port shows the memory, not the cache). vl_snap[0]
 * is 1 once taken; the bytes follow at [4]. Read over the debug port after
 * "done"; in DTCM like the rest of the harness's state. */
HARNESS volatile uint8_t vl_snap[36];
#endif

/* Interrupt context only. */
static void start_next(void)
{
    if (inflight || stop) return;
    uint32_t x = dma_rng = xs(dma_rng);
    uint8_t *p = 0;
    uint32_t len = cur->dma_wr_acquire((uintptr_t)&p, 1u + (x & 15u));
    if (len == 0 || !p) { res->full_events++; return; }
    if (len > 16u) len = 16u;
#if DMA_CACHE == 2
    board_dma_cache_before(p, len);
#endif
    if (early) committed += cur->dma_wr_commit(len, 0);
    inflight_p = p;
    inflight = len;
    res->dma_transfers++;
    board_dma_start(&pat[prod_seq], p, len, 2u + ((x >> 8) & 31u));
}

void BOARD_DMA_IRQ_HANDLER(void)
{
    board_dma_isr_ack();
    uint32_t len = inflight;
    res->dma_irqs++;
    if (len) {
#if DMA_CACHE == 2
        board_dma_cache_after(inflight_p, len);
#endif
        if (!early) committed += cur->dma_wr_commit(len, 0);
        prod_seq = (uint8_t)(prod_seq + len);
        inflight = 0;
    }
    start_next();
}

void BOARD_TIMER_IRQ_HANDLER(void)
{
    uint32_t x = dma_rng;
    board_timer_isr_ack(64u + ((x >> 16) & 127u));
    if (!inflight && !stop) {
        res->retries++;
        start_next();
    }
    board_timer_isr_end();
}

static void error(volatile struct libres *r, uint32_t got, uint32_t want)
{
    if (r->errors++ == 0) {
        r->first_error_at = r->transferred;
        r->first_error_got = got;
        r->first_error_want = want;
    }
}

/* Consume up to max bytes; returns the number consumed. */
static uint32_t consume(volatile struct libres *r, uint8_t *expect, uint32_t max)
{
    const uint8_t *p = 0;
    uint32_t len = cur->dma_rd_acquire((uintptr_t)&p, max);
    if (len == 0 || !p) return 0;
    if (board_dma_remaining()) r->overlaps++;
    for (uint32_t k = 0; k < len; k++) {
        uint8_t v = p[k];
        if (v != *expect) { error(r, v, *expect); *expect = v; }
        *expect = (uint8_t)(*expect + 1u);
    }
    return cur->dma_rd_release(len, 0);
}

static void run(const rb_adapter *ad, volatile struct libres *r, uint32_t is_control)
{
    cur = ad;
    res = r;
    ad->reset();
    early = is_control;
    stop = 0;
    inflight = 0;
    prod_seq = 0;
    committed = 0;
    uint8_t expect = 0;
    const uint32_t transfers = prm[P_TRANSFERS];

    board_dma_init(prm[P_PRESCALER], 2u);
    board_irq_priorities(2u, 2u);        /* TIM2 at the DMA interrupt's level */
    board_timer_start(prm[P_PRESCALER], 128u);

    uint32_t phase = 0, in_phase = 0, idle = 0;
    while (r->transferred < transfers) {
        uint32_t x = rng_main = xs(rng_main);
        uint32_t n = consume(r, &expect, 1u + (x & 15u));
        if (n == 0) {
            if (++idle >= STALL_TURNS) {
                r->stalled = 1;
#ifdef DIAG_SNAP
                for (uint32_t i = 0; i < 32u; i++) vl_snap[4u + i] = ((const volatile uint8_t *)DIAG_SNAP)[i];
                vl_snap[0] = 1;
#endif
                break;
            }
            continue;
        }
        idle = 0;
        r->transferred += n;
        if (++in_phase >= PHASE_LEN) { in_phase = 0; phase++; }
        /* slow phases: up to ~4000 loop turns per read, slower than the DMA
         * at its fast end, so the buffer also runs full (acquire returns
         * short or no areas at the wrap); fast phases: empty */
        if (phase & 1u)
            for (volatile uint32_t i = 0; i < ((x >> 8) & 4095u); i++) {}
    }

    /* Stop: no new transfers, let the one in flight finish, drain. */
    stop = 1;
    for (uint32_t i = 0; inflight && i < 50000000u; i++) {}
    board_timer_stop();
    board_dma_stop();
    if (inflight) r->stalled |= 2u;      /* transfer never completed */
    for (;;) {
        uint32_t n = consume(r, &expect, 16u);
        if (!n) break;
        r->transferred += n;
    }
    r->mismatch = committed > r->transferred ? committed - r->transferred : r->transferred - committed;
}

int main(void)
{
    board_init();
#if DMA_CACHE == 0
    board_dma_mem_init();                /* H723: DMA buffers non-cacheable (board_dma.h) */
#endif
    board_cache(1);
    uart_init();

    uint32_t only = NLIBS;               /* NLIBS: no selection */
    if (SEL[0] == SELECT_MAGIC && SEL[1] - VLS_SEL_BASE < NLIBS && SEL[2] == ~SEL[1])
        only = SEL[1] - VLS_SEL_BASE;
    results.done = 0;
    SEL[0] = SEL[2] = 0;
    if (only == NLIBS) {
        /* No selection: announce, and wait for commands (nothing runs on
         * its own: this test is driven over the serial port only). */
        uart_puts("VLS ready ");
        uart_putu(NLIBS);
        uart_putc('\n');
        uart_commands(0);
    }
    uart_puts("VLS start ");
    uart_putu(VLS_SEL_BASE + only);
    uart_putc('\n');
#ifdef ONLY_LIB
    if (only != ONLY_LIB) {
        uart_puts("VLS error not in image\n");
        uart_commands(0);
    }
#endif
    if (!uart_go(board_clock_hz() / 16u)) uart_commands(0);
    uart_flush();

    rng_main = prm[P_MAIN_SEED];
    dma_rng = prm[P_DMA_SEED];
    results.magic = RESULT_MAGIC;
    results.version = 1;
    results.transfers = prm[P_TRANSFERS];
    results.nlibs = NLIBS;
    results.board_id = BOARD_ID;
    results.clock_hz = board_clock_hz();
    results.prescaler = prm[P_PRESCALER];
    results.main_seed = prm[P_MAIN_SEED];
    results.dma_seed = prm[P_DMA_SEED];
    extern uint32_t _sramtext, _eramtext;
    results.code_in_sram = (&_eramtext != &_sramtext);

    const rb_adapter *const libs[NLIBS] = { &adapter_pxq, &adapter_lwrb, &adapter_zephyr, &adapter_tinyusb,
                                            &adapter_ece, &adapter_nuttx_circbuf, &adapter_bbqueue, &adapter_lwrb };
    for (uint32_t l = 0; l < NLIBS; l++) {
        volatile struct libres *r = &results.lib[l];
        r->transferred = r->errors = r->first_error_at = r->first_error_got = r->first_error_want = 0;
        r->full_events = r->dma_transfers = r->overlaps = r->retries = r->mismatch = 0;
        r->dma_irqs = r->stalled = 0;
        if (l != only || !libs[l]) { r->transferred = NOT_IN_IMAGE; continue; }
        if (!libs[l]->dma_wr_acquire) { r->transferred = NOT_AVAILABLE; continue; }
        run(libs[l], r, l == CONTROL);
    }
    results.done = 1;
    uart_puts("VLS done ");
    uart_putu(VLS_SEL_BASE + only);
    uart_putc('\n');
    uart_commands(0);
    board_idle();
}
