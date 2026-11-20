/* Plan 2a feasibility, network core: when the application core sets
 * GO (shared[2] = 1), add 1 to shared[3] K times atomically (LDREX/STREX,
 * __atomic_fetch_add) and to shared[4] K times plainly, then set shared[5]. */
#include <stdint.h>
#define K 1000000u
extern uint32_t _estack;
void Reset_Handler(void);
static void Default_Handler(void) { for (;;) {} }
__attribute__((section(".isr_vector"), used))
const void *const vectors[16] = { &_estack, Reset_Handler, Default_Handler, Default_Handler };
__attribute__((noreturn)) void Reset_Handler(void)
{
    volatile uint32_t *sh = (volatile uint32_t *)0x20070000u;
    sh[0] = 0x4E455431u;                  /* "NET1" */
    while (sh[2] != 1u) {}
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
    for (uint32_t i = 0; i < K; i++) {
        __atomic_fetch_add((uint32_t *)&sh[3], 1u, __ATOMIC_RELAXED);
        sh[4] = sh[4] + 1u;
    }
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
    sh[5] = 1u;
    for (;;) {}
}
