/*
 * h7-thermal (NUCLEO-H723ZG): how warm does the STM32H723 get at 520 MHz
 * under full load? Logs the die temperature once a second from the digital
 * temperature sensor (DTS, RM0468 Rev 3 chapter 30) through three phases:
 *   1 idle: IDLE_S seconds at the reset clock (HSI 64 MHz), a busy-wait
 *   2 load: LOAD_S seconds at 520 MHz (board.h h7_clock_520), caches on,
 *           the FPU and the integer pipes busy on data in DTCM
 *   3 cool: COOL_S seconds back at 64 MHz (h7_clock_back_to_hsi), busy-wait
 * then it stops in a loop at 64 MHz. SAMPLE_MS sets the sample period
 * (default 1000; the samples must fit in DTCM). If the die reaches LIMIT_C during the
 * load (computed here from the sensor's factory calibration), the load ends
 * at once and the record says so (aborted = 1). VOS0's limit is a junction
 * temperature of 105 C (DS13313).
 *
 * DTS: PCLK as reference (REFCLK_SEL 0), TS1_SMP_TIME 15 FM(T) periods,
 * software start. Calibration needs the PCLK divided below 1 MHz
 * (HSREF_CLK_DIV up to 127, RM0468 30.3.6), so APB4 runs at 65 MHz during
 * the load (D3PPRE /4; board.h makes it 130 MHz). Each sample keeps the raw
 * count (TS1_MFREQ) and the APB4 clock it was counted with; run.sh converts
 * with the factory values the firmware copies into the record:
 *   T = T0 + (F_PCLK * TS1_SMP_TIME / TS1_MFREQ - 100 * TS1_FMT0) / TS1_RAMP_COEFF
 * (RM0468 30.3.7). Results at 0x20000000 (DTCM); run.sh reads them over
 * the debug port while the firmware runs.
 */
#define BOARD_CLOCK_FAST 1
#include <stdint.h>
#include "board.h"

#ifndef IDLE_S
#define IDLE_S 60u
#endif
#ifndef LOAD_S
#define LOAD_S 600u
#endif
#ifndef COOL_S
#define COOL_S 300u
#endif
#ifndef SAMPLE_MS
#define SAMPLE_MS 1000u          /* one sample every SAMPLE_MS */
#endif
#ifndef LIMIT_C
#define LIMIT_C 85
#endif
#define NS ((IDLE_S + LOAD_S + COOL_S) * 1000u / SAMPLE_MS + 8u)
#define MAGIC 0x564C5448u /* "VLTH" */
#define SMP 15u

#define DTS_CFGR1   H7_REG(0x58006800u)
#define DTS_T0VALR1 H7_REG(0x58006808u)
#define DTS_RAMPVALR H7_REG(0x58006810u)
#define DTS_DR      H7_REG(0x5800681Cu)
#define DTS_SR      H7_REG(0x58006820u)
#define DTS_ICIFR   H7_REG(0x58006828u)
#define DTS_ITENR   H7_REG(0x58006824u)
#define RCC_APB4ENR H7_REG(0x580244F4u)
#define SCB_CPACR   H7_REG(0xE000ED88u)

struct sample { uint32_t t_ms, mfreq, pclk_hz, phase; };
struct results {
    uint32_t magic, version, phase, n, aborted, done;
    uint32_t idle_s, load_s, cool_s, limit_c, smp_time;
    uint32_t t0valr1, rampvalr;
    uint32_t load_iterations;
    uint32_t sample_ms;
    struct sample s[NS];
};
__attribute__((section(".results"))) volatile struct results results;

static uint32_t now_ms;            /* elapsed time, kept across clock changes */
static uint32_t last_cyc;

static uint32_t core_hz(void)  { return ((H7_RCC_CFGR >> 3) & 7u) == 3u ? 520000000u : 64000000u; }
static uint32_t apb4_hz(void)
{   /* sys_ck -> D1CPRE (always /1 here) -> HPRE -> D3PPRE */
    uint32_t h = core_hz(), hp = H7_RCC_D1CFGR & 0xFu, pp = (H7_RCC_D3CFGR >> 4) & 7u;
    if (hp & 8u) h >>= (hp & 7u) < 4u ? (hp & 7u) + 1u : (hp & 7u) + 2u;   /* 1000 /2 .. 1011 /16, 1100 /64 ... */
    if (pp & 4u) h >>= (pp & 3u) + 1u;
    return h;
}
static void tick(void)
{
    uint32_t c = ARM_DWT_CYCCNT, khz = core_hz() / 1000u;
    uint32_t d = c - last_cyc;
    if (d >= khz) { now_ms += d / khz; last_cyc += (d / khz) * khz; }
}
static uint32_t dts_measure(void)
{
    /* TS1_ITEF is set only with its enable bit in DTS_ITENR (seen on the
     * board: with ITENR 0 the flag stayed 0 after the measurement); the
     * NVIC line stays disabled, so no interrupt is taken. */
    DTS_ICIFR = 1u;                              /* CITEF */
    DTS_CFGR1 |= 1u << 4;                        /* TS1_START */
    uint32_t t = 0;
    while (!(DTS_SR & 1u) && ++t < 20000000u) {} /* TS1_ITEF: end of measurement (time limit: never hang) */
    DTS_CFGR1 &= ~(1u << 4);
    return t < 20000000u ? DTS_DR & 0xFFFFu : 0u;   /* 0: no measurement */
}
static int celsius_x10(uint32_t mfreq, uint32_t pclk)
{
    uint32_t t0 = (DTS_T0VALR1 >> 16) & 3u ? 130u : 30u, fmt0 = DTS_T0VALR1 & 0xFFFFu, ramp = DTS_RAMPVALR & 0xFFFFu;
    if (!mfreq || !ramp) return 0;
    float f = (float)pclk * SMP / (float)mfreq;
    return (int)(10.0f * ((float)t0 + (f - 100.0f * (float)fmt0) / (float)ramp));
}
static void sample(uint32_t phase)
{
    uint32_t i = results.n;
    if (i >= NS) return;
    uint32_t p = apb4_hz(), m = dts_measure();
    results.s[i].t_ms = now_ms; results.s[i].mfreq = m; results.s[i].pclk_hz = p; results.s[i].phase = phase;
    results.n = i + 1u;
}

/* The load: FPU multiply-adds and integer work on data in DTCM. */
static float fa[512], fb[512];
static uint32_t ia[512];
__attribute__((noinline)) static float load_block(void)
{
    float acc0 = 0, acc1 = 0, acc2 = 0, acc3 = 0;
    uint32_t x = 0x12345678u;
    for (uint32_t r = 0; r < 64u; r++)
        for (uint32_t i = 0; i < 512u; i += 4u) {
            acc0 += fa[i] * fb[i];     acc1 += fa[i + 1] * fb[i + 1];
            acc2 += fa[i + 2] * fb[i + 2]; acc3 += fa[i + 3] * fb[i + 3];
            x ^= x << 13; x ^= x >> 17; x ^= x << 5; ia[i & 511u] += x * 2654435761u;
        }
    return acc0 + acc1 + acc2 + acc3 + (float)(ia[x & 511u] & 0xFFu);
}

static void run_phase(uint32_t phase, uint32_t secs)
{
    results.phase = phase;
    uint32_t end = now_ms + secs * 1000u, next = now_ms;
    volatile float sink = 0;
    while ((int32_t)(now_ms - end) < 0) {
        tick();
        if ((int32_t)(now_ms - next) >= 0) {
            sample(phase);
            next += SAMPLE_MS;
            uint32_t i = results.n - 1u;
            if (phase == 2u && celsius_x10(results.s[i].mfreq, results.s[i].pclk_hz) >= LIMIT_C * 10) {
                results.aborted = 1u;
                return;
            }
        }
        if (phase == 2u) { sink += load_block(); results.load_iterations++; }
    }
    (void)sink;
}

int main(void)
{
    SCB_CPACR |= 0xFu << 20;                     /* CP10, CP11: the FPU */
    __asm volatile("dsb\n isb" ::: "memory");
    for (uint32_t i = 0; i < 512u; i++) { fa[i] = (float)i * 0.5f; fb[i] = 1.0f / (float)(i + 1u); ia[i] = i; }
    results.done = 0; results.n = 0; results.aborted = 0; results.load_iterations = 0;
    results.magic = MAGIC; results.version = 1;
    results.idle_s = IDLE_S; results.load_s = LOAD_S; results.cool_s = COOL_S; results.limit_c = LIMIT_C; results.smp_time = SMP; results.sample_ms = SAMPLE_MS;
    ARM_DEMCR |= 1u << 24; ARM_DWT_LAR = 0xC5ACCE55u; ARM_DWT_CYCCNT = 0; ARM_DWT_CTRL |= 1u;
    last_cyc = 0; now_ms = 0;
    board_cache(1);
    /* DTS: clock, PCLK reference, divider 127, 15 FM(T) periods, enable */
    RCC_APB4ENR |= 1u << 26; (void)RCC_APB4ENR;
    DTS_CFGR1 = (127u << 24) | (SMP << 16) | 1u;
    DTS_ITENR = 1u;                              /* TS1_ITEEN: makes TS1_ITEF report the end of a measurement */
    while (!(DTS_SR & (1u << 15))) {}            /* TS1_RDY */
    results.t0valr1 = DTS_T0VALR1; results.rampvalr = DTS_RAMPVALR;

    run_phase(1u, IDLE_S);
    tick();
    h7_clock_520();
    H7_RCC_D3CFGR = (H7_RCC_D3CFGR & ~0x70u) | (0x5u << 4);   /* APB4 /4: 65 MHz (DTS calibration < 1 MHz) */
    last_cyc = ARM_DWT_CYCCNT;
    run_phase(2u, LOAD_S);
    tick();
    h7_clock_back_to_hsi();
    H7_RCC_D1CFGR &= ~0xFu;                      /* HPRE /1 */
    H7_RCC_D3CFGR &= ~0x70u;                     /* APB4 /1: 64 MHz */
    last_cyc = ARM_DWT_CYCCNT;
    run_phase(3u, COOL_S);
    results.phase = 4u;
    results.done = 1u;
    for (;;) {}
}
