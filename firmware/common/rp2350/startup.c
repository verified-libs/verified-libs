/* Minimal Cortex-M33 startup for the RP2350 (core 0): vector table, code copy to SRAM (SRAM
 * variant only), .data copy, .bss clear, C++ static constructors.
 * Must be built with -fno-tree-loop-distribute-patterns: the copy loops
 * must not become memcpy calls, because memcpy itself may live in SRAM and
 * is not there yet. */
#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
extern uint32_t _siramtext, _sramtext, _eramtext;
extern void (*__init_array_start[])(void);
extern void (*__init_array_end[])(void);
int main(void);

void Reset_Handler(void)
{
    uint32_t *src, *dst;
    /* Core 1 first, before any memory is written: a system reset through
     * core 0's AIRCR (run.sh PER_LIB=1, one reset per library) does not
     * reset core 1, which goes on running the previous image's code until
     * board_core1_launch resets it. Meanwhile this code copies the new
     * image's code over that code (SRAM variant), clears .bss and starts
     * the libraries, and the stray core can write into all of it (seen
     * 2026-11-16: SMP runs with code in SRAM failed in a library that came
     * right after another one, never alone). Reset it here and let it go:
     * it then waits in the boot ROM, as after power-on. PSM FRCE_OFF
     * 0x40018004, PROC1 bit 24; set/clear aliases +0x2000/+0x3000. */
    *(volatile uint32_t *)(0x40018004u + 0x2000u) = 1u << 24;
    while (!(*(volatile uint32_t *)0x40018004u & (1u << 24))) {}
    *(volatile uint32_t *)(0x40018004u + 0x3000u) = 1u << 24;
    for (src = &_siramtext, dst = &_sramtext; dst < &_eramtext;) *dst++ = *src++;
    __asm volatile("dsb\n isb" ::: "memory"); /* code written: sync before executing it */
    for (src = &_sidata, dst = &_sdata; dst < &_edata;) *dst++ = *src++;
    for (dst = &_sbss; dst < &_ebss; dst++) *dst = 0;
    for (void (**f)(void) = __init_array_start; f < __init_array_end; f++) (*f)();
    main();
    for (;;) {}
}

void Default_Handler(void) { for (;;) {} }

/* RP2350 boot block (IMAGE_DEF), as pico-sdk's
 * pico_crt0/embedded_start_block.inc.S (079c6f39) builds it, with the
 * constants of boot/picobin.h: the boot ROM boots a flash image only if a
 * block like this lies in its first 4 KB. One item, IMAGE_TYPE = EXE |
 * SECURITY_S (Secure) | CPU_ARM | CHIP_RP2350 = 0x1021; then the LAST item
 * with the size of the items in words (1), a link of 0 (this block loops to
 * itself), and the end marker. */
__attribute__((section(".embedded_block"), used, aligned(4)))
const uint32_t rp2350_image_def[5] = {
    0xffffded3u,                          /* PICOBIN_BLOCK_MARKER_START */
    0x10210142u,                          /* 0x42 IMAGE_TYPE, size 1 word, 0x1021 */
    0x000001ffu,                          /* 0xff LAST, items size 1 word, pad 0 */
    0x00000000u,                          /* link to the next block: none */
    0xab123579u,                          /* PICOBIN_BLOCK_MARKER_END */
};

/* Peripheral interrupts used by the lab firmware; override as needed. */
void PWM_IRQ_WRAP_0_Handler(void) __attribute__((weak, alias("Default_Handler")));
void SysTick_Handler(void) __attribute__((weak, alias("Default_Handler")));
void PWM_IRQ_WRAP_1_Handler(void) __attribute__((weak, alias("Default_Handler")));

/* Core exceptions + the first 32 peripheral interrupts (pico-sdk intctrl.h). */
#pragma GCC diagnostic ignored "-Woverride-init"
__attribute__((section(".isr_vector"), used))
const void *const vectors[16 + 32] = {
    &_estack,
    Reset_Handler,
    Default_Handler, /* NMI */
    Default_Handler, /* HardFault */
    Default_Handler, /* MemManage */
    Default_Handler, /* BusFault */
    Default_Handler, /* UsageFault */
    Default_Handler, /* SecureFault */
    0, 0, 0,
    Default_Handler, /* SVCall */
    Default_Handler, /* DebugMonitor */
    0,
    Default_Handler, /* PendSV */
    SysTick_Handler, /* SysTick */
    [16 ... 16 + 31] = Default_Handler,
    [16 + 8] = PWM_IRQ_WRAP_0_Handler,   /* PWM_IRQ_WRAP_0 = 8 */
    [16 + 9] = PWM_IRQ_WRAP_1_Handler,   /* PWM_IRQ_WRAP_1 = 9 */
};
