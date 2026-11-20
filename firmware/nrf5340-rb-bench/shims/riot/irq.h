/* Shim for RIOT's irq.h, so sys/tsrb can be built outside RIOT.
 * Same semantics as RIOT's Cortex-M implementation (cpu/cortexm_common/
 * irq_arch.c): irq_disable() saves PRIMASK and disables interrupts,
 * irq_restore() writes the saved PRIMASK back. */
#ifndef IRQ_H
#define IRQ_H
#include <stdbool.h>

static inline __attribute__((always_inline)) unsigned irq_disable(void)
{
    unsigned p;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(p) :: "memory");
    return p;
}

static inline __attribute__((always_inline)) void irq_restore(unsigned state)
{
    __asm volatile("msr primask, %0" ::"r"(state) : "memory");
}

static inline __attribute__((always_inline)) bool irq_is_in(void)
{
    unsigned ipsr;
    __asm volatile("mrs %0, ipsr" : "=r"(ipsr));
    return ipsr != 0;
}

#endif
