/* Part C: the reference over 4 * WORDS bytes is a chain of steps, each the
 * reference over four zero bytes applied to the register XOR the next word,
 * for every start value r and every message w. CONTROL: one wrong result,
 * must fail. */
#include <stddef.h>
#include <stdint.h>
#include "ref_crc.h"
uint32_t nondet_u32(void);
#ifndef WORDS
#define WORDS 10
#endif
static uint32_t w[WORDS], z4[1];
int main(void)
{
    uint32_t r = nondet_u32();
    for (int i = 0; i < WORDS; i++) w[i] = nondet_u32();
    uint32_t x = r;
    for (int i = 0; i < WORDS; i++) x = ref32_update(x ^ w[i], z4, 4);
#ifdef CONTROL
    x ^= (r == 0x12345678u && w[3] == 0x9ABCDEF0u);
#endif
    __CPROVER_assert(ref32_update(r, w, 4 * WORDS) == x, "the reference is a chain of steps over four zero bytes");
    return 0;
}
