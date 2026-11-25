/* Pilot, cross build only: calls every adapter once so that the linker
 * keeps them, and nothing else. Not run (no board is used in the pilot). */
#include "pool.h"
extern const pool_adapter adapter_ref, adapter_etl_pool, adapter_riot_memarray, adapter_threadx_block;
static const pool_adapter *const ADS[] = { &adapter_ref, &adapter_etl_pool, &adapter_riot_memarray, &adapter_threadx_block };
volatile uintptr_t sink;
int main(void)
{
    for (unsigned i = 0; i < sizeof(ADS) / sizeof(ADS[0]); i++) {
        ADS[i]->init();
        uintptr_t b = ADS[i]->alloc(0, 0);
        sink = b;
        if (b) ADS[i]->free(b, 0);
    }
    for (;;) {}
}
