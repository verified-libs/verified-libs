/* libcrc (src/crc32.c, src/crcccitt.c): crc_32 and crc_ccitt_ffff, one call
 * per message, with tables of 256 that the library builds in RAM on its first
 * call; init() makes that first call, so the timed calls find the tables
 * built. Streaming: the library's own per-byte functions update_crc_32 and
 * update_crc_ccitt, which keep the register; the adapter adds the start value
 * and the final XOR its header gives (include/checksum.h: CRC_START_32,
 * CRC_START_CCITT_FFFF; crc_32 ends with "crc ^= 0xffffffffL"). */
#include "adapters.h"
#include "checksum.h"

static void lc32_init(void) { (void)crc_32((const unsigned char *)"", 0); }
static void lc16_init(void) { (void)crc_ccitt_ffff((const unsigned char *)"", 0); }

static uint32_t lc32_crc(uintptr_t a, uintptr_t b) { return crc_32((const unsigned char *)a, (size_t)b); }
static uint32_t lc32_state;
static uint32_t lc32_begin(uintptr_t a, uintptr_t b) { (void)a; (void)b; lc32_state = CRC_START_32; return 0; }
static uint32_t lc32_update(uintptr_t a, uintptr_t b)
{
    const unsigned char *p = (const unsigned char *)a;
    for (size_t i = 0; i < (size_t)b; i++) lc32_state = update_crc_32(lc32_state, p[i]);
    return 0;
}
static uint32_t lc32_final(uintptr_t a, uintptr_t b) { (void)a; (void)b; return lc32_state ^ 0xFFFFFFFFu; }
const crc_adapter adapter_libcrc_crc32 = { "libcrc crc_32", "libcrc", CRC32_ISO_HDLC, CLS_TABLE256, 0, 1, NULL,
    lc32_init, lc32_crc, CRC_STREAM(lc32_begin, lc32_update, lc32_final) };

static uint32_t lc16_crc(uintptr_t a, uintptr_t b) { return crc_ccitt_ffff((const unsigned char *)a, (size_t)b); }
static uint16_t lc16_state;
static uint32_t lc16_begin(uintptr_t a, uintptr_t b) { (void)a; (void)b; lc16_state = CRC_START_CCITT_FFFF; return 0; }
static uint32_t lc16_update(uintptr_t a, uintptr_t b)
{
    const unsigned char *p = (const unsigned char *)a;
    for (size_t i = 0; i < (size_t)b; i++) lc16_state = update_crc_ccitt(lc16_state, p[i]);
    return 0;
}
static uint32_t lc16_final(uintptr_t a, uintptr_t b) { (void)a; (void)b; return lc16_state; }
const crc_adapter adapter_libcrc_ccitt_ffff = { "libcrc crc_ccitt_ffff", "libcrc", CRC16_IBM_3740, CLS_TABLE256, 0, 1, NULL,
    lc16_init, lc16_crc, CRC_STREAM(lc16_begin, lc16_update, lc16_final) };
