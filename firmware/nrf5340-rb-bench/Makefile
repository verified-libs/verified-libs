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

build/main.o: main.c bench.h sets.h $(wildcard $(COMMON)/*.h)
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

# One image per configuration (lab/plans/2026-11-22-bench-image-per-library.md;
# built by onebundle.py): the harness, the baseline and the configuration
# ONE (an adapter's name), FAR + PLACE bytes between the configuration's
# adapter and the library (as SHIFT, for main.c only: the objects are built
# once), linked
# for the flash region SLOT_BASE/SLOT_LEN. Only what the configuration needs
# is linked (the objects come from an archive).
#   make one ONE=adapter_lwrb PLACE=4 SLOT_BASE=0x1000 SLOT_LEN=8192
#   ONE_RUST=1    the configuration is Rust code: link the Rust archive
#   ONE_NORDIC=1  it is Nordic's (nordic.mk; BOARD=nrf5340 only)
# The fixed part is the same code at the same offsets in every image of a
# board: the vector table, the harness, the C library's memory functions
# (all of them in every image, used or not), main.c's other code with the
# baseline, and the start-up code; memcpy starts on a 32-byte boundary (for
# Cortex-M0+ newlib has it in the object memcpy-stub, for the other cores in
# memcpy: both are named). Then
# the configuration's adapter (for a Rust configuration: its functions of
# ../rust-adapters, by their prefixes), FAR + PLACE bytes, and everything
# else: the library.
# FAR (DECISIONS 2026-11-23, "far call"): every library lies at least FAR
# bytes from the adapter that calls it, as a library does in an application
# that is larger than a test image. On the Cortex-M7 a call across about
# 4 KB or more costs 6 to 10 cycles more than a call to code nearby
# (reports/2026-11-23-bench-v2-first-run.md); with the library next to its
# adapter some configurations would pay that and others not, by the size of
# their code. Code that the compiler puts into the adapter itself (a library
# of headers) has no call and stays where the adapter is. 6144: half as
# much again as the 4096 at which the full cost was measured.
# onebundle.py checks that every function of the adapter's table lies
# before the gap. So the baseline and memcpy do not move with
# the size of the library (they did in version 1, where memcpy lay behind
# all libraries), and onebundle.py checks that they do not.
ifneq ($(ONE),)
PLACE ?= 0
FAR ?= 6144
ONE_NEAR = *(.text.bench_adapter*) *libvl_rust_adapters.a:*(.text.hl_* .text.hlm_* .text.bbq_* .text.emb_*) _bench_near_end = .;
OD = build/one/$(ONE)-p$(PLACE)-$(SLOT_BASE)
ONE_OBJS = $(filter-out build/main.o build/startup.o,$(OBJS)) $(RUST_OBJS)
ifeq ($(ONE_NORDIC),1)   # an archive of its own: the other images' archive is the same with and without it
ifneq ($(SET),nordic)
include nordic.mk
build/nordic_parts.o: adapters_nordic/parts_nrf_ringbuf.c | build
	$(CC_LIB) $(CFLAGS) $(NRF5_I) -c $< -o $@
endif
ONE_NORDIC_A = build/one/nordic.a
build/one/nordic.a: $(NORDIC_OBJS) build/nordic_parts.o
	mkdir -p build/one
	rm -f $@
	arm-none-eabi-ar rcs $@ $^
endif
# the C library's memory functions are named to the linker for every image
# (RUST_MEMSYMS, ../common/rust.mk), and the C library comes before the
# Rust archive, so that they are newlib's for C and Rust code alike
ONE_U    = $(addprefix -Wl$(comma)-u$(comma),$(RUST_MEMSYMS))
ONE_TAIL = $(LIBC_A) -Wl,-lc_nano $(if $(filter 1,$(ONE_RUST)),$(RUST_LIB))
ONE_FIXED = . = ALIGN(32); *libc_a-memcpy.o(.text*) *libc_a-memcpy-stub.o(.text*) *libc_a-memmove.o(.text*) *libc_a-memset.o(.text*) *libc_a-memcmp.o(.text*) \
            *libc_a-aeabi_mem*.o(.text*) *main.o(.text.bench_adapter*) *main.o(.text*) *main.o(.rodata*) *startup.o(.text*) \
            *startup.o(.rodata*) _bench_fixed_end = .;
one: $(OD)/fw.elf
build/one/objs.a: $(ONE_OBJS)
	mkdir -p build/one
	rm -f $@
	arm-none-eabi-ar rcs $@ $^
$(OD)/fw.elf: build/one/objs.a $(ONE_NORDIC_A) build/startup.o main.c bench.h $(wildcard $(COMMON)/*.h) $(LIBC_A) $(LD_FLASH) \
              $(if $(filter 1,$(ONE_RUST)),$(RUST_LIB))
	mkdir -p $(OD)
	sed -E -e 's/^([[:space:]]*FLASH[[:space:]]+\(rx\)[[:space:]]*:[[:space:]]*)ORIGIN = [^,]+, LENGTH = [^[:space:]]+/\1ORIGIN = $(SLOT_BASE), LENGTH = $(SLOT_LEN)/' \
	    -e 's/\*\(\.text\.time_call\) \*\(\.text\.bench_adapter\*\)/*(.text.time_call) $(ONE_FIXED) $(ONE_NEAR)/' $(LD_FLASH) > $(OD)/slot.ld
	grep -q 'ORIGIN = $(SLOT_BASE), LENGTH = $(SLOT_LEN)' $(OD)/slot.ld || { echo "$(LD_FLASH): no FLASH region to move" >&2; exit 1; }
	grep -qF '_bench_near_end = .;' $(OD)/slot.ld || { echo "$(LD_FLASH): no place for the adapter" >&2; exit 1; }
	grep -qF '*libc_a-memcpy.o(.text*)' $(OD)/slot.ld || { echo "$(LD_FLASH): no place for the fixed part" >&2; exit 1; }
	arm-none-eabi-gcc $(CFLAGS) -DBENCH_ONE=$(ONE) -DBENCH_SHIFT=$(shell expr $(FAR) + $(PLACE)) -c main.c -o $(OD)/main.o
	arm-none-eabi-g++ $(LDBASE) -Wl,-n -T $(OD)/slot.ld -Wl,-Map=$(OD)/fw.map $(ONE_U) \
	    $(OD)/main.o build/startup.o -Wl,--start-group build/one/objs.a $(ONE_NORDIC_A) -Wl,--end-group $(ONE_TAIL) -o $@
.PHONY: one
endif

# onebundle.py reads the board's variables
print-%:
	@echo '$($*)'

clean:
	rm -rf build/*.o build/flash build/sram build/ccm build/itcm build/size build/one build/.board build/rust

.PHONY: all clean
