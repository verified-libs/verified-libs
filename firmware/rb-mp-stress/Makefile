# Build inside the pinned toolchain image (after ../nrf5340-rb-bench/fetch-libs.sh):
#   podman run --rm -v "$PWD/..":/work:Z -w /work/rb-mp-stress \
#       verified-libs/toolchain:2026-11-05 make MP_MODE=1
# Reuses the libraries and adapters of ../nrf5340-rb-bench and the board
# layer in ../common/<BOARD>. MP_MODE: 1 = MPSC, 2 = SPMC. Only the nRF5340
# has the second timer interrupt so far.
BOARD   ?= nrf5340
CODE    ?= flash
MP_MODE ?= 1
COMMON   = ../common/$(BOARD)
BENCH    = ../nrf5340-rb-bench
LIBS     = $(BENCH)/build/libs
PXQ      = $(LIBS)/pxq-ringbuffer-cortex/RingBuffer_PackedState
LWRB     = $(LIBS)/lwrb/lwrb/src
JNK0LE   = $(LIBS)/jnk0le-ringbuffer

include $(COMMON)/board.mk
OPT     ?= -O2
LTO     ?= 0
ifeq ($(LTO),1)
LTOF     = -flto
endif
COMMONF  = $(ARCH) $(OPT) $(LTOF) -g -Wall -Wextra -Wno-missing-field-initializers -DNDEBUG -ffreestanding \
           -ffunction-sections -fdata-sections -I. -I$(BENCH) -I$(COMMON) -DMP_MODE=$(MP_MODE) $(EXTRA)
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

# Library objects (WITH_EXTRA=1: extra/extra.mk adds the held-back MPSC
# libraries to EXTRA_OBJS; only then, so the default firmware is the same in
# the lab and in the public tree, and its records can be checked there).
ifeq ($(WITH_EXTRA),1)
include extra/extra.mk
COMMONF += -DWITH_EXTRA=1
endif

include $(COMMON)/../compiler.mk
include $(BENCH)/libs.mk
# Rust ring buffers (../rust-adapters): toolchain image 2026-11-13 or later
include ../common/rust.mk

# One firmware per library: ONLY=n links the harness with library n's objects
# alone (main.c ONLY_LIB; the index is the MP library index of main.c's
# MP_LIB_*, the same in both modes). Without ONLY: every library in one
# image, as before.
HARNESS = build/main.o build/startup.o build/bench_heap.o build/bench_heap_cpp.o $(LIB_RT_OBJS)
LIB_0 = build/adapters_mp.o
LIB_1 = build/adapters_mp.o
LIB_2 = build/w2_riot_tsrb.o build/riot_tsrb.o
LIB_3 = build/w2_wizard97_primask.o
LIB_4 = build/adapter_lockfree_mpmc.o
LIB_5 = $(RUST_OBJS)
LIB_6 = build/adapters_mp.o
LIB_7 = build/adapter_jnk0le.o
ifeq ($(WITH_EXTRA),1)
LIB_8 = $(EXTRA_OBJS)
endif
ALL_LIB_OBJS = $(sort $(LIB_0) $(LIB_1) $(LIB_2) $(LIB_3) $(LIB_4) $(LIB_6) $(LIB_7) $(LIB_8)) $(RUST_OBJS)
ifeq ($(ONLY),)
OBJS = $(HARNESS) $(ALL_LIB_OBJS)
LINK_RUST = $(RUST_LINK)
ELF = build/fw.elf
else
ifeq ($(LIB_$(ONLY)),)
$(error ONLY=$(ONLY) is not an MP library index (0..7, 8 with WITH_EXTRA=1))
endif
# Output per library: build/lib<n>/ (fw.elf, fw.map, fw.lst). SLOT_BASE and
# SLOT_LEN: the flash region the image is linked for (../common/bundle.py);
# without them the image starts at the board's flash base.
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
build/startup.o: $(COMMON)/startup.c | build
	arm-none-eabi-gcc $(CFLAGS) -fno-lto -fno-tree-loop-distribute-patterns -c $< -o $@
# DNedic/lockfree MPMC queue, with the settings its README gives for embedded.
LOCKFREE = $(LIBS)/lockfree-dnedic
build/adapter_lockfree_mpmc.o: adapter_lockfree_mpmc.cpp $(BENCH)/bench.h | build
	$(CXX_LIB) $(filter-out -ffreestanding,$(CXXFLAGS)) -DLOCKFREE_CACHE_COHERENT=false -DLOCKFREE_CACHELINE_LENGTH=64 -I$(LOCKFREE) -c $< -o $@
build/adapters_mp.o: adapters_mp.cpp $(BENCH)/bench.h | build
	$(CXX_LIB) $(CXXFLAGS) -c $< -o $@
build/adapter_jnk0le.o: $(BENCH)/adapter_jnk0le.cpp $(BENCH)/bench.h | build
	$(CXX_LIB) $(CXXFLAGS) -I$(JNK0LE) -c $< -o $@

build:
	mkdir -p build

clean:
	rm -rf build/*.o build/fw.* build/rust build/lib[0-9]* build/boot* build/bundle*

.PHONY: clean

# make print-VAR: a variable's value (../common/bundle.py)
print-%:
	@echo '$($*)'
