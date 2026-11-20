# Raspberry Pi Pico 2 H (RP2350A, Cortex-M33 core 0 only so far). Included
# by the firmware Makefiles. Image format: the RP2350 boot ROM only boots a
# flash image with an IMAGE_DEF block in its first 4 KB (startup.c).
ARCH     = -mcpu=cortex-m33 -mthumb -mfloat-abi=soft
LD_FLASH = $(COMMON)/rp2350.ld
LD_SRAM  = $(COMMON)/rp2350_sram.ld
