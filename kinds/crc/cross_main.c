/* The program of the cross builds (cross.sh): calls one adapter's one-shot
 * call (ONE, an adapter's name), so the link keeps that configuration and
 * nothing else; without ONE it is the empty program the sizes are taken
 * against. Never run. */
#include "adapters.h"

static uint8_t buf[64];

int main(void)
{
#ifdef ONE
    extern const crc_adapter ONE;
    if (ONE.init) ONE.init();
    return (int)ONE.crc((uintptr_t)buf, sizeof buf);
#else
    return buf[0];
#endif
}
