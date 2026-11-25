/* Part D: zlib's crc32 equals the reference at the zero input and at each
 * of the 32 + 32 * WORDS inputs (start value, message) with exactly one bit
 * set. i == 32 + 32 * WORDS is the zero input. CONTROL: wrong at one of
 * them, must fail. */
#include <stddef.h>
#include <stdint.h>
#include "ref_crc.h"
#include "zlib.h"
unsigned nondet_unsigned(void);
#ifndef WORDS
#define WORDS 10
#endif
static uint32_t w[WORDS];
int main(void)
{
    unsigned i = nondet_unsigned();
    __CPROVER_assume(i <= 32 + 32 * WORDS);
    uint32_t c = 0;
    if (i < 32) c = (uint32_t)1 << i;
    else if (i < 32 + 32 * WORDS) w[(i - 32) / 32] = (uint32_t)1 << ((i - 32) % 32);
    uint32_t got = (uint32_t)crc32(c, (const unsigned char *)w, 4 * WORDS);
#ifdef CONTROL
    got ^= (i == 200);
#endif
    uint32_t want = ref32_final(ref32_update(c ^ 0xFFFFFFFFu, w, 4 * WORDS));
    __CPROVER_assert(got == want, "equal at zero and at every single bit");
    return 0;
}
