/* Negative control: a deliberately broken SPSC ring buffer.
 *   push publishes the new head BEFORE writing the data (a real bug: the
 *        consumer can read the slot before it is written);
 *   pop  publishes the new tail BEFORE reading the data (benign for one
 *        slot in a sacrificed-slot ring, see below).
 * The stress test must report errors for this adapter in the direction
 * main -> ISR (main is the buggy, preemptible producer); otherwise it cannot
 * detect such bugs at all. */
#include "bench.h"

/* BROKEN_WINDOW: extra delay (loop turns, a few cycles each) between
 * publishing the head and writing the data. 0 for the interrupt modes: an
 * interrupt that lands in the window stops the producer there, so even a
 * tiny window is caught. With the other side on a second core (smp) a
 * window of a few cycles is shorter than the consumer's own path from
 * reading the head to reading the slot, so it can never show; the smp
 * variant (BROKEN_WINDOW_SMP, adapter_broken_smp) has a wider window, and a
 * valid smp run then shows that an ordering bug with a window of that size
 * is caught. Until 2026-11-15 the window was chosen at build time
 * (SMP_MODE); with one image for every mode both variants are built and
 * main.c takes adapter_broken_smp when smp=1. The interrupt-mode functions
 * (window 0) compile to the same code as before. */
#ifndef BROKEN_WINDOW
#define BROKEN_WINDOW 0u
#endif
#ifndef BROKEN_WINDOW_SMP
#define BROKEN_WINDOW_SMP 16u
#endif
static inline __attribute__((always_inline)) void broken_window(uint32_t turns)
{
    if (turns)                           /* a constant: absent with 0 */
        for (volatile uint32_t i = 0; i < turns; i++) {}
}

static volatile uint16_t head, tail;
static volatile uint8_t buf[RB_SLOTS];
#define MASK (RB_SLOTS - 1)

BENCH_ALIGN static void broken_reset(void) { head = 0; tail = 0; }

static inline __attribute__((always_inline)) uint32_t push_body(uintptr_t v, uint32_t window)
{
    uint16_t h = head, next = (h + 1) & MASK;
    if (next == tail) return 0;
    head = next;                 /* BUG: published before the data is written */
    __asm volatile("nop\n nop\n nop\n nop" ::: "memory"); /* widen the window */
    broken_window(window);
    buf[h] = (uint8_t)v;
    return 1;
}
BENCH_ALIGN static uint32_t broken_push(uintptr_t v, uintptr_t unused)
{
    (void)unused;
    return push_body(v, BROKEN_WINDOW);
}
BENCH_ALIGN static uint32_t broken_push_smp(uintptr_t v, uintptr_t unused)
{
    (void)unused;
    return push_body(v, BROKEN_WINDOW_SMP);
}

BENCH_ALIGN static uint32_t broken_pop(uintptr_t p, uintptr_t unused)
{
    (void)unused;
    uint16_t t = tail;
    if (t == head) return 0;
    tail = (t + 1) & MASK;       /* releases the slot before it is read */
    /* Not actually harmful for a single slot in this design: with one slot
     * sacrificed, a full buffer has head = t - 1, so the producer can only
     * fill slot t - 1 and the buffer is full again before slot t can be
     * touched. Measured: 0 errors even with an ~800-cycle window. Kept to
     * document that; the producer-side bug in push is the real control. */
    __asm volatile("nop\n nop\n nop\n nop" ::: "memory");
    *(uint8_t *)p = buf[t];
    return 1;
}

/* Block variants with the same two bugs. Here releasing the slots before
 * reading them IS harmful: with n > 1 slots released at once, the producer
 * can refill slots t .. t+n-2 while they are still being read. */
static inline __attribute__((always_inline)) uint32_t push_n_body(uintptr_t p, uintptr_t n, uint32_t window)
{
    const uint8_t *s = (const uint8_t *)p;
    uint16_t h = head;
    uint32_t space = (uint32_t)((tail - h - 1) & MASK);
    if (n > space) n = space;
    head = (h + n) & MASK;       /* BUG: published before the data is written */
    broken_window(window);
    for (uint32_t k = 0; k < n; k++) buf[(h + k) & MASK] = s[k];
    return n;
}
BENCH_ALIGN static uint32_t broken_push_n(uintptr_t p, uintptr_t n) { return push_n_body(p, n, BROKEN_WINDOW); }
BENCH_ALIGN static uint32_t broken_push_n_smp(uintptr_t p, uintptr_t n) { return push_n_body(p, n, BROKEN_WINDOW_SMP); }

BENCH_ALIGN static uint32_t broken_pop_n(uintptr_t p, uintptr_t n)
{
    uint8_t *d = (uint8_t *)p;
    uint16_t t = tail;
    uint32_t avail = (uint32_t)((head - t) & MASK);
    if (n > avail) n = avail;
    tail = (t + n) & MASK;       /* BUG: slots released before they are read */
    for (uint32_t k = 0; k < n; k++) d[k] = buf[(t + k) & MASK];
    return n;
}

/* Zero-copy variants (DMA_MODE) with a common linear-block bug: the write
 * area runs to the end of the buffer without being limited by the free
 * space, so a nearly full buffer hands out slots that still hold unread data
 * (and the commit can move head past tail). The read side is correct. */
BENCH_ALIGN static uint32_t broken_dma_wr_acquire(uintptr_t pp, uintptr_t max)
{
    uint16_t h = head;
    uint32_t free_space = (uint32_t)((tail - h - 1) & MASK);
    uint32_t to_end = RB_SLOTS - h;
    uint32_t len = to_end;       /* BUG: should be min(to_end, free_space) */
    (void)free_space;
    if (len > max) len = (uint32_t)max;
    *(uint8_t **)pp = (uint8_t *)&buf[h];
    return len;
}
BENCH_ALIGN static uint32_t broken_dma_wr_commit(uintptr_t n, uintptr_t u)
{
    (void)u;
    head = (uint16_t)((head + n) & MASK);
    return (uint32_t)n;
}
BENCH_ALIGN static uint32_t broken_dma_rd_acquire(uintptr_t pp, uintptr_t max)
{
    uint16_t t = tail, h = head;
    uint32_t avail = (uint32_t)((h - t) & MASK);
    uint32_t to_end = RB_SLOTS - t;
    uint32_t len = avail < to_end ? avail : to_end;
    if (len > max) len = (uint32_t)max;
    *(const uint8_t **)pp = (const uint8_t *)&buf[t];
    return len;
}
BENCH_ALIGN static uint32_t broken_dma_rd_release(uintptr_t n, uintptr_t u)
{
    (void)u;
    tail = (uint16_t)((tail + n) & MASK);
    return (uint32_t)n;
}

const rb_adapter adapter_broken = { broken_reset, broken_push, broken_pop, broken_push_n, broken_pop_n, 0, 0,
                                    broken_dma_wr_acquire, broken_dma_wr_commit,
                                    broken_dma_rd_acquire, broken_dma_rd_release };
/* The same with the wider window, for smp (no zero-copy with smp) */
const rb_adapter adapter_broken_smp = { broken_reset, broken_push_smp, broken_pop, broken_push_n_smp, broken_pop_n, 0, 0,
                                        0, 0, 0, 0 };
