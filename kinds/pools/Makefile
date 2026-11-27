# The pools kind (README.md). Runs inside the toolchain image (run.sh), with
# the libraries fetched by fetch.sh mounted at LIBS.
#   make test     the host test (host gcc/g++), plain
#   make san      the same, built with the address and undefined-behaviour sanitizers
#   make proof    CBMC on the reference pool (proof/)
#   make rust     the Rust adapters' static library for the host (needed by test/san)
#   make miri     the Rust adapters' own tests under Miri
#   make cross    every adapter for the four cores at -Os and -O2, and the sizes
LIBS ?= /libs
WARN := -Wall -Wextra

ETL   := $(LIBS)/etl/include
RIOT  := $(LIBS)/riot
TX    := $(LIBS)/threadx
RTX   := $(LIBS)/cmsis-rtx
CMSIS := $(LIBS)/cmsis6
CTK   := $(LIBS)/contiki-ng/os
CAL   := $(LIBS)/c-allocator/src
LWIP  := $(LIBS)/lwip/src
MPOOL := $(LIBS)/memorypool-head/src

TX_SRC   := $(addprefix $(TX)/common/src/,tx_block_allocate.c tx_block_release.c tx_block_pool_create.c tx_block_pool_delete.c)
RIOT_SRC := $(RIOT)/sys/memarray/memarray.c
CTK_SRC  := $(CTK)/lib/memb.c
CAL_SRC  := $(CAL)/fb_allocator.c
CAL_CXX  := $(CAL)/LockGuard.cpp

# Per library: its include paths and defines, the same on the host and the boards.
INC_RIOT := -Ishims/riot -I$(RIOT)/sys/include
INC_TX   := -I$(TX)/common/inc
INC_CTK  := -Ishims/contiki -I$(CTK)
INC_CAL  := -I$(CAL) -DALLOC_LOCK_NONE
INC_LWIP := -Ishims/lwip -I$(LWIP)/include
INC_RTX  := -Ishims -I$(RTX)/Include -I$(RTX)/Source -I$(RTX)/Config -I$(CMSIS)/CMSIS/RTOS2/Include -DOS_EVR_MEMORY=0
# The host build of CMSIS-RTX: its three pool functions cut out unchanged (extract.py), the Armv6-M
# variant (interrupts off; the LDREX/STREX variant is Arm inline assembly), the host device header.
HOST_RTX := $(INC_RTX) -Ishims/host -D__ARM_ARCH_6M__=1 -DCMSIS_device_header=\"ARMCM_host.h\"

RUST_WITH := $(if $(wildcard rust/Cargo.toml),-DPOOL_WITH_RUST,)
RUST_HOST_LIB := build/rust/release/libvl_pools_rust.a
$(RUST_HOST_LIB): rust/Cargo.toml rust/src/lib.rs
	# --cap-lints warn: the dependencies come in by path, so cargo does not cap their lints as it does for
	# crates from crates.io; as-slice 0.1.5 denies warnings, and this rustc warns on its old cfg values.
	cd rust && RUSTFLAGS="--cap-lints warn" cargo build -q --offline --release --target-dir $(CURDIR)/build/rust

define host_rules
# $(1) = build directory, $(2) = extra flags (sanitizers)
$(1)/adapter_ref.o: adapter_ref.c pool.h | $(1)
	gcc -O2 -g $(WARN) $(2) -I. -c $$< -o $$@
$(1)/adapter_ref_primask.o: adapter_ref.c pool.h | $(1)
	gcc -O2 -g $(WARN) $(2) -I. -DPOOL_PRIMASK=1 -c $$< -o $$@
$(1)/broken_%.o: adapter_ref.c pool.h | $(1)
	gcc -O2 -g $(WARN) $(2) -I. -DPOOL_BROKEN=$$(BROKEN_$$*) -c $$< -o $$@
$(1)/test_pool.o: test_pool.c pool.h | $(1)
	gcc -O2 -g $(WARN) $(2) -I. $(RUST_WITH) -DPOOL_WITH_LWIP -c $$< -o $$@
$(1)/adapter_etl.o: adapter_etl.cpp pool.h | $(1)
	g++ -std=c++17 -O2 -g $(WARN) $(2) -I. -I$(ETL) -c $$< -o $$@
$(1)/adapter_riot.o: adapter_riot.c pool.h | $(1)
	gcc -O2 -g $(WARN) $(2) -I. $(INC_RIOT) -c $$< -o $$@
$(1)/adapter_threadx.o: adapter_threadx.c pool.h | $(1)
	gcc -O2 -g $(WARN) $(2) -I. $(INC_TX) -Iports/host -c $$< -o $$@
$(1)/tx_kernel_stubs.o: tx_kernel_stubs.c | $(1)
	gcc -O2 -g $(WARN) $(2) -I. $(INC_TX) -Iports/host -c $$< -o $$@
$(1)/adapter_contiki.o: adapter_contiki.c pool.h | $(1)
	gcc -O2 -g $(WARN) $(2) -I. $(INC_CTK) -c $$< -o $$@
$(1)/adapter_c_allocator.o: adapter_c_allocator.c pool.h | $(1)
	gcc -O2 -g $(WARN) $(2) -I. $(INC_CAL) -c $$< -o $$@
$(1)/adapter_memorypool.o: adapter_memorypool.cpp pool.h | $(1)
	g++ -std=c++17 -O2 -g $(WARN) $(2) -I. -I$(MPOOL) -c $$< -o $$@
$(1)/adapter_lwip.o: adapter_lwip.c pool.h | $(1)
	gcc -O2 -g $(WARN) $(2) -I. $(INC_LWIP) -c $$< -o $$@
$(1)/sys_arch.o: shims/lwip/sys_arch.c pool.h | $(1)
	gcc -O2 -g $(WARN) $(2) -I. $(INC_LWIP) -c $$< -o $$@
$(1)/lib_memp.o: | $(1)
	gcc -O2 -g $(2) -w -I. $(INC_LWIP) -c $(LWIP)/core/memp.c -o $$@
$(1)/adapter_rust.o: adapter_rust.c pool.h | $(1)
	gcc -O2 -g $(WARN) $(2) -I. -c $$< -o $$@
$(1)/adapter_cmsis_rtx.o: adapter_cmsis_rtx.c pool.h | $(1)
	gcc -O2 -g $(WARN) $(2) -I. $(HOST_RTX) -c $$< -o $$@
$(1)/rtx_mempool_pool.c: $(RTX)/Source/rtx_mempool.c extract.py | $(1)
	python3 -I extract.py $$< $$@
$(1)/rtx_mempool_pool.o: $(1)/rtx_mempool_pool.c | $(1)
	gcc -O2 -g $(2) -w -I. $(HOST_RTX) -c $$< -o $$@
$(1)/lib_tx_%.o: | $(1)
	gcc -O2 -g $(2) -w -I. $(INC_TX) -Iports/host -c $(TX)/common/src/tx_$$*.c -o $$@
$(1)/lib_memarray.o: | $(1)
	gcc -O2 -g $(2) -w -I. $(INC_RIOT) -c $(RIOT_SRC) -o $$@
$(1)/lib_memb.o: | $(1)
	gcc -O2 -g $(2) -w -I. $(INC_CTK) -c $(CTK_SRC) -o $$@
$(1)/lib_fb_allocator.o: | $(1)
	gcc -O2 -g $(2) -w -I. $(INC_CAL) -c $(CAL_SRC) -o $$@
$(1)/lib_LockGuard.o: | $(1)
	g++ -std=c++17 -O2 -g $(2) -w -I. $(INC_CAL) -c $(CAL_CXX) -o $$@
$(1)/test_pool: $(addprefix $(1)/,$(HOST_OBJS)) $(if $(RUST_WITH),$(1)/adapter_rust.o $(RUST_HOST_LIB))
	g++ $(2) -o $$@ $$^ -lpthread -ldl
$(1):
	mkdir -p $$@
endef

BROKEN_double := 1
BROKEN_lost := 2
BROKEN_overrun := 3
BROKEN_misaligned := 4
HOST_OBJS := test_pool.o adapter_ref.o adapter_ref_primask.o broken_double.o broken_lost.o broken_overrun.o \
             broken_misaligned.o adapter_etl.o adapter_riot.o adapter_threadx.o tx_kernel_stubs.o adapter_cmsis_rtx.o \
             rtx_mempool_pool.o adapter_contiki.o adapter_c_allocator.o \
             $(addprefix lib_tx_,$(notdir $(patsubst $(TX)/common/src/tx_%,%,$(TX_SRC:.c=.o)))) \
             lib_memarray.o lib_memb.o lib_fb_allocator.o lib_LockGuard.o adapter_lwip.o sys_arch.o lib_memp.o adapter_memorypool.o

COMMA := ,
$(eval $(call host_rules,build/host,))
$(eval $(call host_rules,build/san,-fsanitize=address$(COMMA)undefined -fno-sanitize-recover=all -fno-omit-frame-pointer))

test: build/host/test_pool
	./build/host/test_pool
san: build/san/test_pool
	ASAN_OPTIONS=detect_leaks=0 ./build/san/test_pool

clean:
	rm -rf build
.PHONY: test san clean

# The Rust adapters' tests under Miri (the image's nightly toolchain, as the CRC kind's `make miri`), with
# Miri's default provenance: the C interface passes block addresses as integers (as time_call does),
# which -Zmiri-strict-provenance does not allow.
miri:
	cd rust && MIRI_SYSROOT=/root/.cache/miri RUSTFLAGS="--cap-lints warn" \
	    cargo +nightly-2026-11-05 miri test -q --offline --locked --target-dir $(CURDIR)/build/miri
.PHONY: miri

# CBMC on the reference pool, and on two broken builds of it that it must refute.
proof:
	bash proof/run.sh
.PHONY: proof

# Our check of MemoryPool's only release v0.1.0 (README.md, "MemoryPool"), and the same at the head.
memorypool-v010: | build/host
	g++ -std=c++17 -O0 -g -I$(LIBS)/memorypool/src checks/memorypool_v010.cpp -o build/host/mp_v010 && ./build/host/mp_v010
	g++ -std=c++17 -O0 -g -I$(MPOOL) checks/memorypool_v010.cpp -o build/host/mp_head && echo "-- at the head:" && ./build/host/mp_head
.PHONY: memorypool-v010

# Every adapter for the four cores at -Os and -O2, and the sizes (cross.sh, sizes.py).
cross:
	bash cross.sh
.PHONY: cross
