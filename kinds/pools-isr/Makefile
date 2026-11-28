# The concurrency check of the pools kind on the host (contract.c;
# site/content/method-pools.md, "Use from interrupts"). Runs inside the toolchain
# image (run.sh), with the libraries of ../pools/fetch.sh mounted at LIBS. The
# libraries and adapters are compiled as the kind's host test compiles them
# (../pools/Makefile, the same include paths and defines); nothing of ../pools is
# written: everything goes to build/ here.
#   make check    the five programs: every configuration, CMSIS-RTX's
#                 LDREX/STREX variant and its control, and C_Allocator with its
#                 lock option ALLOC_LOCK_CMSIS_RTOS2 and its control
#                 (site/content/method-pools.md, "C_Allocator twice")
#   make test-board-side   the no-board tests of the image, runner and record writer
LIBS ?= /libs
K := ../pools
WARN := -Wall -Wextra
B := build

ETL   := $(LIBS)/etl/include
RIOT  := $(LIBS)/riot
TX    := $(LIBS)/threadx
RTX   := $(LIBS)/cmsis-rtx
CMSIS := $(LIBS)/cmsis6
CTK   := $(LIBS)/contiki-ng/os
CAL   := $(LIBS)/c-allocator/src
LWIP  := $(LIBS)/lwip/src
MPOOL := $(LIBS)/memorypool-head/src

INC_RIOT := -I$(K)/shims/riot -I$(RIOT)/sys/include
INC_TX   := -I$(TX)/common/inc -I$(K)/ports/host
INC_CTK  := -I$(K)/shims/contiki -I$(CTK)
INC_CAL  := -I$(CAL) -DALLOC_LOCK_NONE
# C_Allocator's lock option on the host: CMSIS-Core's three functions are the check's flag (cal_lock/cmsis_compiler.h)
INC_CAL_LOCK := -I$(K)/shims/host/cal_lock -I$(CAL) -DALLOC_LOCK_CMSIS_RTOS2
INC_LWIP := -I$(K)/shims/lwip -I$(LWIP)/include
INC_RTX  := -I$(K)/shims -I$(RTX)/Include -I$(RTX)/Source -I$(RTX)/Config -I$(CMSIS)/CMSIS/RTOS2/Include -DOS_EVR_MEMORY=0
# CMSIS-RTX on the host: as the kind's host test, but with this directory's device header (ARMCM_isr.h: PRIMASK
# is the check's flag)
HOST_RTX := $(INC_RTX) -I$(K)/shims/host -D__ARM_ARCH_6M__=1 -DCMSIS_device_header=\"ARMCM_isr.h\"
CC  := gcc -O2 -g $(WARN) -I. -I$(K)
CXX := g++ -std=c++17 -O2 -g $(WARN) -I. -I$(K)
LIBCC := gcc -O2 -g -w -I. -I$(K)

RUST_LIB := $(B)/rust/release/libvl_pools_rust.a
TX_OBJS := $(addprefix $(B)/lib_tx_,block_allocate.o block_release.o block_pool_create.o block_pool_delete.o)
OBJS := $(addprefix $(B)/,contract.o adapter_ref.o adapter_ref_primask.o broken_isr_alloc.o broken_isr_free.o \
        adapter_etl.o adapter_riot.o lib_memarray.o adapter_threadx.o tx_kernel_stubs.o adapter_cmsis_rtx.o \
        rtx_mempool_pool.o adapter_contiki.o lib_memb.o adapter_c_allocator.o lib_fb_allocator.o lib_LockGuard.o \
        adapter_lwip.o sys_arch.o lib_memp.o adapter_memorypool.o adapter_rust.o) $(TX_OBJS)

check: $(B)/contract $(B)/contract_rtx_excl $(B)/contract_rtx_excl_broken $(B)/contract_cal_lock $(B)/contract_cal_lock_broken
	./$(B)/contract; a=$$?; ./$(B)/contract_rtx_excl; b=$$?; ./$(B)/contract_rtx_excl_broken; c=$$?; \
	./$(B)/contract_cal_lock; d=$$?; ./$(B)/contract_cal_lock_broken; e=$$?; \
	echo "exit codes $$a $$b $$c $$d $$e"; [ $$a -eq 0 ] && [ $$b -eq 0 ] && [ $$c -eq 0 ] && [ $$d -eq 0 ] && [ $$e -eq 0 ]
.PHONY: check

# the no-board tests of the board side (after bash onebuild.sh): the result block's layout and verdicts, and
# the runner and the record writer against a stand-in for probe-rs
test-board-side:
	python3 -I test_decode.py && python3 -I test_runner.py stm32g474 && python3 -I test_runner.py stm32g0b1
.PHONY: test-board-side


$(B):
	mkdir -p $@
$(RUST_LIB): $(K)/rust/Cargo.toml $(K)/rust/src/lib.rs | $(B)
	cd $(K)/rust && RUSTFLAGS="--cap-lints warn" cargo build -q --offline --release --target-dir $(CURDIR)/$(B)/rust

$(B)/contract.o: contract.c verdict.h excl_host.h $(K)/pool.h | $(B)
	$(CC) -DPOOL_WITH_RUST -c $< -o $@
$(B)/contract_rtx.o: contract.c verdict.h excl_host.h $(K)/pool.h | $(B)
	$(CC) -DRTX_EXCL=1 -c $< -o $@
$(B)/contract_rtx_broken.o: contract.c verdict.h excl_host.h $(K)/pool.h | $(B)
	$(CC) -DRTX_EXCL=1 -DRTX_EXCL_BROKEN=1 -c $< -o $@
$(B)/contract_cal.o: contract.c verdict.h excl_host.h $(K)/pool.h | $(B)
	$(CC) -DCAL_LOCK=1 -c $< -o $@
$(B)/contract_cal_broken.o: contract.c verdict.h excl_host.h $(K)/pool.h | $(B)
	$(CC) -DCAL_LOCK=1 -DCAL_LOCK_BROKEN=1 -c $< -o $@
$(B)/adapter_ref.o: $(K)/adapter_ref.c $(K)/pool.h | $(B)
	$(CC) -c $< -o $@
$(B)/adapter_ref_primask.o: $(K)/adapter_ref.c $(K)/pool.h | $(B)
	$(CC) -DPOOL_PRIMASK=1 -c $< -o $@
$(B)/broken_isr_alloc.o: broken_isr.c $(K)/pool.h | $(B)
	$(CC) -DBROKEN_ISR=1 -c $< -o $@
$(B)/broken_isr_free.o: broken_isr.c $(K)/pool.h | $(B)
	$(CC) -DBROKEN_ISR=2 -c $< -o $@
$(B)/adapter_etl.o: $(K)/adapter_etl.cpp | $(B)
	$(CXX) -I$(ETL) -c $< -o $@
$(B)/adapter_riot.o: $(K)/adapter_riot.c | $(B)
	$(CC) $(INC_RIOT) -c $< -o $@
$(B)/lib_memarray.o: | $(B)
	$(LIBCC) $(INC_RIOT) -c $(RIOT)/sys/memarray/memarray.c -o $@
$(B)/adapter_threadx.o: $(K)/adapter_threadx.c | $(B)
	$(CC) $(INC_TX) -c $< -o $@
$(B)/tx_kernel_stubs.o: $(K)/tx_kernel_stubs.c | $(B)
	$(CC) $(INC_TX) -c $< -o $@
$(B)/lib_tx_%.o: | $(B)
	$(LIBCC) $(INC_TX) -c $(TX)/common/src/tx_$*.c -o $@
$(B)/adapter_cmsis_rtx.o: $(K)/adapter_cmsis_rtx.c ARMCM_isr.h | $(B)
	$(CC) $(HOST_RTX) -c $< -o $@
$(B)/rtx_mempool_pool.c: $(RTX)/Source/rtx_mempool.c $(K)/extract.py | $(B)
	python3 -I $(K)/extract.py $< $@
$(B)/rtx_mempool_pool.o: $(B)/rtx_mempool_pool.c ARMCM_isr.h | $(B)
	$(LIBCC) $(HOST_RTX) -c $< -o $@
# the LDREX/STREX variant: RTX's functions, cut out unchanged, after the prelude (rtx_excl_prelude.h)
$(B)/rtx_mempool_excl.c: $(B)/rtx_mempool_pool.c rtx_excl_prelude.h
	sed '0,/#include "rtx_lib.h"/s//#include "rtx_lib.h"\n#include "rtx_excl_prelude.h"/' $< > $@
	grep -c 'rtx_excl_prelude.h' $@ | grep -qx 1
$(B)/rtx_mempool_excl.o: $(B)/rtx_mempool_excl.c rtx_excl_prelude.h excl_host.h
	$(LIBCC) $(HOST_RTX) -c $< -o $@
$(B)/rtx_mempool_excl_broken.o: $(B)/rtx_mempool_excl.c rtx_excl_prelude.h excl_host.h
	$(LIBCC) $(HOST_RTX) -DRTX_EXCL_BROKEN=1 -c $< -o $@
$(B)/adapter_contiki.o: $(K)/adapter_contiki.c | $(B)
	$(CC) $(INC_CTK) -c $< -o $@
$(B)/lib_memb.o: | $(B)
	$(LIBCC) $(INC_CTK) -c $(CTK)/lib/memb.c -o $@
$(B)/adapter_c_allocator.o: $(K)/adapter_c_allocator.c | $(B)
	$(CC) $(INC_CAL) -c $< -o $@
$(B)/lib_fb_allocator.o: | $(B)
	$(LIBCC) $(INC_CAL) -c $(CAL)/fb_allocator.c -o $@
$(B)/lib_LockGuard.o: | $(B)
	g++ -std=c++17 -O2 -g -w -I$(K) $(INC_CAL) -c $(CAL)/LockGuard.cpp -o $@
$(B)/lib_LockGuard_cal.o: $(K)/shims/host/cal_lock/cmsis_compiler.h | $(B)
	g++ -std=c++17 -O2 -g -w -I$(K) $(INC_CAL_LOCK) -c $(CAL)/LockGuard.cpp -o $@
$(B)/lib_LockGuard_cal_broken.o: $(K)/shims/host/cal_lock/cmsis_compiler.h | $(B)
	g++ -std=c++17 -O2 -g -w -I$(K) $(INC_CAL_LOCK) -DCAL_LOCK_BROKEN=1 -c $(CAL)/LockGuard.cpp -o $@
$(B)/adapter_lwip.o: $(K)/adapter_lwip.c | $(B)
	$(CC) $(INC_LWIP) -c $< -o $@
$(B)/sys_arch.o: $(K)/shims/lwip/sys_arch.c | $(B)
	$(CC) $(INC_LWIP) -c $< -o $@
$(B)/lib_memp.o: | $(B)
	$(LIBCC) $(INC_LWIP) -c $(LWIP)/core/memp.c -o $@
# MemoryPool as on the boards: no std::mutex (no_gthreads.h)
$(B)/adapter_memorypool.o: $(K)/adapter_memorypool.cpp no_gthreads.h | $(B)
	$(CXX) -include no_gthreads.h -I$(MPOOL) -c $< -o $@
$(B)/adapter_rust.o: $(K)/adapter_rust.c | $(B)
	$(CC) -c $< -o $@

$(B)/contract: $(OBJS) $(RUST_LIB)
	g++ -o $@ $^ -lpthread -ldl
$(B)/contract_rtx_excl: $(B)/contract_rtx.o $(B)/adapter_cmsis_rtx.o $(B)/rtx_mempool_excl.o
	gcc -o $@ $^
$(B)/contract_rtx_excl_broken: $(B)/contract_rtx_broken.o $(B)/adapter_cmsis_rtx.o $(B)/rtx_mempool_excl_broken.o
	gcc -o $@ $^
$(B)/contract_cal_lock: $(B)/contract_cal.o $(B)/adapter_c_allocator.o $(B)/lib_fb_allocator.o $(B)/lib_LockGuard_cal.o
	g++ -o $@ $^
$(B)/contract_cal_lock_broken: $(B)/contract_cal_broken.o $(B)/adapter_c_allocator.o $(B)/lib_fb_allocator.o $(B)/lib_LockGuard_cal_broken.o
	g++ -o $@ $^

clean:
	rm -rf $(B)
.PHONY: clean
