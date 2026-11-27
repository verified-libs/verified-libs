/* The program of the cross builds (cross.sh): creates one adapter's pool and
 * calls its alloc and free (ONE, an adapter's name), so the link keeps that
 * configuration and nothing else; without ONE it is the empty program the
 * sizes are taken against. Never run. */
#include "pool.h"

int main(void)
{
#ifdef ONE
    extern ADAPTER_CONST pool_adapter ONE;
    ONE.init();
    uintptr_t b = ONE.alloc(0, 0);
    return (int)ONE.free(b, 0);
#else
    return 0;
#endif
}
