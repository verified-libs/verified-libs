/*
 * Interrupt source for the stress test on the STM32 boards: TIM2 with the
 * update interrupt, period set anew in every interrupt. Included by the
 * STM32 board.h files, which define before including it:
 *   TIM2_RCC_ENR / TIM2_RCC_EN_BIT  clock enable register and bit of TIM2
 *   TIM2_IRQN                      TIM2 interrupt number
 * TIM2 runs at the core clock on all three boards (APB prescaler 1), so one
 * timer tick = 4 << prescaler core cycles, the same scale as the nRF5340's
 * 16 MHz TIMER0 at 64 MHz. The counter restarts from 0 at every update
 * event, so a debugger halt cannot make it miss the next interrupt.
 *
 * TIM2 register layout and bits (same on G0, G4, H7): cmsis-device-g0/g4/h7,
 * TIM_TypeDef and TIM_CR1/DIER/SR/EGR bit definitions; TIM2_BASE 0x40000000.
 */
#pragma once
#include <stdint.h>

#define TIM2_CR1   (*(volatile uint32_t *)0x40000000u)
#define TIM2_DIER  (*(volatile uint32_t *)0x4000000Cu)
#define TIM2_SR    (*(volatile uint32_t *)0x40000010u)
#define TIM2_EGR   (*(volatile uint32_t *)0x40000014u)
#define TIM2_CNT   (*(volatile uint32_t *)0x40000024u)
#define TIM2_PSC   (*(volatile uint32_t *)0x40000028u)
#define TIM2_ARR   (*(volatile uint32_t *)0x4000002Cu)
#define TIM_CR1_CEN   (1u << 0)
#define TIM_CR1_URS   (1u << 2)   /* update interrupt only from overflow, not from UG */
#define TIM_DIER_UIE  (1u << 0)
#define TIM_SR_UIF    (1u << 0)
#define TIM_EGR_UG    (1u << 0)

#define STM32_NVIC_ISER0  (*(volatile uint32_t *)0xE000E100u)
#define STM32_NVIC_ICER0  (*(volatile uint32_t *)0xE000E180u)
#define STM32_NVIC_ICPR0  (*(volatile uint32_t *)0xE000E280u)

#define BOARD_TIMER_IRQ_HANDLER TIM2_IRQHandler

/* period in timer ticks (>= 2) */
static inline void board_timer_start(uint32_t prescaler, uint32_t first_period)
{
    TIM2_RCC_ENR |= TIM2_RCC_EN_BIT;
    (void)TIM2_RCC_ENR;
    TIM2_CR1 = TIM_CR1_URS;
    TIM2_DIER = 0;
    TIM2_PSC = (4u << prescaler) - 1u;
    TIM2_ARR = first_period - 1u;
    TIM2_CNT = 0;
    TIM2_EGR = TIM_EGR_UG;            /* load PSC; URS: no interrupt from this */
    TIM2_SR = 0;
    STM32_NVIC_ICPR0 = 1u << TIM2_IRQN;
    STM32_NVIC_ISER0 = 1u << TIM2_IRQN;
    TIM2_DIER = TIM_DIER_UIE;
    TIM2_CR1 = TIM_CR1_URS | TIM_CR1_CEN;
}

/* In the interrupt: acknowledge, and set the period until the next one.
 * TIM2 is a 32-bit counter. If it has already passed the new period when
 * ARR is written (late interrupt, or the core was halted while the timer
 * ran), it would count on to 2^32 before the next update: about 100 s at
 * 170 MHz / 4, during which the test stalls (seen on the G474, 2026-11-11).
 * So restart it from 0 in that case (UG with URS set: no extra interrupt),
 * like the nRF5340's 8-bit timer, which wraps within 256 ticks. */
static inline void board_timer_isr_ack(uint32_t next_period)
{
    TIM2_SR = ~TIM_SR_UIF;            /* rc_w0: write 0 to clear */
    TIM2_ARR = next_period - 1u;      /* no preload: applies to this period */
    if (TIM2_CNT >= next_period - 1u) TIM2_EGR = TIM_EGR_UG;
}

/* At the end of the interrupt: make sure the flag clear has landed, so the
 * interrupt is not taken again for the same event. */
static inline void board_timer_isr_end(void) { (void)TIM2_SR; }

static inline void board_timer_stop(void)
{
    TIM2_CR1 = 0;
    TIM2_DIER = 0;
    STM32_NVIC_ICER0 = 1u << TIM2_IRQN;
    __asm volatile("dsb\n isb" ::: "memory");
    TIM2_SR = 0;
    STM32_NVIC_ICPR0 = 1u << TIM2_IRQN;
}
