/* Adapter: hathach/tinyusb tu_fifo (src/common/tusb_fifo.c), release 0.21.0,
 * byte items, not overwritable (lossless SPSC). The header documents it as
 * safe for one writer and one reader, e.g. an ISR and the main loop, with no
 * mutex when there is no RTOS (OSAL_MUTEX_REQUIRED 0, see
 * shims/tinyusb/tusb_config.h). The indices are volatile uint16_t; there are
 * no atomics. All RB_SLOTS bytes are usable (no slot is sacrificed).
 * Native block API: tu_fifo_write_n / tu_fifo_read_n. Zero-copy (DMA) API:
 * tu_fifo_get_write_info + tu_fifo_advance_write_pointer and
 * tu_fifo_get_read_info + tu_fifo_advance_read_pointer; the linear part of
 * the info is the contiguous area. */
/* osal/osal.h first, as tusb_fifo.c itself and tusb.h do: osal_none.h uses
 * the tu_fifo functions, so tusb_fifo.h on its own does not compile. */
#include "osal/osal.h"
#include "tusb_fifo.h"
#include "bench.h"

static tu_fifo_t ff;
static uint8_t data[RB_SLOTS];

BENCH_ALIGN static void tusb_reset(void) { tu_fifo_config(&ff, data, RB_SLOTS, false); }

BENCH_ALIGN static uint32_t tusb_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    uint8_t b = (uint8_t)v;
    return tu_fifo_write(&ff, &b);
}

BENCH_ALIGN static uint32_t tusb_pop(uintptr_t p, uintptr_t u)
{
    (void)u;
    return tu_fifo_read(&ff, (void *)p);
}

BENCH_ALIGN static uint32_t tusb_push_n(uintptr_t p, uintptr_t n)
{
    return tu_fifo_write_n(&ff, (const void *)p, (uint16_t)n);
}

BENCH_ALIGN static uint32_t tusb_pop_n(uintptr_t p, uintptr_t n)
{
    return tu_fifo_read_n(&ff, (void *)p, (uint16_t)n);
}

BENCH_ALIGN static uint32_t tusb_dma_wr_acquire(uintptr_t pp, uintptr_t max)
{
    tu_fifo_buffer_info_t info;
    tu_fifo_get_write_info(&ff, &info);
    *(uint8_t **)pp = info.linear.ptr;
    return info.linear.len < max ? info.linear.len : (uint32_t)max;
}
BENCH_ALIGN static uint32_t tusb_dma_wr_commit(uintptr_t n, uintptr_t u)
{
    (void)u;
    tu_fifo_advance_write_pointer(&ff, (uint16_t)n);
    return (uint32_t)n;
}
BENCH_ALIGN static uint32_t tusb_dma_rd_acquire(uintptr_t pp, uintptr_t max)
{
    tu_fifo_buffer_info_t info;
    tu_fifo_get_read_info(&ff, &info);
    *(const uint8_t **)pp = info.linear.ptr;
    return info.linear.len < max ? info.linear.len : (uint32_t)max;
}
BENCH_ALIGN static uint32_t tusb_dma_rd_release(uintptr_t n, uintptr_t u)
{
    (void)u;
    tu_fifo_advance_read_pointer(&ff, (uint16_t)n);
    return (uint32_t)n;
}

const rb_adapter adapter_tinyusb = { tusb_reset, tusb_push, tusb_pop, tusb_push_n, tusb_pop_n, 0, 0,
                                     tusb_dma_wr_acquire, tusb_dma_wr_commit,
                                     tusb_dma_rd_acquire, tusb_dma_rd_release };
