/* Feasibility test for plan item 2a, application core side: give the
 * network core secure access to application RAM (SPU EXTDOMAIN[0].PERM
 * SECATTR, 0x50003440 bit 4), release it (RESET.NETWORK.FORCEOFF,
 * 0x50005614 = 0; addresses from the nrfx MDK nrf5340_application.h), then
 * record what it writes at 0x20070000 (net.c) into words at 0x20000000:
 *   [0] "APP0" when done, [1] SPU value read back, [2] FORCEOFF read back,
 *   [3..4] shared words after ~0.1 s, [5..6] after ~0.2 s. */
#include <stdint.h>
#define REG(a) (*(volatile uint32_t *)(a))
extern uint32_t _estack;
void Reset_Handler(void);
static void Default_Handler(void) { for (;;) {} }
__attribute__((section(".isr_vector"), used))
const void *const vectors[16] = { &_estack, Reset_Handler, Default_Handler, Default_Handler };
static void delay(uint32_t n) { for (volatile uint32_t i = 0; i < n; i++) {} }
__attribute__((noreturn)) void Reset_Handler(void)
{
    volatile uint32_t *res = (volatile uint32_t *)0x20000000u, *sh = (volatile uint32_t *)0x20070000u;
    for (int i = 0; i < 8; i++) res[i] = 0;
    sh[0] = sh[1] = 0;
    REG(0x50003440u) = 0x10u;
    REG(0x50005614u) = 0u;
    res[1] = REG(0x50003440u);
    res[2] = REG(0x50005614u);
    delay(1000000);
    res[3] = sh[0]; res[4] = sh[1];
    delay(1000000);
    res[5] = sh[0]; res[6] = sh[1];
    res[0] = 0x41505030u;   /* "APP0" */
    for (;;) {}
}
