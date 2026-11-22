/* Adapter: MaJerle/lwrb, default configuration (C11 atomics enabled).
 * Single bytes go through lwrb_write_byte / lwrb_read_byte (new in v3.4.0,
 * the library's functions for one byte); blocks through lwrb_write /
 * lwrb_read. Up to v3.3.0 a single byte was lwrb_write / lwrb_read with a
 * length of 1. */
#include "lwrb/lwrb.h"
#include "bench.h"

static lwrb_t rb;
static uint8_t data[RB_SLOTS];

BENCH_ALIGN static void lwrb_bench_reset(void) { lwrb_init(&rb, data, sizeof data); }

BENCH_ALIGN static uint32_t lwrb_bench_push(uintptr_t v, uintptr_t unused)
{
    (void)unused;
    return lwrb_write_byte(&rb, (uint8_t)v);
}

BENCH_ALIGN static uint32_t lwrb_bench_pop(uintptr_t p, uintptr_t unused)
{
    (void)unused;
    return lwrb_read_byte(&rb, (uint8_t *)p);
}

BENCH_ALIGN static uint32_t lwrb_bench_push_n(uintptr_t p, uintptr_t n)
{
    return (uint32_t)lwrb_write(&rb, (const void *)p, n);
}

BENCH_ALIGN static uint32_t lwrb_bench_pop_n(uintptr_t p, uintptr_t n)
{
    return (uint32_t)lwrb_read(&rb, (void *)p, n);
}

/* Zero-copy: lwrb_get_linear_block_write_address/_length + lwrb_advance and
 * lwrb_get_linear_block_read_address/_length + lwrb_skip. */
BENCH_ALIGN static uint32_t lwrb_dma_wr_acquire(uintptr_t pp, uintptr_t max)
{
    lwrb_sz_t len = lwrb_get_linear_block_write_length(&rb);
    *(uint8_t **)pp = lwrb_get_linear_block_write_address(&rb);
    return (uint32_t)(len < max ? len : max);
}
BENCH_ALIGN static uint32_t lwrb_dma_wr_commit(uintptr_t n, uintptr_t u) { (void)u; return (uint32_t)lwrb_advance(&rb, n); }
BENCH_ALIGN static uint32_t lwrb_dma_rd_acquire(uintptr_t pp, uintptr_t max)
{
    lwrb_sz_t len = lwrb_get_linear_block_read_length(&rb);
    *(const uint8_t **)pp = lwrb_get_linear_block_read_address(&rb);
    return (uint32_t)(len < max ? len : max);
}
BENCH_ALIGN static uint32_t lwrb_dma_rd_release(uintptr_t n, uintptr_t u) { (void)u; return (uint32_t)lwrb_skip(&rb, n); }

const rb_adapter adapter_lwrb = {
    lwrb_bench_reset, lwrb_bench_push, lwrb_bench_pop, lwrb_bench_push_n, lwrb_bench_pop_n, 0, 0,
    lwrb_dma_wr_acquire, lwrb_dma_wr_commit, lwrb_dma_rd_acquire, lwrb_dma_rd_release
};
