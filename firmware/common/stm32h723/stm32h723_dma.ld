/* STM32H723ZGT6, the variant for rb-dma-stress (board.mk LD_DMA): as
 * stm32h723.ld, but .bss in AXI SRAM (0x24000000, which DMA1 reaches; the
 * DTCM it does not), every variable on its own 32-byte cache lines, made
 * non-cacheable by board_dma_mem_init() unless DMA_CACHE. .data stays in
 * DTCM: the test harness keeps its own state there (rb-dma-stress main.c
 * HARNESS), so cache maintenance on a library's lines cannot touch it.
 * Results, the selection words and the stack stay in DTCM, at the
 * addresses the host and the boot stub use. */
MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 1024K
    RAM    (rwx) : ORIGIN = 0x20000000, LENGTH = 131056   /* 128K less the selection words */
    SELECT (rw)  : ORIGIN = 0x2001fff0, LENGTH = 16
    AXI    (rwx) : ORIGIN = 0x24000000, LENGTH = 128K
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

    /* SUBALIGN(32): every variable (-fdata-sections) starts on a cache
     * line, so two variables never share one; only what one object holds
     * (e.g. a library keeping its state next to its data) can. */
    .bss (NOLOAD) : SUBALIGN(32) {
        _sbss = .;
        *(.bss*) *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > AXI

    /* The selection words of a bundle (common/select.h): the last 16 bytes
     * of RAM, the same address in every image of the board, not cleared
     * at start-up; the stack starts below them. */
    .select (NOLOAD) : { KEEP(*(.select)) } > SELECT

    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) }
}
