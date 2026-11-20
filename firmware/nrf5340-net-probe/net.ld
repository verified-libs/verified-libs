/* nRF5340 network core: 256 KB flash at 0x01000000, 64 KB RAM at
 * 0x21000000 (nrfx MDK nrf5340_xxaa_network.ld; probe-rs chip info). */
MEMORY
{
    FLASH (rx)  : ORIGIN = 0x01000000, LENGTH = 256K
    RAM   (rwx) : ORIGIN = 0x21000000, LENGTH = 64K
}
ENTRY(Reset_Handler)
_estack = ORIGIN(RAM) + LENGTH(RAM);
SECTIONS
{
    .isr_vector : { KEEP(*(.isr_vector)) } > FLASH
    .text : { *(.text*) *(.rodata*) } > FLASH
    .bss (NOLOAD) : { *(.bss*) *(COMMON) } > RAM
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.data*) }
}
