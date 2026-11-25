/* Checks of the reference itself (step 1 of the plan), run by ref_check.py:
 *   ref_check self      the catalogue's check value and residue per CRC:
 *                       "<crc> check|residue <got> <want> pass|FAIL"
 *   ref_check random N  N random messages per CRC, as "<crc> <hex bytes> <crc>",
 *                       for the second, independent implementation (Python's
 *                       zlib.crc32 and binascii.crc_hqx) in ref_check.py
 * Built normally and with REF_WRONG=1..4 (ref_crc.c). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ref_crc.h"

static uint32_t rng = 0x2545F491u;
static uint32_t xs(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }

int main(int argc, char **argv)
{
    if (argc >= 2 && !strcmp(argv[1], "self")) {
        static const uint8_t msg[] = "123456789";
        for (int id = 0; id < CRC_COUNT; id++) {
            const crc_params *p = &CRC_PARAMS[id];
            uint32_t c = ref_crc((crc_id)id, msg, 9);
            printf("%s check %08x %08x %s\n", p->name, c, p->check, c == p->check ? "pass" : "FAIL");
            /* The codeword: the message, then the CRC in the order it is sent:
             * least significant byte first for a reflected CRC, most
             * significant first otherwise (the catalogue's convention). */
            uint8_t cw[16];
            memcpy(cw, msg, 9);
            unsigned nb = p->width / 8u;
            for (unsigned i = 0; i < nb; i++)
                cw[9 + i] = (uint8_t)(p->refout ? c >> (8 * i) : c >> (8 * (nb - 1 - i)));
            uint32_t r = ref_update((crc_id)id, ref_start((crc_id)id), cw, 9 + nb);
            printf("%s residue %08x %08x %s\n", p->name, r, p->residue, r == p->residue ? "pass" : "FAIL");
        }
        return 0;
    }
    if (argc >= 3 && !strcmp(argv[1], "random")) {
        unsigned n = (unsigned)strtoul(argv[2], NULL, 0);
        uint8_t buf[512];
        for (int id = 0; id < CRC_COUNT; id++)
            for (unsigned k = 0; k < n; k++) {
                size_t len = k < 64 ? k : xs() % sizeof buf;   /* every length to 63, then random */
                for (size_t i = 0; i < len; i++) buf[i] = (uint8_t)xs();
                printf("%s ", CRC_PARAMS[id].name);
                for (size_t i = 0; i < len; i++) printf("%02x", buf[i]);
                printf("%s %08x\n", len ? "" : "-", ref_crc((crc_id)id, buf, len));
            }
        return 0;
    }
    fprintf(stderr, "usage: ref_check self | random N\n");
    return 2;
}
