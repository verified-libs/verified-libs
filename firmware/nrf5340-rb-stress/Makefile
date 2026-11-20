# Build inside the pinned toolchain image (after ../nrf5340-rb-bench/fetch-libs.sh):
#   podman run --rm -v "$PWD/..":/work:Z -w /work/nrf5340-rb-stress \
#       verified-libs/toolchain:2026-11-05 make
# Reuses the library adapters of nrf5340-rb-bench.
# BOARD selects common/<BOARD>/ (nrf5340 default, stm32g0b1, stm32g474,
# stm32h723); CODE selects where code runs: flash (default), sram, or the
# board's third location (VAR3 in board.mk: ccm, itcm). Switching boards
# needs "make clean" (run.sh always cleans).
BOARD  ?= nrf5340
CODE   ?= flash
COMMON  = ../common/$(BOARD)
BENCH   = ../nrf5340-rb-bench
LIBS    = $(BENCH)/build/libs
PXQ     = $(LIBS)/pxq-ringbuffer-cortex/RingBuffer_PackedState
LWRB    = $(LIBS)/lwrb/lwrb/src
ANDERS  = $(LIBS)/anders-ringbuffer
JNK0LE  = $(LIBS)/jnk0le-ringbuffer
ETL     = $(LIBS)/etl/include

include $(COMMON)/board.mk
# Optimisation: OPT (default -O2), LTO=1 for link-time optimisation; the
# startup code is always built without LTO (see ../nrf5340-rb-bench/Makefile).
OPT     ?= -O2
LTO     ?= 0
ifeq ($(LTO),1)
LTOF     = -flto
endif
# -DNDEBUG: release build; assert() would pull in fprintf and the heap.
COMMONF  = $(ARCH) $(OPT) $(LTOF) -g -Wall -Wextra -Wno-missing-field-initializers -DNDEBUG -ffreestanding -ffunction-sections -fdata-sections \
           -I. -I$(BENCH) -I$(COMMON) $(EXTRA)
CFLAGS   = $(COMMONF) -std=c11 -I$(LWRB)/include
CXXFLAGS = $(COMMONF) -std=c++20 -fno-exceptions -fno-rtti -fno-threadsafe-statics -I$(PXQ)
LD_flash = $(LD_FLASH)
LD_sram  = $(LD_SRAM)
ifneq ($(VAR3),)
LD_$(VAR3) = $(LD_VAR3)
endif
LDSCRIPT = $(LD_$(CODE))
ifeq ($(LDSCRIPT),)
$(error CODE=$(CODE) is not a code location of BOARD=$(BOARD))
endif
LDFLAGS  = $(ARCH) $(OPT) $(LTOF) $(LD_LIB_EXTRA) -nostartfiles --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections \
           -T $(LDSCRIPT) -Wl,-Map=build/fw.map

OBJS = build/main.o build/startup.o build/broken.o build/mutants.o build/adapter_pxq.o build/adapter_lwrb.o build/lwrb.o \
       build/adapter_anders.o build/anders_ringbuffer.o build/adapter_jnk0le.o build/adapter_etl.o

.DEFAULT_GOAL := build/fw.elf
include $(COMMON)/../compiler.mk
include $(BENCH)/libs.mk
# NORDIC=1 (BOARD=nrf5340 only, Nordic's licence): Nordic's nrf_ringbuf as
# library 40 (main.c WITH_NORDIC; run.sh NORDIC=1). Without it the firmware
# is the one every board runs, unchanged.
ifeq ($(NORDIC),1)
ifneq ($(BOARD),nrf5340)
$(error NORDIC=1: Nordic's licence allows Nordic chips only, not BOARD=$(BOARD))
endif
include $(BENCH)/nordic.mk
COMMONF += -DWITH_NORDIC
LIB_40 = $(NORDIC_OBJS)
OBJS += $(NORDIC_OBJS)
endif
# Rust ring buffers (../rust-adapters): toolchain image 2026-11-13 or later
include ../common/rust.mk

# One firmware per library: ONLY=n (an index into decode.py's LIBS) links
# the test harness with library n's objects alone (main.c ONLY_LIB). Without
# ONLY: every library in one image, as before.
HARNESS = build/main.o build/startup.o build/bench_heap.o build/bench_heap_cpp.o $(LIB_RT_OBJS)
LIB_0  = build/adapter_pxq.o
LIB_1  = build/adapter_lwrb.o build/lwrb.o
LIB_2  = build/adapter_anders.o build/anders_ringbuffer.o
LIB_3  = build/adapter_jnk0le.o
LIB_4  = build/adapter_etl.o
LIB_5  = build/adapter_etl.o
LIB_6  = build/w2_qp_lfrb.o build/qp_ring_buf.o
LIB_7  = build/w2_ea_cbuf.o build/ea_circular_buffer.o
LIB_8  = build/w2_ece.o build/ece_ring_buffer.o
LIB_9  = build/w2_micoring.o build/micoring_mring.o
LIB_10 = build/w2_kostyk.o
LIB_11 = build/w2_diffstorm.o build/diffstorm_cb.o
LIB_12 = build/w2_riot_tsrb.o build/riot_tsrb.o
LIB_13 = build/w2_contiki.o build/contiki_ringbuf.o
LIB_14 = build/w2_rigtorp.o
LIB_15 = build/w2_wizard97_plain.o
LIB_16 = build/w2_wizard97_primask.o
LIB_17 = build/w2_polycratia.o
LIB_18 = build/w2_rtspsc.o
LIB_19 = build/w2_tinyusb.o build/tinyusb_fifo.o
LIB_20 = build/w2_zephyr.o
LIB_21 = build/w2_zephyr_smp.o
LIB_22 = build/w2_lockfree.o
LIB_23 = build/w2_etl_locked.o
LIB_24 = build/w2_freertos_sb.o build/freertos_stream_buffer.o build/freertos_shim.o
LIB_25 = build/w2_nuttx_circbuf.o build/nuttx_circbuf.o
LIB_26 = build/w2_arduino_plain.o
LIB_27 = build/w2_arduino_safe.o
LIB_28 = build/w2_rtthread_plain.o build/rtthread_ringbuffer.o
LIB_29 = build/w2_rtthread_locked.o build/rtthread_ringbuffer.o
LIB_30 = build/w2_mbed_cb.o
LIB_31 = build/w2_moodycamel.o
LIB_32 = $(RUST_OBJS)
LIB_33 = $(RUST_OBJS)
LIB_34 = $(RUST_OBJS)
LIB_35 = build/broken.o
LIB_36 = build/mutants.o
LIB_37 = build/mutants.o
LIB_38 = build/mutants.o
LIB_39 = build/mutants.o
ifeq ($(ONLY),)
OBJS += $(WAVE2_OBJS) $(LIB_RT_OBJS) $(RUST_OBJS)
LINK_RUST = $(RUST_LINK)
ELF = build/fw.elf
else
ifeq ($(LIB_$(ONLY)),)
$(error ONLY=$(ONLY) is not a library index (0..39))
endif
# Output per library: build/lib<n>/ (fw.elf, fw.map, fw.lst). SLOT_BASE and
# SLOT_LEN: the flash region the image is linked for (bundle.sh: several
# libraries' images side by side in flash, and slotboot.c picks one after
# each reset); without them the image starts at the board's flash base.
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
# no page alignment: otherwise the ELF headers are loaded in front of the
# image's first section, into the flash below the slot (the stub)
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
build/broken.o: broken.c $(BENCH)/bench.h | build
	arm-none-eabi-gcc $(CFLAGS) -c $< -o $@
build/mutants.o: mutants.c $(BENCH)/bench.h | build
	arm-none-eabi-gcc $(CFLAGS) -c $< -o $@
build/startup.o: $(COMMON)/startup.c | build
	arm-none-eabi-gcc $(CFLAGS) -fno-lto -fno-tree-loop-distribute-patterns -c $< -o $@
build/adapter_pxq.o: $(BENCH)/adapter_pxq.cpp $(BENCH)/bench.h | build
	$(CXX_LIB) $(CXXFLAGS) -c $< -o $@
build/adapter_lwrb.o: $(BENCH)/adapter_lwrb.c $(BENCH)/bench.h | build
	$(CC_LIB) $(CFLAGS) -c $< -o $@
build/lwrb.o: $(LWRB)/lwrb/lwrb.c | build
	$(CC_LIB) $(CFLAGS) -c $< -o $@
build/adapter_anders.o: $(BENCH)/adapter_anders.c $(BENCH)/bench.h | build
	$(CC_LIB) $(CFLAGS) -I$(ANDERS) -c $< -o $@
build/anders_ringbuffer.o: $(ANDERS)/ringbuffer.c | build
	$(CC_LIB) $(CFLAGS) -I$(ANDERS) -c $< -o $@
build/adapter_jnk0le.o: $(BENCH)/adapter_jnk0le.cpp $(BENCH)/bench.h | build
	$(CXX_LIB) $(CXXFLAGS) -I$(JNK0LE) -c $< -o $@
# ETL pulls in hosted STL headers (<cmath> etc.), so no -ffreestanding here.
build/adapter_etl.o: $(BENCH)/adapter_etl.cpp $(BENCH)/bench.h | build
	$(CXX_LIB) $(filter-out -ffreestanding,$(CXXFLAGS)) -I$(ETL) -c $< -o $@

build:
	mkdir -p build

clean:
	rm -rf build/*.o build/fw.* build/rust build/lib[0-9]* build/boot* build/bundle*

.PHONY: clean

# make print-VAR: a variable's value (../common/bundle.py)
print-%:
	@echo '$($*)'
