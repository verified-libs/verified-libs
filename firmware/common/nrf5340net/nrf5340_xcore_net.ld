/* nRF5340 network core for rb-xcore-stress: 256 KB flash at 0x01000000,
 * 64 KB own RAM at 0x21000000 (nrfx MDK nrf5340_xxaa_network.ld; probe-rs
 * chip info), and the application RAM's XSHARED part at the same address
 * and with the same layout as in the application core's image
 * (../nrf5340/nrf5340_xcore_app.ld). */
MEMORY
{
    FLASH   (rx)  : ORIGIN = 0x01000000, LENGTH = 256K
    RAM     (rwx) : ORIGIN = 0x21000000, LENGTH = 64K
    XSHARED (rw)  : ORIGIN = 0x20070000, LENGTH = 0xFFF0
}

ENTRY(Reset_Handler)
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
    .isr_vector : { KEEP(*(.isr_vector)) } > FLASH
    .text : { *(.text*) *(.rodata*) . = ALIGN(4); } > FLASH
    .init_array : {
        __init_array_start = .;
        KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array))
        __init_array_end = .;
    } > FLASH

    .data : {
        _sdata = .;
        *main.o(.data*) *startup_net.o(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT > FLASH
    _sidata = LOADADDR(.data);
    .xdata : { *(.data*) } > XSHARED
    ASSERT(SIZEOF(.xdata) == 0, "rb-xcore-stress: a library has initialised data; it cannot be shared")

    .bss (NOLOAD) : {
        _sbss = .;
        *main.o(.bss* COMMON) *startup_net.o(.bss* COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > RAM

    .xshared (NOLOAD) : {
        _sxshared = .;
        KEEP(*(.xshared.ctl))
        *(.bss*) *(COMMON)
        . = ALIGN(4);
        _exshared = .;
    } > XSHARED

    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) }
}
