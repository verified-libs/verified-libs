/* Part B, on the host (-DZ_TESTW=4, so zlib's 4-byte tables and
 * crc_word()): braid(), crc_word() and the reference over four zero bytes
 * are linear over GF(2): for each of the 2^32 values x, f(x) is the XOR of
 * f at the set bits of x. Computed, not sampled. CONTROL: one wrong value
 * per function, must report exactly 1 for each. */
#include <inttypes.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>
#include "crc32.c"
#include "ref_crc.h"
#include "braid.h"
static uint32_t f_braid(uint32_t x) { return braid(x); }
static uint32_t f_word(uint32_t x) { return crc_word(x); }
static uint32_t f_ref(uint32_t x) { static const uint32_t z[1] = {0}; return ref32_update(x, z, 4); }
static uint32_t (*const F[3])(uint32_t) = { f_braid, f_word, f_ref };
static const char *const NAME[3] = { "braid", "crc_word", "reference, four zero bytes" };
static uint32_t M[4][256];   /* the function as the sum of its values at the 32 single bits */
static uint32_t (*f)(uint32_t);
struct part { uint64_t lo, hi, bad; };
static void *run(void *arg)
{
    struct part *p = arg;
    for (uint64_t i = p->lo; i < p->hi; i++) {
        uint32_t x = (uint32_t)i, got = f(x);
#ifdef CONTROL
        got ^= (x == 0x12345678u);
#endif
        p->bad += got != (M[0][x & 0xff] ^ M[1][(x >> 8) & 0xff] ^ M[2][(x >> 16) & 0xff] ^ M[3][x >> 24]);
    }
    return NULL;
}
int main(void)
{
    long n = sysconf(_SC_NPROCESSORS_ONLN);
    if (n > 64) n = 64;
    int rc = 0;
    for (int which = 0; which < 3; which++) {
        f = F[which];
        for (int k = 0; k < 4; k++)
            for (int v = 0; v < 256; v++) {
                M[k][v] = 0;
                for (int j = 0; j < 8; j++) if (v >> j & 1) M[k][v] ^= f((uint32_t)1 << (8 * k + j));
            }
        struct part parts[64] = {0}; pthread_t t[64]; uint64_t bad = 0;
        for (long k = 0; k < n; k++) {
            parts[k].lo = ((uint64_t)1 << 32) * k / n; parts[k].hi = ((uint64_t)1 << 32) * (k + 1) / n;
            pthread_create(&t[k], NULL, run, &parts[k]);
        }
        for (long k = 0; k < n; k++) { pthread_join(t[k], NULL); bad += parts[k].bad; }
        printf("%s: 4294967296 values, %" PRIu64 " not the sum of its bits\n", NAME[which], bad);
        rc |= bad != 0;
    }
    return rc;
}
