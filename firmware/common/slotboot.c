/* Boot stub for a bundle of firmware images (nrf5340-rb-stress/bundle.py):
 * one image per library, each linked for its own place ("slot") in flash,
 * all flashed together once. The stub sits at the start of flash and runs
 * after every reset. When the selection words (the ones main.c's
 * select_and_reset writes before the reset: magic, index, ~index) name a
 * library that has a slot in this bundle, it starts that library's image;
 * otherwise it starts the bundle's first image, which says "VLS ready" and
 * takes the next "run <n>". The stub leaves the selection alone (the image
 * reads and clears it), uses no RAM besides a few words of stack at the top
 * of RAM, sets no clock or peripheral, and so hands over the chip as the
 * reset left it.
 *
 * Why: one image per library (a library cannot change another library's
 * image), without flashing again for every library; flash is written only
 * when an image changes (the boards' flash wears out after 10k erase cycles
 * or fewer).
 *
 * Built by bundle.py with:
 *   SLOTBOOT_SEL_ADDR  address of the three selection words
 *   SLOTBOOT_TABLE     the slots: {library index, image base}, ...
 *   SLOTBOOT_RP2350    the RP2350 boot block (IMAGE_DEF) */
#include <stdint.h>

#define SELECT_MAGIC 0x564C5345u   /* "VLSE", main.c */
#define VTOR (*(volatile uint32_t *)0xE000ED08u)

struct slot { uint32_t lib, base; };
static const struct slot slots[] = { SLOTBOOT_TABLE };

extern uint32_t _estack;
void Reset_Handler(void);

__attribute__((noreturn)) void Reset_Handler(void)
{
    const volatile uint32_t *sel = (const volatile uint32_t *)SLOTBOOT_SEL_ADDR;
    uint32_t base = slots[0].base;
    if (sel[0] == SELECT_MAGIC && sel[2] == ~sel[1])
        for (uint32_t i = 0; i < sizeof slots / sizeof slots[0]; i++)
            if (slots[i].lib == sel[1]) base = slots[i].base;
    const uint32_t *v = (const uint32_t *)base;
    VTOR = base;
    __asm volatile("dsb\n isb\n msr msp, %0\n bx %1" :: "r"(v[0]), "r"(v[1]) : "memory");
    __builtin_unreachable();
}

static void Default_Handler(void) { for (;;) {} }

__attribute__((section(".isr_vector"), used))
const void *const vectors[16] = {
    &_estack, Reset_Handler,
    Default_Handler, Default_Handler,   /* NMI, HardFault */
};

#ifdef SLOTBOOT_RP2350
/* As common/rp2350/startup.c: the boot ROM boots a flash image only if a
 * block like this lies in its first 4 KB. */
__attribute__((section(".embedded_block"), used, aligned(4)))
const uint32_t rp2350_image_def[5] = {
    0xffffded3u, 0x10210142u, 0x000001ffu, 0x00000000u, 0xab123579u,
};
#endif
