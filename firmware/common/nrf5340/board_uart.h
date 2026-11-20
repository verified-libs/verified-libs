/* UART to the J-Link's virtual COM port (nRF5340 DK, VCOM0: UARTE0 of the
 * application core, P0.20 TX / P0.22 RX), 115200 8N1, polled through
 * EasyDMA with one-byte buffers; no interrupt is ever enabled, so it cannot
 * disturb a stress test. Secure addresses, as the rest of this board layer. */
#pragma once
#include <stdint.h>
#define NU_REG(o)     (*(volatile uint32_t *)(0x50008000u + (o)))   /* UARTE0 */
#define NU_P0(o)      (*(volatile uint32_t *)(0x50842500u + (o)))   /* GPIO P0 */
#define NU_TX_PIN     20u
#define NU_RX_PIN     22u
static volatile uint8_t nu_txb, nu_rxb;

static inline void uart_init(void)
{
    NU_REG(0x500) = 0;                         /* ENABLE: off */
    NU_P0(0x008) = 1u << NU_TX_PIN;            /* OUTSET: TX idles high */
    NU_P0(0x018) = 1u << NU_TX_PIN;            /* DIRSET */
    NU_REG(0x50C) = NU_TX_PIN;                 /* PSEL.TXD: port 0 */
    NU_REG(0x514) = NU_RX_PIN;                 /* PSEL.RXD */
    NU_REG(0x524) = 0x01D60000u;               /* BAUDRATE 115200 */
    NU_REG(0x56C) = 0;                         /* CONFIG: no parity, no flow control */
    NU_REG(0x500) = 8u;                        /* ENABLE: UARTE */
    NU_REG(0x534) = (uint32_t)&nu_rxb;         /* RXD.PTR */
    NU_REG(0x538) = 1u;                        /* RXD.MAXCNT */
    NU_REG(0x200) = 1u << 5;                   /* SHORTS: ENDRX -> STARTRX */
    NU_REG(0x110) = 0;                         /* EVENTS_ENDRX */
    NU_REG(0x000) = 1u;                        /* TASKS_STARTRX */
}

static inline void uart_putc(char c)
{
    nu_txb = (uint8_t)c;
    NU_REG(0x544) = (uint32_t)&nu_txb;         /* TXD.PTR */
    NU_REG(0x548) = 1u;                        /* TXD.MAXCNT */
    NU_REG(0x120) = 0;                         /* EVENTS_ENDTX */
    NU_REG(0x008) = 1u;                        /* TASKS_STARTTX */
    while (!NU_REG(0x120)) {}
}

static inline void uart_flush(void) {}         /* uart_putc waits for ENDTX */

static inline int uart_getc(void)
{
    if (!NU_REG(0x110)) return -1;             /* EVENTS_ENDRX */
    NU_REG(0x110) = 0;
    return nu_rxb;
}
