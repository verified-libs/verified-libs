/* UART to the ST-LINK's virtual COM port, NUCLEO-G474RE: LPUART1, PA2 TX /
 * PA3 RX (AF12), clocked from PCLK1 = 170 MHz (CCIPR default). Addresses
 * from cmsis-device-g4 stm32g474xx.h. See ../stm32/uart_stm32.h. */
#pragma once
#include <stdint.h>
#define SU_BASE 0x40008000u                    /* LPUART1 */
#define SU_BRR  377778u                        /* LPUART: 256 * 170 MHz / 115200 */
static inline void su_clocks_pins(void)
{
    *(volatile uint32_t *)0x4002104Cu |= 1u << 0;   /* RCC_AHB2ENR.GPIOAEN */
    *(volatile uint32_t *)0x4002105Cu |= 1u << 0;   /* RCC_APB1ENR2.LPUART1EN */
    (void)*(volatile uint32_t *)0x4002105Cu;
    volatile uint32_t *moder = (volatile uint32_t *)0x48000000u, *afrl = (volatile uint32_t *)0x48000020u;
    *moder = (*moder & ~(0xFu << 4)) | (0xAu << 4); /* PA2, PA3: alternate function */
    *afrl = (*afrl & ~(0xFFu << 8)) | (0xCCu << 8); /* AF12 */
}
#include "../stm32/uart_stm32.h"
