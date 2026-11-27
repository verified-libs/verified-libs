/* Calls the CMSIS-RTX adapter once, so that a Cortex-M link keeps it and
 * shows every symbol the pool needs from the rest of the kernel; not run. */
#include "pool.h"
extern const pool_adapter adapter_cmsis_rtx;
volatile uintptr_t sink;
int main(void)
{
    adapter_cmsis_rtx.init();
    uintptr_t b = adapter_cmsis_rtx.alloc(0, 0);
    sink = b;
    sink += adapter_cmsis_rtx.free(b, 0);
    return 0;
}
