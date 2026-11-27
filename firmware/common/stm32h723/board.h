/*
 * Board layer for the benchmark firmware: NUCLEO-H723ZG (STM32H723ZGT6,
 * Cortex-M7 with L1 instruction and data caches). Same interface as
 * common/nrf5340/board.h.
 *
 * Clock: the reset default, HSI 64 MHz, flash wait states as after reset
 * (7, RM0468 4.3.8; 1 would do at 64 MHz). Cycle counts are what the
 * benchmark reports, so 64 MHz is usable; flash numbers with the cache off
 * include the reset wait states.
 *
 * -DBOARD_CLOCK_FAST=1: 520 MHz (h7_clock_520 below), the most the
 * STM32H723 runs without the CPUFREQ_BOOST option byte (DS13313 Rev 5, table
 * "General operating conditions": VOS0 520 MHz, 550 MHz only with
 * CPUFREQ_BOOST; we write no option bytes). Facts it rests on:
 * - supply: the STM32H723ZGT6 (LQFP144) has the LDO and no SMPS (DS13313
 *   table 1); UM2407 Rev 6 shows no SMPS circuit on the MB1364 board. LDO
 *   supply = SDEN 0, LDOEN 1, BYPASS 0 (RM0468 Rev 3 table 30, ID 1). An
 *   illegal combination would be ignored and lock PWR_CR3 until a power
 *   cycle (RM0468 6.8.4), which the lab can do by switching the USB port.
 * - VOS0: PWR_D3CR.VOS = 00 (RM0468 6.8.6), after ACTVOSRDY.
 * - flash: 3 wait states, WRHIGHFREQ 11 for an AXI clock of 210-275 MHz at
 *   VOS0 (RM0468 table 16); set before the clock goes up.
 * - PLL1 from HSI 64 MHz: DIVM1 8 -> 8 MHz (PLL1RGE 11: 8-16 MHz), DIVN1 65
 *   -> VCO 520 MHz (wide VCO 192-836 MHz), DIVP1 1 (allowed: "odd division
 *   factors are not allowed, except for 1") -> sys_ck 520 MHz (RM0468 8.7.11,
 *   8.7.12).
 * - buses: core /1 = 520 MHz, AHB/AXI /2 = 260 MHz (max 275), every APB /2 =
 *   130 MHz (max 137.5; DS13313). APB1 timers (TIM2, TIM3) then run at 2 x
 *   PCLK1 = 260 MHz (TIMPRE 0): one timer tick is 2 core cycles, not 1.
 *   USART3 (PCLK1) gets its baud divisor for 130 MHz (board_uart.h).
 * - board_idle switches back to HSI 64 MHz and stops PLL1, so the board does
 *   not draw the extra ~0.4 W between runs (DS13313 table 20: ~135 mA typ.
 *   at 520 MHz, ~13.5 mA at 60 MHz).
 *
 * Data, bss, stack and results are in DTCM (0x20000000), which the L1 data
 * cache never caches. Cache maintenance follows the ARMv7-M architecture
 * (as in CMSIS core_cm7.h). Peripheral addresses: ST cmsis-device-h7
 * v1.10.7 (commit 8f922cdc), Include/stm32h723xx.h.
 */
#pragma once
#include <stdint.h>
#include "bench.h"

#define BOARD_ID 4u              /* decode.py: BOARDS */
/* To be confirmed on the board with the empty-call calibration (the M7 is
 * dual-issue; a load from the PPB is assumed to take 1 cycle here). */
#define BOARD_READ_OVERHEAD 1u

#define H7_REG(addr) (*(volatile uint32_t *)(addr))

#define SCB_CCR      H7_REG(0xE000ED14u)
#define SCB_CCSIDR   H7_REG(0xE000ED80u)
#define SCB_CSSELR   H7_REG(0xE000ED84u)
#define SCB_ICIALLU  H7_REG(0xE000EF50u)
#define SCB_DCISW    H7_REG(0xE000EF60u)
#define SCB_DCCISW   H7_REG(0xE000EF74u)
#define SCB_CCR_DC   (1u << 16)
#define SCB_CCR_IC   (1u << 17)

#define ARM_DEMCR       H7_REG(0xE000EDFCu)
#define ARM_DWT_LAR     H7_REG(0xE0001FB0u)   /* CoreSight lock access (Cortex-M7) */
#define ARM_DWT_CTRL    H7_REG(0xE0001000u)
#define ARM_DWT_CYCCNT  H7_REG(0xE0001004u)

static inline void h7_barriers(void) { __asm volatile("dsb\n isb" ::: "memory"); }

/* Runs op on every set/way of the L1 data cache (DCISW or DCCISW). */
static inline void h7_dcache_all(volatile uint32_t *op)
{
    SCB_CSSELR = 0;   /* level 1 data cache */
    h7_barriers();
    uint32_t ccsidr = SCB_CCSIDR;
    uint32_t sets = (ccsidr >> 13) & 0x7FFFu;
    do {
        uint32_t ways = (ccsidr >> 3) & 0x3FFu;
        do {
            *op = ((sets << 5) & (0x1FFu << 5)) | ((ways << 30) & (3u << 30));
        } while (ways-- != 0u);
    } while (sets-- != 0u);
    h7_barriers();
}

/* Method version 3 (DECISIONS 2026-11-26): 520 MHz, VOS0, 3 wait states is the
 * default, as ST's template and examples for the NUCLEO-H723ZG run it
 * (lab/plans/2026-11-26-method-version-3.md, section 1); -DBOARD_CLOCK_FAST=0
 * gives the reset clock of version 2. */
#ifndef BOARD_CLOCK_FAST
#define BOARD_CLOCK_FAST 1
#endif
/* The APB1 timers (TIM2, TIM3) run at 2 x PCLK1: at 520 MHz that is 260 MHz,
 * half the core clock; at the reset clock, the core clock. The stress timers
 * (../stm32/tim2_stress.h, tim3_stress_b.h) divide their prescaler by this, so
 * that one tick stays 4 << prescaler core cycles. */
#define BOARD_TIMER_CLK_DIV (BOARD_CLOCK_FAST ? 2u : 1u)
#define H7_PWR_CSR1    H7_REG(0x58024804u)
#define H7_PWR_CR3     H7_REG(0x5802480Cu)
#define H7_PWR_D3CR    H7_REG(0x58024818u)
#define H7_RCC_CR      H7_REG(0x58024400u)
#define H7_RCC_CFGR    H7_REG(0x58024410u)
#define H7_RCC_D1CFGR  H7_REG(0x58024418u)
#define H7_RCC_D2CFGR  H7_REG(0x5802441Cu)
#define H7_RCC_D3CFGR  H7_REG(0x58024420u)
#define H7_RCC_PLLCKSELR H7_REG(0x58024428u)
#define H7_RCC_PLLCFGR H7_REG(0x5802442Cu)
#define H7_RCC_PLL1DIVR H7_REG(0x58024430u)
#define H7_RCC_PLL1FRACR H7_REG(0x58024434u)
#define H7_FLASH_ACR   H7_REG(0x52002000u)

#if BOARD_CLOCK_FAST
static inline void h7_clock_520(void)
{
    /* 1. supply: LDO (written once after power-on; RM0468 6.4.1 step 5) */
    H7_PWR_CR3 = (H7_PWR_CR3 & ~0x3Fu) | (1u << 1);      /* SDLEVEL 0, SDEXTHP 0, SDEN 0, LDOEN 1, BYPASS 0 */
    while (!(H7_PWR_CSR1 & (1u << 13))) {}                /* ACTVOSRDY */
    /* 2. VOS0 before raising the clock */
    H7_PWR_D3CR = H7_PWR_D3CR & ~(3u << 14);              /* VOS = 00: scale 0 */
    while (!(H7_PWR_D3CR & (1u << 13))) {}                /* VOSRDY */
    while (((H7_PWR_CSR1 >> 14) & 3u) != 0u || !(H7_PWR_CSR1 & (1u << 13))) {}   /* ACTVOS = VOS, ACTVOSRDY */
    /* 3. flash: 3 wait states, WRHIGHFREQ 11 (AXI 260 MHz at VOS0) */
    H7_FLASH_ACR = (H7_FLASH_ACR & ~0x3Fu) | (3u << 4) | 3u;
    while ((H7_FLASH_ACR & 0x3Fu) != ((3u << 4) | 3u)) {}
    /* 4. bus prescalers before the switch: AHB /2, APB3 /2, APB1 /2, APB2 /2, APB4 /2 */
    H7_RCC_D1CFGR = (H7_RCC_D1CFGR & ~0xF7Fu) | (0x4u << 4) | 0x8u;   /* D1CPRE /1, D1PPRE /2, HPRE /2 */
    H7_RCC_D2CFGR = (H7_RCC_D2CFGR & ~0x770u) | (0x4u << 8) | (0x4u << 4);
    H7_RCC_D3CFGR = (H7_RCC_D3CFGR & ~0x70u) | (0x4u << 4);
    /* 5. PLL1: HSI 64 MHz / 8 = 8 MHz, x 65 = 520 MHz VCO, P / 1 */
    H7_RCC_CR &= ~(1u << 24);                             /* PLL1 off (it is after reset) */
    while (H7_RCC_CR & (1u << 25)) {}
    H7_RCC_PLLCKSELR = (H7_RCC_PLLCKSELR & ~((0x3Fu << 4) | 3u)) | (8u << 4);   /* PLLSRC HSI, DIVM1 8 */
    H7_RCC_PLLCFGR = (H7_RCC_PLLCFGR & ~0xFu) | (3u << 2) | (1u << 16);         /* PLL1RGE 8-16 MHz, wide VCO, integer, DIVP1EN */
    H7_RCC_PLL1FRACR = 0;
    H7_RCC_PLL1DIVR = (1u << 24) | (1u << 16) | (0u << 9) | (65u - 1u);         /* R /2, Q /2, P /1, N 65 */
    H7_RCC_CR |= 1u << 24;
    while (!(H7_RCC_CR & (1u << 25))) {}                  /* PLL1RDY */
    /* 6. switch sys_ck to PLL1 */
    H7_RCC_CFGR = (H7_RCC_CFGR & ~7u) | 3u;
    while (((H7_RCC_CFGR >> 3) & 7u) != 3u) {}            /* SWS = PLL1 */
}

/* Back to HSI 64 MHz between runs (power; see the header). VOS and the flash
 * wait states stay where they are (both are safe at the lower clock). */
static inline void h7_clock_back_to_hsi(void)
{
    H7_RCC_CFGR &= ~7u;                                   /* SW = HSI */
    while (((H7_RCC_CFGR >> 3) & 7u) != 0u) {}
    H7_RCC_CR &= ~(1u << 24);                             /* PLL1 off */
}
#endif

static inline void board_init(void)
{
#if BOARD_CLOCK_FAST
    h7_clock_520();
#endif
    /* Wait (~1 s at 64 MHz) before starting CYCCNT, as on the nRF5340. */
    for (volatile uint32_t i = 0; i < 8000000u; i++) {}
    ARM_DEMCR |= 1u << 24;        /* TRCENA */
    ARM_DWT_LAR = 0xC5ACCE55u;    /* unlock DWT (needed on some M7 parts) */
    ARM_DWT_CYCCNT = 0;
    ARM_DWT_CTRL |= 1u;           /* CYCCNTENA */
}

static inline uint32_t board_clock_hz(void) { return BOARD_CLOCK_FAST ? 520000000u : 64000000u; }

/* "Cache" on the H7 = the core's L1 instruction and data caches. */
static inline void board_cache(int on)
{
    /* Clean only a cache that was on: after reset the D-cache contents are
     * undefined, and cleaning them writes random lines back to random
     * addresses (an imprecise BusFault, seen 2026-11-11 in counter-check;
     * the benchmark got away with it). Invalidating is always safe. */
    uint32_t was_on = SCB_CCR & SCB_CCR_DC;
    h7_barriers();
    SCB_CCR &= ~(SCB_CCR_IC | SCB_CCR_DC);
    h7_barriers();
    SCB_ICIALLU = 0;
    if (was_on) h7_dcache_all(&SCB_DCCISW);   /* clean + invalidate */
    if (on) {
        h7_dcache_all(&SCB_DCISW);
        SCB_ICIALLU = 0;
        h7_barriers();
        SCB_CCR |= SCB_CCR_IC | SCB_CCR_DC;
        h7_barriers();
    }
}

static inline int board_counter_running(void)
{
    uint32_t a = ARM_DWT_CYCCNT;
    __asm volatile("nop\n nop\n nop\n nop");
    return ARM_DWT_CYCCNT != a;
}

static inline void board_idle(void)
{
#if BOARD_CLOCK_FAST
    h7_clock_back_to_hsi();
#endif
    for (;;) {}
}

/* Stress test interrupt source: TIM2 (cmsis-device-h7: RCC_BASE 0x58024400,
 * APB1LENR at offset 0xE8, TIM2EN bit 0; TIM2_IRQn 28). At the reset clock
 * the APB1 timer clock equals the 64 MHz core clock; at 520 MHz it is half the
 * core clock (BOARD_TIMER_CLK_DIV above). */
#define TIM2_RCC_ENR    H7_REG(0x580244E8u)
#define TIM2_RCC_EN_BIT (1u << 0)
#define TIM2_IRQN       28u
#include "../stm32/tim2_stress.h"

/* Second stress interrupt (rb-mp-stress): TIM3, enable bit 1 in the same
 * RCC register as TIM2; IRQ 29. */
#define TIM3_RCC_ENR    H7_REG(0x580244E8u)
#define TIM3_RCC_EN_BIT (1u << 1)
#define TIM3_IRQN       29u
#include "../stm32/tim3_stress_b.h"

/* Same as common/nrf5340/board.h: CYCCNT(after) - CYCCNT(before). */
__attribute__((naked, noinline, aligned(32), unused))
static uint32_t time_call(rb_op op, uintptr_t a, uintptr_t b, uint32_t *ret)
{
    (void)op; (void)a; (void)b; (void)ret;
    __asm volatile(
        ".syntax unified\n"
        "push {r4, r5, r6, lr}\n"
        "mov  r4, r3\n"
        "ldr  r5, =0xE0001004\n"   /* DWT_CYCCNT */
        "mov  r3, r0\n"
        "mov  r0, r1\n"
        "mov  r1, r2\n"
        "ldr  r6, [r5]\n"          /* t0 */
        "blx  r3\n"
        "ldr  r1, [r5]\n"          /* t1 */
        "str  r0, [r4]\n"
        "subs r0, r1, r6\n"
        "pop  {r4, r5, r6, pc}\n"
        ".ltorg\n");
}
