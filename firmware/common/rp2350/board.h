/*
 * Board layer for the benchmark firmware: Raspberry Pi Pico 2 H (RP2350A),
 * Cortex-M33 core 0 (core 1 stays in the boot ROM's wait loop). Same
 * interface as common/nrf5340/board.h.
 *
 * Clock: 150 MHz (pico-sdk's default for the RP2350): XOSC 12 MHz -> PLL_SYS
 * REFDIV 1, FBDIV 125 (VCO 1500 MHz), POSTDIV1 5, POSTDIV2 2 -> clk_sys;
 * clk_ref from XOSC. The flash (QMI M0_TIMING) stays as the boot ROM left
 * it: CLKDIV 3 (read 0x60007203 on 2026-11-11), i.e. 50 MHz SCK at 150 MHz.
 * Earlier the same day this layer ran clk_sys at 12 MHz from XOSC; the
 * bench was too slow to finish in reasonable time.
 *
 * Cycle counter: DWT CYCCNT, as on the nRF5340. pico-sdk's m33.h gives
 * DWT_CTRL.NOCYCCNT a reset value of 1, but on this chip (2026-11-11)
 * DWT_CTRL reads 0x40000000 with TRCENA set (NOCYCCNT = 0) and CYCCNT is
 * writable; it does not count while the core sleeps (boot ROM's USB wait).
 *
 * "Cache" = the XIP cache (XIP_CTRL EN_SECURE / EN_NONSECURE); turning it
 * on does not invalidate it (flash content does not change here).
 *
 * Register addresses and fields: pico-sdk 079c6f39,
 * src/rp2350/hardware_regs/include/hardware/regs (addressmap.h, xosc.h,
 * clocks.h, xip.h, resets.h, pll.h, qmi.h).
 */
#pragma once
#include <stdint.h>
#include "bench.h"

#define BOARD_ID 6u              /* decode.py: BOARDS */
#define BOARD_READ_OVERHEAD 1u   /* CYCCNT read, as on the nRF5340's M33; to confirm */

#define RP_REG(a) (*(volatile uint32_t *)(a))
#define XOSC_CTRL         RP_REG(0x40048000u + 0x00u)
#define XOSC_STATUS       RP_REG(0x40048000u + 0x04u)
#define XOSC_STARTUP      RP_REG(0x40048000u + 0x0Cu)
#define XOSC_STATUS_STABLE (1u << 31)
#define CLK_REF_CTRL      RP_REG(0x40010000u + 0x30u)
#define CLK_REF_SELECTED  RP_REG(0x40010000u + 0x38u)
#define CLK_SYS_CTRL      RP_REG(0x40010000u + 0x3Cu)
#define CLK_SYS_SELECTED  RP_REG(0x40010000u + 0x44u)
#define RESETS_RESET      RP_REG(0x40020000u + 0x00u)
#define RESETS_RESET_DONE RP_REG(0x40020000u + 0x08u)
#define RESETS_PLL_SYS    (1u << 14)
#define PLL_SYS_CS        RP_REG(0x40050000u + 0x00u)
#define PLL_SYS_PWR       RP_REG(0x40050000u + 0x04u)
#define PLL_SYS_FBDIV_INT RP_REG(0x40050000u + 0x08u)
#define PLL_SYS_PRIM      RP_REG(0x40050000u + 0x0Cu)
#define PLL_CS_LOCK       (1u << 31)
#define PLL_PWR_PD        (1u << 0)
#define PLL_PWR_POSTDIVPD (1u << 3)
#define PLL_PWR_VCOPD     (1u << 5)
#define XIP_CTRL          RP_REG(0x400C8000u + 0x00u)
#define XIP_CTRL_EN       (3u << 0)          /* EN_SECURE | EN_NONSECURE */

#define ARM_DEMCR       RP_REG(0xE000EDFCu)
#define ARM_DWT_CTRL    RP_REG(0xE0001000u)
#define ARM_DWT_CYCCNT  RP_REG(0xE0001004u)

static inline void board_init(void)
{
    /* XOSC on (1-15 MHz range), start-up delay as pico-sdk computes it for
     * 12 MHz with its default multiplier 64: ((12000 + 128) / 256) * 64. */
    XOSC_CTRL = 0xAA0u;                                /* FREQ_RANGE 1_15MHZ */
    XOSC_STARTUP = 47u * 64u;
    XOSC_CTRL = 0xAA0u | (0xFABu << 12);               /* ENABLE */
    while (!(XOSC_STATUS & XOSC_STATUS_STABLE)) {}
    /* clk_ref <- XOSC (SRC 2), then clk_sys <- clk_ref (SRC 0). Both are
     * glitchless muxes; *_SELECTED is one-hot. */
    CLK_REF_CTRL = (CLK_REF_CTRL & ~3u) | 2u;
    while (CLK_REF_SELECTED != (1u << 2)) {}
    CLK_SYS_CTRL &= ~1u;
    while (CLK_SYS_SELECTED != 1u) {}

    /* PLL_SYS to 150 MHz (as pico-sdk's pll_init): reset, program, power up
     * the VCO, wait for lock, then the post dividers. */
    RESETS_RESET |= RESETS_PLL_SYS;
    RESETS_RESET &= ~RESETS_PLL_SYS;
    while (!(RESETS_RESET_DONE & RESETS_PLL_SYS)) {}
    PLL_SYS_CS = 1u;                                   /* REFDIV 1 */
    PLL_SYS_FBDIV_INT = 125u;
    PLL_SYS_PWR &= ~(PLL_PWR_PD | PLL_PWR_VCOPD);
    while (!(PLL_SYS_CS & PLL_CS_LOCK)) {}
    PLL_SYS_PRIM = (5u << 16) | (2u << 12);
    PLL_SYS_PWR &= ~PLL_PWR_POSTDIVPD;
    /* clk_sys: AUXSRC = pll_sys (0) while on clk_ref, then SRC = aux (1). */
    CLK_SYS_CTRL &= ~(7u << 5);
    CLK_SYS_CTRL |= 1u;
    while (CLK_SYS_SELECTED != 2u) {}

    /* As on the nRF5340: probe-rs may clear DEMCR.TRCENA when it detaches
     * after "reset", which stops CYCCNT. Wait before starting it. */
    for (volatile uint32_t i = 0; i < 20000000u; i++) {}   /* ~1 s at 150 MHz */

    ARM_DEMCR |= 1u << 24;    /* TRCENA */
    ARM_DWT_CYCCNT = 0;
    ARM_DWT_CTRL |= 1u;       /* CYCCNTENA */
}

static inline uint32_t board_clock_hz(void)
{
    if (CLK_SYS_SELECTED == 2u) return 150000000u;
    return (CLK_SYS_SELECTED == 1u && CLK_REF_SELECTED == (1u << 2)) ? 12000000u : 0u;
}

static inline void board_cache(int on)
{
    if (on) XIP_CTRL |= XIP_CTRL_EN;
    else    XIP_CTRL &= ~XIP_CTRL_EN;
    __asm volatile("dsb\n isb" ::: "memory");
}

static inline int board_counter_running(void)
{
    uint32_t a = ARM_DWT_CYCCNT;
    __asm volatile("nop\n nop\n nop\n nop");
    return ARM_DWT_CYCCNT != a;
}

static inline void board_idle(void) { for (;;) {} }

/* ---- Stress interrupt sources: PWM slices 0 (A) and 1 (B) ----
 * Each slice counts clk_sys / DIV and wraps after TOP (period = TOP + 1
 * ticks), raising its wrap flag in INTR; slice 0 is routed to
 * PWM_IRQ_WRAP_0 (IRQ 8) through IRQ0_INTE, slice 1 to PWM_IRQ_WRAP_1
 * (IRQ 9) through IRQ1_INTE. DIV (8.4 fixed point) = 4 << prescaler, so one
 * tick = 4 << prescaler core cycles as on the other boards. TOP is
 * double-buffered (latched at the wrap), so a period written in the
 * interrupt takes effect one period later and the counter can never be
 * past it: no stall as with the STM32's 32-bit TIM2. pico-sdk 079c6f39:
 * pwm.h, intctrl.h, resets.h (PWM reset bit 16). */
#define PWM_BASE          0x400A8000u
#define PWM_CSR(s)        RP_REG(PWM_BASE + 0x14u * (s) + 0x00u)
#define PWM_DIV(s)        RP_REG(PWM_BASE + 0x14u * (s) + 0x04u)
#define PWM_CTR(s)        RP_REG(PWM_BASE + 0x14u * (s) + 0x08u)
#define PWM_TOP(s)        RP_REG(PWM_BASE + 0x14u * (s) + 0x10u)
#define PWM_INTR          RP_REG(PWM_BASE + 0xF4u)
#define PWM_IRQ0_INTE     RP_REG(PWM_BASE + 0xF8u)
#define PWM_IRQ1_INTE     RP_REG(PWM_BASE + 0x104u)
#define RESETS_PWM        (1u << 16)
#define PWM_IRQN_A        8u
#define PWM_IRQN_B        9u
#define RP_NVIC_ISER0     RP_REG(0xE000E100u)
#define RP_NVIC_ICER0     RP_REG(0xE000E180u)
#define RP_NVIC_ICPR0     RP_REG(0xE000E280u)

#define BOARD_TIMER_IRQ_HANDLER   PWM_IRQ_WRAP_0_Handler
#define BOARD_TIMER_B_IRQ_HANDLER PWM_IRQ_WRAP_1_Handler

static inline void rp_pwm_start(uint32_t s, uint32_t irq, uint32_t prescaler, uint32_t first_period)
{
    if (RESETS_RESET & RESETS_PWM) {
        RESETS_RESET &= ~RESETS_PWM;
        while (!(RESETS_RESET_DONE & RESETS_PWM)) {}
    }
    PWM_CSR(s) = 0;
    PWM_DIV(s) = (4u << prescaler) << 4;          /* integer part, frac 0 */
    PWM_TOP(s) = first_period - 1u;
    PWM_CTR(s) = 0;
    PWM_INTR = 1u << s;                            /* write 1 to clear */
    if (s == 0) PWM_IRQ0_INTE |= 1u << s; else PWM_IRQ1_INTE |= 1u << s;
    RP_NVIC_ICPR0 = 1u << irq;
    RP_NVIC_ISER0 = 1u << irq;
    PWM_CSR(s) = 1u;                               /* EN, free-running */
}

static inline void rp_pwm_stop(uint32_t s, uint32_t irq)
{
    PWM_CSR(s) = 0;
    if (s == 0) PWM_IRQ0_INTE &= ~(1u << s); else PWM_IRQ1_INTE &= ~(1u << s);
    RP_NVIC_ICER0 = 1u << irq;
    __asm volatile("dsb\n isb" ::: "memory");
    PWM_INTR = 1u << s;
    RP_NVIC_ICPR0 = 1u << irq;
}

static inline void board_timer_start(uint32_t p, uint32_t first) { rp_pwm_start(0, PWM_IRQN_A, p, first); }
static inline void board_timer_isr_ack(uint32_t next) { PWM_INTR = 1u << 0; PWM_TOP(0) = next - 1u; }
static inline void board_timer_isr_end(void) { (void)PWM_INTR; }
static inline void board_timer_stop(void) { rp_pwm_stop(0, PWM_IRQN_A); }
static inline void board_timer_b_start(uint32_t p, uint32_t first) { rp_pwm_start(1, PWM_IRQN_B, p, first); }
static inline void board_timer_b_isr_ack(uint32_t next) { PWM_INTR = 1u << 1; PWM_TOP(1) = next - 1u; }
static inline void board_timer_b_isr_end(void) { (void)PWM_INTR; }
static inline void board_timer_b_stop(void) { rp_pwm_stop(1, PWM_IRQN_B); }

/* NVIC priorities (RP2350 M33: 4 implemented bits); byte access is fine on
 * ARMv8-M. a = slice 0, b = slice 1. */
static inline void board_irq_priorities(uint32_t a, uint32_t b)
{
    *(volatile uint8_t *)(0xE000E400u + PWM_IRQN_A) = (uint8_t)(a << 6);
    *(volatile uint8_t *)(0xE000E400u + PWM_IRQN_B) = (uint8_t)(b << 6);
}


/* ---- Core 1 (dual-core stress, SMP_MODE in nrf5340-rb-stress) ----
 * Launch as pico-sdk's multicore_launch_core1_raw (pico_multicore
 * multicore.c, 079c6f39): send {0, 0, 1, VTOR, SP, entry} over the SIO FIFO
 * to the boot ROM's core-1 wait loop; each word must be echoed back, and a
 * wrong echo restarts the sequence; before each 0 the read FIFO is drained
 * and a SEV is sent. SIO 0xD0000000: FIFO_ST 0x50 (VLD bit 0, RDY bit 1),
 * FIFO_WR 0x54, FIFO_RD 0x58 (sio.h). */
#define BOARD_HAS_CORE1 1
#define SIO_FIFO_ST RP_REG(0xD0000050u)
#define SIO_FIFO_WR RP_REG(0xD0000054u)
#define SIO_FIFO_RD RP_REG(0xD0000058u)

/* SRAM as Shareable for both cores (SMP builds). In the ARMv8-M default
 * memory map SRAM is Normal, Non-shareable, and the RP2350 then keeps
 * LDREX/STREX in each core's local monitor: a C11 read-modify-write (CAS,
 * fetch_add) is not atomic between the cores (rp2350-excl-check: about half
 * of 2 x 10^6 increments lost; none with this region). One MPU region over
 * SRAM, Normal non-cacheable (the RP2350 has no data cache on SRAM), Inner
 * Shareable; the default map for everything else (PRIVDEFENA). Each core
 * has its own MPU: board_core1_launch sets it on core 0 and, through the
 * trampoline, on core 1 before its entry runs. Not used by single-core
 * builds (bench, ISR stress), whose memory map stays the default. */
static inline void board_sram_shareable(void)
{
    __asm volatile("dsb\nisb" ::: "memory");
    RP_REG(0xE000ED94u) = 0;                                   /* MPU_CTRL */
    RP_REG(0xE000EDC0u) = 0x44u;                               /* MAIR0 attr 0: Normal, non-cacheable */
    RP_REG(0xE000ED98u) = 0;                                   /* RNR */
    RP_REG(0xE000ED9Cu) = 0x20000000u | (3u << 3) | (1u << 1); /* RBAR: SH inner, AP RW */
    RP_REG(0xE000EDA0u) = 0x20081FE0u | 1u;                    /* RLAR: limit 0x20081FFF, attr 0, EN */
    RP_REG(0xE000ED94u) = 5u;                                  /* MPU_CTRL: ENABLE | PRIVDEFENA */
    __asm volatile("dsb\nisb" ::: "memory");
}
static void (*volatile board_core1_entry)(void);
__attribute__((unused)) static void board_core1_trampoline(void)
{
    board_sram_shareable();
    board_core1_entry();
}

static inline void board_core1_launch(void (*entry_fn)(void), uint32_t *stack_top)
{
    /* Reset core 1 first, as pico-sdk's multicore_reset_core1: a system
     * reset through core 0's AIRCR (run.sh PER_LIB=1, one library per
     * reset) leaves core 1 running the previous start's code, and the
     * launch sequence below then never gets its echo (seen 2026-11-14: SMP
     * builds hung from the second library on). PSM 0x40018000 FRCE_OFF
     * 0x04, PROC1 bit 24 (psm.h); set/clear aliases +0x2000/+0x3000. Out of
     * reset, core 1 drains its FIFO and pushes a 0 to ours. */
    RP_REG(0x40018004u + 0x2000u) = 1u << 24;
    while (!(RP_REG(0x40018004u) & (1u << 24))) {}
    RP_REG(0x40018004u + 0x3000u) = 1u << 24;
    while (!(SIO_FIFO_ST & 1u)) __asm volatile("wfe");
    (void)SIO_FIFO_RD;
    board_sram_shareable();
    board_core1_entry = entry_fn;
    void (*entry)(void) = board_core1_trampoline;
    __asm volatile("dsb" ::: "memory");
    extern const void *const vectors[];
    const uint32_t seq[6] = {0, 0, 1, (uint32_t)(uintptr_t)vectors,
                             (uint32_t)(uintptr_t)stack_top, (uint32_t)(uintptr_t)entry};
    uint32_t i = 0;
    while (i < 6u) {
        uint32_t cmd = seq[i];
        if (!cmd) {
            while (SIO_FIFO_ST & 1u) (void)SIO_FIFO_RD;     /* drain */
            __asm volatile("sev");
        }
        while (!(SIO_FIFO_ST & 2u)) {}
        SIO_FIFO_WR = cmd;
        __asm volatile("sev");
        while (!(SIO_FIFO_ST & 1u)) __asm volatile("wfe");
        uint32_t resp = SIO_FIFO_RD;
        i = (resp == cmd) ? i + 1u : 0u;
    }
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
