/* The reference of the CRC kind: the bitwise algorithm written from the
 * catalogue's parameters (CRC_PARAMS below), one function per CRC with the
 * parameters as compile-time constants. It is the reference of the host test
 * and the baseline of the benchmark (README.md).
 *
 * The register form follows the parameters: a CRC with reflected input and
 * output (refin = refout = 1) is computed in a right-shifting register with
 * the reflected polynomial; one without reflection in a left-shifting
 * register. Both forms are the Williams model of the catalogue; which one a
 * parameter set takes is decided here, not by hand. The register kept
 * between calls (ref_*_update) is that form's register: for a reflected CRC
 * the reflected register, which is also the form the catalogue's residue is
 * given in.
 *
 * REF_WRONG (test builds only, run.sh refcheck) builds the reference with one
 * parameter of every CRC wrong, to show that the checks of the reference
 * catch it: 1 polynomial, 2 initial value, 3 reflection, 4 final XOR.
 */
#include "crc.h"
#include "ref_crc.h"

#ifndef REF_WRONG
#define REF_WRONG 0
#endif

const crc_params CRC_PARAMS[CRC_COUNT] = {
    [CRC32_ISO_HDLC] = { "CRC-32/ISO-HDLC", 32, 0x04C11DB7u, 0xFFFFFFFFu, 1, 1, 0xFFFFFFFFu, 0xCBF43926u, 0xDEBB20E3u },
    [CRC16_IBM_3740] = { "CRC-16/IBM-3740", 16, 0x1021u,     0xFFFFu,     0, 0, 0x0000u,     0x29B1u,     0x0000u },
    [CRC8_SMBUS]     = { "CRC-8/SMBUS",      8, 0x07u,       0x00u,       0, 0, 0x00u,       0xF4u,       0x00u },
};

const char *const CRC_CLASS_NAME[] = { "bitwise", "table of 16", "table of 256", "slicing", "other" };

/* The parameters the code below is built from, as constants. */
#if REF_WRONG == 1
#define P32 0x04C11DB6u
#define P16 0x1023u
#define P8  0x05u
#else
#define P32 0x04C11DB7u
#define P16 0x1021u
#define P8  0x07u
#endif
#if REF_WRONG == 2
#define I32 0xFFFFFFFEu
#define I16 0xFFFEu
#define I8  0x01u
#else
#define I32 0xFFFFFFFFu
#define I16 0xFFFFu
#define I8  0x00u
#endif
#if REF_WRONG == 3
#define R32 0
#define R16 1
#define R8  1
#else
#define R32 1
#define R16 0
#define R8  0
#endif
#if REF_WRONG == 4
#define X32 0x00000000u
#define X16 0xFFFFu
#define X8  0xFFu
#else
#define X32 0xFFFFFFFFu
#define X16 0x0000u
#define X8  0x00u
#endif

/* The bits of a value in reverse order, as a constant expression: the
 * reflected polynomial and initial value are then constants of the build.
 * Written as a loop they were computed at run time, 32 steps each, at every
 * call of the CRC-32 reference: about 450 cycles a call of the baseline on
 * the NUCLEO-G474RE (514 cycles for one byte, smoke test of 2026-11-24). The
 * values are checked below against the ones the literature gives. */
#define SWAP1(v)  ((((v) >> 1) & 0x55555555u) | (((v) & 0x55555555u) << 1))
#define SWAP2(v)  ((((v) >> 2) & 0x33333333u) | (((v) & 0x33333333u) << 2))
#define SWAP4(v)  ((((v) >> 4) & 0x0F0F0F0Fu) | (((v) & 0x0F0F0F0Fu) << 4))
#define SWAP8(v)  ((((v) >> 8) & 0x00FF00FFu) | (((v) & 0x00FF00FFu) << 8))
#define SWAP16(v) (((v) >> 16) | ((v) << 16))
#define REFLECT32(v)  SWAP16(SWAP8(SWAP4(SWAP2(SWAP1((uint32_t)(v))))))
#define REFLECT(v, w) (REFLECT32(v) >> (32 - (w)))
_Static_assert(REFLECT(0x04C11DB7u, 32) == 0xEDB88320u, "CRC-32 polynomial, reflected");
_Static_assert(REFLECT(0x1021u, 16) == 0x8408u, "CRC-16 polynomial 0x1021, reflected");
_Static_assert(REFLECT(0x07u, 8) == 0xE0u, "CRC-8 polynomial 0x07, reflected");
_Static_assert(REFLECT(0x00000001u, 32) == 0x80000000u && REFLECT(0x0001u, 16) == 0x8000u, "bit 0 becomes the top bit");

/* One function body for every CRC: W bits, polynomial P, reflected R. */
#define REF_UPDATE(W, P, R)                                                    \
    {                                                                          \
        const uint8_t *p = (const uint8_t *)data;                              \
        const uint32_t mask = (W) == 32 ? 0xFFFFFFFFu : ((1u << (W)) - 1u);    \
        if (R) {                                                               \
            const uint32_t rpoly = REFLECT((P), (W));                          \
            while (len--) {                                                    \
                reg ^= *p++;                                                   \
                for (int k = 0; k < 8; k++)                                    \
                    reg = (reg & 1u) ? (reg >> 1) ^ rpoly : reg >> 1;          \
            }                                                                  \
        } else {                                                               \
            const uint32_t top = 1u << ((W) - 1);                              \
            while (len--) {                                                    \
                reg ^= (uint32_t)*p++ << ((W) - 8);                            \
                for (int k = 0; k < 8; k++)                                    \
                    reg = (reg & top) ? (reg << 1) ^ (P) : reg << 1;           \
                reg &= mask;                                                   \
            }                                                                  \
        }                                                                      \
        return reg;                                                            \
    }

/* The register form's initial value and final step. With refin = refout the
 * register needs no reflection at the end: only the final XOR. */
uint32_t ref32_update(uint32_t reg, const void *data, size_t len) REF_UPDATE(32, P32, R32)
uint32_t ref16_update(uint32_t reg, const void *data, size_t len) REF_UPDATE(16, P16, R16)
uint32_t ref8_update(uint32_t reg, const void *data, size_t len)  REF_UPDATE(8, P8, R8)
uint32_t ref32_start(void) { return R32 ? REFLECT(I32, 32) : I32; }
uint32_t ref16_start(void) { return R16 ? REFLECT(I16, 16) : I16; }
uint32_t ref8_start(void)  { return R8 ? REFLECT(I8, 8) : I8; }
uint32_t ref32_final(uint32_t reg) { return reg ^ X32; }
uint32_t ref16_final(uint32_t reg) { return reg ^ X16; }
uint32_t ref8_final(uint32_t reg)  { return reg ^ X8; }

uint32_t ref_update(crc_id id, uint32_t reg, const void *data, size_t len)
{
    switch (id) {
    case CRC32_ISO_HDLC: return ref32_update(reg, data, len);
    case CRC16_IBM_3740: return ref16_update(reg, data, len);
    default:             return ref8_update(reg, data, len);
    }
}
uint32_t ref_start(crc_id id)
{
    return id == CRC32_ISO_HDLC ? ref32_start() : id == CRC16_IBM_3740 ? ref16_start() : ref8_start();
}
uint32_t ref_final(crc_id id, uint32_t reg)
{
    return id == CRC32_ISO_HDLC ? ref32_final(reg) : id == CRC16_IBM_3740 ? ref16_final(reg) : ref8_final(reg);
}
uint32_t ref_crc(crc_id id, const void *data, size_t len)
{
    return ref_final(id, ref_update(id, ref_start(id), data, len));
}

/* The reference as three adapters: the baseline of the benchmark. */
#define REF_ADAPTER(N, ID, NAME)                                                   \
    static uint32_t N##_crc(uintptr_t a, uintptr_t b)                              \
    { return N##_final(N##_update(N##_start(), (const void *)a, (size_t)b)); }     \
    static uint32_t N##_reg;                                                       \
    static uint32_t N##_begin(uintptr_t a, uintptr_t b)                            \
    { (void)a; (void)b; N##_reg = N##_start(); return 0; }                         \
    static uint32_t N##_upd(uintptr_t a, uintptr_t b)                              \
    { N##_reg = N##_update(N##_reg, (const void *)a, (size_t)b); return 0; }       \
    static uint32_t N##_fin(uintptr_t a, uintptr_t b)                              \
    { (void)a; (void)b; return N##_final(N##_reg); }                               \
    const crc_adapter adapter_##N = { NAME, "ours", ID, CLS_BITWISE, 0, 0, NULL,   \
        NULL, N##_crc, CRC_STREAM(N##_begin, N##_upd, N##_fin) };

REF_ADAPTER(ref32, CRC32_ISO_HDLC, "reference CRC-32 (ours)")
REF_ADAPTER(ref16, CRC16_IBM_3740, "reference CRC-16 (ours)")
REF_ADAPTER(ref8,  CRC8_SMBUS,     "reference CRC-8 (ours)")
