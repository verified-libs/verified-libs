/* Every adapter of the CRC kind: the first configurations (README.md, step
 * 2), the reference and the deliberately broken ones of the host test. */
#pragma once
#include "crc.h"

#ifdef __cplusplus
extern "C" {
#endif

/* the reference, the baseline (ref_crc.c) */
extern const crc_adapter adapter_ref32, adapter_ref16, adapter_ref8;
/* the first configurations */
extern const crc_adapter adapter_etl_crc32_t256, adapter_etl_crc32_t16;
extern const crc_adapter adapter_etl_crc16_t256, adapter_etl_crc16_t16;
extern const crc_adapter adapter_etl_crc8_t256, adapter_etl_crc8_t16;
extern const crc_adapter adapter_crcany_crc32_bit, adapter_crcany_crc32_byte, adapter_crcany_crc32_word;
extern const crc_adapter adapter_crcany_crc16_byte, adapter_crcany_crc8_byte;
extern const crc_adapter adapter_zlib_crc32;
extern const crc_adapter adapter_libcrc_crc32, adapter_libcrc_ccitt_ffff;
extern const crc_adapter adapter_zephyr_crc32_ieee, adapter_zephyr_crc16_itu_t, adapter_zephyr_crc8_ccitt;
extern const crc_adapter adapter_acecrc_crc8_byte;
extern const crc_adapter adapter_crcpp_ccittfalse_table;
extern const crc_adapter adapter_rust_crc32_table1;
/* the boards' CRC hardware, driven by our code (adapter_hw.c; boards.txt names the boards) */
extern const crc_adapter adapter_hw_crc32, adapter_hw_crc16, adapter_hw_crc8;
/* host test only: zlib with the boards' word size (adapter_zlib.c, ZLIB_W4) */
extern const crc_adapter adapter_zlib_crc32_w4;
/* deliberately broken, host test only (adapters_broken.c) */
extern const crc_adapter adapter_broken_table, adapter_broken_init, adapter_broken_xorout;
extern const crc_adapter adapter_broken_tail, adapter_broken_state;

#ifdef __cplusplus
}
#endif
