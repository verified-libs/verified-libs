# SAM D20 Xplained Pro (ATSAMD20J18A, Cortex-M0+). Included by the firmware
# Makefiles. Only code in flash: 32 KB RAM does not hold the benchmark's code
# and data together (no LD_SRAM).
ARCH     = -mcpu=cortex-m0plus -mthumb -mfloat-abi=soft
LD_FLASH = $(COMMON)/samd20.ld
