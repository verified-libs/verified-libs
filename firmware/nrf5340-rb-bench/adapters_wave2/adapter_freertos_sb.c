/* Adapter: FreeRTOS stream buffer (FreeRTOS-Kernel V11.3.3, stream_buffer.c
 * unchanged), built without the scheduler: shims/freertos has the config,
 * a minimal port (critical sections with PRIMASK) and inert task stubs.
 * FreeRTOS documents a stream buffer for one writer and one reader, tasks
 * or interrupts; from an interrupt the ...FromISR functions must be used.
 * This adapter reads IPSR and calls the FromISR variant in interrupt
 * context, so the stress test's interrupt side always uses the API meant
 * for it. Timeouts are 0 (never block); trigger level 1. Capacity
 * RB_SLOTS - 1 bytes (storage RB_SLOTS, FreeRTOS needs one byte more). */
#include "FreeRTOS.h"
#include "stream_buffer.h"
#include "bench.h"

static StaticStreamBuffer_t sb_struct;
static uint8_t sb_storage[RB_SLOTS];
static StreamBufferHandle_t sb;

static inline int in_isr(void)
{
    uint32_t ipsr;
    __asm volatile("mrs %0, ipsr" : "=r"(ipsr));
    return ipsr != 0;
}

BENCH_ALIGN static void frs_reset(void)
{
    if (!sb) sb = xStreamBufferCreateStatic(RB_SLOTS - 1, 1, sb_storage, &sb_struct);
    xStreamBufferReset(sb);
}
BENCH_ALIGN static uint32_t frs_push_n(uintptr_t p, uintptr_t n)
{
    return in_isr() ? (uint32_t)xStreamBufferSendFromISR(sb, (const void *)p, n, NULL)
                    : (uint32_t)xStreamBufferSend(sb, (const void *)p, n, 0);
}
BENCH_ALIGN static uint32_t frs_pop_n(uintptr_t p, uintptr_t n)
{
    return in_isr() ? (uint32_t)xStreamBufferReceiveFromISR(sb, (void *)p, n, NULL)
                    : (uint32_t)xStreamBufferReceive(sb, (void *)p, n, 0);
}
BENCH_ALIGN static uint32_t frs_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    uint8_t b = (uint8_t)v;
    return frs_push_n((uintptr_t)&b, 1);
}
BENCH_ALIGN static uint32_t frs_pop(uintptr_t p, uintptr_t u) { (void)u; return frs_pop_n(p, 1); }

const rb_adapter adapter_freertos_sb = { frs_reset, frs_push, frs_pop, frs_push_n, frs_pop_n, 0, 0 };
