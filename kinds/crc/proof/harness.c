/* CBMC harnesses for CRC-32/ISO-HDLC (step 3 of the plan): one configuration
 * of each class against the reference (../ref_crc.c), for every previous CRC
 * value and every input byte or word. Built with one of:
 *   -DH_CRCANY_BYTE   crcany crc32iso_hdlc_byte  (table of 256)
 *   -DH_ZEPHYR        zephyr crc32_ieee_update   (table of 16)
 *   -DH_CRCANY_WORD   crcany crc32iso_hdlc_word  (slicing by 4)
 *   -DH_CRCANY_BIT    crcany crc32iso_hdlc_bit   (bitwise)
 *   -DH_ZLIB          zlib crc32                 (braided words)
 *   -DH_CONTROL       crcany crc32iso_hdlc_byte with a fault at one input of
 *                     2^40 (previous CRC 0x12345678, byte 0x5A): a control
 *                     that must FAIL, to show the proof covers every input
 * and MSG_LEN, the number of message bytes (each byte nondeterministic), and OFF,
 * the offset of the message in a 4-byte aligned buffer. Every routine here
 * continues from a previous CRC value c; the reference's register for c is
 * c XOR 0xFFFFFFFF (ref_crc.c: the reflected register, final XOR all ones).
 * The claim proven: for every c and every MSG_LEN-byte message at that offset, the
 * library's result equals the reference's. */
#include <stddef.h>
#include <stdint.h>
#include "ref_crc.h"

uint32_t nondet_u32(void);
uint8_t nondet_u8(void);

#if defined(H_CRCANY_BYTE) || defined(H_CRCANY_WORD) || defined(H_CRCANY_BIT) || defined(H_CONTROL)
#include "crc32iso_hdlc.h"
#endif
#ifdef H_ZEPHYR
uint32_t crc32_ieee_update(uint32_t crc, const uint8_t *data, size_t len);
#endif
#ifdef H_ZLIB
#include "zlib.h"
#endif

#ifndef OFF
#define OFF 0
#endif

static uint32_t lib(uint32_t c, const uint8_t *p, size_t n)
{
#if defined(H_CRCANY_BYTE)
    return crc32iso_hdlc_byte(c, p, n);
#elif defined(H_CRCANY_WORD)
    return crc32iso_hdlc_word(c, p, n);
#elif defined(H_CRCANY_BIT)
    return crc32iso_hdlc_bit(c, p, n);
#elif defined(H_ZEPHYR)
    return crc32_ieee_update(c, p, n);
#elif defined(H_ZLIB)
    return (uint32_t)crc32(c, p, (uInt)n);
#elif defined(H_CONTROL)
    return crc32iso_hdlc_byte(c, p, n) ^ (c == 0x12345678u && n == 1 && p[0] == 0x5A);
#else
#error choose a harness
#endif
}

static uint32_t buf32[(MSG_LEN + OFF + 3) / 4 + 1];

int main(void)
{
    uint8_t *msg = (uint8_t *)buf32 + OFF;
    for (size_t i = 0; i < MSG_LEN; i++) msg[i] = nondet_u8();
    uint32_t c = nondet_u32();
    uint32_t got = lib(c, msg, MSG_LEN);
    uint32_t want = ref32_final(ref32_update(c ^ 0xFFFFFFFFu, msg, MSG_LEN));
    __CPROVER_assert(got == want, "equal to the reference for every previous CRC and message");
    return 0;
}
