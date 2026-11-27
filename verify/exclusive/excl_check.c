/* Check 2 of the pool pre-checks: can the one-core contract check (an
 * interrupt at every instruction, ../contract) judge code that uses LDREX and
 * STREX? A made-up lock-free free list (a stack of blocks, as CMSIS-RTX's pool
 * keeps its free blocks), its pop and push written in C with the model of the
 * exclusive monitor (excl_model.h), one statement per instruction of the
 * Cortex-M code they stand for, and variants the check must catch.
 *
 * The stack holds node numbers 1..NODES (0 = empty); next[] is the link a
 * block keeps in itself. Per trial: a start stack of 0..3 nodes, main's call
 * (pop, or push of a node it holds), and the interrupt's calls (pop; push of a
 * node it holds; pop, pop, push of the first one back: the A-B-A case), with
 * the interrupt at host instruction k of main's call, for every k until the
 * call ends first. Verdict per trial: every node is exactly once either in
 * the stack (a list that ends) or held by whoever popped it last, and every
 * pop returned a node that was in the stack. */
#define _GNU_SOURCE
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <ucontext.h>
#include "excl_model.h"

#define NODES 6u
volatile int vl_excl_inside, vl_mon_exclusive, vl_excl_clear_on_exception = 1;
volatile uintptr_t vl_mon_addr;
volatile int vl_excl_isr, vl_excl_fail_isr;
volatile unsigned vl_excl_strex_n, vl_excl_fail_nth;
static volatile uint32_t root, next[NODES + 1];

/* ---- the free list, as CMSIS-RTX's atomic_link_get / atomic_link_put ---- */
static uint32_t pop_excl(void)          /* atomic_link_get */
{
    uint32_t ret, val;
    for (;;) {
        ret = vl_ldrex(&root);          /* ldrex ret,[root] */
        if (ret == 0) { vl_clrex(); return 0; }   /* cbnz; clrex */
        val = next[ret];                /* ldr val,[ret] */
        if (vl_strex(val, &root) == 0) return ret;   /* strex; cbz */
    }
}
static void push_excl(uint32_t link)    /* atomic_link_put */
{
    uint32_t v1, v2;
    for (;;) {
        v1 = root;                      /* ldr val1,[root] */
        next[link] = v1;                /* str val1,[link] */
        __asm__ volatile("" ::: "memory");   /* dmb */
        v1 = vl_ldrex(&root);           /* ldrex val1,[root] */
        v2 = next[link];                /* ldr val2,[link] */
        if (v2 != v1) continue;         /* cmp; bne 1b */
        if (vl_strex(link, &root) == 0) return;   /* strex; cbz */
    }
}
/* broken: the same pop with plain loads and a plain store */
static uint32_t pop_plain(void)
{
    uint32_t ret = root;
    if (ret == 0) return 0;
    uint32_t val = next[ret];
    root = val;
    return ret;
}
/* broken: pop and push that ignore STREX's result (go on as if stored) */
static uint32_t pop_ignore(void)
{
    uint32_t ret = vl_ldrex(&root);
    if (ret == 0) { vl_clrex(); return 0; }
    (void)vl_strex(next[ret], &root);
    return ret;
}
static void push_ignore(uint32_t link)
{
    next[link] = vl_ldrex(&root);
    (void)vl_strex(link, &root);
}
/* an interrupt's calls with plain accesses: correct in an interrupt, which
 * nothing on this core preempts here (the interrupts-off path of a pool) */
static void push_plain(uint32_t link) { next[link] = root; root = link; }

/* ---- calls, variants ---- */
typedef enum { POP, PUSH } Kind;
typedef struct { Kind k; int arg; } Op;   /* arg of PUSH: index into the pusher's held list, -1: the node it popped first */
typedef struct {
    const char *name;
    uint32_t (*main_pop)(void); void (*main_push)(uint32_t);
    uint32_t (*isr_pop)(void); void (*isr_push)(uint32_t);
    int clear_on_exception, expect_pass;
    int spurious;   /* 1: also a STREX failing without a cause, at each of main's STREXes in turn, and the interrupt's */
} Variant;
static const Variant VARIANTS[] = {
    { "LDREX/STREX in main and interrupt", pop_excl, push_excl, pop_excl, push_excl, 1, 1, 0 },
    { "broken: main pops with plain accesses", pop_plain, push_excl, pop_excl, push_excl, 1, 0, 0 },
    { "LDREX/STREX in main, plain in interrupt", pop_excl, push_excl, pop_plain, push_plain, 1, 1, 0 },
    { "model control: the same, monitor kept at exception", pop_excl, push_excl, pop_plain, push_plain, 0, 0, 0 },
    { "LDREX/STREX everywhere, monitor kept at exception", pop_excl, push_excl, pop_excl, push_excl, 0, 1, 0 },
    { "LDREX/STREX, a STREX failing without a cause", pop_excl, push_excl, pop_excl, push_excl, 1, 1, 1 },
    { "broken: STREX's result ignored, STREX failing", pop_ignore, push_ignore, pop_excl, push_excl, 1, 0, 1 },
};
static const Variant *V;

/* who holds a node: 0 the stack (or nobody yet), 1 main, 2 the interrupt */
static int holder[NODES + 1];
static int bad;
static char why[160];
static uint32_t isr_first;

static void do_op(int who, Op op)
{
    if (op.k == POP) {
        uint32_t n = who == 1 ? V->main_pop() : V->isr_pop();
        if (n) {
            if (n > NODES || holder[n] != 0) { bad = 1; snprintf(why, sizeof why, "pop returned node %u, held by %d", n, n <= NODES ? holder[n] : -1); return; }
            holder[n] = who;
            if (who == 2 && !isr_first) isr_first = n;
        }
    } else {
        uint32_t n = op.arg < 0 ? isr_first : (uint32_t)op.arg;
        if (!n || holder[n] != who) return;   /* nothing to push back */
        holder[n] = 0;
        if (who == 1) V->main_push(n); else V->isr_push(n);
    }
}

/* ---- the interrupt at host instruction k of main's call ---- */
static volatile int armed, in_isr, pending, fired;
static volatile unsigned step, point;
static Op isr_ops[3];
static int n_isr;
static void fire(void)
{
    in_isr = 1;
    vl_excl_isr = 1;
    vl_excl_exception();                /* exception entry */
    for (int i = 0; i < n_isr; i++) do_op(2, isr_ops[i]);
    vl_excl_exception();                /* exception return */
    vl_excl_isr = 0;
    in_isr = 0;
    fired = 1;
}
void vl_excl_after(void)
{
    if (pending && !in_isr) { pending = 0; fire(); }
}
static void on_trap(int sig, siginfo_t *si, void *ucv)
{
    (void)sig; (void)si;
    if (!armed || in_isr || fired) return;
    step = step + 1;
    if (step == point) {
        if (vl_excl_inside) pending = 1; else fire();
    }
    if (fired) ((ucontext_t *)ucv)->uc_mcontext.gregs[REG_EFL] &= ~0x100LL;
}
__attribute__((noinline)) static void run_main(Op op)
{
    step = 0; pending = 0; fired = 0;
    armed = 1;
    __asm__ volatile("pushfq\n orq $0x100, (%%rsp)\n popfq" ::: "memory", "cc");
    do_op(1, op);
    __asm__ volatile("pushfq\n andq $~0x100, (%%rsp)\n popfq" ::: "memory", "cc");
    armed = 0;
}

static unsigned cur_depth;   /* nodes 1..cur_depth start in the stack; 4 is never used */
static void setup(unsigned depth)
{
    cur_depth = depth;
    root = 0;
    memset((void *)next, 0, sizeof next);
    memset(holder, 0, sizeof holder);
    for (unsigned n = depth; n >= 1; n--) { next[n] = root; root = n; }
    holder[5] = 1;   /* main holds node 5 */
    holder[6] = 2;   /* the interrupt holds node 6 */
    isr_first = 0; bad = 0; why[0] = 0;
    vl_mon_exclusive = 0;
}
static void verdict(void)
{
    if (bad) return;
    int seen[NODES + 1] = {0};
    uint32_t n = root;
    for (unsigned i = 0; n && i <= NODES; i++, n = next[n]) {
        if (n > NODES) { bad = 1; snprintf(why, sizeof why, "the stack links to node %u", n); return; }
        if (seen[n]++) { bad = 1; snprintf(why, sizeof why, "node %u twice in the stack (a cycle)", n); return; }
        if (holder[n]) { bad = 1; snprintf(why, sizeof why, "node %u in the stack and held by %d", n, holder[n]); return; }
    }
    if (n) { bad = 1; snprintf(why, sizeof why, "the stack does not end"); return; }
    for (unsigned i = 1; i <= NODES; i++)
        if (!seen[i] && !holder[i] && (i <= cur_depth || i >= 5)) {
            /* a node never in the stack and held by nobody: lost */
            bad = 1; snprintf(why, sizeof why, "node %u lost", i); return;
        }
}

int main(void)
{
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_sigaction = on_trap;
    sa.sa_flags = SA_SIGINFO;
    sigaction(SIGTRAP, &sa, NULL);
    static const Op MAIN_OPS[] = { { POP, 0 }, { PUSH, 5 } };
    static const Op ISR_SEQ[][3] = { { { POP, 0 } }, { { PUSH, 6 } }, { { POP, 0 }, { POP, 0 }, { PUSH, -1 } } };
    static const int ISR_LEN[] = { 1, 1, 3 };
    int all_ok = 1;
    for (unsigned v = 0; v < sizeof VARIANTS / sizeof VARIANTS[0]; v++) {
        V = &VARIANTS[v];
        vl_excl_clear_on_exception = V->clear_on_exception;
        unsigned trials = 0, failed = 0;
        char first[256] = "";
        for (unsigned depth = 0; depth <= 3; depth++)
            for (unsigned m = 0; m < 2; m++)
                for (unsigned s = 0; s < 3; s++) {
                    n_isr = ISR_LEN[s];
                    memcpy(isr_ops, ISR_SEQ[s], sizeof isr_ops);
                    for (point = 1;; point++) {
                        /* the STREX that fails without a cause: none; or main's 1st, 2nd, ... in turn
                         * (until main makes no more), then the interrupt's (spurious variants only) */
                        int any_inside = 0;
                        for (unsigned nth = 0, isr_fail = 0;;) {
                            setup(depth);
                            vl_excl_strex_n = 0; vl_excl_fail_nth = nth; vl_excl_fail_isr = (int)isr_fail;
                            run_main(MAIN_OPS[m]);
                            unsigned made = vl_excl_strex_n;
                            vl_excl_fail_nth = 0; vl_excl_fail_isr = 0;
                            int ended_first = !fired && !pending;
                            if (!ended_first) {
                                any_inside = 1;
                                verdict();
                                trials++;
                                if (bad) {
                                    failed++;
                                    if (!first[0])
                                        snprintf(first, sizeof first, "stack of %u, main %s, interrupt %s, at instruction %u%s: %s",
                                                 depth, m ? "push" : "pop", s == 0 ? "pop" : s == 1 ? "push" : "pop pop push",
                                                 point, isr_fail ? ", the interrupt's STREX failing" : nth ? ", a STREX of main failing" : "", why);
                                }
                            }
                            if (!V->spurious || isr_fail) break;
                            if (nth < made) nth++;       /* the next of main's STREXes */
                            else { nth = 0; isr_fail = 1; }
                        }
                        if (!any_inside) break;   /* the call ended before this point in every trial: every point done */
                    }
                }
        int passed = failed == 0;
        int as_expected = passed == V->expect_pass;
        all_ok &= as_expected;
        printf("%-52s %s (expected %s)%s  %u trials, %u failed%s%s\n", V->name, passed ? "pass" : "FAIL",
               V->expect_pass ? "pass" : "FAIL", as_expected ? "" : "  <-- NOT AS EXPECTED", trials, failed,
               first[0] ? "; first: " : "", first);
    }
    printf("%s\n", all_ok ? "exit 0: every verdict as expected" : "exit 1: a verdict not as expected");
    return all_ok ? 0 : 1;
}
