/* Minimal stand-in for <Arduino.h> as ArduinoCore-renesas's sync.h uses it:
 * the CMSIS core intrinsics __get_PRIMASK, __disable_irq, __enable_irq and
 * __ISB, written as CMSIS defines them for GCC. */
#pragma once
#include <stdint.h>
static inline uint32_t __get_PRIMASK(void)
{
    uint32_t r;
    __asm volatile("mrs %0, primask" : "=r"(r));
    return r;
}
static inline void __disable_irq(void) { __asm volatile("cpsid i" ::: "memory"); }
static inline void __enable_irq(void) { __asm volatile("cpsie i" ::: "memory"); }
static inline void __ISB(void) { __asm volatile("isb 0xF" ::: "memory"); }
