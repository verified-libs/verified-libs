/* Minimal static bump allocator for libraries that allocate once at
 * initialisation (Embedded Artistry's circular_buf_init, rigtorp::SPSCQueue
 * via std::allocator). Replaces newlib's malloc so no heap/sbrk is pulled
 * in. free() does nothing: the benchmarks allocate a fixed set of objects
 * once. Running out of the arena traps (BKPT), it never returns NULL
 * silently. */
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#ifndef BENCH_HEAP_SIZE
#define BENCH_HEAP_SIZE 4096
#endif

static uint8_t arena[BENCH_HEAP_SIZE] __attribute__((aligned(64)));
static size_t used;

void *malloc(size_t n)
{
    size_t start = (used + 63u) & ~(size_t)63u; /* 64-byte alignment covers alignas(64) */
    if (start + n > sizeof arena) { __asm volatile("bkpt #1"); for (;;) {} }
    used = start + n;
    return &arena[start];
}

void free(void *p) { (void)p; }

void *calloc(size_t a, size_t b)
{
    void *p = malloc(a * b);
    memset(p, 0, a * b);
    return p;
}

void *realloc(void *p, size_t n)
{
    (void)p; (void)n;
    __asm volatile("bkpt #2");
    for (;;) {}
}

/* abort() traps the same way (moodycamel calls it when an allocation fails
 * with exceptions off); newlib's abort would pull in signal() and its heap. */
void abort(void)
{
    __asm volatile("bkpt #3");
    for (;;) {}
}
/* C++ aligned new for over-aligned types (rigtorp uses alignas(64)). */
void *aligned_alloc(size_t align, size_t n) { (void)align; return malloc(n); }
