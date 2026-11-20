/* ATSAMD20J18A: 256 KB flash at 0, 32 KB SRAM at 0x20000000 (FLASH_SIZE,
 * HRAMC0 in hal_atmel samd20j18.h, 8f95c79f). Code runs from flash. */
MEMORY
{
    FLASH (rx)  : ORIGIN = 0x00000000, LENGTH = 256K
    RAM    (rwx) : ORIGIN = 0x20000000, LENGTH = 32752   /* 32K less the selection words */
    SELECT (rw)  : ORIGIN = 0x20007ff0, LENGTH = 16
}

ENTRY(Reset_Handler)
_estack = ORIGIN(RAM) + LENGTH(RAM);

/* No code in SRAM in this variant: empty copy for the startup code. */
_sramtext = 0;
_eramtext = 0;
_siramtext = 0;

SECTIONS
{
    .isr_vector : { KEEP(*(.isr_vector)) } > FLASH
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

    /* The selection words of a bundle (common/select.h): the last 16 bytes
     * of RAM, the same address in every image of the board, not cleared
     * at start-up; the stack starts below them. */
    .select (NOLOAD) : { KEEP(*(.select)) } > SELECT

    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) }
}
