/*
 * rb-mp-stress: multi-producer / multi-consumer stress test of ring buffers
 * on ONE core, with two interrupts at different priorities (B can preempt A,
 * both preempt the main loop). Only libraries in a mode they document for
 * several producers or consumers, plus a control.
 *
 * MP_MODE 1 (MPSC): interrupt A (low priority) and interrupt B (high) are
 *   producers, the main loop is the consumer. Byte = producer id (bit 7) |
 *   that producer's sequence number (bits 0..6). Checked: every producer's
 *   values arrive one by one in order (no loss, duplicate or reorder within
 *   a producer), and after a final drain popped == pushed per producer.
 * MP_MODE 2 (SPMC): the main loop is the producer (sequence 0, 1, 2, ...
 *   mod 256), interrupts A and B are the consumers. Checked: each consumer
 *   sees increasing values, and after a final drain every value was
 *   delivered exactly once (count per value mod 256).
 *
 * SMP_MODE=1 (boards with a second core, BOARD_HAS_CORE1: the RP2350): no
 *   interrupts. Role B runs on core 1 in a loop with random pauses; role A
 *   is taken by the main loop on core 0 itself, which alternates it with
 *   its own role (MPSC: produce as A, then consume; SPMC: produce, then
 *   consume as A). So two cores really run at the same time; "irqs" count
 *   the attempts of each role. Only libraries made for several cores
 *   (atomic read-modify-write or a lock that works across cores) are in
 *   their documented mode here.
 *
 * The interrupt periods are random (xorshift32, separate seeds); the main
 * loop alternates fast and slow phases so the buffer runs full and empty.
 * Results at 0x20000000, decoded by decode.py.
 *
 * Run parameters (since 2026-11-15): one image holds both modes; the mode,
 * the seeds, the timer prescaler and the transfers are chosen per run, so
 * a campaign does not flash a new image for every run (flash wears out).
 * At start the firmware sets results.prm_wait = PRM_WAIT and waits some
 * 20 s for the host (run.sh, over the debug port) to write the parameters
 * into results.prm[] and then results.prm_magic = PRM_MAGIC ^ checksum; it
 * clears both and runs. Without them in time, or with an invalid set, it
 * runs with the build's defaults (MP_MODE, MAIN_SEED, ... as -D flags); the
 * header of the result block always holds what was used. The block is
 * written over while the firmware runs, not before a reset, because the
 * RP2350's boot ROM uses SRAM at every reset.
 *
 * One library per reset (since 2026-11-17, boards with board_uart.h): the
 * host sends "run <n>" (n: 64 + the MP library index, MP_IDX_*), the firmware
 * resets itself with the selection words set (common/select.h), says "VLS
 * start <n>", takes the run parameters as a "go" line (mode, transfers,
 * prescaler, main_seed, seed_a, seed_b), runs library n alone in that mode
 * (the other slots NOT_IN_IMAGE) and says "VLS done <n>"; "dump" sends the
 * result block (common/vls_uart.h, host: common/uart_host.py). With
 * ONLY_LIB (Makefile ONLY=n, one image per library in a bundle) the same
 * protocol. Without a selection everything is as before: "VLS ready", then
 * the parameters over the debug port and every library of the mode.
 */
#include <stdint.h>
#include "board.h"
#include "bench.h"
/* UART to the debug probe's serial port (common/<board>/board_uart.h):
 * one library per reset and the run parameters over it (since 2026-11-17,
 * the protocol of ../nrf5340-rb-stress, common/vls_uart.h), polled, used
 * only before and after a library runs. */
#if defined(__has_include)
#if __has_include("board_uart.h")
#include "board_uart.h"
#define HAVE_UART 1
#endif
#endif
#ifndef HAVE_UART
#define HAVE_UART 0
#endif

#ifndef MP_MODE
#define MP_MODE 1
#endif
#ifndef TRANSFERS
#define TRANSFERS 200000u
#endif
#ifndef TIMER_PRESCALER
#define TIMER_PRESCALER 0u
#endif
#ifndef MAIN_SEED
#define MAIN_SEED 0x12345678u
#endif
#ifndef SEED_A
#define SEED_A 0xCAFEBABEu
#endif
#ifndef SEED_B
#define SEED_B 0x0BADF00Du
#endif
#define PERIOD_MIN_A 40u
#define PERIOD_MIN_B 47u
#define PHASE_LEN 2048u
#define IRQ_CAP_PER_BYTE 60u
#define NOT_AVAILABLE 0xFFFFFFFFu /* libres.transferred: library cannot be built for this core */
#define NOT_IN_IMAGE  0xFFFFFFFEu /* libres.transferred: ONLY_LIB image of another library */
#define RESULT_MAGIC 0x564C4D31u  /* "VLM1" */

extern const rb_adapter adapter_pxq_mpsc, adapter_pxq_spmc, adapter_pxq_mpmc, adapter_lockfree_mpmc;
extern const rb_adapter adapter_pxq_mpsc_resv;   /* pxq 1.5.0 producer reservations */
extern const rb_adapter adapter_heapless_mpmc;   /* Rust: ../rust-adapters */
/* Further MPSC libraries held back from the public tree (extra/, with their
 * own Makefile part): only in a WITH_EXTRA=1 build. */
#if defined(WITH_EXTRA) && WITH_EXTRA
#include "extra/mp_extra.h"
#endif
#ifndef MP_EXTRA_MPSC
#define MP_EXTRA_MPSC
#define MP_EXTRA_MPSC_IDX
#define MP_EXTRA_MPSC_N 0u
#endif

/* MP library index: one per library (and topology family), the same in both
 * modes; Makefile LIB_<n> lists its objects, ONLY=n builds its image.
 *   0 pxq MPSC (mode 1) / SPMC (mode 2)   4 DNedic lockfree mpmc
 *   1 pxq MPMC                            5 heapless mpmc (Rust)
 *   2 RIOT tsrb                           6 pxq MPSC reserve/commit (mode 1)
 *   3 wizard97 + PRIMASK                  7 control: jnk0le (SPSC)
 *   8.. extra/ (WITH_EXTRA=1, mode 1)
 * The result slots keep their order per mode (decode.py); MP_IDX_* gives
 * each slot's library index. */
#define MP_IDX_MPSC { 0u, 1u, 2u, 3u, 4u, 5u, 6u, MP_EXTRA_MPSC_IDX 7u }
#define MP_IDX_SPMC { 0u, 1u, 2u, 3u, 4u, 5u, 7u }
/* One firmware per library (ONLY_LIB=n): only library n's objects are
 * linked, every adapter is a weak reference and the slots of the other
 * libraries are marked NOT_IN_IMAGE (as ../nrf5340-rb-stress). */
#ifdef ONLY_LIB
extern const rb_adapter adapter_pxq_mpsc __attribute__((weak)), adapter_pxq_spmc __attribute__((weak)),
    adapter_pxq_mpmc __attribute__((weak)), adapter_lockfree_mpmc __attribute__((weak)),
    adapter_pxq_mpsc_resv __attribute__((weak)), adapter_heapless_mpmc __attribute__((weak)),
    adapter_riot_tsrb __attribute__((weak)), adapter_wizard97_primask __attribute__((weak)),
    adapter_jnk0le __attribute__((weak));
#ifdef MP_EXTRA_WEAK
MP_EXTRA_WEAK
#endif
#endif

#ifndef SMP_MODE
#define SMP_MODE 0
#endif
#if SMP_MODE && !defined(BOARD_HAS_CORE1)
#error "SMP_MODE needs a board with a second core (BOARD_HAS_CORE1)"
#endif
#define NLIBS_MPSC (8u + MP_EXTRA_MPSC_N)
#define NLIBS_SPMC 7u
#define NLIBS NLIBS_MPSC                 /* result slots: the larger of the two */

struct libres {
    uint32_t transferred, errors, first_error_at, first_error_got, first_error_want;
    uint32_t full_or_empty[2];   /* per interrupt: full (MPSC) / empty (SPMC) events */
    uint32_t irqs[2];
    uint32_t moved[2];           /* per interrupt: pushed (MPSC) / popped (SPMC) */
    uint32_t mismatch;           /* after the drain: lost + duplicated values */
};
#ifndef COVERAGE
#define COVERAGE 0
#endif
/* prm[]: the run parameters; the first NPRM_HOST also in results.prm (the
 * debug-port way). COVERAGE builds take three more over the serial port
 * (the aimed interrupts, see vl_cov below; 0: the build's, none). */
enum { P_MODE, P_TRANSFERS, P_PRESCALER, P_MAIN_SEED, P_SEED_A, P_SEED_B, NPRM_HOST,
       P_COV_AIM = NPRM_HOST, P_COV_WINDOW, P_COV_SEED, P_COV_OFF, NPRM_COV };
#define NPRM (COVERAGE ? NPRM_COV : NPRM_HOST)
struct results {
    uint32_t magic, mode, done, transfers, nlibs, board_id, clock_hz, timer_prescaler;
    uint32_t main_seed, seed_a, seed_b, code_in_sram;
    struct libres lib[NLIBS];
    /* run parameters from the host (see the header); the last words of the
     * block, their address read from the ELF */
    uint32_t prm_wait, prm_magic, prm[NPRM_HOST];
};
#define PRM_WAIT  0x564C4D57u            /* "VLMW": waiting for parameters */
#define PRM_MAGIC 0x564C4D50u            /* "VLMP" ^ sum of prm[] */
__attribute__((section(".results")))
volatile struct results results;
#include "../common/select.h"
VL_SELECT_DEFINE
#define MP_NIDX (8u + MP_EXTRA_MPSC_N)   /* MP library indices 0 .. MP_NIDX - 1 */
/* Selection index of MP library n: VLS_SEL_BASE + n, after the ISR stress
 * test's libraries (0..40), so the images of both tests can share one bundle
 * (../common/bundle.py --index-base). "run <n>" takes any index below 256:
 * an MP image can select an ISR library too. */
#define VLS_SEL_BASE 64u
#define VLS_SEL_LIMIT 256u


static const rb_adapter *volatile cur;
static volatile struct libres *res;
static volatile uint32_t rng_a = SEED_A, rng_b = SEED_B;
static uint32_t rng_main = MAIN_SEED;
static uint32_t prm[NPRM] = { MP_MODE, TRANSFERS, TIMER_PRESCALER, MAIN_SEED, SEED_A, SEED_B };
static __attribute__((unused)) const char *const prm_names[NPRM] = {
    "mode", "transfers", "prescaler", "main_seed", "seed_a", "seed_b",
#if COVERAGE
    "cov_aim", "cov_window", "cov_seed", "cov_off",
#endif
};
static volatile uint32_t mode;           /* 1 MPSC, 2 SPMC (prm[P_MODE]) */

/* Mode 1/2, transfers 1..2^26 (the interrupt cap must not overflow),
 * prescaler 0..4, seeds not 0 (xorshift). */
static __attribute__((unused)) int prm_valid(void)
{
    return prm[P_MODE] >= 1u && prm[P_MODE] <= 2u && prm[P_TRANSFERS] >= 1u && prm[P_TRANSFERS] <= (1u << 26)
        && prm[P_PRESCALER] <= 4u && prm[P_MAIN_SEED] && prm[P_SEED_A] && prm[P_SEED_B]
#if COVERAGE
        && prm[P_COV_WINDOW] <= 65536u
#endif
        ;
}
#if HAVE_UART
/* The serial-port protocol (common/vls_uart.h). Against the H7's RAM ECC
 * write buffer after the selection: done (offset 8) and the block's last
 * word, in the other bank. */
#define VLS_RESULTS results
#define VLS_NSEL MP_NIDX
#define VLS_ECC_WRITE() do { results.done = 0; results.prm[NPRM_HOST - 1] = results.prm[NPRM_HOST - 1]; } while (0)
#define VLS_ECC_READ() do { (void)results.done; (void)results.prm[NPRM_HOST - 1]; } while (0)
#if COVERAGE
#define VLS_DUMP2 cov_dump               /* "dump2": the coverage table (below) */
#endif
#include "../common/vls_uart.h"
#endif

static inline uint32_t xs(uint32_t x) { x ^= x << 13; x ^= x >> 17; x ^= x << 5; return x; }

static void error(volatile struct libres *r, uint32_t got, uint32_t want)
{
    if (r->errors++ == 0) {
        r->first_error_at = r->transferred;
        r->first_error_got = got;
        r->first_error_want = want;
    }
}

/* ---------------- MPSC: interrupts produce, main consumes ---------------- */
static volatile uint8_t seq[2];          /* next sequence number per producer */
static uint8_t expect[2];                /* main: next expected per producer */
static uint32_t popped[2];

static inline void produce(uint32_t id)
{
    uint8_t s = seq[id];
    if (cur->push((uintptr_t)((id << 7) | s), 0)) {
        seq[id] = (uint8_t)((s + 1u) & 0x7Fu);
        res->moved[id]++;
    } else {
        res->full_or_empty[id]++;
    }
}

static inline uint32_t consume_one(volatile struct libres *r)
{
    uint8_t v;
    if (!cur->pop((uintptr_t)&v, 0)) return 0;
    uint32_t id = v >> 7, s = v & 0x7Fu;
    if (s != expect[id]) error(r, v, (id << 7) | expect[id]);
    expect[id] = (uint8_t)((s + 1u) & 0x7Fu);
    popped[id]++;
    r->transferred++;
    return 1;
}
/* ---------------- SPMC: main produces, interrupts consume ---------------- */
static uint8_t main_seq;
static uint32_t pushed_total;
static volatile uint32_t count[256];     /* deliveries per value mod 256 */
static volatile uint8_t last[2];
static volatile uint8_t have_last[2];

static inline void consume_isr(uint32_t id)
{
    uint8_t v;
    if (!cur->pop((uintptr_t)&v, 0)) { res->full_or_empty[id]++; return; }
#if SMP_MODE
    /* Two cores: the count is a read-modify-write from both, so atomic (SRAM
     * is Shareable in SMP builds, see board_sram_shareable). No order check:
     * the values are 8 bits, so "increasing" holds only across gaps below
     * 128, and with two free-running cores one consumer can take 128 or
     * more values while the other is busy (core 0 also produces). That gave
     * order "errors" in every library alike, the control included. Lost and
     * duplicated values are still counted exactly. */
    __atomic_fetch_add(&count[v], 1u, __ATOMIC_RELAXED);
#else
    count[v]++;
    if (have_last[id]) {
        uint8_t d = (uint8_t)(v - last[id]);
        if (d == 0 || d > 127u) error(res, v, (uint8_t)(last[id] + 1u));   /* not increasing */
    }
#endif
    last[id] = v;
    have_last[id] = 1;
    res->moved[id]++;
#if !SMP_MODE
    res->transferred++;          /* SMP: main sums moved[0] + moved[1] instead */
#endif
}

/* ---------------- Coverage measurement and aimed interrupts ----------------
 * COVERAGE=1 (build flag, -DCOVERAGE=1 in MP_PARAMS; a prototype since
 * 2026-11-17, not in the campaign images): each interrupt records the
 * address at which it interrupted (the PC in the exception frame the core
 * stacked), per library slot and interrupt, in the table vl_cov. Read by
 * the host after the run (run.sh COV_OUT, cov_report.py), which maps the
 * addresses to the library's instructions: how often each instruction
 * boundary of push/pop was interrupted, and which never were. That is the
 * test's real reach for a library, independent of the control.
 * Aimed interrupts (vl_cov.aim != 0, written by the host with the run
 * parameters): besides the timers, the main loop arms SysTick before its
 * push/pop with a random delay of 1..vl_cov.window cycles (with
 * probability 1/aim), and SysTick (highest priority) pends interrupt A or
 * B; interrupt A arms SysTick the same way for B before its own push/pop.
 * So interrupts land inside the operations, at every offset, whatever the
 * timer rate. The settings come from the host: written into vl_cov over
 * the debug port, or as run parameters cov_aim, cov_window, cov_seed, cov_off over
 * the serial port (one library per reset), where "dump2" then sends the
 * table (common/vls_uart.h). On the M0+ boards SysTick is otherwise the
 * cycle counter of time_call(), which this test does not use. */
#if COVERAGE && SMP_MODE
#error "COVERAGE: interrupts only, not SMP_MODE"
#endif
#if COVERAGE
#ifndef COV_N
#if BOARD_ID == 5u                       /* SAM D20: 32 KB of SRAM */
#define COV_N 2048u
#else
#define COV_N 4096u
#endif
#endif
#define COV_MAGIC 0x564C4356u            /* "VLCV" */
struct cov {
    uint32_t magic, n, aim, window, full, aims, aim_seed, off;   /* off: no recording */
    uint32_t key[COV_N];                 /* interrupted PC | 1 if interrupt B; 0: free */
    uint32_t cnt[COV_N];                 /* slot << 24 | count (saturates at 2^24 - 1) */
};
volatile struct cov vl_cov;
static uint32_t cov_slot;
#if HAVE_UART
static void cov_dump(void)
{
    uart_dump_block((const volatile uint32_t *)&vl_cov, sizeof vl_cov / 4u);
}
#endif
static void cov_add(uint32_t pc, uint32_t irq)
{
    uint32_t key = (pc & ~1u) | irq, tag = cov_slot << 24;
    uint32_t h = ((key ^ (tag >> 8)) * 0x9E3779B1u) >> 20;
    for (uint32_t i = 0; i < 32u; i++, h++) {
        uint32_t j = h & (COV_N - 1u);
        uint32_t k = vl_cov.key[j];
        if (k == 0) { vl_cov.key[j] = key; vl_cov.cnt[j] = tag | 1u; return; }
        if (k == key && (vl_cov.cnt[j] & 0xFF000000u) == tag) {
            if ((vl_cov.cnt[j] & 0xFFFFFFu) != 0xFFFFFFu) vl_cov.cnt[j]++;
            return;
        }
    }
    vl_cov.full++;
}
#if defined(TIM2_IRQN) && defined(TIM3_IRQN)   /* STM32 */
#define COV_IRQN_A TIM2_IRQN
#define COV_IRQN_B TIM3_IRQN
#elif defined(TIMER0_IRQN) && defined(TIMER1_IRQN)   /* nRF5340 */
#define COV_IRQN_A TIMER0_IRQN
#define COV_IRQN_B TIMER1_IRQN
#elif defined(PWM_IRQN_A) && defined(PWM_IRQN_B)   /* RP2350 */
#define COV_IRQN_A PWM_IRQN_A
#define COV_IRQN_B PWM_IRQN_B
#elif defined(TC0_IRQN) && defined(TC2_IRQN)   /* SAM D20 */
#define COV_IRQN_A TC0_IRQN
#define COV_IRQN_B TC2_IRQN
#else
#error "COVERAGE: no timer IRQ numbers for this board yet"
#endif
#define SYST_CSR_R (*(volatile uint32_t *)0xE000E010u)
#define SYST_RVR_R (*(volatile uint32_t *)0xE000E014u)
#define SYST_CVR_R (*(volatile uint32_t *)0xE000E018u)
#define SHPR3_R    (*(volatile uint32_t *)0xE000ED20u)
#define NVIC_ISPR_R(n) (*(volatile uint32_t *)(0xE000E200u + 4u * ((n) / 32u)))
static volatile uint32_t aim_irqn, aim_on;
static uint32_t rng_aim = 0x6A09E667u;
void SysTick_Handler(void)
{
    SYST_CSR_R = 0;
    NVIC_ISPR_R(aim_irqn) = 1u << (aim_irqn % 32u);
}
/* Arm SysTick: interrupt irqn pended 1..window cycles from now. */
static inline void aim(uint32_t irqn)
{
    uint32_t x = rng_aim = xs(rng_aim);
    if (vl_cov.aim > 1u && x % vl_cov.aim) return;
    if (SYST_CSR_R & 1u) return;          /* one already armed */
    aim_irqn = irqn;
    SYST_RVR_R = 1u + (x >> 8) % vl_cov.window;
    SYST_CVR_R = 0;
    vl_cov.aims++;
    SYST_CSR_R = 7u;                     /* core clock, interrupt, enable */
}
static void aim_init(void)
{
    SYST_CSR_R = 0;                      /* the M0+ boards' board_init left it running (time_call) */
    SHPR3_R &= 0x00FFFFFFu;              /* SysTick: priority 0, above A and B */
    aim_on = vl_cov.aim != 0u && vl_cov.window != 0u;
    if (vl_cov.aim_seed) rng_aim = vl_cov.aim_seed;
}
#define AIM_MAIN() do { if (aim_on) aim((rng_aim & 0x100u) ? COV_IRQN_B : COV_IRQN_A); } while (0)
#define AIM_A() do { if (aim_on) aim(COV_IRQN_B); } while (0)
/* The interrupt entry: the stacked frame (MSP or PSP by EXC_RETURN bit 2)
 * to the C body, which returns through the EXC_RETURN still in lr. */
#define COV_ENTRY(name, body) \
    __attribute__((naked)) void name(void) \
    { __asm volatile("mov r0, lr\n movs r1, #4\n tst r0, r1\n mrs r0, msp\n beq 1f\n mrs r0, psp\n" \
                     "1: ldr r1, =" #body "\n bx r1\n .ltorg" ::: "memory"); }
/* Recording costs some dozens of cycles per interrupt: at prescaler 1 on
 * the M0+ boards that starved the main loop (2026-11-17), so it can be
 * switched off per run (vl_cov.off, cov_off); the campaigns record at the
 * slow rates only. */
#define COV_HIT(frame, irq) do { if (!vl_cov.off) cov_add((frame)[6], (irq)); } while (0)
#else
#define AIM_MAIN() do {} while (0)
#define AIM_A() do {} while (0)
#endif

#if COVERAGE
__attribute__((used)) void timer_a_body(const uint32_t *frame)
#else
void BOARD_TIMER_IRQ_HANDLER(void)         /* interrupt A, low priority */
#endif
{
    uint32_t x = rng_a = xs(rng_a);
    board_timer_isr_ack(PERIOD_MIN_A + (x & 127u));
    res->irqs[0]++;
#if COVERAGE
    COV_HIT(frame, 0u);
    AIM_A();
#endif
    if (mode == 1u) produce(0); else consume_isr(0);
    board_timer_isr_end();
}

#if COVERAGE
__attribute__((used)) void timer_b_body(const uint32_t *frame)
#else
void BOARD_TIMER_B_IRQ_HANDLER(void)       /* interrupt B, high priority */
#endif
{
    uint32_t x = rng_b = xs(rng_b);
    board_timer_b_isr_ack(PERIOD_MIN_B + (x & 127u));
    res->irqs[1]++;
#if COVERAGE
    COV_HIT(frame, 1u);
#endif
    if (mode == 1u) produce(1); else consume_isr(1);
    board_timer_b_isr_end();
}
#if COVERAGE
COV_ENTRY(BOARD_TIMER_IRQ_HANDLER, timer_a_body)
COV_ENTRY(BOARD_TIMER_B_IRQ_HANDLER, timer_b_body)
#endif

static void slow_wait(uint32_t phase)
{
    if (phase & 1u) {
        uint32_t n = (rng_main = xs(rng_main)) & 1023u;
        for (volatile uint32_t i = 0; i < n; i++) {}
    }
}

#if SMP_MODE
static volatile uint32_t smp_run, smp_stop, smp_ack;
static uint32_t core1_stack[1024];
static void core1_main(void)             /* role B on core 1 */
{
    uint32_t seen = 0;
    for (;;) {
        while (smp_run == seen) {}
        seen = smp_run;
        __asm volatile("dmb" ::: "memory");
        while (smp_stop != seen) {
            uint32_t x = rng_b = xs(rng_b);
            res->irqs[1]++;
            if (mode == 1u) produce(1); else consume_isr(1);
            for (volatile uint32_t i = 0; i < (x & 63u); i++) {}
        }
        __asm volatile("dmb" ::: "memory");
        smp_ack = seen;
    }
}
static void roles_start(void) { __asm volatile("dmb" ::: "memory"); smp_run = smp_run + 1u; }
static void roles_stop(void)
{
    smp_stop = smp_run;
    while (smp_ack != smp_run) {}
    __asm volatile("dmb" ::: "memory");
}
#else
static void roles_start(void)
{
    board_timer_start(prm[P_PRESCALER], PERIOD_MIN_A + 64);
    board_timer_b_start(prm[P_PRESCALER], PERIOD_MIN_B + 64);
}
static void roles_stop(void)
{
    board_timer_b_stop();
    board_timer_stop();
}
#endif

static void run(const rb_adapter *ad, volatile struct libres *r)
{
    cur = ad;
    res = r;
#if COVERAGE
    cov_slot = (uint32_t)(r - results.lib);
#endif
    ad->reset();
    if (mode == 1u) {
        seq[0] = seq[1] = 0;
        expect[0] = expect[1] = 0;
        popped[0] = popped[1] = 0;
    } else {
        main_seq = 0;
        pushed_total = 0;
        for (uint32_t i = 0; i < 256; i++) count[i] = 0;
        have_last[0] = have_last[1] = 0;
    }
    roles_start();

    uint32_t phase = 0, in_phase = 0;
    const uint32_t transfers = prm[P_TRANSFERS];
    uint32_t cap = IRQ_CAP_PER_BYTE * transfers;
    while (r->transferred < transfers && r->irqs[0] + r->irqs[1] < cap) {
#if SMP_MODE                             /* role A, taken by main itself */
        res->irqs[0]++;
        if (mode == 1u) produce(0);
        else { consume_isr(0); r->transferred = r->moved[0] + r->moved[1]; }
#endif
        AIM_MAIN();
        if (mode == 1u) {
            if (!consume_one(r)) continue;
        } else {
            if (!ad->push(main_seq, 0)) continue;
            main_seq++;
            pushed_total++;
        }
        if (++in_phase >= PHASE_LEN) { in_phase = 0; phase++; }
        slow_wait(phase);
    }
    roles_stop();
#if COVERAGE
    SYST_CSR_R = 0;
#endif

    /* Drain what is left and compare totals. */
    if (mode == 1u) {
        while (consume_one(r)) {}
        for (uint32_t id = 0; id < 2; id++) {
            uint32_t d = r->moved[id] > popped[id] ? r->moved[id] - popped[id] : popped[id] - r->moved[id];
            r->mismatch += d;
        }
    } else {
        uint8_t v;
        while (ad->pop((uintptr_t)&v, 0)) count[v]++;
        for (uint32_t i = 0; i < 256; i++) {
            uint32_t want = pushed_total / 256u + (i < pushed_total % 256u ? 1u : 0u);
            uint32_t got = count[i];
            r->mismatch += got > want ? got - want : want - got;
        }
    }
}

/* The run parameters from the host over the debug port (see the header;
 * the checks of prm_valid). */
static void params_from_host(void)
{
    results.prm_magic = 0;
    results.prm_wait = PRM_WAIT;
    for (uint32_t i = 0, n = board_clock_hz() / 2u; i < n; i++) {   /* some 20 s or more */
        if (results.prm_magic) break;
        for (volatile uint32_t k = 0; k < 8u; k++) {}
    }
    uint32_t m = results.prm_magic, sum = 0, p[NPRM_HOST];
    for (uint32_t k = 0; k < NPRM_HOST; k++) { p[k] = results.prm[k]; sum += p[k]; }
    results.prm_wait = 0;
    results.prm_magic = 0;
    if (m != (PRM_MAGIC ^ sum)) return;
    if (p[P_MODE] < 1u || p[P_MODE] > 2u || p[P_TRANSFERS] < 1u || p[P_TRANSFERS] > (1u << 26)
        || p[P_PRESCALER] > 4u || !p[P_MAIN_SEED] || !p[P_SEED_A] || !p[P_SEED_B]) return;
    for (uint32_t k = 0; k < NPRM_HOST; k++) prm[k] = p[k];
}

int main(void)
{
    board_init();
    board_cache(1);
#if SMP_MODE
    board_core1_launch(core1_main, core1_stack + sizeof core1_stack / sizeof core1_stack[0]);
#else
    board_irq_priorities(2u, 1u);        /* B (1) preempts A (2); both preempt main */
#endif

    uint32_t only = MP_NIDX;             /* MP_NIDX: no selection, every library */
    if (SEL[0] == SELECT_MAGIC && SEL[1] - VLS_SEL_BASE < MP_NIDX && SEL[2] == ~SEL[1])
        only = SEL[1] - VLS_SEL_BASE;
    results.done = 0;                    /* before the host sees the selection consumed */
    SEL[0] = SEL[2] = 0;
#if HAVE_UART
    uart_init();
    if (only == MP_NIDX) {
        /* No selection: announce, and give the host about a second to choose */
        uart_puts("VLS ready ");
        uart_putu(MP_NIDX);
        uart_putc('\n');
        uart_commands(board_clock_hz() / 16u);
    } else {
        uart_puts("VLS start ");
        uart_putu(VLS_SEL_BASE + only);
        uart_putc('\n');
#ifdef ONLY_LIB
        if (only != ONLY_LIB) {          /* not this image's library */
            uart_puts("VLS error not in image\n");
            uart_commands(0);
        }
#endif
        if (!uart_go(board_clock_hz() / 16u)) uart_commands(0);   /* bad: not run */
        uart_flush();                    /* then silent until the library is done */
    }
#endif
    if (only == MP_NIDX) params_from_host();   /* the debug-port way, as before */
    mode = prm[P_MODE];
#if COVERAGE
    if (only != MP_NIDX) {               /* serial port: the run parameters */
        vl_cov.aim = prm[P_COV_AIM];
        vl_cov.window = prm[P_COV_WINDOW];
        vl_cov.aim_seed = prm[P_COV_SEED];
        vl_cov.off = prm[P_COV_OFF];
    }
    vl_cov.magic = COV_MAGIC;
    vl_cov.n = COV_N;
    aim_init();
#endif
    rng_main = prm[P_MAIN_SEED];
    rng_a = prm[P_SEED_A];
    rng_b = prm[P_SEED_B];
    const uint32_t nlibs = mode == 1u ? NLIBS_MPSC : NLIBS_SPMC;

    results.magic = RESULT_MAGIC;
    results.mode = mode | (SMP_MODE ? 0x100u : 0u);      /* + 0x100: roles on two cores */
    results.transfers = prm[P_TRANSFERS];
    results.nlibs = nlibs;
    results.board_id = BOARD_ID;
    results.clock_hz = board_clock_hz();
    results.timer_prescaler = prm[P_PRESCALER];
    results.main_seed = prm[P_MAIN_SEED];
    results.seed_a = prm[P_SEED_A];
    results.seed_b = prm[P_SEED_B];
    extern uint32_t _sramtext, _eramtext;
    results.code_in_sram = (&_eramtext != &_sramtext);

    static const rb_adapter *const libs_mpsc[NLIBS_MPSC] = {
        &adapter_pxq_mpsc, &adapter_pxq_mpmc, &adapter_riot_tsrb,
        &adapter_wizard97_primask, &adapter_lockfree_mpmc, &adapter_heapless_mpmc,
        &adapter_pxq_mpsc_resv,
        MP_EXTRA_MPSC
        &adapter_jnk0le };
    static const rb_adapter *const libs_spmc[NLIBS_SPMC] = {
        &adapter_pxq_spmc, &adapter_pxq_mpmc, &adapter_riot_tsrb,
        &adapter_wizard97_primask, &adapter_lockfree_mpmc, &adapter_heapless_mpmc,
        &adapter_jnk0le };
    const rb_adapter *const *libs = mode == 1u ? libs_mpsc : libs_spmc;
    static const uint8_t idx_mpsc[NLIBS_MPSC] = MP_IDX_MPSC, idx_spmc[NLIBS_SPMC] = MP_IDX_SPMC;
    const uint8_t *idx = mode == 1u ? idx_mpsc : idx_spmc;
    for (uint32_t l = 0; l < nlibs; l++) {
        volatile struct libres *r = &results.lib[l];
        r->transferred = r->errors = r->first_error_at = r->first_error_got = r->first_error_want = 0;
        r->full_or_empty[0] = r->full_or_empty[1] = r->irqs[0] = r->irqs[1] = 0;
        r->moved[0] = r->moved[1] = r->mismatch = 0;
        if ((only != MP_NIDX && idx[l] != only) || !libs[l]) {   /* not selected, or not in this image */
            r->transferred = NOT_IN_IMAGE;
            continue;
        }
#ifdef ONLY_LIB
        if (idx[l] != ONLY_LIB) {        /* another library's image */
            r->transferred = NOT_IN_IMAGE;
            continue;
        }
#endif
        if (!libs[l]->push) {            /* not available on this core */
            r->transferred = NOT_AVAILABLE;
            continue;
        }
        run(libs[l], r);
    }
    results.done = 1;
#if HAVE_UART
    uart_puts("VLS done ");
    if (only == MP_NIDX) uart_puts("all"); else uart_putu(VLS_SEL_BASE + only);
    uart_putc('\n');
    uart_commands(0);
#endif
    board_idle();
}
