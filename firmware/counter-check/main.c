/*
 * counter-check: does the board's cycle counter count core cycles, one per
 * cycle, through the same time_call() the benchmark uses?
 *
 * Times functions of 0, 1, 2, 4, 8, 16, 32 and 64 NOPs (plus "bx lr"), and a
 * loop of known length, with the board's time_call (DWT CYCCNT or SysTick),
 * 256 runs each, keeping min and max. On a single-issue core with no wait
 * states every NOP costs 1 cycle, so raw(n) - raw(0) = n; dual-issue cores
 * (Cortex-M7) may pair NOPs. raw(0) is the fixed part of every benchmark
 * number (blx, bx lr, the second counter read); BOARD_READ_OVERHEAD is what
 * the benchmark subtracts from it.
 * Results at 0x20000000; run.sh reads them back and prints the table.
 */
#include <stdint.h>
#include "board.h"

#define RUNS 256u
#define NFUN 8u
#define MAGIC 0x564C4343u /* "VLCC" */

#define NOPS1  "nop\n"
#define NOPS2  NOPS1 NOPS1
#define NOPS4  NOPS2 NOPS2
#define NOPS8  NOPS4 NOPS4
#define NOPS16 NOPS8 NOPS8
#define NOPS32 NOPS16 NOPS16
#define NOPS64 NOPS32 NOPS32
#define NOPFN(name, body) \
    __attribute__((naked, noinline, aligned(32))) static uint32_t name(uintptr_t a, uintptr_t b) \
    { (void)a; (void)b; __asm volatile(".syntax unified\n" body "bx lr\n"); }
NOPFN(n0, "")
NOPFN(n1, NOPS1)
NOPFN(n2, NOPS2)
NOPFN(n4, NOPS4)
NOPFN(n8, NOPS8)
NOPFN(n16, NOPS16)
NOPFN(n32, NOPS32)
NOPFN(n64, NOPS64)

struct res { uint32_t magic, done, board_id, clock_hz, read_overhead, nfun;
             uint32_t nops[NFUN], min[NFUN], max[NFUN]; };
__attribute__((section(".results"))) volatile struct res results;

int main(void)
{
    static const rb_op f[NFUN] = { n0, n1, n2, n4, n8, n16, n32, n64 };
    static const uint32_t nops[NFUN] = { 0, 1, 2, 4, 8, 16, 32, 64 };
    board_init();
    board_cache(1);
    results.magic = MAGIC;
    results.done = 0;
    results.board_id = BOARD_ID;
    results.clock_hz = board_clock_hz();
    results.read_overhead = BOARD_READ_OVERHEAD;
    results.nfun = NFUN;
    for (uint32_t i = 0; i < NFUN; i++) {
        uint32_t mn = 0xFFFFFFFFu, mx = 0, ret;
        for (uint32_t r = 0; r < RUNS; r++) {
            uint32_t c = time_call(f[i], 0, 0, &ret);
            if (c < mn) mn = c;
            if (c > mx) mx = c;
        }
        results.nops[i] = nops[i];
        results.min[i] = mn;
        results.max[i] = mx;
    }
    results.done = 1;
    board_idle();
}
