/* Minimal Cortex-M0+ startup for the SAM D20 (ATSAMD20J18A): vector table, code copy to
 * SRAM (SRAM variant only), .data copy, .bss clear, C++ static constructors.
 * Same structure as common/nrf5340/startup.c. Must be built with
 * -fno-tree-loop-distribute-patterns: the copy loops must not become memcpy
 * calls, because memcpy itself may live in SRAM and is not there yet. */
#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
extern uint32_t _siramtext, _sramtext, _eramtext;
extern void (*__init_array_start[])(void);
extern void (*__init_array_end[])(void);
int main(void);

void Reset_Handler(void)
{
    uint32_t *src, *dst;
    for (src = &_siramtext, dst = &_sramtext; dst < &_eramtext;) *dst++ = *src++;
    __asm volatile("dsb\n isb" ::: "memory"); /* code written: sync before executing it */
    for (src = &_sidata, dst = &_sdata; dst < &_edata;) *dst++ = *src++;
    for (dst = &_sbss; dst < &_ebss; dst++) *dst = 0;
    for (void (**f)(void) = __init_array_start; f < __init_array_end; f++) (*f)();
    main();
    for (;;) {}
}

void Default_Handler(void) { for (;;) {} }

/* Peripheral interrupts used by the lab firmware; override as needed. */
void TC0_Handler(void) __attribute__((weak, alias("Default_Handler")));
void SysTick_Handler(void) __attribute__((weak, alias("Default_Handler")));
void TC2_Handler(void) __attribute__((weak, alias("Default_Handler")));

/* Core exceptions + the 25 peripheral interrupts (hal_atmel samd20j18.h,
 * 8f95c79f: PM_IRQn = 0 ... PTC_IRQn = 24). */
#pragma GCC diagnostic ignored "-Woverride-init"
__attribute__((section(".isr_vector"), used))
const void *const vectors[16 + 25] = {
    &_estack,
    Reset_Handler,
    Default_Handler, /* NMI */
    Default_Handler, /* HardFault */
    0, 0, 0, 0, 0, 0, 0,
    Default_Handler, /* SVCall */
    0, 0,
    Default_Handler, /* PendSV */
    SysTick_Handler, /* SysTick */
    [16 ... 16 + 24] = Default_Handler,
    [16 + 13] = TC0_Handler,         /* TC0_IRQn = 13 */
    [16 + 15] = TC2_Handler,         /* TC2_IRQn = 15 */
};
