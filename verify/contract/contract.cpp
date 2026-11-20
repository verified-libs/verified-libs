/* Contract check: is a ring buffer correct as an interrupt <-> main queue on
 * ONE core, for every point at which the interrupt can come?
 *
 * The one-core contract (pxq, lwrb without atomics, RIOT tsrb, ...: volatile
 * indices or interrupt masking instead of C/C++ atomics) is: an interrupt
 * handler runs to completion between two instructions of the main loop,
 * and everything is in program order. GenMC checks threads under the C/C++
 * memory model, where such code always has data races, so it cannot judge
 * this contract. Here the contract is executed instead:
 *
 * - main's call runs with the x86 trap flag set, so the CPU stops after
 *   every instruction (SIGTRAP); at the chosen instruction the signal
 *   handler makes the interrupt's call, which runs to completion there:
 *   exactly an interrupt on one core, at instruction granularity, on the
 *   library's own code (compiled for the host);
 * - interrupt masking (PRIMASK) is host_irq.h's flag: an interrupt point
 *   inside a masked section is held pending and taken right after the
 *   unmask, as on a Cortex-M;
 * - every start state of a small buffer (RB_SLOTS slots: every start
 *   position and every fill level), every interrupt point in main's call,
 *   and every pair of points for two interrupts in one call;
 * - the result (return values, bytes popped, what is left in the buffer,
 *   drained) must be the result of one of the orders in which the calls
 *   could have run one after the other (main's call before, between or
 *   after the interrupt's calls), and for single-byte calls also that of an
 *   ideal FIFO of the buffer's capacity (so a sequential bug fails too).
 *
 * What it does not check: what a compiler for the target makes of the code
 * (the hardware interrupt sweep in ../../firmware/nrf5340-rb-stress does),
 * and more than one core.
 *
 * Usage: contract [ADAPTER ...]   (default: all; exit 0 only if every
 * adapter gives its expected verdict: real libraries pass, controls fail)
 */
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <ucontext.h>
#include <string>
#include <vector>
#include "bench.h"
#include "host_irq.h"

extern "C" {
extern const rb_adapter adapter_pxq_h_mpsc, adapter_pxq_h_spmc, adapter_pxq_h_mpmc, adapter_pxq_h_mpscr;
extern const rb_adapter adapter_broken;
extern const rb_adapter adapter_mut_count_nolock, adapter_mut_count_poplock, adapter_mut_full_nowrap,
                        adapter_mut_drain_reread;
}

enum Kind { PUSH, POP, PUSHN, POPN, DMAW, DMAR };
struct Op { Kind k; uint8_t v; uint32_t n; };
/* Fixed size, no heap: run_op runs inside the signal handler too, where
 * malloc must not be called (main may be inside it). */
struct Res {
    uint32_t ret = 0, nd = 0;
    uint8_t data[RB_SLOTS * 2] = {0};   /* bytes popped */
    void add(uint8_t b) { if (nd < sizeof data) data[nd++] = b; }
    bool operator==(const Res &o) const { return ret == o.ret && nd == o.nd && !memcmp(data, o.data, nd); }
};
struct Outcome {
    Res main;
    std::vector<Res> isr;
    std::vector<uint8_t> left;   /* drained afterwards */
    bool operator==(const Outcome &o) const { return main == o.main && isr == o.isr && left == o.left; }
};

static const rb_adapter *ad;
static uint32_t cap;

static Res run_op(const Op &op, bool isr)
{
    Res r;
    uint8_t buf[RB_SLOTS * 2] = {0};
    switch (op.k) {
    case PUSH: r.ret = (isr && ad->isr_push ? ad->isr_push : ad->push)(op.v, 0); break;
    case POP: {
        uint8_t b = 0;
        r.ret = (isr && ad->isr_pop ? ad->isr_pop : ad->pop)((uintptr_t)&b, 0);
        if (r.ret) r.add(b);
        break;
    }
    case PUSHN:
        for (uint32_t i = 0; i < op.n; i++) buf[i] = (uint8_t)(op.v + i);
        r.ret = ad->push_n((uintptr_t)buf, op.n);
        break;
    case POPN:
        r.ret = ad->pop_n((uintptr_t)buf, op.n);
        for (uint32_t i = 0; i < r.ret && i < sizeof buf; i++) r.add(buf[i]);
        break;
    case DMAW: {   /* zero-copy write: acquire up to n, fill, commit what was granted */
        uint8_t *p = nullptr;
        uint32_t g = ad->dma_wr_acquire((uintptr_t)&p, op.n);
        for (uint32_t i = 0; i < g; i++) p[i] = (uint8_t)(op.v + i);
        r.ret = g ? ad->dma_wr_commit(g, 0) : 0;
        break;
    }
    case DMAR: {   /* zero-copy read: acquire up to n, read, release */
        const uint8_t *p = nullptr;
        uint32_t g = ad->dma_rd_acquire((uintptr_t)&p, op.n);
        for (uint32_t i = 0; i < g; i++) r.add(p[i]);
        r.ret = g ? ad->dma_rd_release(g, 0) : 0;
        break;
    }
    }
    return r;
}

/* ---- the interrupt at an instruction of main's call ---- */
extern "C" { volatile uint32_t vl_masked; }
static volatile int armed;
extern "C" { volatile int vl_in_isr; }
#define in_isr vl_in_isr
static volatile long step;
static long points[2];
static int npoints, nextp, nisr, isr_done;
static volatile int pending;
static Op isr_ops[2];
static Res isr_res[2];

static void fire()
{
    in_isr = 1;
    isr_res[isr_done] = run_op(isr_ops[isr_done], true);
    isr_done++;
    in_isr = 0;
}
/* The host's prebuilt Rust core refers to the unwinder's personality
 * routine; the crate is built with panic = abort and never unwinds. */
extern "C" void rust_eh_personality(void) {}
/* for the Rust adapters' critical section (rust-adapters/src/cs.rs, vl_host) */
extern "C" uint32_t vl_host_irq_save(void) { return host_irq_save(); }
extern "C" void vl_host_irq_restore(uint32_t p) { host_irq_restore(p); }
extern "C" void vl_irq_unmasked(void)
{
    while (pending && !vl_masked && !in_isr) { pending = pending - 1; fire(); }
}
static void on_trap(int, siginfo_t *, void *ucv)
{
    if (!armed || in_isr) return;
    if (!vl_masked) while (pending) { pending = pending - 1; fire(); }   /* taken at the unmask */
    step = step + 1;
    while (nextp < npoints && step >= points[nextp]) {
        nextp++;
        if (vl_masked) pending = pending + 1; else fire();
    }
    /* every interrupt placed (one held pending is taken at the unmask, in
     * host_irq_restore): no more single steps needed */
    if (npoints && nextp == npoints)
        ((ucontext_t *)ucv)->uc_mcontext.gregs[REG_EFL] &= ~0x100LL;
}
__attribute__((noinline)) static Res run_main(const Op &op)
{
    step = 0; nextp = 0; pending = 0; isr_done = 0; vl_masked = 0;
    armed = 1;
    __asm__ volatile("pushfq\n orq $0x100, (%%rsp)\n popfq" ::: "memory", "cc");
    Res r = run_op(op, false);
    __asm__ volatile("pushfq\n andq $~0x100, (%%rsp)\n popfq" ::: "memory", "cc");
    armed = 0;
    while (isr_done < nisr) fire();   /* points after the call: the interrupts come after it */
    return r;
}

/* ---- states and outcomes ---- */
static uint8_t seq_val;
static void setup(uint32_t pos, uint32_t fill)
{
    ad->reset();
    uint8_t b;
    /* every slot holds 0xEE first, so a slot read before it was written
     * shows (and not a value left from an earlier trial) */
    for (uint32_t i = 0; i < RB_SLOTS * 2 && ad->push(0xEE, 0); i++) {}
    while (ad->pop((uintptr_t)&b, 0)) {}
    ad->reset();
    for (uint32_t i = 0; i < RB_SLOTS * 2 && ad->push(0xEE, 0); i++) {}
    while (ad->pop((uintptr_t)&b, 0)) {}
    for (uint32_t i = 0; i < pos; i++) { ad->push(0xEE, 0); ad->pop((uintptr_t)&b, 0); }
    seq_val = 1;
    for (uint32_t i = 0; i < fill; i++) ad->push(seq_val++, 0);
}
static std::vector<uint8_t> drain()
{
    std::vector<uint8_t> v;
    uint8_t b;
    while (v.size() < RB_SLOTS * 2 && ad->pop((uintptr_t)&b, 0)) v.push_back(b);
    return v;
}
/* The sequential outcomes: main's call at position m among the interrupts'. */
static std::vector<Outcome> sequential(uint32_t pos, uint32_t fill, const Op &mop)
{
    std::vector<Outcome> outs;
    for (int m = 0; m <= nisr; m++) {
        setup(pos, fill);
        Outcome o;
        o.isr.resize(nisr);
        for (int i = 0; i < nisr; i++) {
            if (i == m) o.main = run_op(mop, false);
            o.isr[i] = run_op(isr_ops[i], true);
        }
        if (m == nisr) o.main = run_op(mop, false);
        o.left = drain();
        outs.push_back(o);
    }
    /* A block call need not be atomic: its bytes may become visible (or be
     * taken) one after the other, as from a loop over single calls. So also
     * every split of main's block, with the interrupt's call between the two
     * parts (the second part only if the first moved all its bytes, as a
     * loop stops at the first byte that does not fit or is not there). */
    if ((mop.k == PUSHN || mop.k == POPN) && nisr == 1)
        for (uint32_t j = 1; j < mop.n; j++) {
            setup(pos, fill);
            Outcome o;
            o.isr.resize(1);
            Op a = mop, b = mop;
            a.n = j;
            b.n = mop.n - j;
            b.v = (uint8_t)(mop.v + j);
            Res r1 = run_op(a, false);
            o.isr[0] = run_op(isr_ops[0], true);
            o.main = r1;
            if (r1.ret == j) {
                Res r2 = run_op(b, false);
                o.main.ret += r2.ret;
                for (uint32_t i = 0; i < r2.nd; i++) o.main.add(r2.data[i]);
            }
            o.left = drain();
            outs.push_back(o);
        }
    return outs;
}
/* The same on an ideal FIFO of capacity cap (single-byte calls only). */
static std::vector<Outcome> ideal(uint32_t fill, const Op &mop)
{
    std::vector<Outcome> outs;
    auto apply = [](std::vector<uint8_t> &q, const Op &op) {
        Res r;
        if (op.k == PUSH) { if (q.size() < cap) { q.push_back(op.v); r.ret = 1; } }
        else if (!q.empty()) { r.ret = 1; r.add(q.front()); q.erase(q.begin()); }
        return r;
    };
    for (int m = 0; m <= nisr; m++) {
        std::vector<uint8_t> q;
        for (uint32_t i = 0; i < fill; i++) q.push_back((uint8_t)(1 + i));
        Outcome o;
        o.isr.resize(nisr);
        for (int i = 0; i < nisr; i++) {
            if (i == m) o.main = apply(q, mop);
            o.isr[i] = apply(q, isr_ops[i]);
        }
        if (m == nisr) o.main = apply(q, mop);
        o.left = q;
        outs.push_back(o);
    }
    return outs;
}

struct Scenario { const char *name; Op main; std::vector<Op> isr; };
static long trials, failures;
static std::string first_failure;

static bool no_ideal;
static void check(const Scenario &sc, bool double_points)
{
    nisr = (int)sc.isr.size();
    for (int i = 0; i < nisr; i++) isr_ops[i] = sc.isr[i];
    bool single_byte = sc.main.k <= POP && !no_ideal;
    for (int i = 0; i < nisr; i++) single_byte = single_byte && sc.isr[i].k <= POP;
    /* Two interrupts in one call: every pair of points is quadratic in the
     * call's length, so only the states where the races of ring buffers sit:
     * start position 0 and the last slot (the wrap), fill empty, 1, full - 1
     * and full. One interrupt: every state. */
    auto wanted = [&](uint32_t pos, uint32_t fill) {
        if (nisr < 2) return true;
        return (pos == 0 || pos == RB_SLOTS - 1) && (fill <= 1 || fill + 1 >= cap);
    };
    for (uint32_t pos = 0; pos < RB_SLOTS; pos++)
        for (uint32_t fill = 0; fill <= cap; fill++) {
            if (!wanted(pos, fill)) continue;
            auto seq = sequential(pos, fill, sc.main);
            auto idl = single_byte ? ideal(fill, sc.main) : std::vector<Outcome>();
            /* steps of main's call without an interrupt */
            setup(pos, fill);
            npoints = 0;
            int keep = nisr; nisr = 0;
            run_main(sc.main);
            nisr = keep;
            long n = step + 2;
            auto one = [&](long a, long b) {
                setup(pos, fill);
                npoints = nisr;
                points[0] = a; points[1] = b;
                Outcome o;
                o.isr.resize(nisr);
                o.main = run_main(sc.main);
                for (int i = 0; i < nisr; i++) o.isr[i] = isr_res[i];
                o.left = drain();
                trials++;
                bool ok = false;
                for (auto &s : seq) ok = ok || o == s;
                bool ok_ideal = !single_byte;
                for (auto &s : idl) ok_ideal = ok_ideal || o == s;
                if (!ok || !ok_ideal) {
                    if (failures++ == 0) {
                        char buf[200];
                        snprintf(buf, sizeof buf, "%s: start position %u, fill %u, interrupt at instruction %ld%s%ld: %s",
                                 sc.name, pos, fill, a, nisr > 1 ? " and " : "", nisr > 1 ? b : 0L,
                                 ok ? "not what an ideal FIFO gives (sequential bug)" : "no order of the calls gives this result");
                        first_failure = buf;
                        if (getenv("CONTRACT_VERBOSE")) {
                            auto show = [](const char *what, const Outcome &x) {
                                fprintf(stderr, "    %s: main ret %u data [", what, x.main.ret);
                                for (uint32_t i = 0; i < x.main.nd; i++) fprintf(stderr, " %02x", x.main.data[i]);
                                fprintf(stderr, " ]");
                                for (auto &r : x.isr) {
                                    fprintf(stderr, "  isr ret %u [", r.ret);
                                    for (uint32_t i = 0; i < r.nd; i++) fprintf(stderr, " %02x", r.data[i]);
                                    fprintf(stderr, " ]");
                                }
                                fprintf(stderr, "  left [");
                                for (auto b : x.left) fprintf(stderr, " %02x", b);
                                fprintf(stderr, " ]\n");
                            };
                            fprintf(stderr, "%s\n", buf);
                            show("got     ", o);
                            for (auto &r : seq) show("allowed ", r);
                        }
                    }
                }
            };
            if (nisr == 1) for (long a = 1; a <= n; a++) one(a, 0);
            else if (double_points) { for (long a = 1; a <= n; a++) for (long b = a; b <= n + 40; b++) one(a, b); }
        }
}

/* expect: 1 pass, 0 fail, -1 none (unsafe by its own documentation: reported only) */
/* no_ideal: a push may be refused while there is room (bbqueue: a grant
 * must be contiguous), so the ideal-FIFO comparison does not apply; the
 * library's own sequential results (linearisability) still do. */
struct Target { const char *name; const rb_adapter *a; const char *kind; int expect; bool no_ideal = false; };
static const Target targets[] = {
    { "pxq SPSC", &adapter_pxq, "spsc", 1 },
    { "lwrb", &adapter_lwrb, "spsc", 1 },
    { "AndersKaloer Ring-Buffer", &adapter_anders, "spsc", 1 },
    { "jnk0le Ringbuffer", &adapter_jnk0le, "spsc", 1 },
    { "ETL queue_spsc_isr", &adapter_etl_isr, "spsc", 1 },
    { "ETL queue_spsc_atomic", &adapter_etl_atomic, "spsc", 1 },
    { "ETL queue_spsc_locked", &adapter_etl_locked, "spsc", 1 },
    { "QuantumLeaps LFRB", &adapter_qp_lfrb, "spsc", 1 },
    { "EmbeddedArtistry cbuf threadsafe", &adapter_ea_cbuf, "spsc", 1 },
    { "ece-mohammad RingBuffer", &adapter_ece, "spsc", 1 },
    { "micoring SPSC mode", &adapter_micoring, "spsc", 1 },
    { "kostyk348 lf_spsc", &adapter_kostyk, "spsc", 1 },
    { "diffstorm cb", &adapter_diffstorm, "spsc", 1 },
    { "RIOT tsrb", &adapter_riot_tsrb, "spsc", 1 },
    { "Contiki-NG ringbuf", &adapter_contiki, "spsc", 1 },
    { "rigtorp SPSCQueue", &adapter_rigtorp, "spsc", 1 },
    { "wizard97 as shipped", &adapter_wizard97_plain, "spsc", -1 },
    { "wizard97 + PRIMASK macros", &adapter_wizard97_primask, "spsc", 1 },
    { "polycratia spscring", &adapter_polycratia, "spsc", 1 },
    { "rt-spsc", &adapter_rtspsc, "spsc", 1 },
    { "TinyUSB tu_fifo", &adapter_tinyusb, "spsc", 1 },
    { "Zephyr ring_buf", &adapter_zephyr, "spsc", 1 },
    { "Zephyr ring_buf, CONFIG_SMP", &adapter_zephyr_smp, "spsc", 1 },
    { "DNedic lockfree spsc::RingBuf", &adapter_lockfree, "spsc", 1 },
    { "FreeRTOS stream buffer", &adapter_freertos_sb, "spsc", 1 },
    { "NuttX circbuf", &adapter_nuttx_circbuf, "spsc", 1 },
    { "Arduino RingBufferN as shipped", &adapter_arduino_plain, "spsc", -1 },
    { "Arduino SafeRingBufferN", &adapter_arduino_safe, "spsc", 1 },
    { "RT-Thread rt_ringbuffer, no lock", &adapter_rtthread_plain, "spsc", -1 },
    { "RT-Thread rt_ringbuffer + interrupt lock", &adapter_rtthread_locked, "spsc", 1 },
    { "Mbed CE CircularBuffer", &adapter_mbed_cb, "spsc", 1 },
    { "moodycamel ReaderWriterQueue", &adapter_moodycamel, "spsc", 1 },
    { "heapless spsc::Queue (Rust)", &adapter_heapless, "spsc", 1 },
    { "bbqueue (Rust)", &adapter_bbqueue, "spsc", 1, true },
    { "embassy-sync Pipe (Rust)", &adapter_embassy_pipe, "spsc", 1 },
    { "heapless mpmc::Queue (Rust)", &adapter_heapless_mpmc, "mpmc", 1 },
    { "pxq MPSC", &adapter_pxq_h_mpsc, "mpsc", 1 },
    { "pxq SPMC", &adapter_pxq_h_spmc, "spmc", 1 },
    { "pxq MPMC", &adapter_pxq_h_mpmc, "mpmc", 1 },
    { "pxq MPSC reserve/commit", &adapter_pxq_h_mpscr, "mpsc", 1 },
    { "control: broken", &adapter_broken, "spsc", 0 },
    { "mutant: count_nolock", &adapter_mut_count_nolock, "spsc", 0 },
    { "mutant: count_poplock", &adapter_mut_count_poplock, "spsc", 0 },
    { "mutant: full_nowrap", &adapter_mut_full_nowrap, "spsc", 0 },
    { "mutant: drain_reread", &adapter_mut_drain_reread, "spsc", 0 },
};

static std::vector<Scenario> scenarios(const std::string &kind)
{
    const Op push{PUSH, 0xA0, 0}, pop{POP, 0, 0};
    const Op ipush{PUSH, 0xB0, 0}, ipush2{PUSH, 0xB1, 0}, ipop{POP, 0, 0};
    const Op pushn{PUSHN, 0xC0, 3}, popn{POPN, 0, 3}, ipushn{PUSHN, 0xD0, 2}, ipopn{POPN, 0, 2};
    std::vector<Scenario> s;
    /* SPSC both ways (every configuration has one producer and one consumer case) */
    s.push_back({"main push / interrupt pop", push, {ipop}});
    s.push_back({"main pop / interrupt push", pop, {ipush}});
    s.push_back({"main push / two interrupt pops", push, {ipop, ipop}});
    s.push_back({"main pop / two interrupt pushes", pop, {ipush, ipush2}});
    s.push_back({"main push_n(3) / interrupt pop_n(2)", pushn, {ipopn}});
    s.push_back({"main pop_n(3) / interrupt push_n(2)", popn, {ipushn}});
    if (ad->dma_wr_acquire) {   /* zero-copy API: a call in several steps */
        const Op dw{DMAW, 0xE0, 3}, dr{DMAR, 0, 3}, idw{DMAW, 0xF0, 2}, idr{DMAR, 0, 2};
        s.push_back({"main zero-copy write(3) / interrupt pop", dw, {ipop}});
        s.push_back({"main zero-copy read(3) / interrupt push", dr, {ipush}});
        s.push_back({"main pop / interrupt zero-copy write(2)", pop, {idw}});
        s.push_back({"main push / interrupt zero-copy read(2)", push, {idr}});
    }
    if (kind == "mpsc" || kind == "mpmc") {
        s.push_back({"main push / interrupt push", push, {ipush}});
        s.push_back({"main push / two interrupt pushes", push, {ipush, ipush2}});
        s.push_back({"main push_n(3) / interrupt push_n(2)", pushn, {ipushn}});
    }
    if (kind == "spmc" || kind == "mpmc") {
        s.push_back({"main pop / interrupt pop", pop, {ipop}});
        s.push_back({"main pop / two interrupt pops", pop, {ipop, ipop}});
        s.push_back({"main pop_n(3) / interrupt pop_n(2)", popn, {ipopn}});
    }
    return s;
}

int main(int argc, char **argv)
{
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_sigaction = on_trap;
    sa.sa_flags = SA_SIGINFO | SA_NODEFER;
    sigaction(SIGTRAP, &sa, nullptr);
    int bad = 0;
    for (const Target &t : targets) {
        if (argc > 1) {
            bool want = false;
            for (int i = 1; i < argc; i++) want = want || std::string(argv[i]) == t.name;
            if (!want) continue;
        }
        ad = t.a;
        no_ideal = t.no_ideal;
        ad->reset();
        cap = 0;
        while (cap < RB_SLOTS * 2 && ad->push(1, 0)) cap++;
        trials = failures = 0;
        first_failure.clear();
        const char *d = getenv("CONTRACT_DOUBLE");
        for (auto &sc : scenarios(t.kind)) check(sc, !d || strcmp(d, "0"));
        bool pass = failures == 0;
        bool as_expected = t.expect < 0 || pass == (t.expect == 1);
        if (!as_expected) bad++;
        printf("%-42s capacity %3u  %9ld trials  %s%s%s\n", t.name, cap, trials,
               pass ? "pass" : "FAIL", t.expect < 0 ? "  (not ISR-safe by its own documentation)" : as_expected ? "" : "  <-- NOT AS EXPECTED",
               pass ? "" : ("\n    first: " + first_failure).c_str());
        fflush(stdout);
    }
    return bad ? 1 : 0;
}
