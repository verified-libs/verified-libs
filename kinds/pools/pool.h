/* The adapter interface of the pools kind (lab/plans/2026-11-26-pools-kind.md,
 * section 2), grown out of the pilot's (pilot/pools/pool.h).
 *
 * Every adapter offers the same operations on one pool of POOL_BLOCKS blocks
 * of POOL_BLOCK_SIZE bytes. On the 32-bit boards each operation has the
 * signature the boards' time_call() takes (uint32_t op(uintptr_t, uintptr_t)),
 * so the timed window of firmware/common/<board>/board.h times it unchanged;
 * alloc returns a uintptr_t so that the same adapters run on a 64-bit host:
 *   alloc:  a, b unused             -> address of a block, 0 if none is free
 *   free:   a = address of a block  -> 1 if the adapter gave it back, 0 if
 *                                      the library refused it
 *
 * Why this shape:
 * - One block size per pool, fixed at build time: every candidate is a pool
 *   of one block size. The shape of the first series is decided: 32 blocks
 *   of 32 bytes (DECISIONS 2026-11-26).
 * - The adapter owns the storage and creates the pool in init(): the
 *   libraries need different amounts of it for the same blocks (ThreadX
 *   keeps a pointer in front of every block; ETL, RIOT and our reference
 *   keep their list inside free blocks; Contiki-NG keeps a flag array).
 *   region() tells the test where blocks may lie.
 * - Canaries: each adapter puts the library's state and storage between two
 *   arrays of POOL_CANARY_WORDS words (POOL_GUARDED below), so that a write
 *   outside the pool's own memory shows. The test fills them after init()
 *   and checks them after every call.
 * - No "free count" call: not every library has one; the test counts the
 *   blocks it holds.
 * - align: the alignment the library promises for a block, taken from its
 *   code where its documentation says none (the README says which).
 * - Interrupt variants (ThreadX's TX_NO_WAIT is an argument; ChibiOS has
 *   separate ...I calls) are left to the later concurrency series; the first
 *   series is one context (DECISIONS 2026-11-26).
 */
#pragma once
#include <stddef.h>
#include <stdint.h>

#ifndef POOL_BLOCK_SIZE
#define POOL_BLOCK_SIZE 32u
#endif
#ifndef POOL_BLOCKS
#define POOL_BLOCKS 32u
#endif
#define POOL_CANARY_WORDS 4u
#define POOL_CANARY 0xC0DECAFEu

/* The library's state and storage of an adapter, between two canary arrays. */
#define POOL_GUARDED(...) struct { uint32_t canary_lo[POOL_CANARY_WORDS]; __VA_ARGS__ uint32_t canary_hi[POOL_CANARY_WORDS]; }

#ifdef __cplusplus
extern "C" {
#endif

typedef uint32_t (*pool_op)(uintptr_t a, uintptr_t b);
typedef uintptr_t (*pool_alloc_op)(uintptr_t a, uintptr_t b);

typedef struct {
    const char *name;
    void (*init)(void);                 /* (re)create an empty pool: every block free */
    pool_alloc_op alloc;                /* -> block address or 0 */
    pool_op free;                       /* a = block address -> 1 */
    void (*region)(uintptr_t *lo, uintptr_t *hi);  /* where blocks may lie: [lo, hi) */
    uint32_t align;                     /* the alignment the library promises for a block */
    uint32_t *canary_lo, *canary_hi;    /* POOL_CANARY_WORDS words each, around the pool's memory */
} pool_adapter;

/* "Interrupts off" for the pools that turn them off (ThreadX, CMSIS-RTX on
 * Armv6-M, our PRIMASK row): PRIMASK on a board; on the host a flag of the
 * test, counted, as in the contract check's host_irq.h. */
#if defined(__arm__)
static inline unsigned pool_irq_disable(void)
{
    unsigned s;
    __asm volatile ("mrs %0, primask\n\tcpsid i" : "=r" (s) :: "memory");
    return s;
}
static inline void pool_irq_restore(unsigned s) { __asm volatile ("msr primask, %0" :: "r" (s) : "memory"); }
#else
unsigned pool_irq_disable(void);
void pool_irq_restore(unsigned was);
#endif

#ifdef __cplusplus
}
#endif
