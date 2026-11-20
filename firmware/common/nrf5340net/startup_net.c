/* nRF5340 network core start-up for rb-xcore-stress: debug access kept
 * open (CTRLAP.APPROTECT.DISABLE, 0x41006544 = 0x50FA50FA, the key that
 * UICR.APPROTECT holds when unprotected; nrfx MDK nrf5340_network.h,
 * CTRLAPPERI_APPROTECT_Type at 0x540 of CTRLAP 0x41006000), own .data and
 * .bss, C++ constructors, main. The shared part (XSHARED) is left alone:
 * the application core owns it. */
#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
extern void (*__init_array_start[])(void);
extern void (*__init_array_end[])(void);
int main(void);

void Reset_Handler(void)
{
    *(volatile uint32_t *)0x41006544u = 0x50FA50FAu;
    uint32_t *src, *dst;
    for (src = &_sidata, dst = &_sdata; dst < &_edata;) *dst++ = *src++;
    for (dst = &_sbss; dst < &_ebss; dst++) *dst = 0;
    for (void (**f)(void) = __init_array_start; f < __init_array_end; f++) (*f)();
    main();
    for (;;) {}
}

void Default_Handler(void) { for (;;) {} }

__attribute__((section(".isr_vector"), used))
const void *const vectors[16] = {
    &_estack, Reset_Handler,
    Default_Handler, Default_Handler, Default_Handler, Default_Handler, Default_Handler,
    0, 0, 0, 0,
    Default_Handler, Default_Handler, 0, Default_Handler, Default_Handler,
};
