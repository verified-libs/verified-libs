/* AceCRC (src/ace_crc/crc8_byte.*, generated with pycrc 0.10.0): CRC-8 with a
 * table of 256 in flash. Its crc8 is polynomial 0x07, initial value 0, no
 * reflection, no final XOR (the parameters in the generated file's comment),
 * that is CRC-8/SMBUS. Its crc16ccitt is another CRC (its README gives the
 * check 0xE5CC, CRC-16/SPI-FUJITSU) and is not used here. */
#include "adapters.h"
#include "ace_crc/crc8_byte.hpp"

using namespace ace_crc;
static uint32_t ace8_crc(uintptr_t a, uintptr_t b) { return crc8_byte::crc_calculate((const void *)a, (size_t)b); }
static crc8_byte::crc_t ace8_state;
static uint32_t ace8_begin(uintptr_t, uintptr_t) { ace8_state = crc8_byte::crc_init(); return 0; }
static uint32_t ace8_update(uintptr_t a, uintptr_t b) { ace8_state = crc8_byte::crc_update(ace8_state, (const void *)a, (size_t)b); return 0; }
static uint32_t ace8_final(uintptr_t, uintptr_t) { return crc8_byte::crc_finalize(ace8_state); }
extern "C" const crc_adapter adapter_acecrc_crc8_byte = { "acecrc crc8_byte", "acecrc", CRC8_SMBUS, CLS_TABLE256, 0, 0, NULL,
    NULL, ace8_crc, CRC_STREAM(ace8_begin, ace8_update, ace8_final) };
