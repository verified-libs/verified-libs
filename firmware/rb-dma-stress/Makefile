# rb-dma-stress: a DMA controller as the producer (main.c). Build inside the
# pinned toolchain image (after ../nrf5340-rb-bench/fetch-libs.sh), as
# ../rb-mp-stress. Boards with a DMA layer (common/<BOARD>/board_dma.h):
# stm32g474, stm32h723 (code in flash; the H723 links its data into AXI
# SRAM, LD_DMA).
BOARD   ?= stm32g474
CODE    ?= flash
COMMON   = ../common/$(BOARD)
BENCH    = ../nrf5340-rb-bench
LIBS     = $(BENCH)/build/libs
PXQ      = $(LIBS)/pxq-ringbuffer-cortex/RingBuffer_PackedState
LWRB     = $(LIBS)/lwrb/lwrb/src

include $(COMMON)/board.mk
ifeq ($(wildcard $(COMMON)/board_dma.h),)
$(error rb-dma-stress: no DMA layer for BOARD=$(BOARD) (common/$(BOARD)/board_dma.h))
endif
OPT     ?= -O2
LTO     ?= 0
ifeq ($(LTO),1)
LTOF     = -flto
endif
COMMONF  = $(ARCH) $(OPT) $(LTOF) -g -Wall -Wextra -Wno-missing-field-initializers -DNDEBUG -ffreestanding \
           -ffunction-sections -fdata-sections -I. -I$(BENCH) -I$(COMMON) $(EXTRA)
CFLAGS   = $(COMMONF) -std=c11 -I$(LWRB)/include
CXXFLAGS = $(COMMONF) -std=c++20 -fno-exceptions -fno-rtti -fno-threadsafe-statics -I$(PXQ)
# a board whose DMA cannot reach its usual RAM has its own linker script
# for this firmware (LD_DMA, e.g. the H723: data in AXI SRAM)
LD_flash = $(or $(LD_DMA),$(LD_FLASH))
LD_sram  = $(LD_SRAM)
ifneq ($(VAR3),)
LD_$(VAR3) = $(LD_VAR3)
endif
LDSCRIPT = $(LD_$(CODE))
ifneq ($(LD_DMA),)
ifneq ($(CODE),flash)
$(error rb-dma-stress on BOARD=$(BOARD): code in flash only (its DMA buffers need LD_DMA))
endif
endif
ifeq ($(LDSCRIPT),)
$(error CODE=$(CODE) is not a code location of BOARD=$(BOARD))
endif
LDFLAGS  = $(ARCH) $(OPT) $(LTOF) $(LD_LIB_EXTRA) -nostartfiles --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections \
           -T $(LDSCRIPT) -Wl,-Map=build/fw.map

include $(COMMON)/../compiler.mk
include $(BENCH)/libs.mk
include ../common/rust.mk

# One firmware per library: ONLY=n (main.c's DMA library index; selection
# index 96 + n). Without ONLY: every library in one image.
HARNESS = build/main.o build/startup.o build/bench_heap.o build/bench_heap_cpp.o $(LIB_RT_OBJS)
LIB_0 = build/adapter_pxq.o
LIB_1 = build/adapter_lwrb.o build/lwrb.o
LIB_2 = build/w2_zephyr.o
LIB_3 = build/w2_tinyusb.o build/tinyusb_fifo.o
LIB_4 = build/w2_ece.o build/ece_ring_buffer.o
LIB_5 = build/w2_nuttx_circbuf.o build/nuttx_circbuf.o
LIB_6 = $(RUST_OBJS)
LIB_7 = $(LIB_1)
ifeq ($(ONLY),)
OBJS = $(HARNESS) $(sort $(LIB_0) $(LIB_1) $(LIB_2) $(LIB_3) $(LIB_4) $(LIB_5)) $(RUST_OBJS)
LINK_RUST = $(RUST_LINK)
ELF = build/fw.elf
else
ifeq ($(LIB_$(ONLY)),)
$(error ONLY=$(ONLY) is not a DMA library index (0..7))
endif
LO   = build/lib$(ONLY)
ELF  = $(LO)/fw.elf
OBJS := $(subst build/main.o,$(LO)/main.o,$(HARNESS)) $(LIB_$(ONLY))
LINK_RUST = $(if $(filter $(RUST_OBJS),$(OBJS)),$(RUST_LINK))
ifneq ($(SLOT_BASE),)
$(LO)/slot.ld: $(LDSCRIPT) | build
	mkdir -p $(LO)
	sed -E 's/^([[:space:]]*FLASH[[:space:]]+\(rx\)[[:space:]]*:[[:space:]]*)ORIGIN = [^,]+, LENGTH = [^[:space:]]+/\1ORIGIN = $(SLOT_BASE), LENGTH = $(SLOT_LEN)/' $< > $@
	grep -q 'ORIGIN = $(SLOT_BASE), LENGTH = $(SLOT_LEN)' $@ || { echo "$<: no FLASH region to move" >&2; rm -f $@; exit 1; }
LDSCRIPT := $(LO)/slot.ld
SLOT_LDF = -Wl,-n
endif
endif
.DEFAULT_GOAL := $(ELF)

$(ELF): $(OBJS) $(if $(LINK_RUST),$(RUST_LIB)) $(LDSCRIPT)
	mkdir -p $(dir $@)
	arm-none-eabi-g++ $(subst build/fw.map,$(dir $@)fw.map,$(LDFLAGS)) $(SLOT_LDF) $(OBJS) $(LINK_RUST) -o $@
	arm-none-eabi-size $@
	arm-none-eabi-objdump -d -C $@ > $(dir $@)fw.lst

build/main.o: main.c $(BENCH)/bench.h $(wildcard $(COMMON)/*.h ../common/*.h) | build
	arm-none-eabi-gcc $(CFLAGS) -c $< -o $@
build/lib%/main.o: main.c $(BENCH)/bench.h $(wildcard $(COMMON)/*.h ../common/*.h) | build
	mkdir -p $(dir $@)
	arm-none-eabi-gcc $(CFLAGS) -DONLY_LIB=$*u -c $< -o $@
build/startup.o: $(COMMON)/startup.c | build
	arm-none-eabi-gcc $(CFLAGS) -fno-lto -fno-tree-loop-distribute-patterns -c $< -o $@
build/adapter_pxq.o: $(BENCH)/adapter_pxq.cpp $(BENCH)/bench.h | build
	$(CXX_LIB) $(CXXFLAGS) -c $< -o $@
build/adapter_lwrb.o: $(BENCH)/adapter_lwrb.c $(BENCH)/bench.h | build
	$(CC_LIB) $(CFLAGS) -c $< -o $@
build/lwrb.o: $(LWRB)/lwrb/lwrb.c | build
	$(CC_LIB) $(CFLAGS) -c $< -o $@

build:
	mkdir -p build

clean:
	rm -rf build/*.o build/fw.* build/rust build/lib[0-9]* build/boot* build/bundle*

.PHONY: clean

print-%:
	@echo '$($*)'
