/* The common adapter interface of the CRC kind (lab/plans/2026-11-24-crc-kind.md,
 * step 1). Nothing measured with it yet; see README.md.
 *
 * One adapter = one library x one CRC x one implementation of it (a
 * "configuration"). Every adapter offers the one-shot call
 *   crc:     a = address of the bytes, b = their number -> the CRC (final value)
 * with the signature of the ring-buffer benchmark's operations (rb_op:
 * uint32_t op(uintptr_t, uintptr_t)), so the boards' timed window
 * time_call() in firmware/common/<board>/board.h times it unchanged. On the
 * 64-bit host the same adapters run with 64-bit addresses.
 *
 * Optional, where the library has a streaming interface (NULL otherwise):
 *   begin:   a, b unused                 -> 0; starts a message
 *   update:  a = address, b = number     -> 0; adds bytes to the message
 *   final:   a, b unused                 -> the CRC of every byte since begin
 * The state between the calls lives in the adapter (one message at a time).
 *
 * Optional: init, called once before the first call. Some libraries build
 * their table in RAM at run time (CRC++'s Table, libcrc's tables); init does
 * that the way the library documents, so the timed calls do not include it.
 *
 * Why this shape:
 * - One CRC per adapter, fixed at build time: on a board one image holds one
 *   configuration (the rule of version 2 of the ring-buffer benchmark), and
 *   the CRC's parameters are compile-time constants in every library here.
 * - The one-shot call is what the benchmark times; streaming is tested on the
 *   host (every split of a message) because a library can be right in one
 *   call and wrong across calls (the state not carried over).
 * - crc_class names the algorithm, which is what decides the inner loop: the
 *   open question of the plan is whether two libraries with the same class
 *   compile to the same instructions (step 4).
 */
#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef uint32_t (*crc_op)(uintptr_t a, uintptr_t b);

/* The streaming fields of an adapter's initializer. A build with
 * CRC_ONESHOT_ONLY (the cross builds and the board image, which time only the
 * one-shot call) leaves them NULL, so the streaming code is not linked and
 * not counted in the sizes. */
#ifdef CRC_ONESHOT_ONLY
#define CRC_STREAM(begin, update, final) NULL, NULL, NULL
#else
#define CRC_STREAM(begin, update, final) begin, update, final
#endif

/* The three CRCs of the first set, by their names in the CRC RevEng
 * catalogue (https://reveng.sourceforge.io/crc-catalogue/all.htm). */
typedef enum {
    CRC32_ISO_HDLC,   /* "CRC-32" */
    CRC16_IBM_3740,   /* "CRC-16/CCITT-FALSE" */
    CRC8_SMBUS,       /* "CRC-8" */
    CRC_COUNT
} crc_id;

/* The catalogue's parameters (Williams model) and its check and residue. */
typedef struct {
    const char *name;
    uint8_t  width;
    uint32_t poly, init;
    uint8_t  refin, refout;
    uint32_t xorout;
    uint32_t check;    /* the CRC of the nine ASCII bytes "123456789" */
    uint32_t residue;  /* the register after a codeword, before xorout */
} crc_params;
extern const crc_params CRC_PARAMS[CRC_COUNT];

typedef enum {
    CLS_BITWISE,      /* one bit per step, no table */
    CLS_TABLE16,      /* a table of 16 entries, four bits per step */
    CLS_TABLE256,     /* a table of 256 entries, one byte per step */
    CLS_SLICING,      /* several tables of 256, `slice` bytes per step */
    CLS_OTHER         /* none of these (crc_adapter.note says what) */
} crc_class;
extern const char *const CRC_CLASS_NAME[];

typedef struct {
    const char *name;        /* "etl crc32_t256": library and its own name for it */
    const char *lib;         /* its name in libs.lock; "ours" for the reference */
    crc_id    id;          /* which CRC */
    crc_class cls;
    uint8_t   slice;         /* bytes per step for CLS_SLICING, else 0 */
    uint8_t   table_in_ram;  /* 1 if the library builds its table in RAM */
    const char *note;        /* NULL, or what the class does not say */
    void   (*init)(void);    /* optional, NULL = nothing to do */
    crc_op crc;              /* one-shot: a = address, b = length -> CRC */
    crc_op begin, update, final;   /* optional streaming, NULL = none */
} crc_adapter;

#ifdef __cplusplus
}
#endif
