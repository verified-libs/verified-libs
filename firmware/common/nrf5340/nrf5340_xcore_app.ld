/* nRF5340 application core for rb-xcore-stress (the library object shared
 * with the network core). As nrf5340_app.ld, but the RAM is split:
 *   RAM      0x20000000..0x2006ffff  this core's own data and stack
 *   XSHARED  0x20070000..0x2007ffef  the libraries' data (.bss of every object
 *            but main.o and startup.o), the same layout as in the network
 *            core's image (../nrf5340net/nrf5340_xcore_net.ld; checked after
 *            linking, rb-xcore-stress/Makefile)
 *   SELECT   0x2007fff0              the selection words, as everywhere
 * The shared part is not cleared at start-up: main() clears it before it
 * releases the network core. Library .data must be empty (asserted). */
MEMORY
{
    FLASH   (rx)  : ORIGIN = 0x00000000, LENGTH = 1024K
    RAM     (rwx) : ORIGIN = 0x20000000, LENGTH = 0x70000
    XSHARED (rw)  : ORIGIN = 0x20070000, LENGTH = 0xFFF0
    SELECT  (rw)  : ORIGIN = 0x2007fff0, LENGTH = 16
}

ENTRY(Reset_Handler)
_estack = ORIGIN(RAM) + LENGTH(RAM);
_sramtext = 0;
_eramtext = 0;
_siramtext = 0;

SECTIONS
{
    .isr_vector : { KEEP(*(.isr_vector)) } > FLASH
    .text : { *(.text*) *(.rodata*) . = ALIGN(4); } > FLASH
    .init_array : {
        __init_array_start = .;
        KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array))
        __init_array_end = .;
    } > FLASH

    .results (NOLOAD) : { KEEP(*(.results)) . = ALIGN(4); } > RAM

    .data : {
        _sdata = .;
        *main.o(.data*) *startup.o(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT > FLASH
    _sidata = LOADADDR(.data);
    .xdata : { *(.data*) } > XSHARED
    ASSERT(SIZEOF(.xdata) == 0, "rb-xcore-stress: a library has initialised data; it cannot be shared")

    .bss (NOLOAD) : {
        _sbss = .;
        *main.o(.bss* COMMON) *startup.o(.bss* COMMON)
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

    .select (NOLOAD) : { KEEP(*(.select)) } > SELECT
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) }
}
