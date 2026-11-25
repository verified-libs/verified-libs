/* Deliberately broken adapters, for the host test only: each has one fault,
 * and each must be caught by the check made for it (test_crc.c, "expect").
 * They are ours, built on the reference; no library is involved.
 *   broken_table   CRC-16 with a table of 256 of which one entry has one bit
 *                  wrong: caught by "step" (every state and byte);
 *   broken_init    CRC-32 with a wrong initial value: caught by "check";
 *   broken_xorout  CRC-32 without the final XOR: caught by "check";
 *   broken_tail    CRC-32 that skips the last len % 4 bytes, as word-wise
 *                  code with a missing tail loop would: caught by "lengths";
 *   broken_state   CRC-32 whose update starts again in every call (the state
 *                  not carried between two calls): right in one call, caught
 *                  by "splits". */
#include "adapters.h"
#include "ref_crc.h"

static uint16_t bt_table[256];
static void bt_init(void)
{
    for (unsigned i = 0; i < 256; i++) {
        /* the table of the left-shifting CRC-16: the register after one step
         * from (i << 8) with a zero byte */
        const uint8_t zero = 0;
        bt_table[i] = (uint16_t)ref16_update((uint32_t)i << 8, &zero, 1);
    }
    bt_table[0xA7] ^= 0x0100;   /* the fault */
}
static uint16_t bt_update(uint16_t reg, const uint8_t *p, size_t n)
{
    while (n--) reg = (uint16_t)((reg << 8) ^ bt_table[(reg >> 8) ^ *p++]);
    return reg;
}
static uint32_t bt_crc(uintptr_t a, uintptr_t b) { return bt_update(0xFFFF, (const uint8_t *)a, (size_t)b); }
const crc_adapter adapter_broken_table = { "broken: one table entry wrong", "ours", CRC16_IBM_3740, CLS_TABLE256, 0, 1, NULL,
    bt_init, bt_crc, NULL, NULL, NULL };

static uint32_t bi_crc(uintptr_t a, uintptr_t b) { return ref32_final(ref32_update(ref32_start() ^ 0x10u, (const void *)a, (size_t)b)); }
const crc_adapter adapter_broken_init = { "broken: wrong initial value", "ours", CRC32_ISO_HDLC, CLS_BITWISE, 0, 0, NULL,
    NULL, bi_crc, NULL, NULL, NULL };

static uint32_t bx_crc(uintptr_t a, uintptr_t b) { return ref32_update(ref32_start(), (const void *)a, (size_t)b); }
const crc_adapter adapter_broken_xorout = { "broken: no final XOR", "ours", CRC32_ISO_HDLC, CLS_BITWISE, 0, 0, NULL,
    NULL, bx_crc, NULL, NULL, NULL };

static uint32_t bl_crc(uintptr_t a, uintptr_t b) { return ref32_final(ref32_update(ref32_start(), (const void *)a, (size_t)b & ~(size_t)3)); }
const crc_adapter adapter_broken_tail = { "broken: last len % 4 bytes skipped", "ours", CRC32_ISO_HDLC, CLS_BITWISE, 0, 0, NULL,
    NULL, bl_crc, NULL, NULL, NULL };

static uint32_t bs_reg;
static uint32_t bs_crc(uintptr_t a, uintptr_t b) { return ref32_final(ref32_update(ref32_start(), (const void *)a, (size_t)b)); }
static uint32_t bs_begin(uintptr_t a, uintptr_t b) { (void)a; (void)b; bs_reg = ref32_start(); return 0; }
static uint32_t bs_update(uintptr_t a, uintptr_t b) { bs_reg = ref32_update(ref32_start(), (const void *)a, (size_t)b); return 0; }
static uint32_t bs_final(uintptr_t a, uintptr_t b) { (void)a; (void)b; return ref32_final(bs_reg); }
const crc_adapter adapter_broken_state = { "broken: state not carried", "ours", CRC32_ISO_HDLC, CLS_BITWISE, 0, 0, NULL,
    NULL, bs_crc, bs_begin, bs_update, bs_final };
