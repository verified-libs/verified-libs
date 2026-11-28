/* The exclusive-monitor model of the pool prechecks (verify/exclusive/excl_model.h,
 * whose rules and their sources in the Arm manuals are in
 * verify/exclusive/README.md), copied for this check and widened to
 * 64-bit words: on the host CMSIS-RTX's free list links are 64-bit pointers,
 * where on a Cortex-M they are 32-bit words. The rules are the same:
 *   - LDREX marks the address and sets Exclusive Access;
 *   - STREX stores and returns 0 only in Exclusive Access for that address,
 *     else returns 1 without storing; either way Open Access after;
 *   - CLREX: Open Access; exception entry and return: Open Access
 *     (vl_excl_exception, called by the check around an interrupt's calls);
 *   - a plain store to the marked address does not clear the monitor (the
 *     choice that helps a program least);
 *   - a STREX to another address while in Exclusive Access stops the check.
 * Each of LDREX and STREX is one instruction on the core; here it is several,
 * so an interrupt point inside one is held (vl_excl_inside) and taken right
 * after it (vl_excl_after, in the check). */
#ifndef VL_EXCL_HOST_H
#define VL_EXCL_HOST_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

extern volatile int vl_excl_inside, vl_mon_exclusive, vl_excl_clear_on_exception;
extern volatile uintptr_t vl_mon_addr;
void vl_excl_after(void);

static inline void vl_excl_exception(void)
{
    if (vl_excl_clear_on_exception) vl_mon_exclusive = 0;
}
#define VL_LDREX(T, name)                                                       \
    static inline T name(volatile T *a)                                         \
    {                                                                           \
        vl_excl_inside = 1;                                                     \
        __asm__ volatile("" ::: "memory");                                      \
        vl_mon_addr = (uintptr_t)a;                                             \
        vl_mon_exclusive = 1;                                                   \
        T v = *a;                                                               \
        __asm__ volatile("" ::: "memory");                                      \
        vl_excl_inside = 0;                                                     \
        vl_excl_after();                                                        \
        return v;                                                               \
    }
#define VL_STREX(T, name)                                                       \
    static inline uint32_t name(T v, volatile T *a)                             \
    {                                                                           \
        vl_excl_inside = 1;                                                     \
        __asm__ volatile("" ::: "memory");                                      \
        if (vl_mon_exclusive && vl_mon_addr != (uintptr_t)a) {                  \
            fprintf(stderr, "VL_EXCL_FAULT: STREX to %p while %p is marked\n",  \
                    (void *)a, (void *)vl_mon_addr);                            \
            abort();                                                            \
        }                                                                       \
        uint32_t fail = !vl_mon_exclusive;                                      \
        if (!fail) *a = v;                                                      \
        vl_mon_exclusive = 0;                                                   \
        __asm__ volatile("" ::: "memory");                                      \
        vl_excl_inside = 0;                                                     \
        vl_excl_after();                                                        \
        return fail;                                                            \
    }
VL_LDREX(uint32_t, vl_ldrex32)
VL_STREX(uint32_t, vl_strex32)
VL_LDREX(uintptr_t, vl_ldrexp)
VL_STREX(uintptr_t, vl_strexp)
static inline void vl_clrex(void) { vl_mon_exclusive = 0; }
#endif
