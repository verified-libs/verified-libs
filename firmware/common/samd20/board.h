/*
 * Board layer for the benchmark and stress firmware: SAM D20 Xplained Pro
 * (ATSAMD20J18A, Cortex-M0+). Same interface as common/nrf5340/board.h.
 *
 * Clock: DFLL48M in closed-loop mode, locked to the board's 32.768 kHz
 * crystal (XOSC32K -> GCLK1 -> DFLL reference), MUL 1465: 48.005 MHz. Open
 * loop with the factory calibration is not usable on this chip: its DFLL
 * coarse calibration reads 0 and the fine one is unprogrammed (2026-11-11;
 * the open-loop attempt locked up the core). 1 flash wait state (NVM
 * CTRLB.RWS), set before the switch: the SAM D20 needs it above 24 MHz.
 * DFLL bring-up as in Microchip's ASF (ONDEMAND cleared first: DFLL errata).
 * If the crystal or the lock does not come within ~1.5 s, the clock stays
 * at 8 MHz (OSC8M) and clock_hz in the record says so. The first runs on
 * 2026-11-11 were at 8 MHz with 0 wait states.
 *
 * All register addresses, offsets, bit positions and IDs: Zephyr hal_atmel
 * (commit 8f95c79f), asf/sam0/include/samd20 (samd20j18.h, component/ and
 * instance/ headers), Microchip's device headers.
 *
 * Timing: no DWT on the Cortex-M0+, so time_call() reads the 24-bit SysTick
 * counter, as on the STM32G0B1.
 */
#pragma once
#include <stdint.h>
#include "bench.h"

#define BOARD_ID 5u              /* decode.py: BOARDS */
#define BOARD_READ_OVERHEAD 2u   /* LDR on the Cortex-M0+, as on the G0B1 */

#define D20_REG32(a) (*(volatile uint32_t *)(a))
#define D20_REG16(a) (*(volatile uint16_t *)(a))
#define D20_REG8(a)  (*(volatile uint8_t *)(a))

#define SYSCTRL_OSC8M    D20_REG32(0x40000800u + 0x20u)   /* SYSCTRL + OSC8M_OFFSET */
#define OSC8M_PRESC_Msk  (3u << 8)
#define NVMCTRL_CTRLB    D20_REG32(0x41004000u + 0x04u)
#define NVMCTRL_CTRLB_RWS_Msk  (0xFu << 1)
#define NVMCTRL_CTRLB_CACHEDIS (1u << 18)
#define PM_APBCMASK      D20_REG32(0x40000400u + 0x20u)
#define GCLK_STATUS      D20_REG8(0x40000C00u + 0x01u)
#define GCLK_CLKCTRL     D20_REG16(0x40000C00u + 0x02u)
#define GCLK_STATUS_SYNCBUSY (1u << 7)
#define GCLK_CLKCTRL_CLKEN   (1u << 14)   /* GEN = 0 (GCLK0) */

#define SYST_CSR  D20_REG32(0xE000E010u)
#define SYST_RVR  D20_REG32(0xE000E014u)
#define SYST_CVR  D20_REG32(0xE000E018u)

#define SYSCTRL_PCLKSR    D20_REG32(0x40000800u + 0x0Cu)
#define SYSCTRL_XOSC32K   D20_REG16(0x40000800u + 0x14u)
#define SYSCTRL_DFLLCTRL  D20_REG16(0x40000800u + 0x24u)
#define SYSCTRL_DFLLMUL   D20_REG32(0x40000800u + 0x2Cu)
#define PCLKSR_XOSC32KRDY (1u << 1)
#define PCLKSR_DFLLRDY    (1u << 4)
#define PCLKSR_DFLLLCKF   (1u << 6)
#define PCLKSR_DFLLLCKC   (1u << 7)
#define DFLLCTRL_ENABLE   (1u << 1)
#define DFLLCTRL_MODE     (1u << 2)          /* closed loop */
#define GCLK_GENCTRL      D20_REG32(0x40000C00u + 0x04u)
#define GCLK_GENDIV       D20_REG32(0x40000C00u + 0x08u)

static inline int d20_wait(uint32_t mask, uint32_t want)
{
    for (uint32_t t = 0; t < 4000000u; t++)          /* ~1.5 s at 8 MHz */
        if ((SYSCTRL_PCLKSR & mask) == want) return 1;
    return 0;
}

/* Returns 1 if clk_sys now runs from the DFLL at 48 MHz, 0 if it stayed on
 * OSC8M (8 MHz) because the 32 kHz crystal or the DFLL lock did not come. */
static inline int d20_clock_48mhz(void)
{
    /* 32.768 kHz crystal on the Xplained Pro (XOSC32K): XTALEN, EN32K,
     * AAMPEN, startup 6 (~1 s), ENABLE. */
    SYSCTRL_XOSC32K = (uint16_t)((6u << 8) | (1u << 5) | (1u << 3) | (1u << 2));
    SYSCTRL_XOSC32K |= (1u << 1);
    if (!d20_wait(PCLKSR_XOSC32KRDY, PCLKSR_XOSC32KRDY)) return 0;
    /* GCLK1 <- XOSC32K (/1), and the DFLL reference (CLKCTRL ID 0) <- GCLK1. */
    GCLK_GENDIV = 1u;
    GCLK_GENCTRL = 1u | (5u << 8) | (1u << 16);
    while (GCLK_STATUS & GCLK_STATUS_SYNCBUSY) {}
    GCLK_CLKCTRL = (uint16_t)(0u | (1u << 8) | GCLK_CLKCTRL_CLKEN);
    while (GCLK_STATUS & GCLK_STATUS_SYNCBUSY) {}
    /* DFLL in closed loop: MUL = 48 MHz / 32768 Hz = 1464.8 -> 1465 (48.005
     * MHz); coarse/fine steps a quarter of their ranges, as Microchip's ASF.
     * ONDEMAND cleared first (DFLL errata). */
    SYSCTRL_DFLLCTRL = 0;
    if (!d20_wait(PCLKSR_DFLLRDY, PCLKSR_DFLLRDY)) return 0;
    SYSCTRL_DFLLMUL = (7u << 26) | (255u << 16) | 1465u;
    if (!d20_wait(PCLKSR_DFLLRDY, PCLKSR_DFLLRDY)) return 0;
    SYSCTRL_DFLLCTRL = DFLLCTRL_MODE | DFLLCTRL_ENABLE;
    if (!d20_wait(PCLKSR_DFLLLCKC | PCLKSR_DFLLLCKF, PCLKSR_DFLLLCKC | PCLKSR_DFLLLCKF)) {
        SYSCTRL_DFLLCTRL = 0;                    /* no lock: back off, stay on 8 MHz */
        return 0;
    }
    NVMCTRL_CTRLB = (NVMCTRL_CTRLB & ~NVMCTRL_CTRLB_RWS_Msk) | (1u << 1);   /* 1 wait state */
    GCLK_GENCTRL = 0u | (7u << 8) | (1u << 16);  /* GCLK0 <- DFLL48M, GENEN */
    while (GCLK_STATUS & GCLK_STATUS_SYNCBUSY) {}
    return 1;
}

static uint32_t d20_clk_hz;

static inline void board_init(void)
{
    SYSCTRL_OSC8M &= ~OSC8M_PRESC_Msk;               /* OSC8M /1 (8 MHz) first */
    d20_clk_hz = d20_clock_48mhz() ? 48005120u : 8000000u;   /* 1465 * 32768 */

    /* As on the other boards: wait a moment after the debugger has let the
     * core run, before measuring. */
    for (volatile uint32_t i = 0; i < 1500000u; i++) {}

    SYST_RVR = 0x00FFFFFFu;
    SYST_CVR = 0;
    SYST_CSR = (1u << 2) | 1u;   /* CLKSOURCE = core clock, ENABLE, no interrupt */
}

static inline uint32_t board_clock_hz(void) { return d20_clk_hz; }

/* "Cache" on the SAM D20 = the NVM read cache (NVMCTRL CTRLB.CACHEDIS). */
static inline void board_cache(int on)
{
    if (on) NVMCTRL_CTRLB &= ~NVMCTRL_CTRLB_CACHEDIS;
    else    NVMCTRL_CTRLB |= NVMCTRL_CTRLB_CACHEDIS;
}

static inline int board_counter_running(void)
{
    uint32_t a = SYST_CVR;
    __asm volatile("nop\n nop\n nop\n nop");
    return SYST_CVR != a;
}

static inline void board_idle(void) { for (;;) {} }

/* ---- Stress interrupt sources: TC0 (A) and TC2 (B), 16-bit, MFRQ ----
 * The counter counts GCLK0 / prescaler and restarts from 0 at TOP = CC0
 * (wave generation MFRQ), setting INTFLAG.OVF. One tick = 4 << prescaler
 * core cycles like on the other boards: TC prescaler DIV4/8/16 for
 * TIMER_PRESCALER 0/1/2, DIV64 for 4; 3 (DIV32) does not exist on the TC.
 * TC registers are synchronised to the TC clock (= core clock here): writes
 * to CC0/CTRLA and COUNT reads go through the sync logic (STATUS.SYNCBUSY,
 * READREQ). IDs: GCLK_CLKCTRL_ID_TC0_TC1 0x13, ID_TC2_TC3 0x14; PM_APBCMASK
 * TC0 bit 8, TC2 bit 10; TC0_IRQn 13, TC2_IRQn 15; TC0 0x42002000, TC2
 * 0x42002800 (TC1 + 0x400). */
#define TC_CTRLA(b)    D20_REG16((b) + 0x00u)
#define TC_READREQ(b)  D20_REG16((b) + 0x02u)
#define TC_CTRLBSET(b) D20_REG8((b) + 0x05u)
#define TC_INTENCLR(b) D20_REG8((b) + 0x0Cu)
#define TC_INTENSET(b) D20_REG8((b) + 0x0Du)
#define TC_INTFLAG(b)  D20_REG8((b) + 0x0Eu)
#define TC_STATUS(b)   D20_REG8((b) + 0x0Fu)
#define TC_COUNT(b)    D20_REG16((b) + 0x10u)
#define TC_CC0(b)      D20_REG16((b) + 0x18u)
#define TC_CTRLA_SWRST   (1u << 0)
#define TC_CTRLA_ENABLE  (1u << 1)
#define TC_CTRLA_MFRQ    (1u << 5)          /* WAVEGEN = 1 */
#define TC_CTRLA_PRESCSYNC_RESYNC (2u << 12)
#define TC_INT_OVF       (1u << 0)
#define TC_STATUS_SYNCBUSY (1u << 7)
#define TC_READREQ_RREQ  (1u << 15)
#define TC_CMD_RETRIGGER (1u << 6)          /* CTRLBSET.CMD = 1 */
#define D20_NVIC_ISER    D20_REG32(0xE000E100u)
#define D20_NVIC_ICER    D20_REG32(0xE000E180u)
#define D20_NVIC_ICPR    D20_REG32(0xE000E280u)

#define TC0_BASE 0x42002000u
#define TC2_BASE 0x42002800u
#define TC0_IRQN 13u
#define TC2_IRQN 15u

static inline void d20_tc_sync(uint32_t b) { while (TC_STATUS(b) & TC_STATUS_SYNCBUSY) {} }

static inline uint32_t d20_tc_presc(uint32_t prescaler)
{
    /* 4 << prescaler: DIV4 = 2, DIV8 = 3, DIV16 = 4, DIV64 = 5 */
    return prescaler <= 2u ? prescaler + 2u : 5u;
}

static inline void d20_tc_start(uint32_t b, uint32_t apb_bit, uint32_t gclk_id, uint32_t irq,
                                uint32_t prescaler, uint32_t first_period)
{
    PM_APBCMASK |= 1u << apb_bit;
    GCLK_CLKCTRL = (uint16_t)(GCLK_CLKCTRL_CLKEN | gclk_id);
    while (GCLK_STATUS & GCLK_STATUS_SYNCBUSY) {}
    TC_CTRLA(b) = TC_CTRLA_SWRST;
    while (TC_CTRLA(b) & TC_CTRLA_SWRST) {}
    TC_CTRLA(b) = (uint16_t)(TC_CTRLA_MFRQ | TC_CTRLA_PRESCSYNC_RESYNC | (d20_tc_presc(prescaler) << 8));
    d20_tc_sync(b);
    TC_CC0(b) = (uint16_t)(first_period - 1u);
    d20_tc_sync(b);
    TC_INTFLAG(b) = 0xFF;
    TC_INTENSET(b) = TC_INT_OVF;
    D20_NVIC_ICPR = 1u << irq;
    D20_NVIC_ISER = 1u << irq;
    TC_CTRLA(b) |= TC_CTRLA_ENABLE;
    d20_tc_sync(b);
}

/* In the interrupt: acknowledge and set the next period. If the counter has
 * already passed it, restart from 0 (RETRIGGER) instead of letting it run to
 * 2^16, as on the STM32 boards. */
static inline void d20_tc_ack(uint32_t b, uint32_t next_period)
{
    TC_INTFLAG(b) = TC_INT_OVF;                 /* write 1 to clear */
    TC_CC0(b) = (uint16_t)(next_period - 1u);
    d20_tc_sync(b);
    TC_READREQ(b) = (uint16_t)(TC_READREQ_RREQ | 0x10u);   /* read COUNT */
    d20_tc_sync(b);
    if (TC_COUNT(b) >= next_period - 1u) { TC_CTRLBSET(b) = TC_CMD_RETRIGGER; d20_tc_sync(b); }
}

static inline void d20_tc_stop(uint32_t b, uint32_t irq)
{
    TC_CTRLA(b) &= ~TC_CTRLA_ENABLE;
    d20_tc_sync(b);
    TC_INTENCLR(b) = TC_INT_OVF;
    D20_NVIC_ICER = 1u << irq;
    __asm volatile("dsb\n isb" ::: "memory");
    TC_INTFLAG(b) = 0xFF;
    D20_NVIC_ICPR = 1u << irq;
}

#define BOARD_TIMER_IRQ_HANDLER   TC0_Handler
#define BOARD_TIMER_B_IRQ_HANDLER TC2_Handler
static inline void board_timer_start(uint32_t p, uint32_t first) { d20_tc_start(TC0_BASE, 8u, 0x13u, TC0_IRQN, p, first); }
static inline void board_timer_isr_ack(uint32_t next) { d20_tc_ack(TC0_BASE, next); }
static inline void board_timer_isr_end(void) { (void)TC_INTFLAG(TC0_BASE); }
static inline void board_timer_stop(void) { d20_tc_stop(TC0_BASE, TC0_IRQN); }
static inline void board_timer_b_start(uint32_t p, uint32_t first) { d20_tc_start(TC2_BASE, 10u, 0x14u, TC2_IRQN, p, first); }
static inline void board_timer_b_isr_ack(uint32_t next) { d20_tc_ack(TC2_BASE, next); }
static inline void board_timer_b_isr_end(void) { (void)TC_INTFLAG(TC2_BASE); }
static inline void board_timer_b_stop(void) { d20_tc_stop(TC2_BASE, TC2_IRQN); }

/* NVIC priorities (2 implemented bits); word access, ARMv6-M. a = TC0, b = TC2. */
static inline void board_irq_priorities(uint32_t a, uint32_t b)
{
    const uint32_t irq[2] = {TC0_IRQN, TC2_IRQN}, pri[2] = {a, b};
    for (int i = 0; i < 2; i++) {
        volatile uint32_t *ipr = (volatile uint32_t *)(0xE000E400u + 4u * (irq[i] / 4u));
        uint32_t sh = 8u * (irq[i] % 4u);
        *ipr = (*ipr & ~(0xFFu << sh)) | ((pri[i] << 6) & 0xFFu) << sh;
    }
}

/* uint32_t time_call(rb_op op, uintptr_t a, uintptr_t b, uint32_t *ret)
 * Returns SysTick(before) - SysTick(after), modulo 2^24, around one call of
 * op(a, b). Same window as on the other boards: ldr t0 ; blx op ; <op> ;
 * ldr t1. ARMv6-M Thumb only. */
__attribute__((naked, noinline, aligned(32), unused))
static uint32_t time_call(rb_op op, uintptr_t a, uintptr_t b, uint32_t *ret)
{
    (void)op; (void)a; (void)b; (void)ret;
    __asm volatile(
        ".syntax unified\n"
        "push {r4, r5, r6, lr}\n"
        "mov  r4, r3\n"
        "ldr  r5, =0xE000E018\n"   /* SYST_CVR */
        "mov  r3, r0\n"
        "mov  r0, r1\n"
        "mov  r1, r2\n"
        "ldr  r6, [r5]\n"          /* t0 */
        "blx  r3\n"
        "ldr  r1, [r5]\n"          /* t1 */
        "str  r0, [r4]\n"
        "subs r0, r6, r1\n"        /* counts down */
        "lsls r0, r0, #8\n"        /* modulo 2^24 */
        "lsrs r0, r0, #8\n"
        "pop  {r4, r5, r6, pc}\n"
        ".ltorg\n");
}
