/*
 * Shared bare-metal setup for benchmarks on the nRF5340 application core.
 * Register addresses: nrfx MDK v4.7.0, cross-checked against the nRF5340
 * Product Specification (OPS v0.5.1). See ../../nrf5340-cyccnt/README.md.
 */
#pragma once
#include <stdint.h>

#define NRF_REG(addr) (*(volatile uint32_t *)(addr))

#define NRF_CTRLAP_APPROTECT_DISABLE        NRF_REG(0x50006544u)
#define NRF_CTRLAP_SECUREAPPROTECT_DISABLE  NRF_REG(0x5000654Cu)
#define NRF_UICR_APPROTECT                  NRF_REG(0x00FF8000u)
#define NRF_UICR_SECUREAPPROTECT            NRF_REG(0x00FF801Cu)
#define NRF_CLOCK_HFCLKCTRL                 NRF_REG(0x50005558u)
#ifndef BOARD_CLOCK_FAST
#define BOARD_CLOCK_FAST 0       /* 1: application core at 128 MHz (see nrf5340_bench_init) */
#endif
#define NRF_CACHE_ENABLE                    NRF_REG(0x50001500u)
#define NRF_NVMC_READY                      NRF_REG(0x50039400u)
#define NRF_NVMC_CONFIG                     NRF_REG(0x50039504u)
#define NRF_UNPROTECTED 0x50FA50FAu

#define ARM_SCB_AIRCR   NRF_REG(0xE000ED0Cu)
#define ARM_DEMCR       NRF_REG(0xE000EDFCu)
#define ARM_DWT_CTRL    NRF_REG(0xE0001000u)
#define ARM_DWT_CYCCNT  NRF_REG(0xE0001004u)

static inline uint32_t cyccnt(void) { return ARM_DWT_CYCCNT; }

/* Open debug access (UICR on first boot + reset, then CTRL-AP), set the core
 * clock to 64 MHz, start the DWT cycle counter. */
static inline void nrf5340_bench_init(void)
{
    if (NRF_UICR_APPROTECT != NRF_UNPROTECTED || NRF_UICR_SECUREAPPROTECT != NRF_UNPROTECTED) {
        NRF_NVMC_CONFIG = 1u;
        while (!(NRF_NVMC_READY & 1u)) {}
        if (NRF_UICR_APPROTECT != NRF_UNPROTECTED) {
            NRF_UICR_APPROTECT = NRF_UNPROTECTED;
            while (!(NRF_NVMC_READY & 1u)) {}
        }
        if (NRF_UICR_SECUREAPPROTECT != NRF_UNPROTECTED) {
            NRF_UICR_SECUREAPPROTECT = NRF_UNPROTECTED;
            while (!(NRF_NVMC_READY & 1u)) {}
        }
        NRF_NVMC_CONFIG = 0u;
        __asm volatile("dsb" ::: "memory");
        ARM_SCB_AIRCR = 0x05FA0000u | (1u << 2);
        for (;;) {}
    }
    NRF_CTRLAP_APPROTECT_DISABLE = NRF_UICR_APPROTECT;
    NRF_CTRLAP_SECUREAPPROTECT_DISABLE = NRF_UICR_SECUREAPPROTECT;

    /* HCLK = 128 MHz / 2 = 64 MHz; with -DBOARD_CLOCK_FAST=1 the full
     * 128 MHz (divider 1). 64 MHz is the vendor's default: the startup
     * Zephyr builds (nrfx system_nrf5340_application.c) and Zephyr's nRF53
     * SoC code leave the reset value Div2 (method version 3, section 1).
     * Opt-in, so the default firmware is unchanged; board_clock_hz() reads
     * the divider back, so every record names the clock it ran at. The
     * peripherals (timers, UARTE) run from their own 16 MHz clock and are
     * not affected. */
    NRF_CLOCK_HFCLKCTRL = BOARD_CLOCK_FAST ? 0u : 1u;

    /* Wait (about a second with the cache off) before measuring: probe-rs
     * detaches after "reset" and clears
     * DEMCR.TRCENA on the way out, which stops CYCCNT. Counted loop, not
     * CYCCNT, so it cannot hang if the counter is stopped. */
    for (volatile uint32_t i = 0; i < 4000000u; i++) {}

    ARM_DEMCR |= 1u << 24;    /* TRCENA */
    ARM_DWT_CYCCNT = 0;
    ARM_DWT_CTRL |= 1u;       /* CYCCNTENA */
}

/* True if the cycle counter is running (used to reject broken series). */
static inline int cyccnt_running(void)
{
    uint32_t a = ARM_DWT_CYCCNT;
    __asm volatile("nop\n nop\n nop\n nop");
    return ARM_DWT_CYCCNT != a;
}
