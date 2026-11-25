/* zlib crc32 (crc32.c of v1.4): crc32(crc, buf, len) continues from the
 * previous CRC value (0 to start), with the "braided" code over words for long
 * buffers and a byte table otherwise.
 *
 * The word size of the braided code is the library's choice by platform:
 * 8 bytes on x86-64 and AArch64, 4 bytes elsewhere, so 4 on the boards and 8
 * in the host test; the two are different loops with different tables. With
 * ZLIB_W4 (host test only, Makefile) this file is the adapter of a second
 * build of crc32.c with 4-byte words (the library's own Z_TESTW=4) under the
 * library's own name prefix (Z_PREFIX: z_crc32), so the host test runs the
 * boards' code beside the host's. */
#include "adapters.h"
#include "zlib.h"

#ifdef ZLIB_W4
#define ADAPTER adapter_zlib_crc32_w4
#define NAME    "zlib crc32, 4-byte words (boards)"
#else
#define ADAPTER adapter_zlib_crc32
#define NAME    "zlib crc32"
#endif

static uint32_t z_crc(uintptr_t a, uintptr_t b) { return (uint32_t)crc32(0, (const Bytef *)a, (uInt)b); }
static uint32_t z_state;
static uint32_t z_begin(uintptr_t a, uintptr_t b) { (void)a; (void)b; z_state = 0; return 0; }
static uint32_t z_update(uintptr_t a, uintptr_t b) { z_state = (uint32_t)crc32(z_state, (const Bytef *)a, (uInt)b); return 0; }
static uint32_t z_final(uintptr_t a, uintptr_t b) { (void)a; (void)b; return z_state; }
const crc_adapter ADAPTER = { NAME, "zlib", CRC32_ISO_HDLC, CLS_OTHER, 0, 0,
    "braided: several words per step with tables of 256 per byte of a word, a byte table for the rest",
    NULL, z_crc, CRC_STREAM(z_begin, z_update, z_final) };
