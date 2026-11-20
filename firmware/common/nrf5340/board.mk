# nRF5340 DK, application core (Cortex-M33). Included by the firmware Makefiles.
ARCH     = -mcpu=cortex-m33 -mthumb -mfloat-abi=soft
LD_FLASH = $(COMMON)/nrf5340_app.ld
LD_SRAM  = $(COMMON)/nrf5340_app_sram.ld
