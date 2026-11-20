/* RP2350 (Pico 2 H): 4 MB flash (XIP) at 0x10000000, SRAM0-7 512 KB at
 * 0x20000000 (pico-sdk 079c6f39 addressmap.h). Code runs from flash through
 * the XIP cache. The IMAGE_DEF block follows the vector table, inside the
 * first 4 KB as the boot ROM requires. */
MEMORY
{
    FLASH (rx)  : ORIGIN = 0x10000000, LENGTH = 4096K
    RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 512K
}

ENTRY(Reset_Handler)
_estack = ORIGIN(RAM) + LENGTH(RAM);

/* No code in SRAM in this variant: empty copy for the startup code. */
_sramtext = 0;
_eramtext = 0;
_siramtext = 0;

SECTIONS
{
    .isr_vector : { KEEP(*(.isr_vector)) KEEP(*(.embedded_block)) } > FLASH
    .text : { *(.text.bench_harness*) *(.text.time_call) *(.text.bench_adapter*) KEEP(*(.bench_shift)) *(.text*) *(.rodata*) . = ALIGN(4); } > FLASH

    .init_array : {
        __init_array_start = .;
        KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array))
        __init_array_end = .;
    } > FLASH

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

    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) }
}
