/* Zephyr's software CRCs (subsys/crc/crc32_sw.c, crc16_sw.c, crc8_sw.c of
 * v4.5.0), built alone with two small headers in shims/zephyr. Every function
 * takes the previous value, so streaming carries it:
 *   crc32_ieee_update(crc, data, len): CRC-32/ISO-HDLC, a table of 16,
 *     continues from a CRC value (0 to start; crc32_ieee() passes 0);
 *   crc16_itu_t(seed, src, len): polynomial 0x1021 without reflection or
 *     final XOR, computed with shifts and XORs and no table; with the seed
 *     0xFFFF that is CRC-16/IBM-3740;
 *   crc8_ccitt(val, buf, cnt): polynomial 0x07, a table of 16; with the
 *     initial value 0 that is CRC-8/SMBUS (Zephyr's own
 *     CRC8_CCITT_INITIAL_VALUE is 0xFF, which is another CRC). */
#include "adapters.h"
#include <zephyr/sys/crc.h>

static uint32_t z32_crc(uintptr_t a, uintptr_t b) { return crc32_ieee((const uint8_t *)a, (size_t)b); }
static uint32_t z32_state;
static uint32_t z32_begin(uintptr_t a, uintptr_t b) { (void)a; (void)b; z32_state = 0; return 0; }
static uint32_t z32_update(uintptr_t a, uintptr_t b) { z32_state = crc32_ieee_update(z32_state, (const uint8_t *)a, (size_t)b); return 0; }
static uint32_t z32_final(uintptr_t a, uintptr_t b) { (void)a; (void)b; return z32_state; }
const crc_adapter adapter_zephyr_crc32_ieee = { "zephyr crc32_ieee", "zephyr", CRC32_ISO_HDLC, CLS_TABLE16, 0, 0, NULL,
    NULL, z32_crc, CRC_STREAM(z32_begin, z32_update, z32_final) };

static uint32_t z16_crc(uintptr_t a, uintptr_t b) { return crc16_itu_t(0xFFFF, (const uint8_t *)a, (size_t)b); }
static uint16_t z16_state;
static uint32_t z16_begin(uintptr_t a, uintptr_t b) { (void)a; (void)b; z16_state = 0xFFFF; return 0; }
static uint32_t z16_update(uintptr_t a, uintptr_t b) { z16_state = crc16_itu_t(z16_state, (const uint8_t *)a, (size_t)b); return 0; }
static uint32_t z16_final(uintptr_t a, uintptr_t b) { (void)a; (void)b; return z16_state; }
const crc_adapter adapter_zephyr_crc16_itu_t = { "zephyr crc16_itu_t", "zephyr", CRC16_IBM_3740, CLS_OTHER, 0, 0,
    "one byte per step with shifts and XORs, no table",
    NULL, z16_crc, CRC_STREAM(z16_begin, z16_update, z16_final) };

static uint32_t z8_crc(uintptr_t a, uintptr_t b) { return crc8_ccitt(0, (const void *)a, (size_t)b); }
static uint8_t z8_state;
static uint32_t z8_begin(uintptr_t a, uintptr_t b) { (void)a; (void)b; z8_state = 0; return 0; }
static uint32_t z8_update(uintptr_t a, uintptr_t b) { z8_state = crc8_ccitt(z8_state, (const void *)a, (size_t)b); return 0; }
static uint32_t z8_final(uintptr_t a, uintptr_t b) { (void)a; (void)b; return z8_state; }
const crc_adapter adapter_zephyr_crc8_ccitt = { "zephyr crc8_ccitt", "zephyr", CRC8_SMBUS, CLS_TABLE16, 0, 0, NULL,
    NULL, z8_crc, CRC_STREAM(z8_begin, z8_update, z8_final) };
