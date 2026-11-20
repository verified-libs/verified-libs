/* RP2350 (Pico 2 H), code-in-SRAM variant. Flash (XIP) at 0x10000000, 4 MB
 * on the Pico 2; SRAM0-7 at 0x20000000, 512 KB (pico-sdk 079c6f39
 * addressmap.h: XIP_BASE, SRAM_BASE; SRAM8/9 above are not used). Only the
 * vector table, the boot block and the startup code stay in flash. All
 * other code and read-only data are copied by Reset_Handler to the upper
 * half of SRAM; data, bss and the stack live in the lower half. */
MEMORY
{
    FLASH   (rx)  : ORIGIN = 0x10000000, LENGTH = 4096K
    RAM     (rwx) : ORIGIN = 0x20000000, LENGTH = 256K
    RAMCODE (rwx) : ORIGIN = 0x20040000, LENGTH = 256K
}

ENTRY(Reset_Handler)
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
    .isr_vector : { KEEP(*(.isr_vector)) KEEP(*(.embedded_block)) } > FLASH
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

    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) }
}
