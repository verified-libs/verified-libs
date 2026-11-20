# NUCLEO-H723ZG (STM32H723ZGT6, Cortex-M7). Included by the firmware Makefiles.
ARCH     = -mcpu=cortex-m7 -mthumb -mfloat-abi=soft
LD_FLASH = $(COMMON)/stm32h723.ld
# "sram" = AXI SRAM (0x24000000).
LD_SRAM  = $(COMMON)/stm32h723_sram.ld
# Third variant: code in ITCM (zero wait states).
VAR3     = itcm
LD_VAR3  = $(COMMON)/stm32h723_itcm.ld
# rb-dma-stress: data in AXI SRAM, which DMA1 reaches (board_dma.h).
LD_DMA   = $(COMMON)/stm32h723_dma.ld
