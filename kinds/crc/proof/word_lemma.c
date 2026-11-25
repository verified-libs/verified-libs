/* The CRC kind, step 3b: crcany's slicing by 4 (crc32iso_hdlc_word), one
 * 4-byte step, in two parts that together cover every previous CRC c and
 * every aligned 4-byte message w (2^64 inputs):
 *
 *   1. this file, checked by CBMC (proof/run.sh): the library's result and
 *      the reference's depend only on c ^ w:
 *        LEMMA_LIB  word(c, w) == word(c ^ w, 0)
 *        LEMMA_REF  ref(c, w)  == ref(c ^ w, 0)
 *   2. word_exhaustive.c, run on the host: word(x, 0) == ref(x, 0) for every
 *      one of the 2^32 values x.
 *
 * So word(c, w) = word(c ^ w, 0) = ref(c ^ w, 0) = ref(c, w) for every c, w.
 * The one SAT problem that does not finish within 60 minutes (four table
 * lookups XORed against the bitwise reference) is replaced by two that only
 * compare a function with itself, and an enumeration.
 * ref(c, w) is the claim of harness.c: ref32_final(ref32_update(c ^ ~0, w, 4)).
 */
#include <stddef.h>
#include <stdint.h>
#include "ref_crc.h"
#include "crc32iso_hdlc.h"

uint32_t nondet_u32(void);

static uint32_t w4[1], z4[1];

int main(void)
{
    uint32_t c = nondet_u32(), w = nondet_u32();
    w4[0] = w;
    z4[0] = 0;
#if defined(LEMMA_LIB)
    __CPROVER_assert(crc32iso_hdlc_word(c, w4, 4) == crc32iso_hdlc_word(c ^ w, z4, 4),
                     "the library's 4-byte step depends only on crc ^ word");
#elif defined(LEMMA_REF)
    __CPROVER_assert(ref32_final(ref32_update(c ^ 0xFFFFFFFFu, w4, 4)) ==
                     ref32_final(ref32_update((c ^ w) ^ 0xFFFFFFFFu, z4, 4)),
                     "the reference's 4-byte step depends only on crc ^ word");
#elif defined(LEMMA_CONTROL)
    /* must fail: a dependence on w alone, at one input in 2^64 */
    __CPROVER_assert(crc32iso_hdlc_word(c, w4, 4) ==
                     (crc32iso_hdlc_word(c ^ w, z4, 4) ^ (c == 0x12345678u && w == 0x9ABCDEF0u)),
                     "control: must fail");
#else
#error choose LEMMA_LIB, LEMMA_REF or LEMMA_CONTROL
#endif
    return 0;
}
