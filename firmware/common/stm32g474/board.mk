# NUCLEO-G474RE (STM32G474RET6, Cortex-M4F). Included by the firmware Makefiles.
# Soft-float ABI like the other boards: the ring buffers use no floating point.
ARCH     = -mcpu=cortex-m4 -mthumb -mfloat-abi=soft
LD_FLASH = $(COMMON)/stm32g474.ld
LD_SRAM  = $(COMMON)/stm32g474_sram.ld
# Third variant: code in CCM SRAM (0x10000000, zero wait states on the I-bus).
VAR3     = ccm
LD_VAR3  = $(COMMON)/stm32g474_ccm.ld
