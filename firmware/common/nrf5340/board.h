/*
 * Board layer for the benchmark firmware: nRF5340 DK, application core
 * (Cortex-M33, 64 MHz). Every board directory under common/ provides a
 * board.h with the same interface:
 *   BOARD_ID, BOARD_READ_OVERHEAD (cycles of one counter read in time_call)
 *   board_init()            clock, counter, debug access
 *   board_clock_hz()        core clock the results were measured at
 *   board_cache(on)         instruction cache off (0) or invalidated + on (1)
 *   board_counter_running() 1 if the cycle counter advances
 *   time_call(op, a, b, &ret) cycles around one call of op(a, b)
 */
#pragma once
#include <stdint.h>
#include "nrf5340_bench.h"
#include "bench.h"

#define BOARD_ID 1u              /* decode.py: BOARDS */
#define BOARD_READ_OVERHEAD 1u   /* CYCCNT read, measured by nrf5340-cyccnt */

#define NRF_CACHE_INVALIDATE NRF_REG(0x50001504u)

static inline void board_init(void) { nrf5340_bench_init(); }

static inline uint32_t board_clock_hz(void)
{
    return NRF_CLOCK_HFCLKCTRL == 1u ? 64000000u : 128000000u;
}

static inline void board_cache(int on)
{
    NRF_CACHE_ENABLE = 0;
    if (on) {
        NRF_CACHE_INVALIDATE = 1;
        NRF_CACHE_ENABLE = 1;
    }
}

static inline int board_counter_running(void) { return cyccnt_running(); }

/* After the measurement: sleep; the debugger still reads RAM. */
static inline void board_idle(void) { for (;;) __asm volatile("wfi"); }

/* Stress test interrupt source: TIMER0 (nrfx MDK; IRQ 15), 16 MHz >>
 * prescaler, i.e. one tick = 4 << prescaler core cycles at 64 MHz. Same
 * interface as common/stm32/tim2_stress.h. */
#define TIMER0 0x5000F000u
#define TIMER0_TASKS_START    NRF_REG(TIMER0 + 0x000)
#define TIMER0_TASKS_STOP     NRF_REG(TIMER0 + 0x004)
#define TIMER0_TASKS_CLEAR    NRF_REG(TIMER0 + 0x00C)
#define TIMER0_EVENTS_COMPARE0 NRF_REG(TIMER0 + 0x140)
#define TIMER0_SHORTS         NRF_REG(TIMER0 + 0x200)
#define TIMER0_INTENSET       NRF_REG(TIMER0 + 0x304)
#define TIMER0_INTENCLR       NRF_REG(TIMER0 + 0x308)
#define TIMER0_MODE           NRF_REG(TIMER0 + 0x504)
#define TIMER0_BITMODE        NRF_REG(TIMER0 + 0x508)
#define TIMER0_PRESCALER      NRF_REG(TIMER0 + 0x510)
#define TIMER0_CC0            NRF_REG(TIMER0 + 0x540)
#define TIMER0_IRQN 15u
#define NVIC_ISER0  NRF_REG(0xE000E100u)
#define NVIC_ICER0  NRF_REG(0xE000E180u)
#define NVIC_ICPR0  NRF_REG(0xE000E280u)

#define BOARD_TIMER_IRQ_HANDLER TIMER0_IRQHandler

static inline void board_timer_start(uint32_t prescaler, uint32_t first_period)
{
    TIMER0_TASKS_STOP = 1;
    TIMER0_MODE = 0;                     /* timer */
    /* 8 bit: if the counter ever passes CC (e.g. the core was halted by the
     * debugger while the timer kept running), it wraps within 256 ticks
     * (16 us) and hits CC again. With 32 bit it would stall for 268 s. */
    TIMER0_BITMODE = 1;                  /* 8 bit */
    TIMER0_PRESCALER = prescaler;        /* 16 MHz >> prescaler */
    TIMER0_SHORTS = 1u << 0;             /* COMPARE0 -> CLEAR */
    TIMER0_CC0 = first_period;
    TIMER0_EVENTS_COMPARE0 = 0;
    TIMER0_INTENSET = 1u << 16;          /* COMPARE0 */
    NVIC_ICPR0 = 1u << TIMER0_IRQN;
    NVIC_ISER0 = 1u << TIMER0_IRQN;
    TIMER0_TASKS_CLEAR = 1;
    TIMER0_TASKS_START = 1;
}

static inline void board_timer_isr_ack(uint32_t next_period)
{
    TIMER0_EVENTS_COMPARE0 = 0;
    TIMER0_CC0 = next_period;
}

/* make sure the event clear has landed */
static inline void board_timer_isr_end(void) { (void)TIMER0_EVENTS_COMPARE0; }

static inline void board_timer_stop(void)
{
    TIMER0_TASKS_STOP = 1;
    TIMER0_INTENCLR = 1u << 16;
    NVIC_ICER0 = 1u << TIMER0_IRQN;
    __asm volatile("dsb\n isb" ::: "memory");
    TIMER0_EVENTS_COMPARE0 = 0;
    NVIC_ICPR0 = 1u << TIMER0_IRQN;
}

/* Second interrupt source for the multi-producer/-consumer stress test:
 * TIMER1 (nRF5340 PS v0.5.1, 5.1.3.1: secure 0x50010000, ID 16 = IRQ 16),
 * same configuration as TIMER0. Priorities are set with
 * board_irq_priorities(), so TIMER1 can preempt TIMER0. */
#define TIMER1 0x50010000u
#define TIMER1_TASKS_START    NRF_REG(TIMER1 + 0x000)
#define TIMER1_TASKS_STOP     NRF_REG(TIMER1 + 0x004)
#define TIMER1_TASKS_CLEAR    NRF_REG(TIMER1 + 0x00C)
#define TIMER1_EVENTS_COMPARE0 NRF_REG(TIMER1 + 0x140)
#define TIMER1_SHORTS         NRF_REG(TIMER1 + 0x200)
#define TIMER1_INTENSET       NRF_REG(TIMER1 + 0x304)
#define TIMER1_INTENCLR       NRF_REG(TIMER1 + 0x308)
#define TIMER1_MODE           NRF_REG(TIMER1 + 0x504)
#define TIMER1_BITMODE        NRF_REG(TIMER1 + 0x508)
#define TIMER1_PRESCALER      NRF_REG(TIMER1 + 0x510)
#define TIMER1_CC0            NRF_REG(TIMER1 + 0x540)
#define TIMER1_IRQN 16u

#define BOARD_TIMER_B_IRQ_HANDLER TIMER1_IRQHandler

/* NVIC priorities: lower value = more urgent. The value is written to the
 * top bits of the 8-bit field, so it works with any number of implemented
 * priority bits >= 2. a = TIMER0, b = TIMER1. */
static inline void board_irq_priorities(uint32_t a, uint32_t b)
{
    *(volatile uint8_t *)(0xE000E400u + TIMER0_IRQN) = (uint8_t)(a << 6);
    *(volatile uint8_t *)(0xE000E400u + TIMER1_IRQN) = (uint8_t)(b << 6);
}

static inline void board_timer_b_start(uint32_t prescaler, uint32_t first_period)
{
    TIMER1_TASKS_STOP = 1;
    TIMER1_MODE = 0;
    TIMER1_BITMODE = 1;                  /* 8 bit, as TIMER0 */
    TIMER1_PRESCALER = prescaler;
    TIMER1_SHORTS = 1u << 0;
    TIMER1_CC0 = first_period;
    TIMER1_EVENTS_COMPARE0 = 0;
    TIMER1_INTENSET = 1u << 16;
    NVIC_ICPR0 = 1u << TIMER1_IRQN;
    NVIC_ISER0 = 1u << TIMER1_IRQN;
    TIMER1_TASKS_CLEAR = 1;
    TIMER1_TASKS_START = 1;
}

static inline void board_timer_b_isr_ack(uint32_t next_period)
{
    TIMER1_EVENTS_COMPARE0 = 0;
    TIMER1_CC0 = next_period;
}

static inline void board_timer_b_isr_end(void) { (void)TIMER1_EVENTS_COMPARE0; }

static inline void board_timer_b_stop(void)
{
    TIMER1_TASKS_STOP = 1;
    TIMER1_INTENCLR = 1u << 16;
    NVIC_ICER0 = 1u << TIMER1_IRQN;
    __asm volatile("dsb\n isb" ::: "memory");
    TIMER1_EVENTS_COMPARE0 = 0;
    NVIC_ICPR0 = 1u << TIMER1_IRQN;
}

/* uint32_t time_call(rb_op op, uintptr_t a, uintptr_t b, uint32_t *ret)
 * Returns CYCCNT(after) - CYCCNT(before) around one call of op(a, b). The
 * timed window is exactly: ldr t0 ; blx op ; <op> ; ldr t1. */
__attribute__((naked, noinline, aligned(32), unused))
static uint32_t time_call(rb_op op, uintptr_t a, uintptr_t b, uint32_t *ret)
{
    (void)op; (void)a; (void)b; (void)ret;
    __asm volatile(
        ".syntax unified\n"
        "push {r4, r5, r6, lr}\n"
        "mov  r4, r3\n"
        "ldr  r5, =0xE0001004\n"   /* DWT_CYCCNT */
        "mov  r3, r0\n"
        "mov  r0, r1\n"
        "mov  r1, r2\n"
        "ldr  r6, [r5]\n"          /* t0 */
        "blx  r3\n"
        "ldr  r1, [r5]\n"          /* t1 */
        "str  r0, [r4]\n"
        "subs r0, r1, r6\n"
        "pop  {r4, r5, r6, pc}\n"
        ".ltorg\n");
}
