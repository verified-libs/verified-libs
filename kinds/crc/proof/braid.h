/* braid(): one step of a braid of zlib's braided loop (crc32.c of v1.4, W = 4):
 * the four lookups in crc_braid_table that the loop makes for one word. The one
 * text of it that part A (braid_formula.c, CBMC) and part B (braid_linear.c, on
 * the host) both use; include it after crc32.c. */
#ifndef VL_BRAID_H
#define VL_BRAID_H
#include <stdint.h>
static uint32_t braid(uint32_t x)
{
    return crc_braid_table[0][x & 0xff] ^ crc_braid_table[1][(x >> 8) & 0xff] ^
           crc_braid_table[2][(x >> 16) & 0xff] ^ crc_braid_table[3][(x >> 24) & 0xff];
}
#endif
