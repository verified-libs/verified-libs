/* Adapter: AndersKaloer/Ring-Buffer (C).
 * ring_buffer_queue() overwrites the oldest byte when the buffer is full,
 * which moves the tail from the producer side; that is not SPSC-safe. The
 * adapter therefore checks for space first and never calls queue on a full
 * buffer, as a careful SPSC user would. */
#include "ringbuffer.h"
#include "bench.h"

static ring_buffer_t rb;
static char data[RB_SLOTS];

BENCH_ALIGN static void anders_reset(void) { ring_buffer_init(&rb, data, sizeof data); }

BENCH_ALIGN static uint32_t anders_push(uintptr_t v, uintptr_t unused)
{
    (void)unused;
    if (ring_buffer_is_full(&rb)) return 0;
    ring_buffer_queue(&rb, (char)v);
    return 1;
}

BENCH_ALIGN static uint32_t anders_pop(uintptr_t p, uintptr_t unused)
{
    (void)unused;
    return ring_buffer_dequeue(&rb, (char *)p);
}

BENCH_ALIGN static uint32_t anders_push_n(uintptr_t p, uintptr_t n)
{
    ring_buffer_size_t space = RB_SLOTS - 1 - ring_buffer_num_items(&rb);
    if (n > space) n = space;
    ring_buffer_queue_arr(&rb, (const char *)p, n);
    return n;
}

BENCH_ALIGN static uint32_t anders_pop_n(uintptr_t p, uintptr_t n)
{
    return (uint32_t)ring_buffer_dequeue_arr(&rb, (char *)p, n);
}

const rb_adapter adapter_anders = { anders_reset, anders_push, anders_pop, anders_push_n, anders_pop_n, 0, 0 };
