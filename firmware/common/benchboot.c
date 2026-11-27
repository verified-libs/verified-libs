/* Boot stub for a bundle of benchmark images (nrf5340-rb-bench/onebundle.py;
 * lab/plans/2026-11-22-bench-image-per-library.md): one image per
 * configuration and placement, each linked for its own slot in flash, all
 * flashed together. The stub sits at the start of flash and runs after
 * every reset. The host writes the selection words (common/select.h:
 * magic, image address, ~address, run number) over the probe and resets
 * the chip; the stub starts the image at that address.
 *
 * Unlike slotboot.c the stub holds no table of its images: it is the same
 * for every bundle of a board and does not change when an image is added
 * or moves. It starts an image only if the address is a slot boundary
 * behind the stub and a vector table lies there (a stack pointer in RAM,
 * a reset handler in flash behind the address); otherwise it stops here,
 * and the host sees that its run number never shows up in the results.
 * It leaves the selection words alone, uses no RAM, sets no clock or
 * peripheral, and so hands over the chip as the reset left it; but on the
 * nRF5340 (BENCHBOOT_NRF5340) it first opens the debug port, below.
 *
 * Built by onebundle.py with:
 *   BENCHBOOT_SEL_ADDR    address of the four selection words
 *   BENCHBOOT_FIRST/_END  the flash the images may lie in
 *   BENCHBOOT_UNIT        slot boundaries are multiples of this
 *   BENCHBOOT_RAM/_RAM_END  the RAM a stack pointer may point into
 *   BENCHBOOT_RP2350      the RP2350 boot block (IMAGE_DEF)
 *   BENCHBOOT_NRF5340     open the application core's debug port at every boot
 *                         (method version 3, DECISIONS 2026-11-26) */
#include <stdint.h>

#define BENCHBOOT_MAGIC 0x564C4253u   /* "VLBS": not the stress tests' "VLSE" */
#define VTOR (*(volatile uint32_t *)0xE000ED08u)

extern uint32_t _estack;
void Reset_Handler(void);

__attribute__((noreturn)) void Reset_Handler(void)
{
#ifdef BENCHBOOT_NRF5340
    /* The access port of the nRF5340's application core opens only if UICR is
     * unprotected and firmware writes CTRL-AP.APPROTECT.DISABLE after each
     * reset (nRF5340 Product Specification v1.6, §8.2). Before method version 3
     * only a measured image's board_init did that (common/nrf5340/nrf5340_bench.h,
     * nrf5340_bench_init), so after a power-on, with no image started, the port
     * stayed locked. The stub now copies UICR's two words into CTRL-AP at every
     * boot, as nrf5340_bench_init and Nordic's SystemInit do; on a protected
     * UICR the copy leaves the port locked, as before. */
    *(volatile uint32_t *)0x50006544u = *(const volatile uint32_t *)0x00FF8000u;  /* CTRLAP APPROTECT.DISABLE = UICR.APPROTECT */
    *(volatile uint32_t *)0x5000654Cu = *(const volatile uint32_t *)0x00FF801Cu;  /* SECUREAPPROTECT.DISABLE = UICR.SECUREAPPROTECT */
#endif
    const volatile uint32_t *sel = (const volatile uint32_t *)BENCHBOOT_SEL_ADDR;
    uint32_t base = sel[1];
    if (sel[0] == BENCHBOOT_MAGIC && sel[2] == ~base && base % BENCHBOOT_UNIT == 0
        && base >= BENCHBOOT_FIRST && base < BENCHBOOT_END) {
        const uint32_t *v = (const uint32_t *)base;
        uint32_t sp = v[0], pc = v[1];
        if (sp > BENCHBOOT_RAM && sp <= BENCHBOOT_RAM_END && sp % 4 == 0
            && (pc & 1u) && pc > base && pc < BENCHBOOT_END) {
            VTOR = base;
            __asm volatile("dsb\n isb\n msr msp, %0\n bx %1" :: "r"(sp), "r"(pc) : "memory");
        }
    }
    for (;;) {}
}

static void Default_Handler(void) { for (;;) {} }

__attribute__((section(".isr_vector"), used))
const void *const vectors[16] = {
    &_estack, Reset_Handler,
    Default_Handler, Default_Handler,   /* NMI, HardFault */
};

#ifdef BENCHBOOT_RP2350
/* As common/rp2350/startup.c: the boot ROM boots a flash image only if a
 * block like this lies in its first 4 KB. */
__attribute__((section(".embedded_block"), used, aligned(4)))
const uint32_t rp2350_image_def[5] = {
    0xffffded3u, 0x10210142u, 0x000001ffu, 0x00000000u, 0xab123579u,
};
#endif
