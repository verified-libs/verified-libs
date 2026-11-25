/* The host test of the CRC kind (step 3 of the plan): every configuration
 * against the reference (ref_crc.c), and the deliberately broken adapters
 * (adapters_broken.c), each of which must be caught by the check made for it.
 * README.md gives the output of a run. zlib is here twice: as the host builds
 * it (8-byte words) and with the 4-byte words of the boards (adapter_zlib.c).
 *
 * Checks, per adapter:
 *   check    the catalogue's check value: the CRC of "123456789";
 *   lengths  every length from 0 to 300 bytes at every start alignment from
 *            0 to 7, random bytes (xorshift32, fixed seeds). The message is
 *            copied to the end of a buffer of its own from malloc, so a read
 *            past its last byte runs into the sanitizer's red zone in the
 *            sanitizer build;
 *   splits   (streaming adapters) every length from 0 to 300 cut at every
 *            point into two update calls, and the same with an empty update
 *            between them;
 *   step     every input of one step. A CRC register after w/8 bytes takes
 *            every value exactly once over all messages of w/8 bytes (the map
 *            is affine and invertible; the test checks it for the reference
 *            before it relies on it). So all messages of w/8 + 1 bytes give
 *            every pair (state, byte) of the last step exactly once:
 *              CRC-8: all 2^16 messages of 2 bytes;
 *              CRC-16: all 2^24 messages of 3 bytes.
 *            For CRC-32 that would be 2^40 messages; the test runs all 256
 *            last bytes after 65536 random 4-byte prefixes and reports it as
 *            "sampled". The proof for CRC-32 is separate (proof/).
 * Exit 0 if every configuration passes every check and every broken adapter
 * fails the check named for it; 1 otherwise. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "adapters.h"
#include "ref_crc.h"

enum { C_CHECK, C_LENGTHS, C_SPLITS, C_STEP, C_N };
static const char *const CHECK_NAME[C_N] = { "check", "lengths", "splits", "step" };
enum { NA = -1, FAIL = 0, PASS = 1 };

static const struct { const crc_adapter *ad; int expect_fail; } CASES[] = {
    { &adapter_ref32, -1 }, { &adapter_ref16, -1 }, { &adapter_ref8, -1 },
    { &adapter_broken_table, C_STEP }, { &adapter_broken_init, C_CHECK }, { &adapter_broken_xorout, C_CHECK },
    { &adapter_broken_tail, C_LENGTHS }, { &adapter_broken_state, C_SPLITS },
    { &adapter_etl_crc32_t256, -1 }, { &adapter_crcany_crc32_byte, -1 }, { &adapter_libcrc_crc32, -1 },
    { &adapter_rust_crc32_table1, -1 },
    { &adapter_etl_crc32_t16, -1 }, { &adapter_zephyr_crc32_ieee, -1 },
    { &adapter_crcany_crc32_word, -1 }, { &adapter_zlib_crc32, -1 }, { &adapter_zlib_crc32_w4, -1 },
    { &adapter_crcany_crc32_bit, -1 },
    { &adapter_etl_crc16_t256, -1 }, { &adapter_crcany_crc16_byte, -1 }, { &adapter_libcrc_ccitt_ffff, -1 },
    { &adapter_crcpp_ccittfalse_table, -1 },
    { &adapter_etl_crc16_t16, -1 }, { &adapter_zephyr_crc16_itu_t, -1 },
    { &adapter_etl_crc8_t256, -1 }, { &adapter_crcany_crc8_byte, -1 }, { &adapter_acecrc_crc8_byte, -1 },
    { &adapter_etl_crc8_t16, -1 }, { &adapter_zephyr_crc8_ccitt, -1 },
};

static uint32_t rng;
static uint32_t xs(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }

static char detail[160];

static uint32_t one(const crc_adapter *ad, const uint8_t *p, size_t n) { return ad->crc((uintptr_t)p, (uintptr_t)n); }

static int check_value(const crc_adapter *ad)
{
    static const uint8_t msg[9] = { '1', '2', '3', '4', '5', '6', '7', '8', '9' };
    uint8_t *buf = malloc(9);
    memcpy(buf, msg, 9);
    uint32_t c = one(ad, buf, 9);
    free(buf);
    if (c != CRC_PARAMS[ad->id].check) {
        snprintf(detail, sizeof detail, "check: %#x, the catalogue gives %#x", c, CRC_PARAMS[ad->id].check);
        return FAIL;
    }
    return PASS;
}

static int lengths(const crc_adapter *ad)
{
    uint8_t data[300];
    for (unsigned len = 0; len <= 300; len++)
        for (unsigned al = 0; al < 8; al++) {
            rng = 0x9E3779B9u ^ (len * 2654435761u) ^ (al * 40503u);
            for (unsigned i = 0; i < len; i++) data[i] = (uint8_t)xs();
            uint8_t *buf = malloc(len + al + 1);       /* +1: malloc(0) */
            uint8_t *p = buf + al;
            if (((uintptr_t)buf & 7u) != 0) { printf("malloc gave memory not aligned to 8\n"); exit(2); }
            memcpy(p, data, len);
            uint32_t got = one(ad, p, len), want = ref_crc(ad->id, data, len);
            free(buf);
            if (got != want) {
                snprintf(detail, sizeof detail, "lengths: length %u at alignment %u: %#x, the reference gives %#x", len, al, got, want);
                return FAIL;
            }
        }
    return PASS;
}

static int splits(const crc_adapter *ad)
{
    if (!ad->begin) return NA;
    uint8_t data[300];
    rng = 0x51ED270Bu;
    for (unsigned i = 0; i < 300; i++) data[i] = (uint8_t)xs();
    for (unsigned len = 0; len <= 300; len++) {
        uint32_t want = ref_crc(ad->id, data, len);
        uint8_t *buf = malloc(len + 1);
        memcpy(buf, data, len);
        for (unsigned k = 0; k <= len; k++)
            for (int empty = 0; empty < 2; empty++) {
                ad->begin(0, 0);
                ad->update((uintptr_t)buf, k);
                if (empty) ad->update((uintptr_t)(buf + k), 0);
                ad->update((uintptr_t)(buf + k), len - k);
                uint32_t got = ad->final(0, 0);
                if (got != want) {
                    free(buf);
                    snprintf(detail, sizeof detail, "splits: length %u cut at %u%s: %#x, the reference gives %#x",
                             len, k, empty ? " with an empty update" : "", got, want);
                    return FAIL;
                }
            }
        free(buf);
    }
    return PASS;
}

/* The precondition of "step": over all messages of w/8 bytes the reference's
 * register takes every value once (CRC-8 and CRC-16). */
static int bijective(crc_id id)
{
    unsigned nb = CRC_PARAMS[id].width / 8u;
    size_t n = (size_t)1 << (8 * nb);
    uint8_t *seen = calloc(n, 1);
    int ok = 1;
    for (size_t m = 0; m < n; m++) {
        uint8_t msg[2] = { (uint8_t)m, (uint8_t)(m >> 8) };
        uint32_t reg = ref_update(id, ref_start(id), msg, nb);
        if (seen[reg]) ok = 0;
        seen[reg] = 1;
    }
    free(seen);
    return ok;
}

static int step(const crc_adapter *ad, int *sampled)
{
    *sampled = 0;
    uint8_t msg[8];
    if (ad->id == CRC32_ISO_HDLC) {
        *sampled = 1;
        rng = 0x0BADC0DEu;
        for (unsigned k = 0; k < 65536; k++) {
            uint32_t pre = xs();
            memcpy(msg, &pre, 4);
            uint32_t reg = ref32_update(ref32_start(), msg, 4);
            for (unsigned b = 0; b < 256; b++) {
                msg[4] = (uint8_t)b;
                uint32_t want = ref32_final(ref32_update(reg, msg + 4, 1));
                uint32_t got = one(ad, msg, 5);
                if (got != want) {
                    snprintf(detail, sizeof detail, "step: state %#x, byte %#x: %#x, the reference gives %#x", reg, b, got, want);
                    return FAIL;
                }
            }
        }
        return PASS;
    }
    unsigned nb = CRC_PARAMS[ad->id].width / 8u;
    size_t n = (size_t)1 << (8 * nb);
    for (size_t m = 0; m < n; m++) {
        msg[0] = (uint8_t)m; msg[1] = (uint8_t)(m >> 8);
        uint32_t reg = ref_update(ad->id, ref_start(ad->id), msg, nb);
        for (unsigned b = 0; b < 256; b++) {
            msg[nb] = (uint8_t)b;
            uint32_t want = ref_final(ad->id, ref_update(ad->id, reg, msg + nb, 1));
            uint32_t got = one(ad, msg, nb + 1);
            if (got != want) {
                snprintf(detail, sizeof detail, "step: state %#x, byte %#x: %#x, the reference gives %#x", reg, b, got, want);
                return FAIL;
            }
        }
    }
    return PASS;
}

int main(void)
{
    int ok = 1;
    for (int id = CRC16_IBM_3740; id <= CRC8_SMBUS; id++)
        if (!bijective((crc_id)id)) {
            printf("precondition of \"step\" does not hold for %s\n", CRC_PARAMS[id].name);
            ok = 0;
        }
    printf("CRC host test: check, lengths 0-300 x alignments 0-7, splits, step%s\n",
           ok ? " (precondition of step holds for CRC-8 and CRC-16)" : "");
    printf("%-34s %-16s %-12s %-6s %-7s %-6s %-8s verdict\n", "adapter", "CRC", "class", "check", "lengths", "splits", "step");
    for (size_t c = 0; c < sizeof CASES / sizeof CASES[0]; c++) {
        const crc_adapter *ad = CASES[c].ad;
        if (ad->init) ad->init();
        int r[C_N], sampled;
        const char *first = NULL;
        char firstbuf[160] = "";
        detail[0] = 0;
        r[C_CHECK] = check_value(ad);
        if (r[C_CHECK] == FAIL && !first) { strcpy(firstbuf, detail); first = firstbuf; }
        r[C_LENGTHS] = lengths(ad);
        if (r[C_LENGTHS] == FAIL && !first) { strcpy(firstbuf, detail); first = firstbuf; }
        r[C_SPLITS] = splits(ad);
        if (r[C_SPLITS] == FAIL && !first) { strcpy(firstbuf, detail); first = firstbuf; }
        r[C_STEP] = step(ad, &sampled);
        if (r[C_STEP] == FAIL && !first) { strcpy(firstbuf, detail); first = firstbuf; }
        int as_expected;
        if (CASES[c].expect_fail < 0) {
            as_expected = 1;
            for (int k = 0; k < C_N; k++) if (r[k] == FAIL) as_expected = 0;
        } else {
            as_expected = r[CASES[c].expect_fail] == FAIL;
        }
        ok &= as_expected;
        char stepcell[16];
        snprintf(stepcell, sizeof stepcell, "%s%s", r[C_STEP] == PASS ? "pass" : "FAIL", sampled ? "*" : "");
        printf("%-34s %-16s %-12s %-6s %-7s %-6s %-8s %s%s%s\n", ad->name, CRC_PARAMS[ad->id].name,
               ad->cls == CLS_SLICING ? (ad->slice == 4 ? "slicing-4" : "slicing") : CRC_CLASS_NAME[ad->cls],
               r[C_CHECK] == PASS ? "pass" : "FAIL", r[C_LENGTHS] == PASS ? "pass" : "FAIL",
               r[C_SPLITS] == NA ? "-" : r[C_SPLITS] == PASS ? "pass" : "FAIL", stepcell,
               CASES[c].expect_fail < 0 ? "" : "expected FAIL by ",
               CASES[c].expect_fail < 0 ? (as_expected ? "as expected" : "NOT AS EXPECTED")
                                        : CHECK_NAME[CASES[c].expect_fail],
               CASES[c].expect_fail < 0 ? "" : (as_expected ? ": as expected" : ": NOT AS EXPECTED"));
        if (first) printf("    first: %s\n", first);
    }
    printf("* CRC-32: every byte after 65536 random states, not every state (proof/ for the rest)\n");
    printf("%s\n", ok ? "exit 0: every verdict as expected" : "exit 1: a verdict not as expected");
    return ok ? 0 : 1;
}
