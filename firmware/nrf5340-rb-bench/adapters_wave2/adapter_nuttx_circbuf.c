/* Adapter: Apache NuttX circbuf (libs/libc/misc/lib_circbuf.c,
 * include/nuttx/circbuf.h; nuttx-13.1.0), built outside NuttX with the
 * minimal shims in ../shims/nuttx. NuttX documents: "There is no locking
 * required while only one reader and one writer is using the circular
 * buffer." circbuf has no reserved slot, so the buffer is RB_SLOTS - 1
 * bytes: the same usable capacity as the other adapters. (Its offsets are
 * counter % size, a division for any size.) Zero-copy:
 * circbuf_get_writeptr/writecommit, circbuf_get_readptr/readcommit. */
#include <nuttx/config.h>
#include <nuttx/circbuf.h>
#include "bench.h"

static struct circbuf_s ncb;
static uint8_t ndata[RB_SLOTS - 1];

BENCH_ALIGN static void nuttx_reset(void) { circbuf_init(&ncb, ndata, sizeof ndata); }
BENCH_ALIGN static uint32_t nuttx_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    uint8_t b = (uint8_t)v;
    return (uint32_t)circbuf_write(&ncb, &b, 1);
}
BENCH_ALIGN static uint32_t nuttx_pop(uintptr_t p, uintptr_t u) { (void)u; return (uint32_t)circbuf_read(&ncb, (void *)p, 1); }
BENCH_ALIGN static uint32_t nuttx_push_n(uintptr_t p, uintptr_t n) { return (uint32_t)circbuf_write(&ncb, (const void *)p, n); }
BENCH_ALIGN static uint32_t nuttx_pop_n(uintptr_t p, uintptr_t n) { return (uint32_t)circbuf_read(&ncb, (void *)p, n); }
BENCH_ALIGN static uint32_t nuttx_dma_wr_acquire(uintptr_t pp, uintptr_t max)
{
    size_t len;
    *(void **)pp = circbuf_get_writeptr(&ncb, &len);
    return len < max ? (uint32_t)len : (uint32_t)max;
}
BENCH_ALIGN static uint32_t nuttx_dma_wr_commit(uintptr_t n, uintptr_t u) { (void)u; circbuf_writecommit(&ncb, n); return (uint32_t)n; }
BENCH_ALIGN static uint32_t nuttx_dma_rd_acquire(uintptr_t pp, uintptr_t max)
{
    size_t len;
    *(void **)pp = circbuf_get_readptr(&ncb, &len);
    return len < max ? (uint32_t)len : (uint32_t)max;
}
BENCH_ALIGN static uint32_t nuttx_dma_rd_release(uintptr_t n, uintptr_t u) { (void)u; circbuf_readcommit(&ncb, n); return (uint32_t)n; }

const rb_adapter adapter_nuttx_circbuf = {
    nuttx_reset, nuttx_push, nuttx_pop, nuttx_push_n, nuttx_pop_n, 0, 0,
    nuttx_dma_wr_acquire, nuttx_dma_wr_commit, nuttx_dma_rd_acquire, nuttx_dma_rd_release
};
