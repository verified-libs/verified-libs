/* Adapter: Nordic nRF5 SDK nrf_ringbuf (components/libraries/ringbuf, SDK
 * 17.1.1; nrf5-sdk.lock), with the SDK's nrf_atomic (LDREX/STREX). Licence:
 * Nordic 5-clause, use with Nordic chips only: built for the nRF5340 only
 * (SET=nordic). The SDK documents the buffer as thread-safe: a second
 * concurrent put (or get) returns NRF_ERROR_BUSY; one producer and one
 * consumer use separate flags and indices.
 * Its size must be a power of two and every slot is usable: RB_SLOTS bytes
 * (the other adapters: RB_SLOTS - 1).
 * Copying API: nrf_ringbuf_cpy_put / cpy_get. Zero-copy: nrf_ringbuf_alloc
 * + put, nrf_ringbuf_get + free (start = true each time). */
#include "nrf_ringbuf.h"
#include "bench.h"

NRF_RINGBUF_DEF(nrb, RB_SLOTS);

BENCH_ALIGN static void nrb_reset(void) { nrf_ringbuf_init(&nrb); }
BENCH_ALIGN static uint32_t nrb_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    uint8_t b = (uint8_t)v;
    size_t len = 1;
    return nrf_ringbuf_cpy_put(&nrb, &b, &len) == NRF_SUCCESS ? (uint32_t)len : 0u;
}
BENCH_ALIGN static uint32_t nrb_pop(uintptr_t p, uintptr_t u)
{
    (void)u;
    size_t len = 1;
    return nrf_ringbuf_cpy_get(&nrb, (uint8_t *)p, &len) == NRF_SUCCESS ? (uint32_t)len : 0u;
}
BENCH_ALIGN static uint32_t nrb_push_n(uintptr_t p, uintptr_t n)
{
    size_t len = n;
    return nrf_ringbuf_cpy_put(&nrb, (const uint8_t *)p, &len) == NRF_SUCCESS ? (uint32_t)len : 0u;
}
BENCH_ALIGN static uint32_t nrb_pop_n(uintptr_t p, uintptr_t n)
{
    size_t len = n;
    return nrf_ringbuf_cpy_get(&nrb, (uint8_t *)p, &len) == NRF_SUCCESS ? (uint32_t)len : 0u;
}
BENCH_ALIGN static uint32_t nrb_dma_wr_acquire(uintptr_t pp, uintptr_t max)
{
    size_t len = max;
    return nrf_ringbuf_alloc(&nrb, (uint8_t **)pp, &len, true) == NRF_SUCCESS ? (uint32_t)len : 0u;
}
BENCH_ALIGN static uint32_t nrb_dma_wr_commit(uintptr_t n, uintptr_t u)
{
    (void)u;
    return nrf_ringbuf_put(&nrb, n) == NRF_SUCCESS ? (uint32_t)n : 0u;
}
BENCH_ALIGN static uint32_t nrb_dma_rd_acquire(uintptr_t pp, uintptr_t max)
{
    size_t len = max;
    return nrf_ringbuf_get(&nrb, (uint8_t **)pp, &len, true) == NRF_SUCCESS ? (uint32_t)len : 0u;
}
BENCH_ALIGN static uint32_t nrb_dma_rd_release(uintptr_t n, uintptr_t u)
{
    (void)u;
    return nrf_ringbuf_free(&nrb, n) == NRF_SUCCESS ? (uint32_t)n : 0u;
}

const rb_adapter adapter_nrf_ringbuf = {
    nrb_reset, nrb_push, nrb_pop, nrb_push_n, nrb_pop_n, 0, 0,
    nrb_dma_wr_acquire, nrb_dma_wr_commit, nrb_dma_rd_acquire, nrb_dma_rd_release
};
