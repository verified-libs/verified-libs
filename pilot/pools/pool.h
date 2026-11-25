/* Draft of the common adapter interface for fixed-block pools (pilot,
 * lab/plans/2026-11-24-next-library-kinds.md step 4). Nothing measured
 * with it; see README.md.
 *
 * Every adapter offers the same operations on one pool of POOL_BLOCKS
 * blocks of POOL_BLOCK_SIZE bytes. On the 32-bit boards every operation
 * has the signature of the ring-buffer benchmark's operations (rb_op:
 * uint32_t op(uintptr_t, uintptr_t)), so the boards' timed window
 * time_call() can time them unchanged; alloc returns a uintptr_t so that
 * the same adapters run on a 64-bit host:
 *   alloc:  a, b unused             -> address of a block, 0 if none is free
 *   free:   a = address of a block  -> 1 if the adapter gave it back, 0 if
 *                                      the library refused it
 * Optional, for libraries with separate calls for interrupts (ThreadX's
 * TX_NO_WAIT is the argument, not a call; CMSIS-RTOS2 the same): isr_alloc,
 * isr_free; NULL = use alloc/free.
 *
 * Why this shape:
 * - One block size per pool, fixed at build time: every candidate of the
 *   survey (candidates/pools-embedded.md) is a pool of one block size.
 * - The adapter creates the pool itself in init() from its own static
 *   storage: the libraries differ in what they need (ThreadX keeps a
 *   pointer before every block, RIOT and ETL do not), so only the adapter
 *   knows how many bytes POOL_BLOCKS blocks need. region() tells the test
 *   where the blocks may lie.
 * - No "available" call: not every library has one, and the test counts
 *   the blocks it holds itself.
 */
#pragma once
#include <stddef.h>
#include <stdint.h>

#ifndef POOL_BLOCK_SIZE
#define POOL_BLOCK_SIZE 32u
#endif
#ifndef POOL_BLOCKS
#define POOL_BLOCKS 8u
#endif

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
    pool_alloc_op isr_alloc;            /* optional, NULL = alloc */
    pool_op isr_free;                   /* optional, NULL = free */
    void (*region)(uintptr_t *lo, uintptr_t *hi);  /* where blocks may lie: [lo, hi) */
    uint32_t align;                     /* the alignment the library promises for a block */
} pool_adapter;

#ifdef __cplusplus
}
#endif
