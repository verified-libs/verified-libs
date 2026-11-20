/* Plan 2a feasibility, application core: release the network core, set GO,
 * do the same K atomic and K plain increments, wait for the network core.
 * Results at 0x20000000: [0] "APP1", [1] atomic counter (want 2K),
 * [2] plain counter (less than 2K shows the cores really overlap),
 * [3] network core done (1). */
#include <stdint.h>
#define K 1000000u
#define REG(a) (*(volatile uint32_t *)(a))
extern uint32_t _estack;
void Reset_Handler(void);
static void Default_Handler(void) { for (;;) {} }
__attribute__((section(".isr_vector"), used))
const void *const vectors[16] = { &_estack, Reset_Handler, Default_Handler, Default_Handler };
__attribute__((noreturn)) void Reset_Handler(void)
{
    volatile uint32_t *res = (volatile uint32_t *)0x20000000u, *sh = (volatile uint32_t *)0x20070000u;
    for (int i = 0; i < 8; i++) { res[i] = 0; sh[i] = 0; }
    REG(0x50003440u) = 0x10u;
    REG(0x50005614u) = 0u;
    while (sh[0] != 0x4E455431u) {}
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
    sh[2] = 1u;
    for (uint32_t i = 0; i < K; i++) {
        __atomic_fetch_add((uint32_t *)&sh[3], 1u, __ATOMIC_RELAXED);
        sh[4] = sh[4] + 1u;
    }
    for (uint32_t t = 0; sh[5] != 1u && t < 200000000u; t++) {}
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
    res[1] = sh[3]; res[2] = sh[4]; res[3] = sh[5];
    res[0] = 0x41505031u;
    for (;;) {}
}
