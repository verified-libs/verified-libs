/* Minimal stand-in for Mbed's platform/mbed_critical.h: the critical
 * section as Mbed CE mbed-os-7.1.0 implements it on Cortex-M
 * (platform/source/mbed_critical.c: a reentrancy counter around
 * hal/source/mbed_critical_section_api.c: interrupts off on every entry,
 * the state from before the outermost entry restored on the outermost
 * exit). The two variables are defined in the adapter. */
#pragma once
#include <stdint.h>
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
extern volatile uint32_t vl_mbed_cs_depth;
extern volatile bool vl_mbed_cs_irq_were_on;
static inline void core_util_critical_section_enter(void)
{
    uint32_t primask;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(primask) :: "memory");
    if (vl_mbed_cs_depth == 0) vl_mbed_cs_irq_were_on = (primask & 1u) == 0;
    vl_mbed_cs_depth = vl_mbed_cs_depth + 1u;
}
static inline void core_util_critical_section_exit(void)
{
    if (vl_mbed_cs_depth == 0) return;   /* exit without enter: nothing, as Mbed */
    vl_mbed_cs_depth = vl_mbed_cs_depth - 1u;
    if (vl_mbed_cs_depth == 0 && vl_mbed_cs_irq_were_on) __asm volatile("cpsie i" ::: "memory");
}
#ifdef __cplusplus
}
#endif
