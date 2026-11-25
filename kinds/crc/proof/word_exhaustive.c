/* The CRC kind, step 3b, part 2 of the proof of crcany's slicing by 4 (see
 * word_lemma.c): word(x, 0) == ref(x, 0) for every one of the 2^32 values x,
 * where word(x, 0) is crc32iso_hdlc_word(x, four zero bytes, aligned, 4) and
 * ref(x, 0) is ref32_final(ref32_update(x ^ ~0, four zero bytes, 4)).
 * Every x is computed; the range is split over threads. Built for the host
 * by the Makefile (make proof); with -DCONTROL one result (x = 0x12345678)
 * is made wrong, and exactly that one mismatch must be reported.
 * Prints the number of values checked and of mismatches (the first few).
 */
#include <inttypes.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "ref_crc.h"
#include "crc32iso_hdlc.h"

#define SHOW 8

struct part {
    uint64_t lo, hi, bad;
    uint32_t first[SHOW];
};

static void *run(void *arg)
{
    struct part *p = arg;
    static const uint32_t zero[1] = {0};
    for (uint64_t i = p->lo; i < p->hi; i++) {
        uint32_t x = (uint32_t)i;
        uint32_t got = crc32iso_hdlc_word(x, zero, 4);
#ifdef CONTROL
        got ^= (x == 0x12345678u);
#endif
        uint32_t want = ref32_final(ref32_update(x ^ 0xFFFFFFFFu, zero, 4));
        if (got != want) {
            if (p->bad < SHOW) p->first[p->bad] = x;
            p->bad++;
        }
    }
    return NULL;
}

int main(void)
{
    long n = sysconf(_SC_NPROCESSORS_ONLN);
    if (n < 1) n = 1;
    if (n > 64) n = 64;
    struct part parts[64] = {0};
    pthread_t t[64];
    const uint64_t total = (uint64_t)1 << 32;
    for (long k = 0; k < n; k++) {
        parts[k].lo = total * k / n;
        parts[k].hi = total * (k + 1) / n;
        if (pthread_create(&t[k], NULL, run, &parts[k])) { perror("pthread_create"); return 2; }
    }
    uint64_t bad = 0, checked = 0;
    for (long k = 0; k < n; k++) {
        pthread_join(t[k], NULL);
        checked += parts[k].hi - parts[k].lo;
        for (uint64_t j = 0; j < parts[k].bad && j < SHOW; j++)
            printf("mismatch at x = 0x%08" PRIx32 "\n", parts[k].first[j]);
        bad += parts[k].bad;
    }
    printf("%" PRIu64 " values checked (%ld threads), %" PRIu64 " mismatches\n", checked, n, bad);
    return bad != 0;
}
