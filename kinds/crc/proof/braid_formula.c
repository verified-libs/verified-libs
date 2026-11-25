/* Part A of zlib's braided loop, proven in parts (README, step 3b):
 * crc32(c, w, 20 * BLOCKS), the call the adapter and part D make, for every
 * start value c and every message w of 5 * BLOCKS aligned words equals a
 * formula written with zlib's own tables: XOR, the complement of c, braid()
 * (braid.h: four lookups in crc_braid_table) and crc_word(). zlib 1.4 on a
 * 32-bit core: W = 4, N = 5. CONTROL: one wrong result, must fail. */
#include <stddef.h>
#include <stdint.h>
#include "crc32.c"
#include "braid.h"
uint32_t nondet_u32(void);
#ifndef BLOCKS
#define BLOCKS 2
#endif
static uint32_t w[5 * BLOCKS];
int main(void)
{
    uint32_t c = nondet_u32();
    for (int i = 0; i < 5 * BLOCKS; i++) w[i] = nondet_u32();
    uint32_t got = (uint32_t)crc32(c, (const unsigned char *)w, 20 * BLOCKS);
    uint32_t b[5] = { ~c, 0, 0, 0, 0 };
    const uint32_t *p = w;
    for (int k = 1; k < BLOCKS; k++, p += 5)
        for (int i = 0; i < 5; i++) b[i] = braid(b[i] ^ p[i]);
    uint32_t x = 0;
    for (int i = 0; i < 5; i++) x = crc_word(b[i] ^ p[i] ^ x);
#ifdef CONTROL
    x ^= (c == 0x12345678u && w[7] == 0x9ABCDEF0u);
#endif
    __CPROVER_assert(got == ~x, "crc32 is the formula of its tables");
    return 0;
}
