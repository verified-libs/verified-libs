# Wave-2 library adapters and sources, shared by nrf5340-rb-bench and
# nrf5340-rb-stress. The including Makefile sets BENCH (path to this folder),
# CFLAGS and CXXFLAGS, and has a "build" order-only target.
L    = $(BENCH)/build/libs
W2   = $(BENCH)/adapters_wave2
SHIM = $(BENCH)/shims
COMMON_DIR = $(BENCH)/../common/nrf5340

# Header-only C++ libraries here use hosted headers (<atomic>, <optional>,
# <memory>), so no -ffreestanding for the wave-2 C++ adapters.
CXXW2 = $(filter-out -ffreestanding,$(CXXFLAGS))

WAVE2_OBJS = \
    build/w2_qp_lfrb.o build/qp_ring_buf.o \
    build/w2_ea_cbuf.o build/ea_circular_buffer.o \
    build/w2_ece.o build/ece_ring_buffer.o \
    build/w2_micoring.o build/micoring_mring.o \
    build/w2_kostyk.o \
    build/w2_diffstorm.o build/diffstorm_cb.o \
    build/w2_riot_tsrb.o build/riot_tsrb.o \
    build/w2_contiki.o build/contiki_ringbuf.o \
    build/w2_rigtorp.o \
    build/w2_wizard97_plain.o build/w2_wizard97_primask.o \
    build/w2_polycratia.o \
    build/w2_rtspsc.o \
    build/w2_tinyusb.o build/tinyusb_fifo.o \
    build/w2_zephyr.o build/w2_zephyr_smp.o build/w2_lockfree.o build/w2_etl_locked.o \
    build/w2_freertos_sb.o build/freertos_stream_buffer.o build/freertos_shim.o \
    build/w2_nuttx_circbuf.o build/nuttx_circbuf.o build/w2_arduino_plain.o build/w2_arduino_safe.o \
    build/w2_rtthread_plain.o build/w2_rtthread_locked.o build/rtthread_ringbuffer.o \
    build/w2_mbed_cb.o build/w2_moodycamel.o \
    build/bench_heap.o build/bench_heap_cpp.o

# --- C libraries ---
QP_I  = -I$(L)/qp-lfrb/src
build/w2_qp_lfrb.o: $(W2)/adapter_qp_lfrb.c | build
	$(CC_LIB) $(CFLAGS) $(QP_I) -c $< -o $@
build/qp_ring_buf.o: $(L)/qp-lfrb/src/ring_buf.c | build
	$(CC_LIB) $(CFLAGS) $(QP_I) -c $< -o $@

EA_I  = -I$(L)/embeddedartistry/examples/c/circular_buffer
build/w2_ea_cbuf.o: $(W2)/adapter_ea_cbuf.c | build
	$(CC_LIB) $(CFLAGS) $(EA_I) -c $< -o $@
build/ea_circular_buffer.o: $(L)/embeddedartistry/examples/c/circular_buffer/circular_buffer_no_modulo_threadsafe.c | build
	$(CC_LIB) $(CFLAGS) $(EA_I) -c $< -o $@

# ece: its ring_buffer.c includes "main.h" (an STM32CubeMX project header; an
# empty shim here) and its own utils module.
ECE_I = -I$(SHIM)/ece -I$(L)/ece-ringbuffer/Modules -I$(L)/ece-ringbuffer/Modules/ring_buffer
build/w2_ece.o: $(W2)/adapter_ece.c | build
	$(CC_LIB) $(CFLAGS) $(ECE_I) -c $< -o $@
build/ece_ring_buffer.o: $(L)/ece-ringbuffer/Modules/ring_buffer/ring_buffer.c | build
	$(CC_LIB) $(CFLAGS) $(ECE_I) -c $< -o $@

# micoring in its SPSC mode: generated config first on the include path.
# Without it the include path would fall back to the library's default
# header (single-context mode) and build the wrong mode without a word.
MRING_I = -I$(BENCH)/build/gen/micoring -I$(L)/micoring/include
MRING_GEN = $(BENCH)/build/gen/micoring/mring_config.h
$(MRING_GEN):
	@echo "$@ is missing: run fetch-libs.sh first (it generates micoring's SPSC configuration)" >&2; exit 1
build/w2_micoring.o: $(W2)/adapter_micoring.c $(MRING_GEN) | build
	$(CC_LIB) $(CFLAGS) $(MRING_I) -c $< -o $@
build/micoring_mring.o: $(L)/micoring/src/mring.c $(MRING_GEN) | build
	$(CC_LIB) $(CFLAGS) $(MRING_I) -c $< -o $@

build/w2_kostyk.o: $(W2)/adapter_kostyk.c | build
	$(CC_LIB) $(CFLAGS) -I$(L)/kostyk-lockfree/include -c $< -o $@

DS_I  = -I$(L)/diffstorm-cb/src
build/w2_diffstorm.o: $(W2)/adapter_diffstorm.c | build
	$(CC_LIB) $(CFLAGS) $(DS_I) -c $< -o $@
# cb.c calls nanosleep() (POSIX) in its timeout helpers, which newlib does not
# declare; a prototype comes from shims/diffstorm/nanosleep.h. Those helpers
# are unused here and removed by --gc-sections.
build/diffstorm_cb.o: $(L)/diffstorm-cb/src/cb.c | build
	$(CC_LIB) $(CFLAGS) -include $(SHIM)/diffstorm/nanosleep.h $(DS_I) -c $< -o $@

RIOT_I = -I$(SHIM)/riot -I$(L)/riot/sys/include
build/w2_riot_tsrb.o: $(W2)/adapter_riot_tsrb.c | build
	$(CC_LIB) $(CFLAGS) $(RIOT_I) -c $< -o $@
build/riot_tsrb.o: $(L)/riot/sys/tsrb/tsrb.c | build
	$(CC_LIB) $(CFLAGS) $(RIOT_I) -c $< -o $@

CK_I  = -I$(SHIM)/contiki -I$(L)/contiki-ng/os
build/w2_contiki.o: $(W2)/adapter_contiki.c | build
	$(CC_LIB) $(CFLAGS) $(CK_I) -c $< -o $@
build/contiki_ringbuf.o: $(L)/contiki-ng/os/lib/ringbuf.c | build
	$(CC_LIB) $(CFLAGS) $(CK_I) -c $< -o $@

# --- C++ libraries ---
build/w2_rigtorp.o: $(W2)/adapter_rigtorp.cpp | build
	$(CXX_LIB) $(CXXW2) -I$(L)/rigtorp-spscqueue/include -c $< -o $@
build/w2_wizard97_plain.o: $(W2)/adapter_wizard97_plain.cpp | build
	$(CXX_LIB) $(CXXW2) -I$(L)/wizard97-ringbuf -c $< -o $@
build/w2_wizard97_primask.o: $(W2)/adapter_wizard97_primask.cpp | build
	$(CXX_LIB) $(CXXW2) -I$(L)/wizard97-ringbuf -c $< -o $@
# polycratia uses try/catch: needs exceptions.
build/w2_polycratia.o: $(W2)/adapter_polycratia.cpp | build
	$(CXX_LIB) $(filter-out -fno-exceptions,$(CXXW2)) -fexceptions -I$(L)/polycratia-spscring/include -c $< -o $@
# TinyUSB tu_fifo on its own: the minimal tusb_config.h shim (no MCU, no RTOS)
# first on the include path, then TinyUSB's src/ and src/common/.
TUSB_I = -I$(SHIM)/tinyusb -I$(L)/tinyusb/src -I$(L)/tinyusb/src/common
build/w2_tinyusb.o: $(W2)/adapter_tinyusb.c | build
	$(CC_LIB) $(CFLAGS) $(TUSB_I) -c $< -o $@
build/tinyusb_fifo.o: $(L)/tinyusb/src/common/tusb_fifo.c | build
	$(CC_LIB) $(CFLAGS) $(TUSB_I) -c $< -o $@

# Zephyr ring_buf (header only) with minimal Zephyr header shims; built twice:
# Zephyr's single-core code, and as with CONFIG_SMP=y (2 CPUs).
ZR_I = -I$(SHIM)/zephyr -I$(L)/zephyr-ringbuf/include
build/w2_zephyr.o: $(W2)/adapter_zephyr.c | build
	$(CC_LIB) $(CFLAGS) $(ZR_I) -c $< -o $@
build/w2_zephyr_smp.o: $(W2)/adapter_zephyr.c | build
	$(CC_LIB) $(CFLAGS) $(ZR_I) -DZEPHYR_RB_SMP=1 -c $< -o $@
# FreeRTOS stream buffer: the kernel's stream_buffer.c with the minimal
# config/port/task-stub shim in shims/freertos (no scheduler).
FRS_I = -I$(SHIM)/freertos -I$(L)/freertos-kernel/include
build/w2_freertos_sb.o: $(W2)/adapter_freertos_sb.c | build
	$(CC_LIB) $(CFLAGS) $(FRS_I) -c $< -o $@
build/freertos_stream_buffer.o: $(L)/freertos-kernel/stream_buffer.c | build
	$(CC_LIB) $(CFLAGS) $(FRS_I) -c $< -o $@
build/freertos_shim.o: $(SHIM)/freertos/freertos_shim.c | build
	$(CC_LIB) $(CFLAGS) $(FRS_I) -c $< -o $@
# DNedic/lockfree (header only, C++11). Its CMake defines the two settings;
# the README: "On embedded systems, LOCKFREE_CACHE_COHERENT should almost
# always be set as false" (no index padding). The line length is then unused.
LF_D = -DLOCKFREE_CACHE_COHERENT=false -DLOCKFREE_CACHELINE_LENGTH=64
build/w2_lockfree.o: $(W2)/adapter_lockfree.cpp | build
	$(CXX_LIB) $(CXXW2) $(LF_D) -I$(L)/lockfree-dnedic -c $< -o $@
# ETL queue_spsc_locked (same ETL as ../adapter_etl.cpp)
build/w2_etl_locked.o: $(W2)/adapter_etl_locked.cpp | build
	$(CXX_LIB) $(CXXW2) -I$(L)/etl/include -c $< -o $@

build/w2_rtspsc.o: $(W2)/adapter_rtspsc.cpp | build
	$(CXX_LIB) $(CXXW2) -I$(L)/rt-spsc/include -c $< -o $@

# --- single-context variants (benchmark only; not part of WAVE2_OBJS) ---
SC   = $(BENCH)/adapters_sc
SC_OBJS = build/sc_pxq_none.o build/sc_micoring.o build/sc_ea_plain.o build/sc_etl_queue.o
build/sc_pxq_none.o: $(SC)/adapter_pxq_none.cpp | build
	$(CXX_LIB) $(CXXFLAGS) -c $< -o $@
# The library's own include dir only: its default (single-context) config.
build/sc_micoring.o: $(SC)/adapter_micoring_sc.c | build
	$(CC_LIB) $(CFLAGS) -I$(L)/micoring/include -I$(L)/micoring/src -c $< -o $@
build/sc_ea_plain.o: $(SC)/adapter_ea_cbuf_plain.c | build
	$(CC_LIB) $(CFLAGS) $(EA_I) -c $< -o $@
build/sc_etl_queue.o: $(SC)/adapter_etl_queue.cpp | build
	$(CXX_LIB) $(CXXW2) -I$(L)/etl/include -c $< -o $@

build/bench_heap.o: $(COMMON_DIR)/bench_heap.c | build
	arm-none-eabi-gcc $(CFLAGS) -fno-builtin -c $< -o $@
build/bench_heap_cpp.o: $(COMMON_DIR)/bench_heap_cpp.cpp | build
	arm-none-eabi-g++ $(CXXW2) -c $< -o $@

# --- wave 4 ---
# NuttX circbuf (lib_circbuf.c unchanged) with the minimal shims in shims/nuttx.
NX_I = -I$(SHIM)/nuttx -I$(L)/nuttx-circbuf/include
build/w2_nuttx_circbuf.o: $(W2)/adapter_nuttx_circbuf.c | build
	$(CC_LIB) $(CFLAGS) $(NX_I) -c $< -o $@
build/nuttx_circbuf.o: $(L)/nuttx-circbuf/libs/libc/misc/lib_circbuf.c | build
	$(CC_LIB) $(CFLAGS) $(NX_I) -c $< -o $@
# Arduino RingBufferN as shipped, and SafeRingBufferN (Renesas core; its
# sync.h includes <Arduino.h>: shims/arduino). Header-only C++.
ARD_I = -I$(SHIM)/arduino -I$(L)/arduino-api -I$(L)/arduino-renesas/cores/arduino
build/w2_arduino_plain.o: $(W2)/adapter_arduino_rb.cpp | build
	$(CXX_LIB) $(CXXW2) $(ARD_I) -c $< -o $@
build/w2_arduino_safe.o: $(W2)/adapter_arduino_rb.cpp | build
	$(CXX_LIB) $(CXXW2) $(ARD_I) -DARDUINO_SAFE=1 -c $< -o $@
# RT-Thread rt_ringbuffer (ringbuffer.c unchanged), minimal shims in shims/rtthread;
# as shipped and with interrupts off around each call (as RT-Thread's serial driver).
RTT_I = -I$(SHIM)/rtthread -I$(L)/rt-thread/components/drivers/include
build/w2_rtthread_plain.o: $(W2)/adapter_rtthread_rb.c | build
	$(CC_LIB) $(CFLAGS) $(RTT_I) -c $< -o $@
build/w2_rtthread_locked.o: $(W2)/adapter_rtthread_rb.c | build
	$(CC_LIB) $(CFLAGS) $(RTT_I) -DRTT_LOCKED=1 -c $< -o $@
build/rtthread_ringbuffer.o: $(L)/rt-thread/components/drivers/ipc/ringbuffer.c | build
	$(CC_LIB) $(CFLAGS) $(RTT_I) -c $< -o $@
# Mbed CE CircularBuffer (header only), minimal shims in shims/mbed.
build/w2_mbed_cb.o: $(W2)/adapter_mbed_cb.cpp | build
	$(CXX_LIB) $(CXXW2) -I$(SHIM)/mbed -I$(L)/mbed-ce/platform/include -c $< -o $@
# moodycamel ReaderWriterQueue (header only); blocks from the bench heap;
# atomicops.h built through its FreeRTOS branch with declaration-only stubs.
build/w2_moodycamel.o: $(W2)/adapter_moodycamel.cpp | build
	$(CXX_LIB) $(CXXW2) -DFREERTOS -I$(SHIM)/moodycamel -I$(L)/moodycamel-rwq -c $< -o $@

