/* UART to the ST-LINK's virtual COM port, NUCLEO-G0B1RE: USART2, PA2 TX /
 * PA3 RX (AF1), clocked from PCLK = 64 MHz (CCIPR default). Addresses from
 * cmsis-device-g0 stm32g0b1xx.h. See ../stm32/uart_stm32.h. */
#pragma once
#include <stdint.h>
#define SU_BASE 0x40004400u                    /* USART2 */
#define SU_BRR  556u                           /* 64 MHz / 115200 */
static inline void su_clocks_pins(void)
{
    *(volatile uint32_t *)0x40021034u |= 1u << 0;   /* RCC_IOPENR.GPIOAEN */
    *(volatile uint32_t *)0x4002103Cu |= 1u << 17;  /* RCC_APBENR1.USART2EN */
    (void)*(volatile uint32_t *)0x4002103Cu;
    volatile uint32_t *moder = (volatile uint32_t *)0x50000000u, *afrl = (volatile uint32_t *)0x50000020u;
    *moder = (*moder & ~(0xFu << 4)) | (0xAu << 4); /* PA2, PA3: alternate function */
    *afrl = (*afrl & ~(0xFFu << 8)) | (0x11u << 8); /* AF1 */
}
#include "../stm32/uart_stm32.h"
