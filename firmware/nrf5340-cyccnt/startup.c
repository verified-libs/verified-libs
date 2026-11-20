/* Minimal Cortex-M33 startup: vector table, .data copy, .bss clear. */
#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
int main(void);

void Reset_Handler(void)
{
    uint32_t *src = &_sidata, *dst = &_sdata;
    while (dst < &_edata) *dst++ = *src++;
    for (dst = &_sbss; dst < &_ebss; dst++) *dst = 0;
    main();
    for (;;) {}
}

void Default_Handler(void) { for (;;) {} }

/* Core exceptions only; peripheral interrupts are not used. */
__attribute__((section(".isr_vector"), used))
const void *const vectors[16] = {
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
    Default_Handler, /* SysTick */
};
