/*
 * Board layer for the benchmark firmware: NUCLEO-G474RE (STM32G474RET6,
 * Cortex-M4F), core clock 170 MHz from HSI16 via the PLL, range 1 boost
 * mode. Same interface as common/nrf5340/board.h.
 *
 * Register addresses and bit positions: ST cmsis-device-g4 v1.2.6
 * (commit 25664ddc), Include/stm32g474xx.h. Clock procedure as in ST's
 * HAL for 170 MHz (boost mode, 4 wait states, AHB /2 during the switch);
 * to be cross-checked against RM0440 and on the board.
 */
#pragma once
#include <stdint.h>
#include "bench.h"

#define BOARD_ID 3u              /* decode.py: BOARDS */
/* One LDR on the Cortex-M4 takes 2 cycles (unpipelined); to be confirmed on
 * the board with the empty-call calibration in main.c. */
#define BOARD_READ_OVERHEAD 2u

#define G4_REG(addr) (*(volatile uint32_t *)(addr))

#define RCC_CR        G4_REG(0x40021000u)   /* RCC_BASE + 0x00 */
#define RCC_CFGR      G4_REG(0x40021008u)   /* RCC_BASE + 0x08 */
#define RCC_PLLCFGR   G4_REG(0x4002100Cu)   /* RCC_BASE + 0x0C */
#define RCC_APB1ENR1  G4_REG(0x40021058u)   /* RCC_BASE + 0x58 */
#define FLASH_ACR     G4_REG(0x40022000u)   /* FLASH_R_BASE + 0x00 */
#define PWR_SR2       G4_REG(0x40007014u)   /* PWR_BASE + 0x14 */
#define PWR_CR5       G4_REG(0x40007080u)   /* PWR_BASE + 0x80 */

#define RCC_CR_PLLON          (1u << 24)
#define RCC_CR_PLLRDY         (1u << 25)
#define RCC_CFGR_SW_Msk       (3u << 0)
#define RCC_CFGR_SW_PLL       (3u << 0)
#define RCC_CFGR_SWS_Msk      (3u << 2)
#define RCC_CFGR_SWS_PLL      (3u << 2)
#define RCC_CFGR_HPRE_Msk     (0xFu << 4)
#define RCC_CFGR_HPRE_DIV2    (0x8u << 4)
#define RCC_APB1ENR1_PWREN    (1u << 28)
#define PWR_CR5_R1MODE        (1u << 8)
#define PWR_SR2_VOSF          (1u << 10)
/* PLL input HSI16, M = 4 (4 MHz), N = 85 (VCO 340 MHz), R = 2 -> 170 MHz.
 * P and Q outputs disabled. G4 encodings: PLLM = M - 1, PLLR 0 = /2. */
#define G4_PLLCFGR_170MHZ ((2u << 0)      /* PLLSRC = HSI16 */ \
                           | (3u << 4)    /* PLLM: /4 */       \
                           | (85u << 8)   /* PLLN: x85 */      \
                           | (1u << 24)   /* PLLREN */         \
                           | (0u << 25))  /* PLLR: /2 */
#define FLASH_ACR_LATENCY_Msk (0xFu << 0)
#define FLASH_ACR_PRFTEN      (1u << 8)
#define FLASH_ACR_ICEN        (1u << 9)
#define FLASH_ACR_DCEN        (1u << 10)
#define FLASH_ACR_ICRST       (1u << 11)
#define FLASH_ACR_DCRST       (1u << 12)
#define G4_FLASH_LATENCY_170MHZ 4u

#define ARM_DEMCR       G4_REG(0xE000EDFCu)
#define ARM_DWT_CTRL    G4_REG(0xE0001000u)
#define ARM_DWT_CYCCNT  G4_REG(0xE0001004u)

static inline void board_init(void)
{
    RCC_APB1ENR1 |= RCC_APB1ENR1_PWREN;
    (void)RCC_APB1ENR1;
    PWR_CR5 &= ~PWR_CR5_R1MODE;               /* range 1 boost (needed above 150 MHz) */
    while (PWR_SR2 & PWR_SR2_VOSF) {}

    FLASH_ACR = (FLASH_ACR & ~FLASH_ACR_LATENCY_Msk) | G4_FLASH_LATENCY_170MHZ;
    while ((FLASH_ACR & FLASH_ACR_LATENCY_Msk) != G4_FLASH_LATENCY_170MHZ) {}

    RCC_CR &= ~RCC_CR_PLLON;
    while (RCC_CR & RCC_CR_PLLRDY) {}
    RCC_PLLCFGR = G4_PLLCFGR_170MHZ;
    RCC_CR |= RCC_CR_PLLON;
    while (!(RCC_CR & RCC_CR_PLLRDY)) {}
    /* AHB /2 while switching to the PLL, then /1 after > 1 us. */
    RCC_CFGR = (RCC_CFGR & ~(RCC_CFGR_SW_Msk | RCC_CFGR_HPRE_Msk)) | RCC_CFGR_SW_PLL | RCC_CFGR_HPRE_DIV2;
    while ((RCC_CFGR & RCC_CFGR_SWS_Msk) != RCC_CFGR_SWS_PLL) {}
    for (volatile uint32_t i = 0; i < 200u; i++) {}
    RCC_CFGR &= ~RCC_CFGR_HPRE_Msk;

    /* As on the nRF5340: probe-rs may clear DEMCR.TRCENA when it detaches
     * after "reset", which stops CYCCNT. Wait (~1 s) before starting it. */
    for (volatile uint32_t i = 0; i < 20000000u; i++) {}

    ARM_DEMCR |= 1u << 24;    /* TRCENA */
    ARM_DWT_CYCCNT = 0;
    ARM_DWT_CTRL |= 1u;       /* CYCCNTENA */
}

static inline uint32_t board_clock_hz(void)
{
    return (RCC_CFGR & RCC_CFGR_SWS_Msk) == RCC_CFGR_SWS_PLL ? 170000000u : 16000000u;
}

/* "Cache" on the G4 = ART accelerator: instruction cache, data cache and
 * prefetch, all off or all reset and on. */
static inline void board_cache(int on)
{
    FLASH_ACR &= ~(FLASH_ACR_ICEN | FLASH_ACR_DCEN | FLASH_ACR_PRFTEN);
    if (on) {
        FLASH_ACR |= FLASH_ACR_ICRST | FLASH_ACR_DCRST;   /* only while disabled */
        FLASH_ACR &= ~(FLASH_ACR_ICRST | FLASH_ACR_DCRST);
        FLASH_ACR |= FLASH_ACR_ICEN | FLASH_ACR_DCEN | FLASH_ACR_PRFTEN;
    }
}

static inline int board_counter_running(void)
{
    uint32_t a = ARM_DWT_CYCCNT;
    __asm volatile("nop\n nop\n nop\n nop");
    return ARM_DWT_CYCCNT != a;
}

static inline void board_idle(void) { for (;;) {} }

/* Stress test interrupt source: TIM2 (cmsis-device-g4: RCC_APB1ENR1 TIM2EN
 * bit 0; TIM2_IRQn 28). */
#define TIM2_RCC_ENR    RCC_APB1ENR1
#define TIM2_RCC_EN_BIT (1u << 0)
#define TIM2_IRQN       28u
#include "../stm32/tim2_stress.h"

/* Second stress interrupt (rb-mp-stress): TIM3, enable bit 1 in the same
 * RCC register as TIM2; IRQ 29. */
#define TIM3_RCC_ENR    RCC_APB1ENR1
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
