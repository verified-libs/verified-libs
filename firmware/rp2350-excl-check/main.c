/*
 * rp2350-excl-check: is a C11 atomic read-modify-write (LDREX/STREX on the
 * Cortex-M33) atomic between the RP2350's two cores?
 *
 * Both cores do N __atomic_fetch_add(&counter, 1, SEQ_CST) on one word in
 * SRAM; the final value must be 2N. Run three times:
 *   0: MPU off (the ARMv8-M default memory map: SRAM is Normal,
 *      Non-shareable);
 *   1: MPU on in both cores, one region over SRAM marked Normal, Inner
 *      Shareable (and the default map for everything else);
 *   2: as 0 again (MPU off), to show the order of the tests does not matter.
 * The architecture lets exclusives on Non-shareable memory use only the
 * core's local monitor; a global monitor sees only Shareable accesses.
 * Results at 0x20000000 (see run.sh).
 */
#include <stdint.h>
#include "board.h"

#define N 1000000u
#define MAGIC 0x564C5843u /* "VLXC" */
#define NTEST 3u

struct res { uint32_t magic, done, n, ntest; uint32_t got[NTEST], strex_fail0[NTEST], strex_fail1[NTEST]; };
__attribute__((section(".results"))) volatile struct res results;

static volatile uint32_t counter __attribute__((aligned(32)));
static volatile uint32_t go, done1, mpu_mode;
static volatile uint32_t fails1;
static uint32_t core1_stack[512];

#define MPU_CTRL  (*(volatile uint32_t *)0xE000ED94u)
#define MPU_RNR   (*(volatile uint32_t *)0xE000ED98u)
#define MPU_RBAR  (*(volatile uint32_t *)0xE000ED9Cu)
#define MPU_RLAR  (*(volatile uint32_t *)0xE000EDA0u)
#define MPU_MAIR0 (*(volatile uint32_t *)0xE000EDC0u)

static void mpu_set(uint32_t shareable)
{
    __asm volatile("dsb\nisb" ::: "memory");
    MPU_CTRL = 0;
    if (shareable) {
        MPU_MAIR0 = 0x44u;                              /* attr 0: Normal, non-cacheable */
        MPU_RNR = 0;
        MPU_RBAR = 0x20000000u | (3u << 3) | (1u << 1); /* SH = inner shareable, AP = RW any */
        MPU_RLAR = (0x20081FFFu & ~0x1Fu) | (0u << 1) | 1u;
        MPU_CTRL = 5u;                                  /* ENABLE | PRIVDEFENA */
    }
    __asm volatile("dsb\nisb" ::: "memory");
}

/* fetch_add with LDREX/STREX written out, counting failed STREX */
static uint32_t add_loop(uint32_t n)
{
    uint32_t fails = 0;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t v, st;
        do {
            __asm volatile("ldrex %0, [%2]\n"
                           "adds  %0, %0, #1\n"
                           "strex %1, %0, [%2]\n"
                           : "=&r"(v), "=&r"(st) : "r"(&counter) : "memory", "cc");
            fails += st;
        } while (st);
    }
    return fails;
}

static void core1_main(void)
{
    uint32_t seen = 0;
    for (;;) {
        while (go == seen) {}
        seen = go;
        mpu_set(mpu_mode);
        fails1 = add_loop(N);
        __asm volatile("dmb" ::: "memory");
        done1 = seen;
    }
}

int main(void)
{
    static const uint32_t mode[NTEST] = { 0, 1, 0 };
    board_init();
    results.magic = MAGIC; results.done = 0; results.n = N; results.ntest = NTEST;
    board_core1_launch(core1_main, core1_stack + sizeof core1_stack / sizeof core1_stack[0]);
    for (uint32_t t = 0; t < NTEST; t++) {
        counter = 0;
        mpu_mode = mode[t];
        mpu_set(mode[t]);
        __asm volatile("dmb" ::: "memory");
        go = t + 1;
        uint32_t f0 = add_loop(N);
        while (done1 != t + 1) {}
        __asm volatile("dmb" ::: "memory");
        results.got[t] = counter;
        results.strex_fail0[t] = f0;
        results.strex_fail1[t] = fails1;
    }
    mpu_set(0);
    results.done = 1;
    board_idle();
}
