/* The Rust pools (rust/src/lib.rs): heapless's pool and atomic-pool, through
 * the C interface of the static library rust/ builds. What each adapter does
 * around its library is in rust/src/lib.rs. heapless's pool needs LDREX/STREX
 * on Arm (its src/pool.rs: "not thumbv6m-none-eabi"), so it is not built for
 * the two Cortex-M0+ boards. */
#include "pool.h"

#define RUST_ADAPTER(sym, pfx, label)                                                          \
    void pfx##_init(void);                                                                    \
    uintptr_t pfx##_alloc(uintptr_t a, uintptr_t b);                                          \
    uint32_t pfx##_free(uintptr_t a, uintptr_t b);                                            \
    void pfx##_region(uintptr_t *lo, uintptr_t *hi);                                          \
    uint32_t pfx##_align(void);                                                               \
    void pfx##_canaries(uint32_t **lo, uint32_t **hi);                                        \
    pool_adapter sym;                                                                         \
    /* C wrappers, so that the descriptor names functions of the adapter's own code (the      \
     * bench's check puts them before the far gap, as the CRC kind's Rust adapter does) */    \
    static uintptr_t pfx##_c_alloc(uintptr_t a, uintptr_t b) { return pfx##_alloc(a, b); }    \
    static uint32_t pfx##_c_free(uintptr_t a, uintptr_t b) { return pfx##_free(a, b); }       \
    static void pfx##_c_region(uintptr_t *lo, uintptr_t *hi) { pfx##_region(lo, hi); }        \
    static void pfx##_c_init(void)                                                            \
    {                                                                                         \
        pfx##_init();                                                                         \
        sym.align = pfx##_align();                 /* the Rust side's constants, once known */ \
        pfx##_canaries(&sym.canary_lo, &sym.canary_hi);                                        \
    }                                                                                         \
    pool_adapter sym = { label, pfx##_c_init, pfx##_c_alloc, pfx##_c_free, pfx##_c_region, 1, 0, 0 };

#if !defined(__arm__) || (__ARM_ARCH >= 7)
RUST_ADAPTER(adapter_heapless, vl_heapless, "heapless pool, BoxPool (Rust)")
#endif
RUST_ADAPTER(adapter_atomic_pool, vl_atomic_pool, "atomic-pool (Rust)")
