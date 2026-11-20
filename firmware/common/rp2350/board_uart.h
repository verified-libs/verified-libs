/* UART to the Raspberry Pi Debug Probe's UART port (cable on GP0 TX / GP1
 * RX: UART0, function 2), 115200 8N1 from clk_peri = clk_sys (150 MHz),
 * polled; no interrupt is ever enabled, so it cannot disturb a stress test.
 * Addresses from pico-sdk src/rp2350/hardware_regs. */
#pragma once
#include <stdint.h>
#define PU_REG(a) (*(volatile uint32_t *)(a))
#define PU_UART   0x40070000u                          /* UART0 (PL011) */
/* One library per reset (main.c): the selection survives the reset in the
 * watchdog's SCRATCH0-2 (the boot ROM uses SRAM and SCRATCH4-7). */
#define BOARD_SELECT_ADDR 0x400D800Cu

static inline void uart_init(void)
{
    PU_REG(0x40010000u + 0x48u) = (1u << 11);          /* CLK_PERI_CTRL: ENABLE, AUXSRC clk_sys */
    uint32_t bits = (1u << 26) | (1u << 9) | (1u << 6);   /* RESETS: UART0, PADS_BANK0, IO_BANK0 */
    PU_REG(0x40020000u + 0x3000u) = bits;              /* RESETS_RESET, atomic clear alias */
    while ((PU_REG(0x40020000u + 0x08u) & bits) != bits) {}   /* RESET_DONE */
    PU_REG(0x40038000u + 0x04u) = (1u << 6) | (1u << 4);   /* PADS GPIO0: IE, drive 4 mA; ISO cleared */
    PU_REG(0x40038000u + 0x08u) = (1u << 6) | (1u << 3);   /* PADS GPIO1: IE, pull-up; ISO cleared */
    PU_REG(0x40028000u + 0x04u) = 2u;                  /* GPIO0_CTRL: UART0_TX */
    PU_REG(0x40028000u + 0x0Cu) = 2u;                  /* GPIO1_CTRL: UART0_RX */
    PU_REG(PU_UART + 0x30u) = 0;                       /* CR: off */
    PU_REG(PU_UART + 0x24u) = 81u;                     /* IBRD: 150 MHz / (16 * 115200) = 81.38 */
    PU_REG(PU_UART + 0x28u) = 24u;                     /* FBRD: 0.38 * 64 */
    PU_REG(PU_UART + 0x2Cu) = (3u << 5) | (1u << 4);   /* LCR_H: 8 bits, FIFOs on */
    PU_REG(PU_UART + 0x30u) = (1u << 9) | (1u << 8) | 1u;   /* CR: RXE, TXE, UARTEN */
}

static inline void uart_putc(char c)
{
    while (PU_REG(PU_UART + 0x18u) & (1u << 5)) {}    /* FR.TXFF */
    PU_REG(PU_UART + 0x00u) = (uint8_t)c;
}

static inline void uart_flush(void) { while (PU_REG(PU_UART + 0x18u) & (1u << 3)) {} }   /* FR.BUSY */

static inline int uart_getc(void)
{
    if (PU_REG(PU_UART + 0x18u) & (1u << 4)) return -1;   /* FR.RXFE */
    return (int)(PU_REG(PU_UART + 0x00u) & 0xFFu);
}
