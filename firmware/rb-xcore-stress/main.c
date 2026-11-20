/*
 * rb-xcore-stress: SPSC ring buffers with the producer on one core of the
 * nRF5340 and the consumer on the other (plan 2a). The library object lives
 * in the application core's RAM (section .xshared at 0x20070000, the same
 * layout in both images: common/nrf5340/nrf5340_xcore_app.ld,
 * common/nrf5340net/nrf5340_xcore_net.ld); each core runs the library's code
 * from its own flash. Built twice from this file: the application core
 * image (XCORE_NET undefined: serial port, results, the main side) and the
 * network core image (XCORE_NET=1: the other side only).
 *
 * Direction 0: the network core pushes the sequence, the application core
 * pops and checks it. Direction 1: the other way round; the network core
 * checks. Mode 1 single bytes, mode 2 blocks (push_n/pop_n, 1..16 bytes on
 * the application core, 1..4 on the network core). Random pauses on both
 * sides, fast and slow phases on the application core, as the ISR test.
 *
 * Only libraries documented for several cores or threads are in their
 * documented mode here (decode.py MULTICORE_DOCUMENTED, as the RP2350's SMP
 * mode); pxq (a single-core design) is run for information; the control is
 * the ISR test's broken buffer with its SMP window (adapter_broken_smp).
 * Note (firmware/nrf5340-net-probe/README.md): LDREX/STREX is not atomic
 * between the two cores of the nRF5340, so a library that needs a
 * read-modify-write atomic cannot work here; that is the chip's limit.
 *
 * One library per reset over the serial port (common/vls_uart.h),
 * selection indices from 128.
 */
#include <stdint.h>
#include "bench.h"
#ifndef XCORE_NET
#include "board.h"
#include "board_uart.h"
#endif

#define NLIBS 17u
#define NDIRS 2u
#define RESULT_MAGIC 0x564C5831u   /* "VLX1" */
#define NET_MAGIC    0x4E455458u   /* "NETX": the network core is up */
#define NOT_IN_IMAGE 0xFFFFFFFEu
#define PHASE_LEN 2048u
#define STALL_TURNS 20000000u

extern const rb_adapter adapter_lwrb, adapter_jnk0le, adapter_etl_atomic, adapter_qp_lfrb, adapter_micoring,
    adapter_kostyk, adapter_diffstorm, adapter_rigtorp, adapter_polycratia, adapter_rtspsc, adapter_zephyr_smp,
    adapter_lockfree, adapter_moodycamel, adapter_heapless, adapter_bbqueue, adapter_pxq, adapter_broken_smp;
static const rb_adapter *const libs[NLIBS] = {
    &adapter_lwrb, &adapter_jnk0le, &adapter_etl_atomic, &adapter_qp_lfrb, &adapter_micoring,
    &adapter_kostyk, &adapter_diffstorm, &adapter_rigtorp, &adapter_polycratia, &adapter_rtspsc,
    &adapter_zephyr_smp, &adapter_lockfree, &adapter_moodycamel, &adapter_heapless, &adapter_bbqueue,
    &adapter_pxq, &adapter_broken_smp };

/* The control block both cores use, first in .xshared. */
struct xctl {
    uint32_t net_up;                 /* NET_MAGIC once the network core waits */
    uint32_t run, stop, ack;         /* part numbers: run++ starts, stop = run ends, ack = run done */
    uint32_t lib, dir, mode, net_seed;
    uint8_t seq, expect, pad[2];     /* the network core's sequence (dir 0) / expectation (dir 1) */
    uint32_t net_moved, net_calls, net_fullempty;
    uint32_t net_errors, net_first_at, net_first_got, net_first_want;
};
__attribute__((section(".xshared.ctl"), used)) volatile struct xctl xc;

static inline uint32_t xs(uint32_t x) { x ^= x << 13; x ^= x >> 17; x ^= x << 5; return x; }
#define DMB() __asm volatile("dmb" ::: "memory")

/* One transfer by the producer: a byte, or a block of 1..max bytes. */
static uint32_t produce(const rb_adapter *ad, uint32_t mode, uint8_t *seq, uint32_t rnd, uint32_t mask)
{
    if (mode == 1u) {
        if (!ad->push(*seq, 0)) return 0;
        (*seq)++;
        return 1;
    }
    uint8_t blk[16];
    uint32_t n = 1u + (rnd & mask);
    for (uint32_t k = 0; k < n; k++) blk[k] = (uint8_t)(*seq + k);
    uint32_t done = ad->push_n((uintptr_t)blk, n);
    *seq = (uint8_t)(*seq + done);
    return done;
}

#ifdef XCORE_NET
/* ---------------- network core: the other side ---------------- */
static void net_check(uint8_t v)
{
    if (v != xc.expect) {
        if (xc.net_errors++ == 0) {
            xc.net_first_at = xc.net_moved;
            xc.net_first_got = v;
            xc.net_first_want = xc.expect;
        }
        xc.expect = v;
    }
    xc.expect = (uint8_t)(xc.expect + 1u);
}

int main(void)
{
    uint32_t seen = xc.run;
    DMB();
    xc.net_up = NET_MAGIC;
    for (;;) {
        while (xc.run == seen) {}
        seen = xc.run;
        DMB();
        const rb_adapter *ad = libs[xc.lib];
        uint32_t dir = xc.dir, mode = xc.mode, x = xc.net_seed;
        uint8_t seq = xc.seq;
        while (xc.stop != seen) {
            x = xs(x);
            xc.net_calls++;
            if (dir == 0u) {
                uint32_t n = produce(ad, mode, &seq, x, 3u);
                if (n) xc.net_moved += n; else xc.net_fullempty++;
            } else if (mode == 1u) {
                uint8_t v;
                if (ad->pop((uintptr_t)&v, 0)) { net_check(v); xc.net_moved++; } else xc.net_fullempty++;
            } else {
                uint8_t blk[4];
                uint32_t n = ad->pop_n((uintptr_t)blk, 1u + (x & 3u));
                for (uint32_t k = 0; k < n; k++) net_check(blk[k]);
                if (n) xc.net_moved += n; else xc.net_fullempty++;
            }
            for (volatile uint32_t i = 0; i < ((x >> 8) & 63u); i++) {}
        }
        xc.seq = seq;
        DMB();
        xc.ack = seen;
    }
}

#else
/* ---------------- application core: main side, serial port, results ---------------- */
struct dirres {
    uint32_t transferred, errors, first_error_at, first_error_got, first_error_want;
    uint32_t full_events, empty_events, net_calls;
};
struct results {
    uint32_t magic, version, done, transfers, nlibs, board_id, clock_hz, mode;
    uint32_t main_seed, net_seed, net_started, reserved;
    struct dirres r[NLIBS][NDIRS];
};
__attribute__((section(".results")))
volatile struct results results;
#include "../common/select.h"
VL_SELECT_DEFINE

enum { P_MODE, P_TRANSFERS, P_MAIN_SEED, P_NET_SEED, NPRM };
static uint32_t prm[NPRM] = { 1u, 300000u, 0x12345678u, 0xCAFEBABEu };
static const char *const prm_names[NPRM] = { "mode", "transfers", "main_seed", "net_seed" };
static int prm_valid(void)
{
    return prm[P_MODE] >= 1u && prm[P_MODE] <= 2u && prm[P_TRANSFERS] >= 1u && prm[P_TRANSFERS] <= (1u << 26)
        && prm[P_MAIN_SEED] && prm[P_NET_SEED];
}
#define VLS_RESULTS results
#define VLS_NSEL NLIBS
#define VLS_SEL_BASE 128u
#define VLS_SEL_LIMIT 256u
#define VLS_ECC_WRITE() do { results.done = 0; } while (0)
#define VLS_ECC_READ() do { (void)results.done; } while (0)
#include "../common/vls_uart.h"

/* SPU EXTDOMAIN[0].PERM (secure accesses from the network core) and
 * RESET.NETWORK.FORCEOFF (nrfx MDK nrf5340_application.h; see
 * firmware/nrf5340-net-probe/README.md). */
#define NRF_SPU_EXTDOMAIN0_PERM (*(volatile uint32_t *)0x50003440u)
#define NRF_RESET_NET_FORCEOFF  (*(volatile uint32_t *)0x50005614u)

extern uint32_t _sxshared, _exshared;
extern void (*__init_array_start[])(void);
extern void (*__init_array_end[])(void);

static uint32_t rng;

static void check(volatile struct dirres *r, uint8_t v, uint8_t *expect)
{
    if (v != *expect) {
        if (r->errors++ == 0) {
            r->first_error_at = r->transferred;
            r->first_error_got = v;
            r->first_error_want = *expect;
        }
        *expect = v;
    }
    *expect = (uint8_t)(*expect + 1u);
}

static uint32_t consume(const rb_adapter *ad, uint32_t mode, volatile struct dirres *r, uint8_t *expect, uint32_t rnd)
{
    if (mode == 1u) {
        uint8_t v;
        if (!ad->pop((uintptr_t)&v, 0)) return 0;
        check(r, v, expect);
        return 1;
    }
    uint8_t blk[16];
    uint32_t n = ad->pop_n((uintptr_t)blk, 1u + (rnd & 15u));
    for (uint32_t k = 0; k < n; k++) check(r, blk[k], expect);
    return n;
}

static void run_dir(uint32_t l, uint32_t dir, volatile struct dirres *r)
{
    const rb_adapter *ad = libs[l];
    const uint32_t mode = prm[P_MODE], transfers = prm[P_TRANSFERS];
    ad->reset();
    xc.lib = l; xc.dir = dir; xc.mode = mode; xc.net_seed = prm[P_NET_SEED] ^ (l << 8) ^ dir;
    xc.seq = 0; xc.expect = 0;
    xc.net_moved = xc.net_calls = xc.net_fullempty = 0;
    xc.net_errors = xc.net_first_at = xc.net_first_got = xc.net_first_want = 0;
    uint8_t seq = 0, expect = 0;
    DMB();
    xc.run = xc.run + 1u;
    uint32_t part = xc.run, phase = 0, in_phase = 0, idle = 0, moved = 0;
    for (;;) {
        uint32_t done = dir == 0u ? r->transferred : xc.net_moved;
        if (done >= transfers) break;
        uint32_t x = rng = xs(rng);
        uint32_t n = dir == 0u ? consume(ad, mode, r, &expect, x) : produce(ad, mode, &seq, x, 15u);
        if (n == 0) {
            if (dir == 0u) r->empty_events++; else r->full_events++;
            if (++idle >= STALL_TURNS) break;
            continue;
        }
        idle = 0;
        if (dir == 0u) r->transferred += n; else moved += n;
        if (++in_phase >= PHASE_LEN) { in_phase = 0; phase++; }
        if (phase & 1u)
            for (volatile uint32_t i = 0; i < ((x >> 8) & 1023u); i++) {}
    }
    xc.stop = part;
    for (uint32_t t = 0; xc.ack != part && t < 200000000u; t++) {}
    DMB();
    r->net_calls = xc.net_calls;
    if (dir == 0u) {
        /* drain what the network core left */
        for (;;) { uint32_t n = consume(ad, mode, r, &expect, 15u); if (!n) break; r->transferred += n; }
        if (dir == 0u) r->full_events = xc.net_fullempty;
        /* lost or extra values: pushed by the network core vs popped here */
        uint32_t pushed = xc.net_moved;
        if (pushed != r->transferred) r->errors += pushed > r->transferred ? pushed - r->transferred : r->transferred - pushed;
    } else {
        /* the network core checked; drain the rest here with its expectation */
        uint8_t e = xc.expect;
        uint32_t popped = xc.net_moved;
        for (;;) {
            uint8_t v;
            if (!ad->pop((uintptr_t)&v, 0)) break;
            if (v != e) xc.net_errors++;
            e = (uint8_t)(v + 1u);
            popped++;
        }
        r->transferred = popped;
        r->errors = xc.net_errors;
        r->first_error_at = xc.net_first_at;
        r->first_error_got = xc.net_first_got;
        r->first_error_want = xc.net_first_want;
        r->empty_events = xc.net_fullempty;
        if (moved != popped) r->errors += moved > popped ? moved - popped : popped - moved;
    }
}

int main(void)
{
    board_init();
    board_cache(1);
    uart_init();
    uint32_t only = NLIBS;
    if (SEL[0] == SELECT_MAGIC && SEL[1] - VLS_SEL_BASE < NLIBS && SEL[2] == ~SEL[1])
        only = SEL[1] - VLS_SEL_BASE;
    results.done = 0;
    SEL[0] = SEL[2] = 0;
    if (only == NLIBS) {
        uart_puts("VLS ready ");
        uart_putu(NLIBS);
        uart_putc('\n');
        uart_commands(0);
    }
    uart_puts("VLS start ");
    uart_putu(VLS_SEL_BASE + only);
    uart_putc('\n');
    if (!uart_go(board_clock_hz() / 16u)) uart_commands(0);
    uart_flush();

    /* the shared part: cleared, then the constructors again (they ran on
     * it before it was cleared); then the network core */
    for (volatile uint32_t *p = &_sxshared; p < &_exshared; p++) *p = 0;
    for (void (**f)(void) = __init_array_start; f < __init_array_end; f++) (*f)();
    NRF_SPU_EXTDOMAIN0_PERM = 1u << 4;
    NRF_RESET_NET_FORCEOFF = 0;
    uint32_t up = 0;
    for (uint32_t t = 0; t < 100000000u; t++) if (xc.net_up == NET_MAGIC) { up = 1; break; }
    DMB();

    rng = prm[P_MAIN_SEED];
    results.magic = RESULT_MAGIC;
    results.version = 1;
    results.transfers = prm[P_TRANSFERS];
    results.nlibs = NLIBS;
    results.board_id = BOARD_ID;
    results.clock_hz = board_clock_hz();
    results.mode = prm[P_MODE];
    results.main_seed = prm[P_MAIN_SEED];
    results.net_seed = prm[P_NET_SEED];
    results.net_started = up;
    for (uint32_t l = 0; l < NLIBS; l++)
        for (uint32_t d = 0; d < NDIRS; d++) {
            volatile struct dirres *r = &results.r[l][d];
            r->transferred = r->errors = r->first_error_at = r->first_error_got = r->first_error_want = 0;
            r->full_events = r->empty_events = r->net_calls = 0;
            if (l != only || !up) { r->transferred = NOT_IN_IMAGE; continue; }
            run_dir(l, d, r);
        }
    NRF_RESET_NET_FORCEOFF = 1u;         /* network core off again */
    results.done = 1;
    uart_puts("VLS done ");
    uart_putu(VLS_SEL_BASE + only);
    uart_putc('\n');
    uart_commands(0);
    board_idle();
}
#endif
