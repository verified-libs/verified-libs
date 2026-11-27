/* A host model of a Cortex-M core's local exclusive monitor (LDREX, STREX,
 * CLREX), for the one-core check with an interrupt at every instruction
 * (excl_check.c; the same single-step method as ../contract).
 *
 * The rules modelled (the report of the pool pre-checks gives their sources):
 *   - LDREX marks the address and sets the monitor to Exclusive Access;
 *   - STREX stores and returns 0 only if the monitor is in Exclusive Access
 *     for that address; it returns 1 and does not store otherwise; either way
 *     the monitor goes to Open Access;
 *   - CLREX sets Open Access;
 *   - exception entry and exception return set Open Access (vl_excl_exception,
 *     called by the check when it starts and ends an interrupt's call);
 *   - a plain store of the same core to the marked address: whether it clears
 *     the monitor is left to the implementation, so the model takes the choice
 *     that helps a program least: it does not clear it.
 *   - optionally, a STREX that would succeed fails instead (a monitor may go
 *     to Open Access "from some other cause"), at a point the check chooses;
 *   - STREX to another address than the marked one while in Exclusive Access
 *     is not something a correct program does; the model stops the check
 *     (VL_EXCL_FAULT) instead of choosing a behaviour.
 * Each of LDREX and STREX is one instruction on the core, so an interrupt
 * cannot come in the middle of one. Here each is several host instructions;
 * an interrupt point that falls inside one is held and taken right after it
 * (vl_excl_inside), as one held by PRIMASK is taken after the unmask. */
#ifndef VL_EXCL_MODEL_H
#define VL_EXCL_MODEL_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

extern volatile int vl_excl_inside;      /* inside one modelled instruction */
extern volatile int vl_mon_exclusive;    /* 1: Exclusive Access, 0: Open Access */
extern volatile uintptr_t vl_mon_addr;   /* the marked address */
extern volatile int vl_excl_clear_on_exception;   /* 1 as the architecture says; 0 only for the model's control */
void vl_excl_after(void);                /* takes an interrupt held inside the instruction */
/* The check's choice of a STREX that fails without a cause (0: none): */
extern volatile int vl_excl_isr;         /* 1 while the interrupt's calls run */
extern volatile unsigned vl_excl_strex_n, vl_excl_fail_nth;   /* main's STREX count; the one that fails */
extern volatile int vl_excl_fail_isr;    /* 1: the interrupt's first STREX that would succeed fails */

static inline void vl_excl_exception(void)
{
    if (vl_excl_clear_on_exception) vl_mon_exclusive = 0;
}
static inline uint32_t vl_ldrex(volatile uint32_t *a)
{
    vl_excl_inside = 1;
    __asm__ volatile("" ::: "memory");
    vl_mon_addr = (uintptr_t)a;
    vl_mon_exclusive = 1;
    uint32_t v = *a;
    __asm__ volatile("" ::: "memory");
    vl_excl_inside = 0;
    vl_excl_after();
    return v;
}
static inline uint32_t vl_strex(uint32_t v, volatile uint32_t *a)
{
    vl_excl_inside = 1;
    __asm__ volatile("" ::: "memory");
    if (vl_mon_exclusive && vl_mon_addr != (uintptr_t)a) {
        fprintf(stderr, "VL_EXCL_FAULT: STREX to %p while %p is marked\n", (void *)a, (void *)vl_mon_addr);
        abort();
    }
    uint32_t fail = !vl_mon_exclusive;
    /* A STREX failing without a cause (DDI0553B.z, RMRSD), when the check
     * asks for it: main's n-th STREX, or the interrupt's first one that
     * would succeed. */
    if (!vl_excl_isr && ++vl_excl_strex_n == vl_excl_fail_nth) fail = 1;
    if (vl_excl_isr && !fail && vl_excl_fail_isr) { vl_excl_fail_isr = 0; fail = 1; }
    if (!fail) *a = v;
    vl_mon_exclusive = 0;
    __asm__ volatile("" ::: "memory");
    vl_excl_inside = 0;
    vl_excl_after();
    return fail;
}
static inline void vl_clrex(void) { vl_mon_exclusive = 0; }
#endif
