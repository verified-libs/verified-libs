# NUCLEO-G0B1RE (STM32G0B1RET6, Cortex-M0+). Included by the firmware Makefiles.
ARCH     = -mcpu=cortex-m0plus -mthumb -mfloat-abi=soft
LD_FLASH = $(COMMON)/stm32g0b1.ld
LD_SRAM  = $(COMMON)/stm32g0b1_sram.ld
