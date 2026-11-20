/* A DMA channel as a real producer for rb-dma-stress (plan 2b): DMA1
 * channel 1, requested through DMAMUX1 channel 0 by TIM6 update events, so
 * it copies one byte per TIM6 period from a source table into the area a
 * library handed out, while the core runs on. Registers and values from
 * RM0440 Rev 9:
 *   DMA1 0x40020000 (12.6.7): CCR1 0x08, CNDTR1 0x0C, CPAR1 0x10, CMAR1 0x14,
 *     ISR 0x00 (TCIF1 bit 1), IFCR 0x04 (CGIF1 bit 0); CCRx: EN 0, TCIE 1,
 *     DIR 4 (0: peripheral -> memory), PINC 6, MINC 7, PSIZE/MSIZE 8 bit = 0
 *   DMAMUX1 0x40020800 (13.6.7): C0CR 0x00, DMAREQ_ID[6:0]; TIM6_UP = 8
 *     (table 93); DMAMUX channel 0 drives DMA1 channel 1
 *   RCC 0x40021000: AHB1ENR 0x48 (DMA1EN 0, DMAMUX1EN 2), APB1ENR1 0x58
 *     (TIM6EN 4)
 *   TIM6 0x40001000 (32.4.9): CR1 0x00, DIER 0x0C (UDE 8), EGR 0x14, CNT
 *     0x24, PSC 0x28, ARR 0x2C
 *   DMA1_CH1 interrupt: position 11 (vector table)
 * "Peripheral" here is the source table in SRAM (PINC), which the DMA reads
 * like any address; the request pacing comes from TIM6. */
#pragma once
#include <stdint.h>

#define BOARD_HAS_DMA 1
#define BOARD_DMA_IRQ_HANDLER DMA1_Channel1_IRQHandler
#define BOARD_DMA_IRQN 11u

#define G4_DMA1_ISR   (*(volatile uint32_t *)0x40020000u)
#define G4_DMA1_IFCR  (*(volatile uint32_t *)0x40020004u)
#define G4_DMA1_CCR1  (*(volatile uint32_t *)0x40020008u)
#define G4_DMA1_CNDTR1 (*(volatile uint32_t *)0x4002000Cu)
#define G4_DMA1_CPAR1 (*(volatile uint32_t *)0x40020010u)
#define G4_DMA1_CMAR1 (*(volatile uint32_t *)0x40020014u)
#define G4_DMAMUX_C0CR (*(volatile uint32_t *)0x40020800u)
#define G4_RCC_AHB1ENR (*(volatile uint32_t *)0x40021048u)
#define G4_RCC_APB1ENR1 (*(volatile uint32_t *)0x40021058u)
#define G4_TIM6_CR1   (*(volatile uint32_t *)0x40001000u)
#define G4_TIM6_DIER  (*(volatile uint32_t *)0x4000100Cu)
#define G4_TIM6_EGR   (*(volatile uint32_t *)0x40001014u)
#define G4_TIM6_CNT   (*(volatile uint32_t *)0x40001024u)
#define G4_TIM6_PSC   (*(volatile uint32_t *)0x40001028u)
#define G4_TIM6_ARR   (*(volatile uint32_t *)0x4000102Cu)
#define G4_DMA_CCR_EN   (1u << 0)
#define G4_DMA_CCR_TCIE (1u << 1)
#define G4_DMA_CCR_PINC (1u << 6)
#define G4_DMA_CCR_MINC (1u << 7)
#define G4_NVIC_ISER0 (*(volatile uint32_t *)0xE000E100u)
#define G4_NVIC_ICER0 (*(volatile uint32_t *)0xE000E180u)
#define G4_NVIC_ICPR0 (*(volatile uint32_t *)0xE000E280u)
#define G4_NVIC_IPR(n) (*(volatile uint8_t *)(0xE000E400u + (n)))

/* Nothing to do on the G474: no cache, and DMA1 reaches all SRAM. */
static inline void board_dma_mem_init(void) {}
static inline void board_dma_cache_before(volatile void *p, uint32_t len) { (void)p; (void)len; }
static inline void board_dma_cache_after(volatile void *p, uint32_t len) { (void)p; (void)len; }

/* Clocks, DMAMUX route, TIM6 running with the given prescaler (one tick =
 * 4 << prescaler core cycles, as TIM2 in the stress tests) and the DMA
 * interrupt at priority prio (0..3, 0 highest; the scale of
 * board_irq_priorities in ../stm32/tim3_stress_b.h). */
static inline void board_dma_init(uint32_t prescaler, uint32_t prio)
{
    G4_RCC_AHB1ENR |= (1u << 0) | (1u << 2);
    G4_RCC_APB1ENR1 |= 1u << 4;
    (void)G4_RCC_APB1ENR1;
    G4_DMA1_CCR1 = 0;
    G4_DMA1_IFCR = 1u << 0;
    G4_DMAMUX_C0CR = 8u;                 /* TIM6_UP */
    G4_TIM6_CR1 = 0;
    G4_TIM6_PSC = (4u << prescaler) - 1u;
    G4_TIM6_ARR = 63u;
    G4_TIM6_CNT = 0;
    G4_TIM6_EGR = 1u;                    /* load PSC */
    G4_TIM6_DIER = 1u << 8;              /* UDE: a DMA request per update */
    G4_NVIC_IPR(BOARD_DMA_IRQN) = (uint8_t)((prio << 6) & 0xFFu);   /* as board_irq_priorities */
    G4_NVIC_ICPR0 = 1u << BOARD_DMA_IRQN;
    G4_NVIC_ISER0 = 1u << BOARD_DMA_IRQN;
    G4_TIM6_CR1 = 1u;                    /* CEN */
}

/* Start a transfer of len bytes from src to dst, one byte per period TIM6
 * ticks (2..65536); the transfer-complete interrupt follows the last. */
static inline void board_dma_start(const volatile void *src, volatile void *dst, uint32_t len, uint32_t period)
{
    G4_TIM6_ARR = period - 1u;
    G4_DMA1_CPAR1 = (uint32_t)(uintptr_t)src;
    G4_DMA1_CMAR1 = (uint32_t)(uintptr_t)dst;
    G4_DMA1_CNDTR1 = len;
    G4_DMA1_CCR1 = G4_DMA_CCR_PINC | G4_DMA_CCR_MINC | G4_DMA_CCR_TCIE | G4_DMA_CCR_EN;
}

/* Bytes still to transfer (0 when idle or done). */
static inline uint32_t board_dma_remaining(void)
{
    return (G4_DMA1_CCR1 & G4_DMA_CCR_EN) ? G4_DMA1_CNDTR1 : 0u;
}

/* In the interrupt: clear the flags and disable the channel (needed before
 * the next start writes CPAR/CMAR/CNDTR). */
static inline void board_dma_isr_ack(void)
{
    G4_DMA1_IFCR = 1u << 0;
    G4_DMA1_CCR1 = 0;
    (void)G4_DMA1_CCR1;
}

static inline void board_dma_stop(void)
{
    G4_NVIC_ICER0 = 1u << BOARD_DMA_IRQN;
    G4_DMA1_CCR1 = 0;
    G4_DMA1_IFCR = 1u << 0;
    G4_TIM6_CR1 = 0;
    G4_NVIC_ICPR0 = 1u << BOARD_DMA_IRQN;
}
