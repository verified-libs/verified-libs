# counter-check: build for one board (BOARD = a directory under ../common).
#   podman run --rm -v "$PWD/..":/work:Z -w /work/counter-check \
#       verified-libs/toolchain:2026-11-05 make BOARD=stm32g474
BOARD  ?= nrf5340
COMMON  = ../common/$(BOARD)
include $(COMMON)/board.mk
CFLAGS  = $(ARCH) -O2 -g -Wall -Wextra -ffreestanding -fno-tree-loop-distribute-patterns \
          -I. -I$(COMMON) -I../nrf5340-rb-bench -std=c11
build/fw.elf: main.c $(COMMON)/startup.c $(COMMON)/board.h
	mkdir -p build
	arm-none-eabi-gcc $(CFLAGS) -c $(COMMON)/startup.c -o build/startup.o
	arm-none-eabi-gcc $(CFLAGS) -c main.c -o build/main.o
	arm-none-eabi-gcc $(ARCH) -nostartfiles --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections \
	    -T $(LD_FLASH) build/startup.o build/main.o -o $@
clean:
	rm -rf build
