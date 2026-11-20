/* A DMA stream as a real producer for rb-dma-stress (plan 2b) on the
 * STM32H723: DMA1 stream 0, requested through DMAMUX1 channel 0 by TIM6
 * update events, one byte per TIM6 period from a source table into the area
 * a library handed out. Registers and values from RM0468:
 *   DMA1 0x40020000 (15.5): LIFCR 0x008 (stream 0: CFEIF0 0, CDMEIF0 2,
 *     CTEIF0 3, CHTIF0 4, CTCIF0 5); S0CR 0x010, S0NDTR 0x014, S0PAR 0x018,
 *     S0M0AR 0x01C, S0FCR 0x024 (0: direct mode). SxCR: EN 0, TCIE 4,
 *     DIR[7:6] 00 peripheral -> memory, PINC 9, MINC 10, PSIZE/MSIZE 8 bit
 *   DMAMUX1 0x40020800 (17.6): C0CR, DMAREQ_ID[6:0]; TIM6_UP = 69;
 *     DMAMUX1 channel 0 drives DMA1 stream 0
 *   RCC 0x58024400: AHB1ENR 0x0D8 (DMA1EN 0), APB1LENR 0x0E8 (TIM6EN 4)
 *   TIM6 0x40001000 (47.4): as on the G474
 *   DMA1 stream 0 interrupt: position 11 (DMA1_STR0)
 * DMA1 cannot reach the DTCM, where the board's other firmware keeps its
 * data: this firmware links .data/.bss into AXI SRAM (stm32h723_dma.ld,
 * LD_DMA in board.mk) and keeps only the result block, the selection words
 * and the stack in DTCM. board_dma_mem_init() makes the AXI SRAM normal,
 * non-cacheable memory (MPU region 0), so neither side needs cache
 * maintenance: the usual way to give a DMA buffer to software that has
 * none. (A cacheable variant is a separate question: where each library's
 * API lets the clean/invalidate go.) */
#pragma once
#include <stdint.h>

#define BOARD_HAS_DMA 1
#define BOARD_DMA_IRQ_HANDLER DMA1_Stream0_IRQHandler
#define BOARD_DMA_IRQN 11u

#define H7_DMA1_LIFCR  (*(volatile uint32_t *)0x40020008u)
#define H7_DMA1_S0CR   (*(volatile uint32_t *)0x40020010u)
#define H7_DMA1_S0NDTR (*(volatile uint32_t *)0x40020014u)
#define H7_DMA1_S0PAR  (*(volatile uint32_t *)0x40020018u)
#define H7_DMA1_S0M0AR (*(volatile uint32_t *)0x4002001Cu)
#define H7_DMA1_S0FCR  (*(volatile uint32_t *)0x40020024u)
#define H7_DMAMUX1_C0CR (*(volatile uint32_t *)0x40020800u)
#define H7_RCC_AHB1ENR  (*(volatile uint32_t *)0x580244D8u)
#define H7_RCC_APB1LENR (*(volatile uint32_t *)0x580244E8u)
#define H7_TIM6_CR1   (*(volatile uint32_t *)0x40001000u)
#define H7_TIM6_DIER  (*(volatile uint32_t *)0x4000100Cu)
#define H7_TIM6_EGR   (*(volatile uint32_t *)0x40001014u)
#define H7_TIM6_CNT   (*(volatile uint32_t *)0x40001024u)
#define H7_TIM6_PSC   (*(volatile uint32_t *)0x40001028u)
#define H7_TIM6_ARR   (*(volatile uint32_t *)0x4000102Cu)
#define H7_DMA_EN   (1u << 0)
#define H7_DMA_TCIE (1u << 4)
#define H7_DMA_PINC (1u << 9)
#define H7_DMA_MINC (1u << 10)
#define H7_DMA_S0_FLAGS 0x3Du            /* CFEIF0 CDMEIF0 CTEIF0 CHTIF0 CTCIF0 */
#define H7_NVIC_ISER0 (*(volatile uint32_t *)0xE000E100u)
#define H7_NVIC_ICER0 (*(volatile uint32_t *)0xE000E180u)
#define H7_NVIC_ICPR0 (*(volatile uint32_t *)0xE000E280u)
#define H7_NVIC_IPR(n) (*(volatile uint8_t *)(0xE000E400u + (n)))
/* Armv7-M MPU (ARMv7-M ARM B3.5) */
#define H7_MPU_CTRL (*(volatile uint32_t *)0xE000ED94u)
#define H7_MPU_RNR  (*(volatile uint32_t *)0xE000ED98u)
#define H7_MPU_RBAR (*(volatile uint32_t *)0xE000ED9Cu)
#define H7_MPU_RASR (*(volatile uint32_t *)0xE000EDA0u)

/* Before board_cache(1): AXI SRAM 0x24000000, 128 KB (present in every
 * TCM/AXI split, RM0468 table 8) as normal memory, not cacheable
 * (TEX 001, C 0, B 0), full access, no execution; the rest of the map
 * keeps the default (PRIVDEFENA). */
static inline void board_dma_mem_init(void)
{
    __asm volatile("dsb\n isb" ::: "memory");
    H7_MPU_CTRL = 0;
    H7_MPU_RNR = 0;
    H7_MPU_RBAR = 0x24000000u;
    H7_MPU_RASR = (1u << 28)            /* XN */
                | (3u << 24)            /* AP: full access */
                | (1u << 19)            /* TEX 001: normal, non-cacheable */
                | (16u << 1)            /* SIZE: 2^(16+1) = 128 KB */
                | 1u;                   /* ENABLE */
    H7_MPU_CTRL = (1u << 2) | 1u;       /* PRIVDEFENA, ENABLE */
    __asm volatile("dsb\n isb" ::: "memory");
}

/* Clocks, DMAMUX route, TIM6 running (one tick = 4 << prescaler timer
 * clock cycles, as TIM2 in the stress tests) and the DMA interrupt at
 * priority prio (0..3, the scale of board_irq_priorities). */
static inline void board_dma_init(uint32_t prescaler, uint32_t prio)
{
    H7_RCC_AHB1ENR |= 1u << 0;
    H7_RCC_APB1LENR |= 1u << 4;
    (void)H7_RCC_APB1LENR;
    H7_DMA1_S0CR = 0;
    while (H7_DMA1_S0CR & H7_DMA_EN) {}
    H7_DMA1_LIFCR = H7_DMA_S0_FLAGS;
    H7_DMAMUX1_C0CR = 69u;               /* TIM6_UP */
    H7_TIM6_CR1 = 0;
    H7_TIM6_PSC = (4u << prescaler) - 1u;
    H7_TIM6_ARR = 63u;
    H7_TIM6_CNT = 0;
    H7_TIM6_EGR = 1u;
    H7_TIM6_DIER = 1u << 8;              /* UDE */
    H7_NVIC_IPR(BOARD_DMA_IRQN) = (uint8_t)((prio << 6) & 0xFFu);
    H7_NVIC_ICPR0 = 1u << BOARD_DMA_IRQN;
    H7_NVIC_ISER0 = 1u << BOARD_DMA_IRQN;
    H7_TIM6_CR1 = 1u;
}

static inline void board_dma_start(const volatile void *src, volatile void *dst, uint32_t len, uint32_t period)
{
    H7_TIM6_ARR = period - 1u;
    H7_DMA1_S0PAR = (uint32_t)(uintptr_t)src;
    H7_DMA1_S0M0AR = (uint32_t)(uintptr_t)dst;
    H7_DMA1_S0NDTR = len;
    H7_DMA1_S0FCR = 0;                   /* direct mode */
    H7_DMA1_S0CR = H7_DMA_PINC | H7_DMA_MINC | H7_DMA_TCIE | H7_DMA_EN;
}

static inline uint32_t board_dma_remaining(void)
{
    return (H7_DMA1_S0CR & H7_DMA_EN) ? H7_DMA1_S0NDTR : 0u;
}

static inline void board_dma_isr_ack(void)
{
    H7_DMA1_LIFCR = H7_DMA_S0_FLAGS;
    H7_DMA1_S0CR = 0;
    while (H7_DMA1_S0CR & H7_DMA_EN) {}
}

static inline void board_dma_stop(void)
{
    H7_NVIC_ICER0 = 1u << BOARD_DMA_IRQN;
    H7_DMA1_S0CR = 0;
    while (H7_DMA1_S0CR & H7_DMA_EN) {}
    H7_DMA1_LIFCR = H7_DMA_S0_FLAGS;
    H7_TIM6_CR1 = 0;
    H7_NVIC_ICPR0 = 1u << BOARD_DMA_IRQN;
}

/* Cache maintenance by address for a DMA area in cacheable memory
 * (rb-dma-stress DMA_CACHE=2; Armv7-M ARM B2.2.7, the Cortex-M7's 32-byte
 * lines): before a transfer, clean + invalidate the lines of the area
 * (DCCIMVAC), so no dirty line is later written back over what the DMA
 * wrote; after it, invalidate them (DCIMVAC), so the core reads what the
 * DMA wrote. Whole lines: anything else in those lines is cleaned resp.
 * dropped too, which is safe only if the library keeps nothing else there. */
#define H7_SCB_DCIMVAC  (*(volatile uint32_t *)0xE000EF5Cu)
#define H7_SCB_DCCIMVAC (*(volatile uint32_t *)0xE000EF70u)
static inline void board_dma_cache_before(volatile void *p, uint32_t len)
{
    uintptr_t a = (uintptr_t)p & ~31u, e = (uintptr_t)p + len;
    __asm volatile("dsb" ::: "memory");
    for (; a < e; a += 32u) H7_SCB_DCCIMVAC = (uint32_t)a;
    __asm volatile("dsb\n isb" ::: "memory");
}
static inline void board_dma_cache_after(volatile void *p, uint32_t len)
{
    uintptr_t a = (uintptr_t)p & ~31u, e = (uintptr_t)p + len;
    __asm volatile("dsb" ::: "memory");
    for (; a < e; a += 32u) H7_SCB_DCIMVAC = (uint32_t)a;
    __asm volatile("dsb\n isb" ::: "memory");
}

