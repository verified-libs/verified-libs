/* Adapter: ece-mohammad/RingBuffer (Modules/ring_buffer), default config
 * (uint8_t items, uint32_t counters). Native block API: enPutItems/enGetItems. */
#include <stdint.h> /* ring_buffer.h uses uint8_t/uint32_t but does not include it */
#include "ring_buffer.h"
#include "bench.h"

static RingBuffer_t rb;
static RingBuffer_Item_t data[RB_SLOTS];

BENCH_ALIGN static void ece_reset(void) { RingBuffer_enInit(&rb, data, RB_SLOTS); }

BENCH_ALIGN static uint32_t ece_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    RingBuffer_Item_t item = (RingBuffer_Item_t)v;
    return RingBuffer_enPutItem(&rb, &item) == RING_BUFFER_ERROR_NONE;
}

BENCH_ALIGN static uint32_t ece_pop(uintptr_t p, uintptr_t u)
{
    (void)u;
    return RingBuffer_enGetItem(&rb, (RingBuffer_Item_t *)p) == RING_BUFFER_ERROR_NONE;
}

BENCH_ALIGN static uint32_t ece_push_n(uintptr_t p, uintptr_t n)
{
    RingBuffer_Counter_t done = 0;
    RingBuffer_enPutItems(&rb, (const RingBuffer_Item_t *)p, (RingBuffer_Counter_t)n, &done);
    return done;
}

BENCH_ALIGN static uint32_t ece_pop_n(uintptr_t p, uintptr_t n)
{
    RingBuffer_Counter_t done = 0;
    RingBuffer_enGetItems(&rb, (RingBuffer_Item_t *)p, (RingBuffer_Counter_t)n, &done);
    return done;
}

/* Zero-copy: RingBuffer_enBlockWriteAddress/Count + RingBuffer_enAdvance and
 * RingBuffer_enBlockReadAddress/Count + RingBuffer_enSkipItems. */
BENCH_ALIGN static uint32_t ece_dma_wr_acquire(uintptr_t pp, uintptr_t max)
{
    RingBuffer_Item_t *p = 0;
    RingBuffer_Counter_t len = 0;
    if (RingBuffer_enBlockWriteAddress(&rb, &p) != RING_BUFFER_ERROR_NONE) return 0;
    if (RingBuffer_enBlockWriteCount(&rb, &len) != RING_BUFFER_ERROR_NONE) return 0;
    *(uint8_t **)pp = p;
    return len < max ? len : (uint32_t)max;
}
BENCH_ALIGN static uint32_t ece_dma_wr_commit(uintptr_t n, uintptr_t u)
{
    (void)u;
    RingBuffer_Counter_t done = 0;
    RingBuffer_enAdvance(&rb, (RingBuffer_Counter_t)n, &done);
    return done;
}
BENCH_ALIGN static uint32_t ece_dma_rd_acquire(uintptr_t pp, uintptr_t max)
{
    RingBuffer_Item_t *p = 0;
    RingBuffer_Counter_t len = 0;
    if (RingBuffer_enBlockReadAddress(&rb, &p) != RING_BUFFER_ERROR_NONE) return 0;
    if (RingBuffer_enBlockReadCount(&rb, &len) != RING_BUFFER_ERROR_NONE) return 0;
    *(const uint8_t **)pp = p;
    return len < max ? len : (uint32_t)max;
}
BENCH_ALIGN static uint32_t ece_dma_rd_release(uintptr_t n, uintptr_t u)
{
    (void)u;
    RingBuffer_Counter_t done = 0;
    RingBuffer_enSkipItems(&rb, (RingBuffer_Counter_t)n, &done);
    return done;
}

const rb_adapter adapter_ece = { ece_reset, ece_push, ece_pop, ece_push_n, ece_pop_n, 0, 0,
                                 ece_dma_wr_acquire, ece_dma_wr_commit, ece_dma_rd_acquire, ece_dma_rd_release };
