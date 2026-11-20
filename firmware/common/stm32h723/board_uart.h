/* UART to the ST-LINK's virtual COM port, NUCLEO-H723ZG: USART3, PD8 TX /
 * PD9 RX (AF7), clocked from PCLK1 = 64 MHz (HSI, D2CCIP2R default; 130 MHz
 * with BOARD_CLOCK_FAST, board.h).
 * Addresses from cmsis-device-h7 stm32h723xx.h. See ../stm32/uart_stm32.h. */
#pragma once
#include <stdint.h>
#define SU_BASE 0x40004800u                    /* USART3 */
#if defined(BOARD_CLOCK_FAST) && BOARD_CLOCK_FAST
#define SU_BRR  1128u                          /* PCLK1 130 MHz (board.h, 520 MHz) / 115200 */
#else
#define SU_BRR  556u                           /* 64 MHz / 115200 */
#endif
static inline void su_clocks_pins(void)
{
    *(volatile uint32_t *)0x580244E0u |= 1u << 3;   /* RCC_AHB4ENR.GPIODEN */
    *(volatile uint32_t *)0x580244E8u |= 1u << 18;  /* RCC_APB1LENR.USART3EN */
    (void)*(volatile uint32_t *)0x580244E8u;
    volatile uint32_t *moder = (volatile uint32_t *)0x58020C00u, *afrh = (volatile uint32_t *)0x58020C24u;
    *moder = (*moder & ~(0xFu << 16)) | (0xAu << 16); /* PD8, PD9: alternate function */
    *afrh = (*afrh & ~0xFFu) | 0x77u;                  /* AF7 */
}
#include "../stm32/uart_stm32.h"
