/* Adapter: Zephyr ring_buf (include/zephyr/sys/ring_buffer.h, v4.5.0; header
 * only), built outside Zephyr with the minimal shims in ../shims/zephyr.
 * Zephyr documents that one producer and one consumer in separate execution
 * contexts (e.g. a thread and an ISR) may use a ring buffer concurrently
 * without extra locking. Two builds of this file:
 *   default:                  Zephyr's single-core code (plain loads and
 *                             stores with compiler barriers)
 *   -DZEPHYR_RB_SMP=1:        as with CONFIG_SMP=y, CONFIG_MP_MAX_NUM_CPUS=2
 *                             (__atomic acquire/release on the indices)
 * Zephyr's capacity equals the size given to ring_buf_init (no reserved
 * slot), so the buffer is RB_SLOTS - 1 bytes: the same usable capacity as
 * the other adapters. Zero-copy: ring_buf_put_ptr/commit, get_ptr/consume. */
#if defined(ZEPHYR_RB_SMP) && ZEPHYR_RB_SMP
#define CONFIG_SMP 1
#define CONFIG_MP_MAX_NUM_CPUS 2
#define ZR(x) zephyr_smp_##x
#define ZR_ADAPTER adapter_zephyr_smp
#else
#define ZR(x) zephyr_##x
#define ZR_ADAPTER adapter_zephyr
#endif
#include <zephyr/sys/ring_buffer.h>
#include "bench.h"

static struct ring_buf zrb;
static uint8_t zdata[RB_SLOTS - 1];

BENCH_ALIGN static void ZR(reset)(void) { ring_buf_init(&zrb, sizeof zdata, zdata); }
BENCH_ALIGN static uint32_t ZR(push)(uintptr_t v, uintptr_t u)
{
    (void)u;
    uint8_t b = (uint8_t)v;
    return ring_buf_put(&zrb, &b, 1);
}
BENCH_ALIGN static uint32_t ZR(pop)(uintptr_t p, uintptr_t u) { (void)u; return ring_buf_get(&zrb, (uint8_t *)p, 1); }
BENCH_ALIGN static uint32_t ZR(push_n)(uintptr_t p, uintptr_t n) { return ring_buf_put(&zrb, (const uint8_t *)p, (uint32_t)n); }
BENCH_ALIGN static uint32_t ZR(pop_n)(uintptr_t p, uintptr_t n) { return ring_buf_get(&zrb, (uint8_t *)p, (uint32_t)n); }
BENCH_ALIGN static uint32_t ZR(dma_wr_acquire)(uintptr_t pp, uintptr_t max)
{
    uint32_t len = ring_buf_put_ptr(&zrb, (uint8_t **)pp, 0);
    return len < max ? len : (uint32_t)max;
}
BENCH_ALIGN static uint32_t ZR(dma_wr_commit)(uintptr_t n, uintptr_t u) { (void)u; ring_buf_commit(&zrb, n); return (uint32_t)n; }
BENCH_ALIGN static uint32_t ZR(dma_rd_acquire)(uintptr_t pp, uintptr_t max)
{
    uint32_t len = ring_buf_get_ptr(&zrb, (uint8_t **)pp, 0);
    return len < max ? len : (uint32_t)max;
}
BENCH_ALIGN static uint32_t ZR(dma_rd_release)(uintptr_t n, uintptr_t u) { (void)u; ring_buf_consume(&zrb, n); return (uint32_t)n; }

const rb_adapter ZR_ADAPTER = {
    ZR(reset), ZR(push), ZR(pop), ZR(push_n), ZR(pop_n), 0, 0,
    ZR(dma_wr_acquire), ZR(dma_wr_commit), ZR(dma_rd_acquire), ZR(dma_rd_release)
};
