/* UART to the EDBG's virtual COM port (SAM D20 Xplained Pro: SERCOM3, PA24
 * TX = PAD2 / PA25 RX = PAD3, peripheral function C), 115200 8N1 from GCLK0
 * (48 MHz), polled; no interrupt is ever enabled, so it cannot disturb a
 * stress test. Addresses from hal_atmel asf/sam0/include/samd20. */
#pragma once
#include <stdint.h>
#define DU_S32(o)  (*(volatile uint32_t *)(0x42001400u + (o)))   /* SERCOM3 */
#define DU_S16(o)  (*(volatile uint16_t *)(0x42001400u + (o)))
#define DU_S8(o)   (*(volatile uint8_t *)(0x42001400u + (o)))
#define DU_PORT8(o) (*(volatile uint8_t *)(0x41004400u + (o)))   /* PORT group A */

static inline void du_sync(void) { while (DU_S16(0x10) & (1u << 15)) {} }   /* STATUS.SYNCBUSY */

static inline void uart_init(void)
{
    *(volatile uint32_t *)0x40000420u |= 1u << 5;                  /* PM_APBCMASK.SERCOM3 */
    *(volatile uint16_t *)0x40000C02u = (uint16_t)(16u | (1u << 14));   /* GCLK_CLKCTRL: SERCOM3_CORE from GCLK0 */
    while (*(volatile uint8_t *)0x40000C01u & (1u << 7)) {}        /* GCLK_STATUS.SYNCBUSY */
    DU_PORT8(0x30 + 12) = 0x22u;                                  /* PMUX12: PA24, PA25 -> C */
    DU_PORT8(0x40 + 24) = 1u;                                     /* PINCFG24: PMUXEN */
    DU_PORT8(0x40 + 25) = 1u | 2u;                                /* PINCFG25: PMUXEN, INEN */
    DU_S32(0x00) = 0; du_sync();
    DU_S32(0x00) = (1u << 30) | (3u << 20) | (1u << 16) | (1u << 2);   /* DORD, RXPO PAD3, TXPO PAD2, MODE internal clock */
    du_sync();
    DU_S32(0x04) = (1u << 17) | (1u << 16); du_sync();            /* CTRLB: RXEN, TXEN, 8 bits */
    DU_S16(0x0A) = 63019u;                                        /* BAUD: 65536 * (1 - 16 * 115200 / 48 MHz) */
    DU_S32(0x00) |= 1u << 1; du_sync();                           /* ENABLE */
}

static inline void uart_putc(char c)
{
    while (!(DU_S8(0x0E) & 1u)) {}            /* INTFLAG.DRE */
    DU_S16(0x18) = (uint8_t)c;
}

static inline void uart_flush(void) { while (!(DU_S8(0x0E) & 2u)) {} }   /* INTFLAG.TXC */

static inline int uart_getc(void)
{
    if (DU_S16(0x10) & 0x7u) DU_S16(0x10) = 0x7u;   /* STATUS: PERR, FERR, BUFOVF */
    if (!(DU_S8(0x0E) & 4u)) return -1;              /* INTFLAG.RXC */
    return DU_S16(0x18) & 0xFFu;
}
