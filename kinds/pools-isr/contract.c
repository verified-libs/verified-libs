/* The concurrency check of the pools kind on the host: an interrupt at every
 * instruction of the main context's alloc or free, for every configuration
 * (site/content/method-pools.md, "Use from interrupts", "On the host").
 *
 * The method is the ring buffers' contract check (verify/contract) and the
 * pool prechecks' (verify/exclusive): main's call runs with the x86 trap
 * flag, so the CPU stops after every instruction (SIGTRAP); at instruction k
 * the signal handler makes the interrupt's calls, which run to completion
 * there, for every k until main's call ends first. "Interrupts off" is a flag
 * (pool_irq_disable/pool_irq_restore, pool.h, which ThreadX's host port, our
 * lwIP port and this directory's ARMCM_isr.h for CMSIS-RTX call): an
 * interrupt point while it is set is held pending and taken when it is
 * cleared, as on a Cortex-M. For CMSIS-RTX's LDREX/STREX variant
 * (contract_rtx_excl) an interrupt point inside a modelled LDREX or STREX is
 * taken right after it, and the interrupt clears the exclusive monitor on
 * entry and return (excl_host.h).
 *
 * The trial (verdict.h, the same code the board sweep judges with):
 *   start state  init, then all 32 blocks allocated and the blocks not held
 *                freed in a scattered order (k * 7 mod 32), so the free list
 *                is not in address order; HELD blocks stay allocated, each
 *                with a pattern of its own;
 *   main         alloc, or free of a block it holds;
 *   interrupt    alloc; free of a block it holds; alloc then free of that
 *                block; free then alloc; alloc, alloc;
 * and the verdict:
 *   - the answers are those of the calls one after the other, with main's call
 *     before, between or after the interrupt's calls: an alloc gives a block
 *     exactly when fewer than 32 are held at its place in that order, a block
 *     held by no one at that place (no block twice), in the region at the
 *     promised alignment; a free answers 1;
 *   - interrupts are on again after every call, the canaries are intact, and
 *     every block held at the end has its holder's pattern;
 *   - then every block is given back and exactly 32 allocs succeed, each a
 *     different block (none lost, none twice), and are given back.
 * A pool whose state a trial corrupted can lead a later call outside memory;
 * the check catches the signal, counts the trial as failed and goes on.
 *
 * The verdict per configuration is in the class of the plan's section 2:
 * within its documentation (must pass), ours (must pass), a control (must be
 * caught), or outside its documentation (reported, not judged).
 * Usage: contract [NAME...]   only the configurations whose name contains one
 * Exit 0 if every judged verdict is as expected. */
#define _GNU_SOURCE
#include <setjmp.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ucontext.h>
#include "pool.h"
#include "excl_host.h"
#include "verdict.h"

/* ---- the configurations ---- */
enum cls { WITHIN, OURS, CONTROL, OUTSIDE };
static const char *CLS[] = { "within its documentation", "ours", "control", "outside its documentation" };
typedef struct { const pool_adapter *ad; enum cls c; const char *name; } target;

#if RTX_EXCL
extern const pool_adapter adapter_cmsis_rtx;
static const target TARGETS[] = {
#if RTX_EXCL_BROKEN
    { &adapter_cmsis_rtx, CONTROL, "broken: CMSIS-RTX LDREX/STREX, STREX result ignored" },
#else
    { &adapter_cmsis_rtx, WITHIN, "CMSIS-RTX osRtxMemoryPool, LDREX/STREX (C)" },
#endif
};
#elif CAL_LOCK
/* C_Allocator with its interrupt-masking lock option ALLOC_LOCK_CMSIS_RTOS2, no kernel linked
 * (site/content/method-pools.md, "C_Allocator twice"): the library's LockGuard.cpp built against
 * ../pools/shims/host/cal_lock/cmsis_compiler.h, whose __get_PRIMASK, __disable_irq and __set_PRIMASK are this
 * check's interrupts-off flag. The control: the same build with __disable_irq doing nothing (CAL_LOCK_BROKEN). */
extern const pool_adapter adapter_c_allocator;
static const target TARGETS[] = {
#if CAL_LOCK_BROKEN
    { &adapter_c_allocator, CONTROL, "broken: C_Allocator, its lock's __disable_irq does nothing" },
#else
    { &adapter_c_allocator, WITHIN, "C_Allocator fb_allocator, ALLOC_LOCK_CMSIS_RTOS2 (C)" },
#endif
};
#else
extern const pool_adapter adapter_ref, adapter_ref_primask, adapter_broken_isr_alloc, adapter_broken_isr_free;
extern const pool_adapter adapter_etl, adapter_riot, adapter_threadx, adapter_cmsis_rtx, adapter_contiki,
    adapter_c_allocator, adapter_memorypool, adapter_lwip;
#ifdef POOL_WITH_RUST
extern pool_adapter adapter_heapless, adapter_atomic_pool;
#endif
static const target TARGETS[] = {
    { &adapter_ref, CONTROL, 0 },
    { &adapter_broken_isr_alloc, CONTROL, 0 },
    { &adapter_broken_isr_free, CONTROL, 0 },
    { &adapter_ref_primask, OURS, 0 },
    { &adapter_etl, OUTSIDE, 0 },
    { &adapter_riot, OUTSIDE, 0 },
    { &adapter_threadx, WITHIN, 0 },
    { &adapter_cmsis_rtx, WITHIN, "CMSIS-RTX osRtxMemoryPool, interrupts off (C)" },
    { &adapter_contiki, OUTSIDE, 0 },
    { &adapter_c_allocator, OUTSIDE, 0 },
    { &adapter_lwip, WITHIN, 0 },
    { &adapter_memorypool, OUTSIDE, 0 },
#ifdef POOL_WITH_RUST
    { &adapter_heapless, WITHIN, "heapless pool, BoxPool (Rust; host: CAS)" },
    { &adapter_atomic_pool, WITHIN, "atomic-pool (Rust; host: x86 atomics)" },
#endif
};
#endif

/* ---- interrupts off, and the exclusive monitor ---- */
volatile int vl_excl_inside, vl_mon_exclusive, vl_excl_clear_on_exception = 1;
volatile uintptr_t vl_mon_addr;
static volatile unsigned vl_masked;
static volatile int in_isr, armed, pending, fired, fired_inside, main_running;
static volatile long step, point;
static void fire(void);

unsigned pool_irq_disable(void)
{
    unsigned was = vl_masked;
    vl_masked = 1;
    __asm__ volatile("" ::: "memory");
    return was;
}
unsigned pool_irq_state(void) { return vl_masked; }   /* PRIMASK, for ARMCM_isr.h */
static void take_pending(void)
{
    /* pending is cleared inside fire(), after in_isr is set: a trap between the
     * test and the call then finds the interrupt still pending (and in_isr
     * once it runs) and does not fire it a second time */
    if (pending && !vl_masked && !in_isr && !vl_excl_inside) fire();
}
void pool_irq_restore(unsigned was)
{
    __asm__ volatile("" ::: "memory");
    vl_masked = was;
    if (!was) take_pending();
}
void vl_excl_after(void) { take_pending(); }

/* ---- the interrupt at an instruction of main's call ---- */
static void fire(void)
{
    in_isr = 1;
    pending = 0;
    fired_inside = main_running;
    vl_excl_exception();                    /* exception entry clears the monitor */
    uintptr_t got = 0;
    for (int i = 0; i < isr_seq->n; i++) {
        if (isr_seq->op[i] == OP_A) {
            got = isr_ret[i] = ad->alloc(0, 0);
            if (got && in_region(got)) fill(got);
        } else {
            uintptr_t b = i ? got : isr_blk;   /* "alloc, free it" frees what it got */
            isr_arg[i] = b;
            isr_ret[i] = b ? ad->free(b, 0) : 1;
        }
        if (vl_masked) masked_after_isr = 1;
    }
    vl_excl_exception();                    /* and exception return */
    fired = 1;
    in_isr = 0;
}

static void on_trap(int sig, siginfo_t *si, void *ucv)
{
    (void)sig; (void)si;
    if (!armed || in_isr) return;
    step = step + 1;
    if (!fired && !pending && point && step >= point) {   /* fire() sets in_isr at its start, fired at its end */
        if (vl_masked || vl_excl_inside) pending = 1;
        else fire();
    }
    if (fired)   /* the interrupt is placed: no more single steps needed */
        ((ucontext_t *)ucv)->uc_mcontext.gregs[REG_EFL] &= ~0x100LL;
}

__attribute__((noinline)) static void run_main(void)
{
    step = 0; pending = 0; fired = 0; fired_inside = 0; vl_masked = 0;
    masked_after_isr = masked_after_main = 0;
    isr_ret[0] = isr_ret[1] = isr_arg[0] = isr_arg[1] = 0;
    armed = 1; main_running = 1;
    __asm__ volatile("pushfq\n orq $0x100, (%%rsp)\n popfq" ::: "memory", "cc");
    if (main_op == OP_A) main_ret = ad->alloc(0, 0);
    else main_ret = ad->free(main_blk, 0);
    __asm__ volatile("pushfq\n andq $~0x100, (%%rsp)\n popfq" ::: "memory", "cc");
    main_running = 0; armed = 0;
    if (vl_masked) masked_after_main = 1;
    if (main_op == OP_A && main_ret && in_region(main_ret)) fill(main_ret);
    if (point && !fired) fire();   /* a point after the call: the interrupt comes after it */
}

/* ---- a crash is a failed trial ---- */
static sigjmp_buf crash_env;
static volatile int crash_armed;
static void on_crash(int sig, siginfo_t *si, void *ucv)
{
    (void)si; (void)ucv;
    if (crash_armed) { crash_armed = 0; siglongjmp(crash_env, sig); }
    signal(sig, SIG_DFL);
    raise(sig);
}
static void after_crash(void)
{
    __asm__ volatile("pushfq\n andq $~0x100, (%%rsp)\n popfq" ::: "memory", "cc");
    armed = 0; in_isr = 0; main_running = 0; pending = 0; vl_masked = 0; vl_excl_inside = 0; vl_mon_exclusive = 0;
}

/* ---- the cases ---- */
static long trials, inside, failures, fault_count[NPF];
static char first_failure[800];

/* One trial: the start state, then main's call with the interrupt at point
 * pt (0: none); its verdict, PF_CRASH if it crashed. */
static enum fault trial(uint32_t h, int need_main, int need_isr, const seq *sq, long pt)
{
    enum fault f;
    if (sigsetjmp(crash_env, 1) != 0) {
        after_crash();
        return PF_CRASH;
    }
    crash_armed = 1;
    isr_seq = &NO_ISR;
    f = setup(h, 0);
    if (f == PF_OK) {
        /* after every setup: a pool's init need not give the same blocks in the same order (heapless's does not) */
        who_frees(need_main, need_isr);
        isr_seq = sq;
        point = pt;
        run_main();
        f = verdict();
    }
    crash_armed = 0;
    return f;
}

static void check_case(uint32_t h, int mop, const seq *sq)
{
    main_op = mop;
    int need_main = mop == OP_F, need_isr = sq->op[0] == OP_F;
    if (h < (uint32_t)(need_main + need_isr)) return;
    const char *mt = mop == OP_A ? "alloc" : "free";
    /* the steps of main's call without an interrupt */
    enum fault f = trial(h, need_main, need_isr, &NO_ISR, 0);
    long n = step;
    if (f != PF_OK) {
        fault_count[f]++;
        if (failures++ == 0) snprintf(first_failure, sizeof first_failure, "%u held, main %s alone: %s", h, mt, FAULT_TEXT[f]);
        return;
    }
    for (long k = 1; k <= n + 1; k++) {
        f = trial(h, need_main, need_isr, sq, k);
        trials++;
        inside += fired_inside;
        if (f != PF_OK) {   /* the pool may now be in any state: the next setup starts from init */
            fault_count[f]++;
            if (failures++ == 0)
                snprintf(first_failure, sizeof first_failure, "%u held, main %s, interrupt \"%s\" at instruction %ld of %ld: %s",
                         h, mt, sq->text, k, n, FAULT_TEXT[f]);
        }
    }
}

int main(int argc, char **argv)
{
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_sigaction = on_trap;
    sa.sa_flags = SA_SIGINFO | SA_NODEFER;
    sigaction(SIGTRAP, &sa, NULL);
    sa.sa_sigaction = on_crash;
    sigaction(SIGSEGV, &sa, NULL);
    sigaction(SIGBUS, &sa, NULL);
    int bad_n = 0;
    for (size_t t = 0; t < sizeof TARGETS / sizeof TARGETS[0]; t++) {
        ad = TARGETS[t].ad;
        const char *name = TARGETS[t].name ? TARGETS[t].name : ad->name;
        if (argc > 1) {   /* only the configurations whose name contains an argument */
            int want = 0;
            for (int i = 1; i < argc; i++) want |= strstr(name, argv[i]) != 0;
            if (!want) continue;
        }
        ad->init();
        trials = inside = failures = 0;
        memset(fault_count, 0, sizeof fault_count);
        first_failure[0] = 0;
        for (uint32_t h = 0; h < NHELD; h++)
            for (int mop = OP_A; mop <= OP_F; mop++)
                for (size_t s = 0; s < NSEQ; s++)
                    check_case(HELD[h], mop, &ISR_SEQS[s]);
        enum cls c = TARGETS[t].c;
        int pass = failures == 0;
        int as_expected = c == OUTSIDE || pass == (c != CONTROL);
        if (!as_expected) bad_n++;
        /* the verdict words by class: a control is caught or not; a library outside its documentation gets no
         * verdict word, only what was observed (it was used in a way it does not document) */
        const char *word = c == CONTROL ? (pass ? "NOT CAUGHT" : "caught") : c == OUTSIDE ? (pass ? "nothing observed" : "observed")
                                                                        : (pass ? "pass" : "FAIL");
        printf("%-50s %-26s %8ld trials, %7ld inside  %s%s\n", name, CLS[c], trials, inside, word,
               as_expected ? "" : "  <-- NOT AS EXPECTED");
        if (!pass) {
            printf("    in %ld trials; first: %s\n    by kind:", failures, first_failure);
            for (int i = 1; i < NPF; i++) if (fault_count[i]) printf(" %s: %ld;", FAULT_TEXT[i], fault_count[i]);
            printf("\n");
        }
        fflush(stdout);
    }
    printf("exit %d: %s\n", bad_n ? 1 : 0, bad_n ? "a verdict not as expected" : "every judged verdict as expected");
    return bad_n ? 1 : 0;
}
