/* nRF5340 application core, code-in-SRAM variant.
 * Only the vector table and startup code stay in flash. All other code and
 * read-only data are copied by Reset_Handler to the upper half of SRAM and
 * executed from there; data, bss and the stack live in the lower half. */
MEMORY
{
    FLASH   (rx)  : ORIGIN = 0x00000000, LENGTH = 1024K
    RAM    (rwx) : ORIGIN = 0x20000000, LENGTH = 262128   /* 256K less the selection words */
    SELECT (rw)  : ORIGIN = 0x2003fff0, LENGTH = 16
    RAMCODE (rwx) : ORIGIN = 0x20040000, LENGTH = 256K
}

ENTRY(Reset_Handler)
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
    .isr_vector : { KEEP(*(.isr_vector)) } > FLASH
    .text.flash : { *startup.o(.text* .rodata*) . = ALIGN(4); } > FLASH

    .init_array : {
        __init_array_start = .;
        KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array))
        __init_array_end = .;
    } > FLASH

    .ramtext : {
        _sramtext = .;
        *(.text.bench_harness*) *(.text.time_call) *(.text.bench_adapter*) KEEP(*(.bench_shift)) *(.text*) *(.rodata*)
        . = ALIGN(4);
        _eramtext = .;
    } > RAMCODE AT > FLASH
    _siramtext = LOADADDR(.ramtext);

    /* Results first in RAM, at a fixed address the host reads. */
    .results (NOLOAD) : { KEEP(*(.results)) . = ALIGN(4); } > RAM

    .data : {
        _sdata = .;
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT > FLASH
    _sidata = LOADADDR(.data);

    .bss (NOLOAD) : {
        _sbss = .;
        *(.bss*) *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > RAM

    /* The selection words of a bundle (common/select.h): the last 16 bytes
     * of RAM, the same address in every image of the board, not cleared
     * at start-up; the stack starts below them. */
    .select (NOLOAD) : { KEEP(*(.select)) } > SELECT

    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) }
}
