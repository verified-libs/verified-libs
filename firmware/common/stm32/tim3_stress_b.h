/*
 * Second interrupt source for the multi-producer / multi-consumer stress
 * test (rb-mp-stress) on the STM32 boards: TIM3, configured exactly like
 * TIM2 in tim2_stress.h (which must be included first). Included by the
 * STM32 board.h files, which define before including it:
 *   TIM3_RCC_ENR / TIM3_RCC_EN_BIT  clock enable register and bit of TIM3
 *   TIM3_IRQN                      TIM3 interrupt number (on the G0B1 the
 *                                  shared TIM3_TIM4 interrupt; TIM4 is unused)
 * TIM3_BASE 0x40000400 and the enable bit 1 are the same on G0, G4 and H7
 * (cmsis-device-g0 7c77b7cb, -g4 626ee412, -h7 81db1ec6). TIM3 is a 16-bit
 * timer; the periods used (< 400 ticks) fit.
 */
#pragma once
#include <stdint.h>
#ifndef BOARD_TIMER_CLK_DIV
#define BOARD_TIMER_CLK_DIV 1u   /* the timer runs at the core clock (every board but the H723 at 520 MHz) */
#endif

#define TIM3_CR1   (*(volatile uint32_t *)0x40000400u)
#define TIM3_DIER  (*(volatile uint32_t *)0x4000040Cu)
#define TIM3_SR    (*(volatile uint32_t *)0x40000410u)
#define TIM3_EGR   (*(volatile uint32_t *)0x40000414u)
#define TIM3_CNT   (*(volatile uint32_t *)0x40000424u)
#define TIM3_PSC   (*(volatile uint32_t *)0x40000428u)
#define TIM3_ARR   (*(volatile uint32_t *)0x4000042Cu)


#define BOARD_TIMER_B_IRQ_HANDLER TIM3_IRQHandler

/* period in timer ticks (>= 2) */
static inline void board_timer_b_start(uint32_t prescaler, uint32_t first_period)
{
    TIM3_RCC_ENR |= TIM3_RCC_EN_BIT;
    (void)TIM3_RCC_ENR;
    TIM3_CR1 = TIM_CR1_URS;
    TIM3_DIER = 0;
    TIM3_PSC = (4u << prescaler) / BOARD_TIMER_CLK_DIV - 1u;   /* one tick = 4 << prescaler core cycles */
    TIM3_ARR = first_period - 1u;
    TIM3_CNT = 0;
    TIM3_EGR = TIM_EGR_UG;            /* load PSC; URS: no interrupt from this */
    TIM3_SR = 0;
    STM32_NVIC_ICPR0 = 1u << TIM3_IRQN;
    STM32_NVIC_ISER0 = 1u << TIM3_IRQN;
    TIM3_DIER = TIM_DIER_UIE;
    TIM3_CR1 = TIM_CR1_URS | TIM_CR1_CEN;
}

/* As board_timer_isr_ack (tim2_stress.h): if the 16-bit TIM3 has already
 * passed the new period, restart it instead of letting it run to 2^16. */
static inline void board_timer_b_isr_ack(uint32_t next_period)
{
    TIM3_SR = ~TIM_SR_UIF;            /* rc_w0: write 0 to clear */
    TIM3_ARR = next_period - 1u;      /* no preload: applies to this period */
    if (TIM3_CNT >= next_period - 1u) TIM3_EGR = TIM_EGR_UG;
}

/* At the end of the interrupt: make sure the flag clear has landed, so the
 * interrupt is not taken again for the same event. */
static inline void board_timer_b_isr_end(void) { (void)TIM3_SR; }

static inline void board_timer_b_stop(void)
{
    TIM3_CR1 = 0;
    TIM3_DIER = 0;
    STM32_NVIC_ICER0 = 1u << TIM3_IRQN;
    __asm volatile("dsb\n isb" ::: "memory");
    TIM3_SR = 0;
    STM32_NVIC_ICPR0 = 1u << TIM3_IRQN;
}

/* NVIC priorities: lower value = more urgent; a = TIM2, b = TIM3. Written to
 * the top bits of the 8-bit field (works with >= 2 implemented bits). Word
 * read-modify-write: ARMv6-M (Cortex-M0+) does not allow byte access to
 * NVIC_IPR. */
static inline void board_irq_priorities(uint32_t a, uint32_t b)
{
    const uint32_t irq[2] = {TIM2_IRQN, TIM3_IRQN}, pri[2] = {a, b};
    for (int i = 0; i < 2; i++) {
        volatile uint32_t *ipr = (volatile uint32_t *)(0xE000E400u + 4u * (irq[i] / 4u));
        uint32_t sh = 8u * (irq[i] % 4u);
        *ipr = (*ipr & ~(0xFFu << sh)) | ((pri[i] << 6) & 0xFFu) << sh;
    }
}
