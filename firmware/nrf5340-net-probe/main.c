/* Feasibility test for plan item 2a: the nRF5340's network core writes into
 * the application core's RAM. It counts up a word at SHARED (application
 * RAM, which the network core sees at the same address: nrfx MDK
 * nrf5340_xxaa_network.ld RAM1) and marks it with a magic word. The host
 * releases the core (RESET.NETWORK.FORCEOFF) and reads the counter. */
#include <stdint.h>
#define SHARED 0x20070000u
extern uint32_t _estack;
void Reset_Handler(void);
static void Default_Handler(void) { for (;;) {} }
__attribute__((section(".isr_vector"), used))
const void *const vectors[16] = { &_estack, Reset_Handler, Default_Handler, Default_Handler };
__attribute__((noreturn)) void Reset_Handler(void)
{
    volatile uint32_t *w = (volatile uint32_t *)SHARED;
    w[0] = 0x4E455430u;               /* "NET0" */
    for (uint32_t n = 0;; n++) w[1] = n;
}
