/* The crc crate (Rust, rust/src/lib.rs): CRC-32/ISO-HDLC with Table<1>, a
 * table of 256 computed at compile time. */
#include "adapters.h"

uint32_t vl_crc_rs_crc32(const uint8_t *p, size_t n);
void vl_crc_rs_begin(void);
void vl_crc_rs_update(const uint8_t *p, size_t n);
uint32_t vl_crc_rs_final(void);

static uint32_t rs_crc(uintptr_t a, uintptr_t b) { return vl_crc_rs_crc32((const uint8_t *)a, (size_t)b); }
static uint32_t rs_begin(uintptr_t a, uintptr_t b) { (void)a; (void)b; vl_crc_rs_begin(); return 0; }
static uint32_t rs_update(uintptr_t a, uintptr_t b) { vl_crc_rs_update((const uint8_t *)a, (size_t)b); return 0; }
static uint32_t rs_final(uintptr_t a, uintptr_t b) { (void)a; (void)b; return vl_crc_rs_final(); }
const crc_adapter adapter_rust_crc32_table1 = { "crc (Rust) Table<1>", "crc-rs", CRC32_ISO_HDLC, CLS_TABLE256, 0, 0, NULL,
    NULL, rs_crc, CRC_STREAM(rs_begin, rs_update, rs_final) };
