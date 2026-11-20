/*
 * nrf5340-cyccnt: first cycle-count measurement on the nRF5340 application
 * core (Cortex-M33), bare metal, no SDK.
 *
 * What it does:
 *   1. Opens the debug port (software branch of APPROTECT), so the host can
 *      read results after a reset. The hardware branch is opened by writing
 *      UICR on first boot, see uicr_open_debug().
 *   2. Sets the core clock explicitly to 64 MHz (HFCLKCTRL = Div2).
 *   3. Starts the DWT cycle counter.
 *   4. Measures: the cost of the measurement itself, and 100 NOPs executed
 *      from flash with the instruction cache off and on.
 *   5. Writes the results to a fixed RAM address (0x20000000) for the host
 *      to read with probe-rs, then sleeps.
 *
 * Register addresses are taken from Nordic's nrfx MDK v4.7.0
 * (nrf5340_application.h / _bitfields.h), secure aliases.
 */
#include <stdint.h>

#define REG(addr) (*(volatile uint32_t *)(addr))

/* nRF5340 application core, secure peripherals */
#define CTRLAP_APPROTECT_DISABLE        REG(0x50006544u)
#define CTRLAP_SECUREAPPROTECT_DISABLE  REG(0x5000654Cu)
#define UICR_APPROTECT                  REG(0x00FF8000u)
#define UICR_SECUREAPPROTECT            REG(0x00FF801Cu)
#define CLOCK_HFCLKCTRL                 REG(0x50005558u)
#define CACHE_ENABLE                    REG(0x50001500u)

#define UNPROTECTED 0x50FA50FAu

/* Armv8-M debug registers */
#define DEMCR       REG(0xE000EDFCu)
#define DWT_CTRL    REG(0xE0001000u)
#define DWT_CYCCNT  REG(0xE0001004u)
#define DEMCR_TRCENA (1u << 24)
#define DWT_CTRL_CYCCNTENA (1u << 0)

#define NVMC_READY   REG(0x50039400u)
#define NVMC_CONFIG  REG(0x50039504u)
#define SCB_AIRCR    REG(0xE000ED0Cu)
#define AIRCR_SYSRESETREQ (0x05FA0000u | (1u << 2))

/* UICR: open the hardware branch of APPROTECT and SECUREAPPROTECT.
 * probe-rs 0.32 fails to program the UICR page (program_page code 104), so
 * the firmware writes it on first boot and resets once. Erased UICR words
 * read 0xFFFFFFFF, so writing 0x50FA50FA only clears bits (no erase). */
static void uicr_open_debug(void)
{
    if (UICR_APPROTECT == UNPROTECTED && UICR_SECUREAPPROTECT == UNPROTECTED)
        return;
    NVMC_CONFIG = 1u; /* WEN = Wen */
    while (!(NVMC_READY & 1u)) {}
    if (UICR_APPROTECT != UNPROTECTED) {
        UICR_APPROTECT = UNPROTECTED;
        while (!(NVMC_READY & 1u)) {}
    }
    if (UICR_SECUREAPPROTECT != UNPROTECTED) {
        UICR_SECUREAPPROTECT = UNPROTECTED;
        while (!(NVMC_READY & 1u)) {}
    }
    NVMC_CONFIG = 0u; /* WEN = Ren */
    __asm volatile("dsb" ::: "memory");
    SCB_AIRCR = AIRCR_SYSRESETREQ; /* UICR takes effect after reset */
    for (;;) {}
}

#define RUNS 1000u
#define RESULT_MAGIC 0x564C4231u /* "VLB1" */

struct stat { uint32_t min, max, sum_lo; };

/* Host reads this at 0x20000000 (see linker script). */
struct results {
    uint32_t magic;
    uint32_t version;
    uint32_t done;
    uint32_t hfclkctrl;
    uint32_t runs;
    struct stat overhead;      /* back-to-back CYCCNT reads */
    struct stat nop100_nocache;
    struct stat nop100_cache;
    uint32_t cache_enable_at_reset;
};
__attribute__((section(".results")))
volatile struct results results;

static inline uint32_t cyccnt(void) { return DWT_CYCCNT; }

#define NOP10 "nop\n nop\n nop\n nop\n nop\n nop\n nop\n nop\n nop\n nop\n"

__attribute__((noinline)) static uint32_t measure_overhead(void)
{
    uint32_t t0 = cyccnt();
    uint32_t t1 = cyccnt();
    return t1 - t0;
}

__attribute__((noinline, aligned(32))) static uint32_t measure_nop100(void)
{
    uint32_t t0 = cyccnt();
    __asm volatile(NOP10 NOP10 NOP10 NOP10 NOP10 NOP10 NOP10 NOP10 NOP10 NOP10 ::: "memory");
    uint32_t t1 = cyccnt();
    return t1 - t0;
}

static void collect(volatile struct stat *s, uint32_t (*fn)(void))
{
    uint32_t mn = 0xFFFFFFFFu, mx = 0, sum = 0;
    for (uint32_t i = 0; i < RUNS; i++) {
        uint32_t c = fn();
        if (c < mn) mn = c;
        if (c > mx) mx = c;
        sum += c;
    }
    s->min = mn;
    s->max = mx;
    s->sum_lo = sum;
}

int main(void)
{
    /* 1. Debug port: make sure UICR is open (first boot only), then copy
     *    the UICR state into the CTRL-AP software branch, as Nordic's
     *    SystemInit does (nrf53_handle_approtect). */
    uicr_open_debug();
    CTRLAP_APPROTECT_DISABLE = UICR_APPROTECT;
    CTRLAP_SECUREAPPROTECT_DISABLE = UICR_SECUREAPPROTECT;

    /* 2. Clock: 128 MHz HFCLK / 2 = 64 MHz (also covers nRF53 errata 42). */
    CLOCK_HFCLKCTRL = 1u;

    /* 3. Cycle counter */
    DEMCR |= DEMCR_TRCENA;
    DWT_CYCCNT = 0;
    DWT_CTRL |= DWT_CTRL_CYCCNTENA;

    results.magic = RESULT_MAGIC;
    results.version = 1;
    results.done = 0;
    results.hfclkctrl = CLOCK_HFCLKCTRL;
    results.runs = RUNS;
    results.cache_enable_at_reset = CACHE_ENABLE;

    /* 4. Measurements */
    collect(&results.overhead, measure_overhead);

    CACHE_ENABLE = 0;
    collect(&results.nop100_nocache, measure_nop100);

    CACHE_ENABLE = 1;
    collect(&results.nop100_cache, measure_nop100);

    results.done = 1;

    /* 5. Idle */
    for (;;) __asm volatile("wfi");
}
