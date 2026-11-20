# rb-xcore-stress: SPSC across the two cores of the nRF5340 (main.c). Two
# images from the same objects: build/app/fw.elf (application core, flash
# 0x0) and build/net/fw.elf (network core, flash 0x01000000). The library
# objects' .bss is the shared part (.xshared, 0x20070000) in both images;
# check_shared.py fails the build if its layout differs. Build in the
# toolchain image after ../nrf5340-rb-bench/fetch-libs.sh.
BOARD    = nrf5340
COMMON   = ../common/nrf5340
NETCOM   = ../common/nrf5340net
BENCH    = ../nrf5340-rb-bench
STRESS   = ../nrf5340-rb-stress
LIBS     = $(BENCH)/build/libs
PXQ      = $(LIBS)/pxq-ringbuffer-cortex/RingBuffer_PackedState
LWRB     = $(LIBS)/lwrb/lwrb/src
JNK0LE   = $(LIBS)/jnk0le-ringbuffer
ETL      = $(LIBS)/etl/include

include $(COMMON)/board.mk
# The network core is a Cortex-M33 without the DSP extension (2026-11-17:
# pxq's and Zephyr's code, built for the application core's M33 with DSP,
# used UXTAH and the network core faulted on its first call). The library
# objects serve both cores, so everything is built without DSP.
ARCH     = -mcpu=cortex-m33+nodsp -mthumb -mfloat-abi=soft
OPT     ?= -O2
COMMONF  = $(ARCH) $(OPT) -g -Wall -Wextra -Wno-missing-field-initializers -DNDEBUG -ffreestanding \
           -ffunction-sections -fdata-sections -I. -I$(BENCH) -I$(COMMON) $(EXTRA)
CFLAGS   = $(COMMONF) -std=c11 -I$(LWRB)/include
CXXFLAGS = $(COMMONF) -std=c++20 -fno-exceptions -fno-rtti -fno-threadsafe-statics -I$(PXQ)
LDF      = $(ARCH) $(OPT) -nostartfiles --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections

include $(COMMON)/../compiler.mk
include $(BENCH)/libs.mk
include ../common/rust.mk
# Rust: no DSP either (the generic Armv8-M Mainline CPU)
RUST_CPU = generic

LIBOBJS = build/adapter_lwrb.o build/lwrb.o build/adapter_jnk0le.o build/adapter_etl.o \
          build/w2_qp_lfrb.o build/qp_ring_buf.o build/w2_micoring.o build/micoring_mring.o build/w2_kostyk.o \
          build/w2_diffstorm.o build/diffstorm_cb.o build/w2_rigtorp.o build/w2_polycratia.o build/w2_rtspsc.o \
          build/w2_zephyr_smp.o build/w2_lockfree.o build/w2_moodycamel.o build/adapter_pxq.o build/broken.o \
          build/bench_heap.o build/bench_heap_cpp.o $(LIB_RT_OBJS) $(RUST_OBJS)

.DEFAULT_GOAL := all
all: build/app/fw.elf build/net/fw.elf
	python3 -I check_shared.py build/app/fw.elf build/net/fw.elf
	arm-none-eabi-objdump -d build/net/fw.elf > build/net/fw.lst
	! grep -E '\s(uxtah|uxtab|uxtb16|sxtah|sxtab|sxtb16|[us]?[qh]?(add|sub)(8|16)|[us]?[qh]?(asx|sax)|sel|smla[bdltw]+|smls[dl]+|smul[bdltw]+|smmla|smmls|smmul|smuad|smusd|usad8|usada8|pkhbt|pkhtb|[su]sat16|qadd|qsub|qdadd|qdsub)\s' build/net/fw.lst \
	    || { echo "DSP instructions in the network core image" >&2; exit 1; }

build/app/fw.elf: build/app/main.o build/app/startup.o $(LIBOBJS) $(RUST_LIB) $(COMMON)/nrf5340_xcore_app.ld
	arm-none-eabi-g++ $(LDF) -T $(COMMON)/nrf5340_xcore_app.ld -Wl,-Map=build/app/fw.map \
	    build/app/main.o build/app/startup.o $(LIBOBJS) $(RUST_LINK) -o $@
	arm-none-eabi-size $@
build/net/fw.elf: build/net/main.o build/net/startup_net.o $(LIBOBJS) $(RUST_LIB) $(NETCOM)/nrf5340_xcore_net.ld
	arm-none-eabi-g++ $(LDF) -T $(NETCOM)/nrf5340_xcore_net.ld -Wl,-Map=build/net/fw.map \
	    build/net/main.o build/net/startup_net.o $(LIBOBJS) $(RUST_LINK) -o $@
	arm-none-eabi-size $@

build/app/main.o: main.c $(BENCH)/bench.h $(wildcard $(COMMON)/*.h ../common/*.h) | build
	mkdir -p build/app
	arm-none-eabi-gcc $(CFLAGS) -c $< -o $@
build/net/main.o: main.c $(BENCH)/bench.h | build
	mkdir -p build/net
	arm-none-eabi-gcc $(CFLAGS) -DXCORE_NET=1 -c $< -o $@
build/app/startup.o: $(COMMON)/startup.c | build
	mkdir -p build/app
	arm-none-eabi-gcc $(CFLAGS) -fno-tree-loop-distribute-patterns -c $< -o $@
build/net/startup_net.o: $(NETCOM)/startup_net.c | build
	mkdir -p build/net
	arm-none-eabi-gcc $(CFLAGS) -fno-tree-loop-distribute-patterns -c $< -o $@
build/adapter_pxq.o: $(BENCH)/adapter_pxq.cpp $(BENCH)/bench.h | build
	$(CXX_LIB) $(CXXFLAGS) -c $< -o $@
build/adapter_lwrb.o: $(BENCH)/adapter_lwrb.c $(BENCH)/bench.h | build
	$(CC_LIB) $(CFLAGS) -c $< -o $@
build/lwrb.o: $(LWRB)/lwrb/lwrb.c | build
	$(CC_LIB) $(CFLAGS) -c $< -o $@
build/adapter_jnk0le.o: $(BENCH)/adapter_jnk0le.cpp $(BENCH)/bench.h | build
	$(CXX_LIB) $(CXXFLAGS) -I$(JNK0LE) -c $< -o $@
build/adapter_etl.o: $(BENCH)/adapter_etl.cpp $(BENCH)/bench.h | build
	$(CXX_LIB) $(filter-out -ffreestanding,$(CXXFLAGS)) -I$(ETL) -c $< -o $@
build/broken.o: $(STRESS)/broken.c $(BENCH)/bench.h | build
	arm-none-eabi-gcc $(CFLAGS) -c $< -o $@

build:
	mkdir -p build

clean:
	rm -rf build/*.o build/app build/net build/rust

.PHONY: all clean
print-%:
	@echo '$($*)'
