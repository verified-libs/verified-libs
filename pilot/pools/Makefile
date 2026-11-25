# Pool pilot (README.md). Runs inside the toolchain image (run.sh), with the
# libraries fetched by fetch.sh mounted at LIBS.
#   make test     build and run the host test (host gcc/g++)
#   make cross    compile the same adapters and library files for a
#                 Cortex-M4 (the NUCLEO-G474RE's core) and link them into
#                 one ELF; no board is used
LIBS ?= /libs
ETL  := $(LIBS)/etl/include
RIOT := $(LIBS)/riot
TX   := $(LIBS)/threadx

TX_SRC   := $(addprefix $(TX)/common/src/,tx_block_allocate.c tx_block_release.c tx_block_pool_create.c tx_block_pool_delete.c)
RIOT_SRC := $(RIOT)/sys/memarray/memarray.c
WARN     := -Wall -Wextra

# The pilot's own files.
OWN_C    := adapter_ref.c adapter_riot_memarray.c adapter_threadx_block.c tx_kernel_stubs.c

HOST_CFLAGS := -O2 -g $(WARN) -I. -Ishims/riot -I$(RIOT)/sys/include -I$(TX)/common/inc -Iports/host
build/host/%.o: %.c pool.h | build/host
	gcc $(HOST_CFLAGS) -c $< -o $@
build/host/broken_double.o: adapter_ref.c pool.h | build/host
	gcc $(HOST_CFLAGS) -DPOOL_BROKEN=1 -c $< -o $@
build/host/broken_lost.o: adapter_ref.c pool.h | build/host
	gcc $(HOST_CFLAGS) -DPOOL_BROKEN=2 -c $< -o $@
build/host/adapter_etl_pool.o: adapter_etl_pool.cpp pool.h | build/host
	g++ -std=c++17 -O2 -g $(WARN) -I. -I$(ETL) -c $< -o $@
build/host/lib_%.o: | build/host
	gcc $(HOST_CFLAGS) -w -c $(filter %/$*.c,$(TX_SRC) $(RIOT_SRC)) -o $@

HOST_OBJS := $(addprefix build/host/,$(OWN_C:.c=.o) test_pool.o broken_double.o broken_lost.o adapter_etl_pool.o) \
             $(addprefix build/host/lib_,$(notdir $(TX_SRC:.c=.o) $(RIOT_SRC:.c=.o)))
build/host/test_pool: $(HOST_OBJS)
	g++ -o $@ $^
test: build/host/test_pool
	./build/host/test_pool

# Cross: the release's own Cortex-M4 port header for ThreadX (interrupts off
# with PRIMASK), the same adapters, -Os as a firmware would build them.
ARM      := arm-none-eabi
CPU      := -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16
X_CFLAGS := -Os -g $(CPU) -ffunction-sections -fdata-sections $(WARN) -I. -Ishims/riot -I$(RIOT)/sys/include -I$(TX)/common/inc -I$(TX)/ports/cortex_m4/gnu/inc
build/m4/%.o: %.c pool.h | build/m4
	$(ARM)-gcc $(X_CFLAGS) -c $< -o $@
build/m4/adapter_etl_pool.o: adapter_etl_pool.cpp pool.h | build/m4
	$(ARM)-g++ -std=c++17 -Os -g $(CPU) -ffunction-sections -fdata-sections -fno-exceptions -fno-rtti $(WARN) -I. -I$(ETL) -c $< -o $@
build/m4/lib_%.o: | build/m4
	$(ARM)-gcc $(X_CFLAGS) -w -c $(filter %/$*.c,$(TX_SRC) $(RIOT_SRC)) -o $@
M4_OBJS := $(addprefix build/m4/,adapter_ref.o adapter_riot_memarray.o adapter_threadx_block.o tx_kernel_stubs.o adapter_etl_pool.o cross_main.o) \
           $(addprefix build/m4/lib_,$(notdir $(TX_SRC:.c=.o) $(RIOT_SRC:.c=.o)))
build/m4/pools.elf: $(M4_OBJS)
	$(ARM)-g++ $(CPU) --specs=nosys.specs -Wl,--gc-sections -Wl,-Map=build/m4/pools.map -o $@ $^
	$(ARM)-size $@
cross: build/m4/pools.elf
	$(ARM)-nm -S --size-sort build/m4/pools.elf | grep -E 'ref_|riot_|tx_|etl_|memarray|_tx_block' || true

build/host build/m4:
	mkdir -p $@
clean:
	rm -rf build
.PHONY: test cross clean
