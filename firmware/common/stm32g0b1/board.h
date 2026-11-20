/*
 * Board layer for the benchmark firmware: NUCLEO-G0B1RE (STM32G0B1RET6,
 * Cortex-M0+), core clock 64 MHz from HSI16 via the PLL. Same interface as
 * common/nrf5340/board.h.
 *
 * Register addresses and bit positions: ST cmsis-device-g0 v1.4.5
 * (commit f576c24e), Include/stm32g0b1xx.h. Clock tree, PLL limits and
 * flash wait states follow RM0444; to be cross-checked against the manual
 * (not yet in the datasheet library) and on the board.
 *
 * Timing: the Cortex-M0+ has no DWT cycle counter, so time_call() reads the
 * 24-bit SysTick counter (clocked by the core clock, counting down).
 */
#pragma once
#include <stdint.h>
#include "bench.h"

#define BOARD_ID 2u              /* decode.py: BOARDS */
/* One LDR on the Cortex-M0+ takes 2 cycles (Cortex-M0+ TRM); to be
 * confirmed on the board with the empty-call calibration in main.c. */
#define BOARD_READ_OVERHEAD 2u

#define G0_REG(addr) (*(volatile uint32_t *)(addr))

#define RCC_CR       G0_REG(0x40021000u)   /* RCC_BASE + 0x00 */
#define RCC_CFGR     G0_REG(0x40021008u)   /* RCC_BASE + 0x08 */
#define RCC_PLLCFGR  G0_REG(0x4002100Cu)   /* RCC_BASE + 0x0C */
#define FLASH_ACR    G0_REG(0x40022000u)   /* FLASH_R_BASE + 0x00 */

#define RCC_CR_PLLON        (1u << 24)
#define RCC_CR_PLLRDY       (1u << 25)
#define RCC_CFGR_SW_Msk     (7u << 0)
#define RCC_CFGR_SW_PLLRCLK (2u << 0)
#define RCC_CFGR_SWS_Msk    (7u << 3)
#define RCC_CFGR_SWS_PLLRCLK (2u << 3)
/* PLL input HSI16, M = 1, N = 8 (VCO 128 MHz), R = 2 -> PLLRCLK 64 MHz.
 * P and Q set to /2 with their outputs disabled. Field encodings as in the
 * HAL/LL (LL_RCC_PLLM_DIV_1 = 0, LL_RCC_PLLR_DIV_2 = PLLR_0). */
#define G0_PLLCFGR_64MHZ ((2u << 0)        /* PLLSRC = HSI16 */      \
                          | (0u << 4)      /* PLLM: /1 */            \
                          | (8u << 8)      /* PLLN: x8 */            \
                          | (1u << 17)     /* PLLP: /2 (disabled) */ \
                          | (1u << 25)     /* PLLQ: /2 (disabled) */ \
                          | (1u << 28)     /* PLLREN */              \
                          | (1u << 29))    /* PLLR: /2 */
#define FLASH_ACR_LATENCY_Msk (7u << 0)
#define FLASH_ACR_PRFTEN      (1u << 8)
#define FLASH_ACR_ICEN        (1u << 9)
#define FLASH_ACR_ICRST       (1u << 11)
#define G0_FLASH_LATENCY_64MHZ 2u          /* 2 wait states above 48 MHz, range 1 */

#define SYST_CSR  G0_REG(0xE000E010u)
#define SYST_RVR  G0_REG(0xE000E014u)
#define SYST_CVR  G0_REG(0xE000E018u)

static inline void board_init(void)
{
    /* More wait states before the clock goes up. */
    FLASH_ACR = (FLASH_ACR & ~FLASH_ACR_LATENCY_Msk) | G0_FLASH_LATENCY_64MHZ;
    while ((FLASH_ACR & FLASH_ACR_LATENCY_Msk) != G0_FLASH_LATENCY_64MHZ) {}

    RCC_CR &= ~RCC_CR_PLLON;
    while (RCC_CR & RCC_CR_PLLRDY) {}
    RCC_PLLCFGR = G0_PLLCFGR_64MHZ;
    RCC_CR |= RCC_CR_PLLON;
    while (!(RCC_CR & RCC_CR_PLLRDY)) {}
    RCC_CFGR = (RCC_CFGR & ~RCC_CFGR_SW_Msk) | RCC_CFGR_SW_PLLRCLK;  /* AHB, APB: /1 (reset) */
    while ((RCC_CFGR & RCC_CFGR_SWS_Msk) != RCC_CFGR_SWS_PLLRCLK) {}

    /* Same idea as on the nRF5340: wait a moment after probe-rs has let the
     * core run, before measuring. Counted loop, independent of SysTick. */
    for (volatile uint32_t i = 0; i < 2000000u; i++) {}

    SYST_RVR = 0x00FFFFFFu;
    SYST_CVR = 0;
    SYST_CSR = (1u << 2) | 1u;   /* CLKSOURCE = core clock, ENABLE, no interrupt */
}

static inline uint32_t board_clock_hz(void)
{
    return (RCC_CFGR & RCC_CFGR_SWS_Msk) == RCC_CFGR_SWS_PLLRCLK ? 64000000u : 16000000u;
}

/* "Cache" on the G0 = flash instruction cache + prefetch buffer. */
static inline void board_cache(int on)
{
    FLASH_ACR &= ~(FLASH_ACR_ICEN | FLASH_ACR_PRFTEN);
    if (on) {
        FLASH_ACR |= FLASH_ACR_ICRST;    /* reset only while ICEN = 0 */
        FLASH_ACR &= ~FLASH_ACR_ICRST;
        FLASH_ACR |= FLASH_ACR_ICEN | FLASH_ACR_PRFTEN;
    }
}

static inline int board_counter_running(void)
{
    uint32_t a = SYST_CVR;
    __asm volatile("nop\n nop\n nop\n nop");
    return SYST_CVR != a;
}

/* Stress test interrupt source: TIM2 (cmsis-device-g0: RCC_APBENR1 at
 * RCC_BASE + 0x3C, TIM2EN bit 0; TIM2_IRQn 15). */
#define TIM2_RCC_ENR    G0_REG(0x4002103Cu)
#define TIM2_RCC_EN_BIT (1u << 0)
#define TIM2_IRQN       15u
#include "../stm32/tim2_stress.h"

/* Second stress interrupt (rb-mp-stress): TIM3, enable bit 1 in the same
 * RCC register as TIM2; IRQ 16 (shared TIM3_TIM4_IRQn, stm32g0b1xx.h). */
#define TIM3_RCC_ENR    G0_REG(0x4002103Cu)
#define TIM3_RCC_EN_BIT (1u << 1)
#define TIM3_IRQN       16u
#include "../stm32/tim3_stress_b.h"

/* After the measurement: spin instead of WFI, so debug access to RAM does
 * not depend on the low-power debug settings (DBG_CR). */
static inline void board_idle(void) { for (;;) {} }

/* uint32_t time_call(rb_op op, uintptr_t a, uintptr_t b, uint32_t *ret)
 * Returns SysTick(before) - SysTick(after), modulo 2^24, around one call of
 * op(a, b). Same window as on the other boards: ldr t0 ; blx op ; <op> ;
 * ldr t1. ARMv6-M Thumb only. */
__attribute__((naked, noinline, aligned(32), unused))
static uint32_t time_call(rb_op op, uintptr_t a, uintptr_t b, uint32_t *ret)
{
    (void)op; (void)a; (void)b; (void)ret;
    __asm volatile(
        ".syntax unified\n"
        "push {r4, r5, r6, lr}\n"
        "mov  r4, r3\n"
        "ldr  r5, =0xE000E018\n"   /* SYST_CVR */
        "mov  r3, r0\n"
        "mov  r0, r1\n"
        "mov  r1, r2\n"
        "ldr  r6, [r5]\n"          /* t0 */
        "blx  r3\n"
        "ldr  r1, [r5]\n"          /* t1 */
        "str  r0, [r4]\n"
        "subs r0, r6, r1\n"        /* counts down */
        "lsls r0, r0, #8\n"        /* modulo 2^24 */
        "lsrs r0, r0, #8\n"
        "pop  {r4, r5, r6, pc}\n"
        ".ltorg\n");
}
