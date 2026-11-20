/* Mutants: more deliberately broken ring buffers, each with one bug class
 * that is common in hand-written interrupt ring buffers. Unlike "broken"
 * (the negative control, which must be caught for a run to count), the
 * mutants do not decide whether a run is valid: they measure which bug
 * classes each test mode catches (decode.py and summarize*.py report it).
 *
 *   count_nolock   head/tail plus a shared fill counter that both sides
 *                  change with a plain ++ / -- (read-modify-write): an
 *                  interrupt between the read and the write loses an
 *                  update. Can show in both directions.
 *   count_poplock  the same counter, but only push updates it with
 *                  interrupts masked; pop forgot the lock. Shows only when
 *                  main pops (isr_to_main).
 *   full_nowrap    sacrificed-slot ring whose full test forgets the index
 *                  wrap (h + 1 == tail instead of ((h + 1) & MASK) ==
 *                  tail): a full buffer with head at the last slot and
 *                  tail at 0 accepts one more byte, and then looks empty.
 *                  A sequential bug that needs the full state at that one
 *                  position.
 *   drain_reread   pop "drains" by setting tail to head when it took the
 *                  last byte, but reads head again for that: bytes pushed
 *                  in between are skipped. Shows only when main pops.
 *
 * All four use the single-byte API for push_n/pop_n (BENCH_DEFINE_LOOP_N)
 * except drain_reread, whose pop_n has the same bug for a block. No
 * zero-copy API: n/a in DMA mode. */
#include "bench.h"

#define MASK (RB_SLOTS - 1)

static inline uint32_t irq_save(void)
{
    uint32_t p;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(p) :: "memory");
    return p;
}
static inline void irq_restore(uint32_t p) { __asm volatile("msr primask, %0" :: "r"(p) : "memory"); }

/* ---- count_nolock ---- */
static volatile uint16_t cn_head, cn_tail, cn_count;
static volatile uint8_t cn_buf[RB_SLOTS];
BENCH_ALIGN static void cn_reset(void) { cn_head = cn_tail = cn_count = 0; }
BENCH_ALIGN static uint32_t cn_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    if (cn_count >= RB_SLOTS - 1) return 0;
    uint16_t h = cn_head;
    cn_buf[h] = (uint8_t)v;
    cn_head = (h + 1) & MASK;
    cn_count++;                          /* BUG: read-modify-write, shared with pop */
    return 1;
}
BENCH_ALIGN static uint32_t cn_pop(uintptr_t p, uintptr_t u)
{
    (void)u;
    if (cn_count == 0) return 0;
    uint16_t t = cn_tail;
    *(uint8_t *)p = cn_buf[t];
    cn_tail = (t + 1) & MASK;
    cn_count--;                          /* BUG: read-modify-write, shared with push */
    return 1;
}
BENCH_DEFINE_LOOP_N(cn)
const rb_adapter adapter_mut_count_nolock = { cn_reset, cn_push, cn_pop, cn_push_n, cn_pop_n, 0, 0, 0, 0, 0, 0 };

/* ---- count_poplock ---- */
static volatile uint16_t cp_head, cp_tail, cp_count;
static volatile uint8_t cp_buf[RB_SLOTS];
BENCH_ALIGN static void cp_reset(void) { cp_head = cp_tail = cp_count = 0; }
BENCH_ALIGN static uint32_t cp_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    if (cp_count >= RB_SLOTS - 1) return 0;
    uint16_t h = cp_head;
    cp_buf[h] = (uint8_t)v;
    cp_head = (h + 1) & MASK;
    uint32_t s = irq_save();
    cp_count++;                          /* correct: masked */
    irq_restore(s);
    return 1;
}
BENCH_ALIGN static uint32_t cp_pop(uintptr_t p, uintptr_t u)
{
    (void)u;
    if (cp_count == 0) return 0;
    uint16_t t = cp_tail;
    *(uint8_t *)p = cp_buf[t];
    cp_tail = (t + 1) & MASK;
    cp_count--;                          /* BUG: the lock is missing here */
    return 1;
}
BENCH_DEFINE_LOOP_N(cp)
const rb_adapter adapter_mut_count_poplock = { cp_reset, cp_push, cp_pop, cp_push_n, cp_pop_n, 0, 0, 0, 0, 0, 0 };

/* ---- full_nowrap ---- */
static volatile uint16_t fw_head, fw_tail;
static volatile uint8_t fw_buf[RB_SLOTS];
BENCH_ALIGN static void fw_reset(void) { fw_head = fw_tail = 0; }
BENCH_ALIGN static uint32_t fw_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    uint16_t h = fw_head;
    if ((uint16_t)(h + 1u) == fw_tail) return 0;   /* BUG: no "& MASK" */
    fw_buf[h] = (uint8_t)v;
    fw_head = (h + 1) & MASK;
    return 1;
}
BENCH_ALIGN static uint32_t fw_pop(uintptr_t p, uintptr_t u)
{
    (void)u;
    uint16_t t = fw_tail;
    if (t == fw_head) return 0;
    *(uint8_t *)p = fw_buf[t];
    fw_tail = (t + 1) & MASK;
    return 1;
}
BENCH_DEFINE_LOOP_N(fw)
const rb_adapter adapter_mut_full_nowrap = { fw_reset, fw_push, fw_pop, fw_push_n, fw_pop_n, 0, 0, 0, 0, 0, 0 };

/* ---- drain_reread ---- */
static volatile uint16_t dr_head, dr_tail;
static volatile uint8_t dr_buf[RB_SLOTS];
BENCH_ALIGN static void dr_reset(void) { dr_head = dr_tail = 0; }
BENCH_ALIGN static uint32_t dr_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    uint16_t h = dr_head, next = (h + 1) & MASK;
    if (next == dr_tail) return 0;
    dr_buf[h] = (uint8_t)v;
    dr_head = next;
    return 1;
}
BENCH_ALIGN static uint32_t dr_pop(uintptr_t p, uintptr_t u)
{
    (void)u;
    uint16_t t = dr_tail, h = dr_head;
    if (t == h) return 0;
    *(uint8_t *)p = dr_buf[t];
    uint16_t next = (t + 1) & MASK;
    dr_tail = (next == h) ? dr_head : next;        /* BUG: "drained", but head read again */
    return 1;
}
BENCH_ALIGN static uint32_t dr_push_n(uintptr_t p, uintptr_t n)
{
    const uint8_t *s = (const uint8_t *)p;
    uint32_t i = 0;
    while (i < n && dr_push(s[i], 0)) i++;
    return i;
}
BENCH_ALIGN static uint32_t dr_pop_n(uintptr_t p, uintptr_t n)
{
    uint8_t *d = (uint8_t *)p;
    uint16_t t = dr_tail, h = dr_head;
    uint32_t avail = (uint32_t)((h - t) & MASK);
    if (n > avail) n = avail;
    for (uint32_t k = 0; k < n; k++) d[k] = dr_buf[(t + k) & MASK];
    dr_tail = (n == avail) ? dr_head : (uint16_t)((t + n) & MASK);   /* BUG: as in pop */
    return n;
}
const rb_adapter adapter_mut_drain_reread = { dr_reset, dr_push, dr_pop, dr_push_n, dr_pop_n, 0, 0, 0, 0, 0, 0 };
