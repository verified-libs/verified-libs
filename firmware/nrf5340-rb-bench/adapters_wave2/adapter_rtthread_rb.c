/* Adapter: RT-Thread rt_ringbuffer (components/drivers/ipc/ringbuffer.c,
 * v5.3.0), built outside RT-Thread with the minimal shims in
 * ../shims/rtthread. The library documents no concurrency contract; RT-Thread's
 * own serial driver (components/drivers/serial/dev_serial_v2.c) calls it
 * inside RT_SERIAL_FIFO_LOCK, interrupts off on one core. Two builds of
 * this file:
 *   default:            as shipped, no lock. Reported, not counted.
 *   -DRTT_LOCKED=1:     every call inside a PRIMASK save/disable/restore,
 *                       as RT-Thread's serial driver does.
 * Capacity: the mirror-bit design uses all slots and RT_ALIGN_SIZE (8)
 * rounds the size down, so the buffer is RB_SLOTS bytes (one more than the
 * other adapters). No write-side zero-copy API: n/a in DMA mode. */
#include <rtdevice.h>
#include "bench.h"

#if defined(RTT_LOCKED) && RTT_LOCKED
#define RT(x) rttl_##x
#define RT_ADAPTER adapter_rtthread_locked
#define LOCK uint32_t pm_; __asm volatile("mrs %0, primask\n cpsid i" : "=r"(pm_) :: "memory");
#define UNLOCK __asm volatile("msr primask, %0" :: "r"(pm_) : "memory");
#else
#define RT(x) rttp_##x
#define RT_ADAPTER adapter_rtthread_plain
#define LOCK
#define UNLOCK
#endif

static struct rt_ringbuffer rrb;
static rt_uint8_t rdata[RB_SLOTS];

BENCH_ALIGN static void RT(reset)(void) { rt_ringbuffer_init(&rrb, rdata, sizeof rdata); }
BENCH_ALIGN static uint32_t RT(push)(uintptr_t v, uintptr_t u)
{
    (void)u;
    LOCK
    uint32_t n = (uint32_t)rt_ringbuffer_putchar(&rrb, (rt_uint8_t)v);
    UNLOCK
    return n;
}
BENCH_ALIGN static uint32_t RT(pop)(uintptr_t p, uintptr_t u)
{
    (void)u;
    LOCK
    uint32_t n = (uint32_t)rt_ringbuffer_getchar(&rrb, (rt_uint8_t *)p);
    UNLOCK
    return n;
}
BENCH_ALIGN static uint32_t RT(push_n)(uintptr_t p, uintptr_t n)
{
    LOCK
    uint32_t r = (uint32_t)rt_ringbuffer_put(&rrb, (const rt_uint8_t *)p, (rt_uint32_t)n);
    UNLOCK
    return r;
}
BENCH_ALIGN static uint32_t RT(pop_n)(uintptr_t p, uintptr_t n)
{
    LOCK
    uint32_t r = (uint32_t)rt_ringbuffer_get(&rrb, (rt_uint8_t *)p, (rt_uint32_t)n);
    UNLOCK
    return r;
}

const rb_adapter RT_ADAPTER = { RT(reset), RT(push), RT(pop), RT(push_n), RT(pop_n), 0, 0 };
