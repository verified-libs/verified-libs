/* The CRC benchmark image (step 5 of the plan): one configuration (BENCH_CRC,
 * an adapter's name) and the reference of its CRC (BENCH_REF) as the
 * baseline, timed by the board's time_call() (firmware/common/<board>/board.h,
 * unchanged). Built, not run: README.md.
 *
 * Scenarios: one-shot CRC of LEN bytes, LEN in 1, 4, 16, 64, 256, 1024, the
 * buffer at an 8-byte boundary (offset 0) and one byte after it (offset 1),
 * with the cache off and on (board_cache). RUNS timed calls per scenario; one
 * byte of the message changes between runs, and every result is compared
 * with the reference's (ref_crc(), untimed). The results are left in RAM at
 * the start of .results (struct results), as in the ring-buffer images.
 *
 * In a bundle (onecrc.py, the slots of ../slots.txt): the boot stub of
 * version 2 (firmware/common/benchboot.c) starts the image the host named in
 * the selection words (firmware/common/select.h); the image records the
 * address it runs from (VTOR) and the host's run number (the fourth
 * selection word), so the host takes only the results of the start it asked
 * for. BENCH_PLACE bytes (the placement, onecrc.py) lie between the fixed
 * part and the adapter, so the adapter and the library both move with the
 * placement; BENCH_SHIFT bytes (FAR) lie between the adapter and the
 * library, as in the ring-buffer images. */
#include <stdint.h>
#include <string.h>
#include "board.h"
#include "board_uart.h"   /* only for BOARD_SELECT_ADDR, on the board that has one (RP2350) */
#include "select.h"
VL_SELECT_DEFINE
#include "../crc.h"
#include "../adapters.h"
#include "../ref_crc.h"

#ifndef BENCH_CRC
#error BENCH_CRC: the adapter of the configuration
#endif
#ifndef BENCH_REF
#error BENCH_REF: the reference adapter of its CRC
#endif
#define RUNS 256u
#define NLEN 6u
#define NOFF 2u
static const uint32_t LENS[NLEN] = { 1, 4, 16, 64, 256, 1024 };
static const uint32_t OFFS[NOFF] = { 0, 1 };

#define RESULT_MAGIC 0x564C4331u   /* "VLC1" */
#define RESULT_VERSION 2u   /* 2: image_base and nonce at the end */

struct stat { uint32_t min, max, sum, first, count; };
struct crcres { struct stat s[2][NLEN][NOFF]; uint32_t errors; };   /* [cache][len][offset] */
struct results {
    uint32_t magic, version, done, clock_hz, runs, nlen, noff, nlibs;
    uint32_t crc_id;                 /* crc.h crc_id of the configuration */
    uint32_t lens[NLEN], offs[NOFF];
    struct crcres lib[2];            /* 0 the reference (baseline), 1 the configuration */
    uint32_t dwt_stalls, board_id, read_overhead, empty_call_min;
    uint32_t image_base;             /* the vector table this image runs from (VTOR, set by the boot stub) */
    uint32_t nonce;                  /* the fourth selection word: the host's number for this start */
};
__attribute__((section(".results")))
volatile struct results results;

#define BENCH_HARNESS __attribute__((noinline, aligned(32), section(".text.bench_harness")))

/* The placement bytes between the fixed part and the adapter, and the FAR
 * bytes between the adapter and the library (onecrc.py's linker script puts
 * .bench_place right behind the fixed part and .bench_shift right behind the
 * adapter's code). A library of headers is compiled into its adapter, so its
 * loop moves with the placement only because the adapter does. */
#ifndef BENCH_PLACE
#define BENCH_PLACE 0
#endif
#if BENCH_PLACE > 0
__attribute__((section(".bench_place"), used, aligned(1)))
static const uint8_t bench_place[BENCH_PLACE] = {0};
#endif
#ifndef BENCH_SHIFT
#define BENCH_SHIFT 0
#endif
#if BENCH_SHIFT > 0
__attribute__((section(".bench_shift"), used, aligned(1)))
static const uint8_t bench_shift[BENCH_SHIFT] = {0};
#endif

static uint32_t empty_op(uintptr_t a, uintptr_t b) { (void)a; (void)b; return 0; }

BENCH_HARNESS static uint32_t empty_call_min(void)
{
    uint32_t ret, m = 0xFFFFFFFFu;
    for (uint32_t i = 0; i < 64; i++) {
        uint32_t c = time_call(empty_op, 0, 0, &ret);
        if (c < m) m = c;
    }
    return m;
}

BENCH_HARNESS static void stat_add(volatile struct stat *s, uint32_t c)
{
    if (s->count == 0) { s->min = s->max = s->sum = s->first = c; s->count = 1; return; }
    if (c < s->min) s->min = c;
    if (c > s->max) s->max = c;
    s->sum += c;
    s->count++;
}

/* The message: 1024 bytes and one more for offset 1, at an 8-byte boundary. */
static uint8_t msg[1024 + 8] __attribute__((aligned(8)));

BENCH_HARNESS static void scenario(const crc_adapter *ad, volatile struct stat *s, uint32_t len, uint32_t off,
                                   volatile uint32_t *errors)
{
    uint8_t *p = msg + off;
    for (uint32_t i = 0; i < RUNS; i++) {
        p[i % len] ^= (uint8_t)(i * 29u + 1u);
        uint32_t want = ref_crc(ad->id, p, len);
        uint32_t got;
        uint32_t c = time_call(ad->crc, (uintptr_t)p, len, &got);
        if (c == 0) results.dwt_stalls++;
        stat_add(s, c);
        if (got != want) (*errors)++;
    }
}

BENCH_HARNESS static void run_all(const crc_adapter *ad, volatile struct crcres *r, int cache)
{
    for (uint32_t l = 0; l < NLEN; l++)
        for (uint32_t o = 0; o < NOFF; o++)
            scenario(ad, &r->s[cache][l][o], LENS[l], OFFS[o], &r->errors);
}

extern const crc_adapter BENCH_CRC, BENCH_REF;

int main(void)
{
    board_init();
    memset((void *)&results, 0, sizeof results);
    results.magic = RESULT_MAGIC;
    results.version = RESULT_VERSION;
    results.clock_hz = board_clock_hz();
    results.runs = RUNS;
    results.nlen = NLEN;
    results.noff = NOFF;
    results.nlibs = 2;
    results.crc_id = BENCH_CRC.id;
    for (uint32_t l = 0; l < NLEN; l++) results.lens[l] = LENS[l];
    for (uint32_t o = 0; o < NOFF; o++) results.offs[o] = OFFS[o];
    results.board_id = BOARD_ID;
    results.read_overhead = BOARD_READ_OVERHEAD;
    results.dwt_stalls = board_counter_running() ? 0u : 0xFFFFFFFFu;
    results.image_base = *(volatile uint32_t *)0xE000ED08u;   /* VTOR */
    results.nonce = SEL[3];
    results.empty_call_min = empty_call_min();
    uint32_t x = 0x12345678u;
    for (uint32_t i = 0; i < sizeof msg; i++) { x ^= x << 13; x ^= x >> 17; x ^= x << 5; msg[i] = (uint8_t)x; }
    const crc_adapter *libs[2] = { &BENCH_REF, &BENCH_CRC };
    for (int k = 0; k < 2; k++) {
        if (libs[k]->id != BENCH_CRC.id) results.lib[k].errors = 0xFFFFFFFFu;  /* wrong reference */
        if (libs[k]->init) libs[k]->init();
        board_cache(0);
        run_all(libs[k], &results.lib[k], 0);
        board_cache(1);
        run_all(libs[k], &results.lib[k], 1);
    }
    results.done = 1;
    board_idle();
    return 0;
}
