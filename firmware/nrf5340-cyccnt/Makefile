# Build inside the pinned toolchain image:
#   podman run --rm -v "$PWD":/work:Z verified-libs/toolchain:2026-11-05 make
CC      = arm-none-eabi-gcc
CFLAGS  = -mcpu=cortex-m33 -mthumb -mfloat-abi=soft -O2 -g -std=c11 \
          -Wall -Wextra -ffreestanding -ffunction-sections -fdata-sections
LDFLAGS = -nostdlib -T nrf5340_app.ld -Wl,--gc-sections -Wl,-Map=build/fw.map

build/fw.elf: main.c startup.c nrf5340_app.ld | build
	$(CC) $(CFLAGS) $(LDFLAGS) main.c startup.c -o $@
	arm-none-eabi-size $@
	arm-none-eabi-objdump -d $@ > build/fw.lst

build:
	mkdir -p build

clean:
	rm -rf build
