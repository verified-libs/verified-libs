# Build inside the pinned toolchain image (after fetch-libs.sh):
#   podman run --rm -v "$PWD/..":/work:Z -w /work/nrf5340-rb-bench \
#       verified-libs/toolchain:2026-11-05 make
# Two images from the same object files, differing only in where code runs:
#   build/flash/fw.elf  code executes from flash (via the instruction cache)
#   build/sram/fw.elf   code is copied to SRAM at startup and executes there
# BOARD selects common/<BOARD>/ (board.h, board.mk, startup.c, linker
# scripts): nrf5340 (default), stm32g0b1, stm32g474, stm32h723, samd20
# (flash image only: no LD_SRAM). Objects of one board only are
# kept in build/; switching boards needs "make clean".
BOARD  ?= nrf5340
COMMON  = ../common/$(BOARD)
PXQ     = build/libs/pxq-ringbuffer-cortex/RingBuffer_PackedState
LWRB    = build/libs/lwrb/lwrb/src
ANDERS  = build/libs/anders-ringbuffer
JNK0LE  = build/libs/jnk0le-ringbuffer
ETL     = build/libs/etl/include

include $(COMMON)/board.mk
ifeq ($(filter clean,$(MAKECMDGOALS)),)
PREV_BOARD := $(shell cat build/.board 2>/dev/null)
ifneq ($(PREV_BOARD),)
ifneq ($(PREV_BOARD),$(BOARD))
$(error build/ holds objects for BOARD=$(PREV_BOARD); run "make clean" first)
endif
endif
$(shell mkdir -p build && echo $(BOARD) > build/.board)
endif

# Optimisation: OPT (default -O2) and LTO=1 for link-time optimisation. The
# startup code is always built without LTO: the SRAM linker scripts keep
# startup.o in flash by file name, and its copy loops must keep
# -fno-tree-loop-distribute-patterns.
OPT     ?= -O2
LTO     ?= 0
ifeq ($(LTO),1)
LTOF     = -flto
endif
WARN     = -Wall -Wextra -Wno-missing-field-initializers
# -DNDEBUG: release build; assert() (used by AndersKaloer's init) would pull in
# fprintf and the heap.
# SET=mp: time the modes for more than one producer or consumer (9 entries)
# instead of the 37 SPSC configurations; records are kept apart by run.sh.
# SET=rust: the Rust libraries (../rust-adapters, built by ../common/rust.mk).
# SET=nordic: Nordic's nrf_ringbuf (nordic.mk; the nRF5 SDK files from
# nrf5-sdk.sh), BOARD=nrf5340 only (Nordic's licence: Nordic chips only).
SET     ?= spsc
ifeq ($(SET),mp)
SETF     = -DBENCH_MP
else ifeq ($(SET),rust)
SETF     = -DBENCH_RUST
else ifeq ($(SET),nordic)
SETF     = -DBENCH_NORDIC
endif
# SHIFT=N: placement experiment, N bytes between the harness and the rest of
# the code (main.c, BENCH_SHIFT). Unset or 0: the normal build.
ifneq ($(filter-out 0,$(SHIFT)),)
SETF    += -DBENCH_SHIFT=$(SHIFT)
endif
# SIZE=1 (size.sh only): the adapters' functions without their 32-byte
# alignment and common section (bench.h BENCH_NO_ALIGN), so the linker can
# drop each unused one and no padding is counted; the same for the Rust code.
ifeq ($(SIZE),1)
SETF    += -DBENCH_NO_ALIGN
endif
COMMONF  = $(ARCH) $(OPT) $(LTOF) $(SETF) $(EXTRA) -g $(WARN) -DNDEBUG -ffreestanding -ffunction-sections -fdata-sections \
           -I. -I$(COMMON)
CFLAGS   = $(COMMONF) -std=c11 -I$(LWRB)/include
CXXFLAGS = $(COMMONF) -std=c++20 -fno-exceptions -fno-rtti -fno-threadsafe-statics -I$(PXQ)
# newlib-nano from the toolchain image provides memcpy (used by lwrb).
LDBASE   = $(ARCH) $(OPT) $(LTOF) $(LD_LIB_EXTRA) -nostartfiles --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections

OBJS = build/main.o build/startup.o build/adapter_pxq.o build/adapter_lwrb.o build/lwrb.o \
       build/adapter_anders.o build/anders_ringbuffer.o build/adapter_jnk0le.o build/adapter_etl.o

.DEFAULT_GOAL := all
BENCH = .
include $(COMMON)/../compiler.mk
include libs.mk
OBJS += $(WAVE2_OBJS) $(SC_OBJS)
# Modes for more than one producer or consumer (linked into the result only
# with SET=mp); the lockfree adapter is the one rb-mp-stress tests.
OBJS += build/mp_pxq.o build/mp_lockfree_mpmc.o
build/mp_pxq.o: adapters_mp/adapter_pxq_mp.cpp bench.h | build
	$(CXX_LIB) $(CXXFLAGS) -c $< -o $@
build/mp_lockfree_mpmc.o: ../rb-mp-stress/adapter_lockfree_mpmc.cpp bench.h | build
	$(CXX_LIB) $(CXXW2) $(LF_D) -I. -I$(L)/lockfree-dnedic -c $< -o $@
OBJS += $(LIB_RT_OBJS)
ifeq ($(SET),nordic)
include nordic.mk
OBJS += $(NORDIC_OBJS) build/nordic_parts.o
build/nordic_parts.o: adapters_nordic/parts_nrf_ringbuf.c | build
	$(CC_LIB) $(CFLAGS) $(NRF5_I) -c $< -o $@
endif
include ../common/rust.mk
include ../common/libc.mk
ifneq ($(filter $(SET),mp rust),)
OBJS += $(RUST_OBJS)
LINK_TAIL = $(if $(filter rust,$(MEMCPY)),$(RUST_LINK_OWN),$(RUST_LINK))
LINK_DEPS = $(RUST_LIB)
endif

# MEMCPY=stub: replace the C library's memcpy with newlib's memcpy-stub (a
# byte loop), as a C library built for size links it (e.g. ST's GNU Tools
# for STM32). Default: the toolchain image's newlib-nano memcpy.
MEMCPY ?= newlib
ifeq ($(MEMCPY),stub)
OBJS += build/memcpy_stub.o
endif
build/memcpy_stub.o: shims/memcpy_stub.c | build
	arm-none-eabi-gcc $(ARCH) -Os -g -ffreestanding -fno-builtin -fno-tree-loop-distribute-patterns \
	    -ffunction-sections -c $< -o $@

all: build/flash/fw.elf $(if $(LD_SRAM),build/sram/fw.elf) $(if $(VAR3),build/$(VAR3)/fw.elf)

build:
	mkdir -p build

build/flash/fw.elf: $(OBJS) $(LINK_DEPS) $(LIBC_A) $(LD_FLASH)
	mkdir -p build/flash
	arm-none-eabi-g++ $(LDBASE) -T $(LD_FLASH) -Wl,-Map=build/flash/fw.map $(OBJS) $(LIBC_A) $(LINK_TAIL) -o $@
	arm-none-eabi-size $@
	arm-none-eabi-objdump -d -C $@ > build/flash/fw.lst

build/sram/fw.elf: $(OBJS) $(LINK_DEPS) $(LIBC_A) $(LD_SRAM)
	mkdir -p build/sram
	arm-none-eabi-g++ $(LDBASE) -T $(LD_SRAM) -Wl,-Map=build/sram/fw.map $(OBJS) $(LIBC_A) $(LINK_TAIL) -o $@
	arm-none-eabi-size $@
	arm-none-eabi-objdump -d -C $@ > build/sram/fw.lst

# Boards with a third code location (VAR3/LD_VAR3 in board.mk): CCM SRAM on
# the STM32G474, ITCM on the STM32H723.
ifneq ($(VAR3),)
build/$(VAR3)/fw.elf: $(OBJS) $(LINK_DEPS) $(LIBC_A) $(LD_VAR3)
	mkdir -p build/$(VAR3)
	arm-none-eabi-g++ $(LDBASE) -T $(LD_VAR3) -Wl,-Map=build/$(VAR3)/fw.map $(OBJS) $(LIBC_A) $(LINK_TAIL) -o $@
	arm-none-eabi-size $@
	arm-none-eabi-objdump -d -C $@ > build/$(VAR3)/fw.lst
endif

build/main.o: main.c bench.h $(wildcard $(COMMON)/*.h)
	arm-none-eabi-gcc $(CFLAGS) -c $< -o $@
build/startup.o: $(COMMON)/startup.c
	arm-none-eabi-gcc $(CFLAGS) -fno-lto -fno-tree-loop-distribute-patterns -c $< -o $@
build/adapter_pxq.o: adapter_pxq.cpp bench.h
	$(CXX_LIB) $(CXXFLAGS) -c $< -o $@
build/adapter_lwrb.o: adapter_lwrb.c bench.h
	$(CC_LIB) $(CFLAGS) -c $< -o $@
build/lwrb.o: $(LWRB)/lwrb/lwrb.c
	$(CC_LIB) $(CFLAGS) -c $< -o $@
build/adapter_anders.o: adapter_anders.c bench.h
	$(CC_LIB) $(CFLAGS) -I$(ANDERS) -c $< -o $@
build/anders_ringbuffer.o: $(ANDERS)/ringbuffer.c
	$(CC_LIB) $(CFLAGS) -I$(ANDERS) -c $< -o $@
build/adapter_jnk0le.o: adapter_jnk0le.cpp bench.h
	$(CXX_LIB) $(CXXFLAGS) -I$(JNK0LE) -c $< -o $@
# ETL pulls in hosted STL headers (<cmath> etc.), so no -ffreestanding here.
build/adapter_etl.o: adapter_etl.cpp bench.h
	$(CXX_LIB) $(filter-out -ffreestanding,$(CXXFLAGS)) -I$(ETL) -c $< -o $@

# size.sh: one flash firmware per configuration (build/size/<adapter>.elf:
# main.c with only that entry in its table, everything else as above, so
# --gc-sections keeps what that configuration needs) and adapter_none (the
# harness alone). The C library's memory functions are linked into every one,
# so they count for none.
build/size/%.elf: $(OBJS) $(LINK_DEPS) $(LIBC_A) $(LD_FLASH) size_none.c
	mkdir -p build/size
	arm-none-eabi-gcc $(CFLAGS) -DBENCH_ONLY=$* -c main.c -o build/size/main_$*.o
	arm-none-eabi-gcc $(CFLAGS) -c size_none.c -o build/size/none.o
	rm -f build/size/objs_$*.a
	arm-none-eabi-ar rcs build/size/objs_$*.a $(filter-out build/main.o,$(OBJS))
	arm-none-eabi-g++ $(LDBASE) -T $(LD_FLASH) -Wl,-u,memcpy -Wl,-u,memmove -Wl,-u,memset -Wl,-Map=build/size/$*.map \
	    build/size/main_$*.o build/size/none.o -Wl,--start-group build/size/objs_$*.a -Wl,--end-group $(LINK_TAIL) -o $@

clean:
	rm -rf build/*.o build/flash build/sram build/ccm build/itcm build/size build/.board build/rust

.PHONY: all clean
