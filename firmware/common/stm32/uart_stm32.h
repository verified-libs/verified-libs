/* Polled UART for the STM32 boards (USART and LPUART share the registers
 * used here: CR1 0x00, BRR 0x0C, ISR 0x1C, ICR 0x20, RDR 0x24, TDR 0x28;
 * from cmsis-device-g0/g4/h7). The board's board_uart.h defines:
 *   SU_BASE        the USART
 *   SU_BRR         its baud rate register value for 115200
 *   su_clocks_pins() enabling the clocks and setting TX/RX to their AF
 * No interrupt is ever enabled: it cannot disturb a stress test. */
#pragma once
#include <stdint.h>

#define SU_REG(o) (*(volatile uint32_t *)(SU_BASE + (o)))

static inline void uart_init(void)
{
    su_clocks_pins();
    SU_REG(0x00) = 0;                          /* CR1: off */
    SU_REG(0x0C) = SU_BRR;
    SU_REG(0x00) = (1u << 3) | (1u << 2) | 1u; /* TE, RE, UE */
}

static inline void uart_putc(char c)
{
    while (!(SU_REG(0x1C) & (1u << 7))) {}     /* ISR.TXE */
    SU_REG(0x28) = (uint8_t)c;
}

static inline void uart_flush(void)
{
    while (!(SU_REG(0x1C) & (1u << 6))) {}     /* ISR.TC */
}

/* A received byte, or -1; errors (PE, FE, NE, ORE) are cleared. */
static inline int uart_getc(void)
{
    uint32_t isr = SU_REG(0x1C);
    if (isr & 0xFu) SU_REG(0x20) = 0xFu;
    if (isr & (1u << 5)) return (int)(SU_REG(0x24) & 0xFFu);   /* RXNE */
    return -1;
}
