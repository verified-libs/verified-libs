# h7-thermal: NUCLEO-H723ZG only. Full load at 520 MHz with the die
# temperature logged from the digital temperature sensor (README.md).
#   podman run --rm -v "$PWD/..":/work:Z -w /work/h7-thermal \
#       verified-libs/toolchain:2026-11-05 make
COMMON  = ../common/stm32h723
# hard-float ABI with the M7's double-precision FPU, so the load uses it
ARCH    = -mcpu=cortex-m7 -mthumb -mfloat-abi=hard -mfpu=fpv5-d16
CFLAGS  = $(ARCH) -O2 -g -Wall -Wextra -ffreestanding -fno-tree-loop-distribute-patterns \
          -I. -I$(COMMON) -I../nrf5340-rb-bench -std=c11 $(EXTRA)
build/fw.elf: main.c $(COMMON)/startup.c $(COMMON)/board.h
	mkdir -p build
	arm-none-eabi-gcc $(CFLAGS) -c $(COMMON)/startup.c -o build/startup.o
	arm-none-eabi-gcc $(CFLAGS) -c main.c -o build/main.o
	arm-none-eabi-gcc $(ARCH) -nostartfiles --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections \
	    -T $(COMMON)/stm32h723.ld build/startup.o build/main.o -lm -o $@
	arm-none-eabi-size $@
clean:
	rm -rf build
