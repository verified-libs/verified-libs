/* Minimal Cortex-M33 startup: vector table, code copy to SRAM (SRAM
 * variant only), .data copy, .bss clear, C++ static constructors.
 * Must be built with -fno-tree-loop-distribute-patterns: the copy loops
 * must not become memcpy calls, because memcpy itself may live in SRAM and
 * is not there yet. */
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
void TIMER0_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void SysTick_Handler(void) __attribute__((weak, alias("Default_Handler")));
void TIMER1_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));

/* Core exceptions + the first 32 peripheral interrupts. All peripheral
 * slots default to Default_Handler; the used ones are overridden below. */
#pragma GCC diagnostic ignored "-Woverride-init"
__attribute__((section(".isr_vector"), used))
const void *const vectors[16 + 32] = {
    &_estack,
    Reset_Handler,
    Default_Handler, /* NMI */
    Default_Handler, /* HardFault */
    Default_Handler, /* MemManage */
    Default_Handler, /* BusFault */
    Default_Handler, /* UsageFault */
    Default_Handler, /* SecureFault */
    0, 0, 0,
    Default_Handler, /* SVCall */
    Default_Handler, /* DebugMonitor */
    0,
    Default_Handler, /* PendSV */
    SysTick_Handler, /* SysTick */
    [16 ... 16 + 31] = Default_Handler,
    [16 + 15] = TIMER0_IRQHandler,  /* TIMER0_IRQn = 15 (nrfx MDK) */
    [16 + 16] = TIMER1_IRQHandler,  /* TIMER1_IRQn = 16 (nRF5340 PS 5.1.3.1) */
};
