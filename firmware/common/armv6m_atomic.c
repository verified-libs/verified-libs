/*
 * Atomic load/store library calls for clang builds on ARMv6-M (Cortex-M0+).
 *
 * clang treats atomics on thumbv6m as not lock-free and turns every
 * _Atomic / std::atomic load and store into a call (__atomic_load_4, ...);
 * arm-none-eabi-gcc inlines the same operations (an aligned LDR/STR plus
 * DMB as the order needs), and the toolchain ships no libatomic for
 * Cortex-M. This file is compiled with gcc and implements each call with
 * gcc's own inline atomic of the same order, so a clang-built library gets
 * the code a gcc build would have inlined. Only loads and stores: there is no
 * read-modify-write on ARMv6-M (no LDREX/STREX), so a library that needs one
 * still fails to link, as it should.
 *
 * Linked only for COMPILER=clang on cortex-m0plus (see compiler.mk).
 */
#include <stdint.h>


#define LOAD_STORE(N, T)                                                    \
    T vl_atomic_load_##N(const volatile void *p, int mo)                   \
        __asm__("__atomic_load_" #N);                                      \
    T vl_atomic_load_##N(const volatile void *p, int mo)                   \
    {                                                                      \
        T v;                                                               \
        if (mo == __ATOMIC_RELAXED) v = __atomic_load_n((const volatile T *)p, __ATOMIC_RELAXED); \
        else if (mo == __ATOMIC_ACQUIRE || mo == __ATOMIC_CONSUME) v = __atomic_load_n((const volatile T *)p, __ATOMIC_ACQUIRE); \
        else v = __atomic_load_n((const volatile T *)p, __ATOMIC_SEQ_CST); \
        return v;                                                          \
    }                                                                      \
    void vl_atomic_store_##N(volatile void *p, T v, int mo)                \
        __asm__("__atomic_store_" #N);                                     \
    void vl_atomic_store_##N(volatile void *p, T v, int mo)                \
    {                                                                      \
        if (mo == __ATOMIC_RELAXED) __atomic_store_n((volatile T *)p, v, __ATOMIC_RELAXED); \
        else if (mo == __ATOMIC_RELEASE) __atomic_store_n((volatile T *)p, v, __ATOMIC_RELEASE); \
        else __atomic_store_n((volatile T *)p, v, __ATOMIC_SEQ_CST);       \
    }

LOAD_STORE(1, uint8_t)
LOAD_STORE(2, uint16_t)
LOAD_STORE(4, uint32_t)
