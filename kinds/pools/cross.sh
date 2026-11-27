#!/bin/bash
# Every adapter of the pools kind compiled for the four cores of the six
# boards at -Os and -O2, with the compiler flags of the version 2 benchmark
# (as kinds/crc/cross.sh: firmware/nrf5340-rb-bench/Makefile's COMMONF, the
# soft-float ABI of every board's board.mk), each linked into an ELF of its
# own that creates its pool and calls alloc and free once (cross_main.c).
# Runs inside the toolchain image (make cross). Output: build/x/<core>/<opt>/
# <config>.elf and .map, and build/x/sizes.tsv (sizes.py). Never run on a board.
set -euo pipefail
cd "$(dirname "$0")"
LIBS=${LIBS:-/libs}
C_CONFIGS="ref ref_primask etl riot threadx cmsis_rtx contiki c_allocator lwip memorypool"
INC_LIB="-Ishims/riot -I$LIBS/riot/sys/include -I$LIBS/threadx/common/inc -Ishims/contiki -I$LIBS/contiki-ng/os
     -I$LIBS/c-allocator/src -DALLOC_LOCK_NONE -Ishims/lwip -I$LIBS/lwip/src/include
     -Ishims -I$LIBS/cmsis-rtx/Include -I$LIBS/cmsis-rtx/Source -I$LIBS/cmsis-rtx/Config
     -I$LIBS/cmsis6/CMSIS/Core/Include -I$LIBS/cmsis6/CMSIS/RTOS2/Include -DOS_EVR_MEMORY=0"
OWN_C="adapter_riot.c adapter_threadx.c tx_kernel_stubs.c adapter_cmsis_rtx.c adapter_contiki.c adapter_c_allocator.c
       adapter_lwip.c shims/lwip/sys_arch.c adapter_rust.c"
OWN_CXX="adapter_etl.cpp adapter_memorypool.cpp"
LIB_C="$LIBS/riot/sys/memarray/memarray.c $LIBS/contiki-ng/os/lib/memb.c $LIBS/c-allocator/src/fb_allocator.c
       $LIBS/lwip/src/core/memp.c $LIBS/cmsis-rtx/Source/rtx_mempool.c
       $LIBS/threadx/common/src/tx_block_allocate.c $LIBS/threadx/common/src/tx_block_release.c
       $LIBS/threadx/common/src/tx_block_pool_create.c $LIBS/threadx/common/src/tx_block_pool_delete.c"
LIB_CXX="$LIBS/c-allocator/src/LockGuard.cpp"

for core in m0plus m4 m7 m33; do
    case $core in
        m0plus) cpu=cortex-m0plus; rt=thumbv6m-none-eabi;      txp=cortex_m0;  dev=ARMCM0plus:ARMCM0P; feat=--no-default-features ;;
        m4)     cpu=cortex-m4;     rt=thumbv7em-none-eabi;     txp=cortex_m4;  dev=ARMCM4:ARMCM4;      feat= ;;
        m7)     cpu=cortex-m7;     rt=thumbv7em-none-eabi;     txp=cortex_m7;  dev=ARMCM7:ARMCM7;      feat= ;;
        m33)    cpu=cortex-m33;    rt=thumbv8m.main-none-eabi; txp=cortex_m33; dev=ARMCM33:ARMCM33;    feat= ;;
    esac
    IFS=: read -r devdir devmacro <<<"$dev"
    ARCH="-mcpu=$cpu -mthumb -mfloat-abi=soft"
    for opt in -Os -O2; do
        d=build/x/$core/${opt#-}
        mkdir -p "$d/o"
        COMMONF="$ARCH $opt -g -Wall -Wextra -Wno-unused-function -DNDEBUG -ffreestanding -ffunction-sections -fdata-sections
                 -I. $INC_LIB -I$LIBS/threadx/ports/$txp/gnu/inc -I$LIBS/cortex-dfp/Device/$devdir/Include
                 -D$devmacro -DCMSIS_device_header=\"$devdir.h\""
        objs=""
        for f in adapter_ref.c $OWN_C $LIB_C; do
            o=$d/o/$(echo "$f" | tr '/' '_' | sed 's/^_*//').o
            arm-none-eabi-gcc $COMMONF -std=c11 -w -c "$f" -o "$o"
            objs="$objs $o"
        done
        arm-none-eabi-gcc $COMMONF -std=c11 -w -DPOOL_PRIMASK=1 -c adapter_ref.c -o "$d/o/adapter_ref_primask.o"
        objs="$objs $d/o/adapter_ref_primask.o"
        for f in $OWN_CXX $LIB_CXX; do
            o=$d/o/$(echo "$f" | tr '/' '_' | sed 's/^_*//').o
            # without -ffreestanding, as the bench builds its C++ adapters
            arm-none-eabi-g++ ${COMMONF/-ffreestanding/} -std=c++20 -fno-exceptions -fno-rtti -fno-threadsafe-statics -w \
                -I$LIBS/etl/include -I$LIBS/memorypool-head/src -c "$f" -o "$o"
            objs="$objs $o"
        done
        # The Rust pools: the crate for the core's soft-float target, opt-level from the C build's
        # (-Os -> s, -O2 -> 2), as common/rust.mk; heapless's pool not on the Cortex-M0+.
        ( cd rust && CARGO_PROFILE_RELEASE_OPT_LEVEL=${opt#-O} RUSTFLAGS="-C target-cpu=$cpu --cap-lints warn" \
            cargo build -q --offline --locked --release $feat --target $rt --target-dir "$OLDPWD/$d/rust" )
        rlib=$d/rust/$rt/release/libvl_pools_rust.a
        LD="arm-none-eabi-g++ $ARCH $opt --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections"
        arm-none-eabi-gcc $COMMONF -std=c11 -c cross_main.c -o "$d/o/main_none.o"
        $LD -Wl,-Map="$d/none.map" -o "$d/none.elf" "$d/o/main_none.o"
        o=$d/o; L=$(echo "$LIBS" | tr '/' '_' | sed 's/^_*//')
        rust_configs="atomic_pool"
        [ $core = m0plus ] || rust_configs="heapless $rust_configs"
        for c in $C_CONFIGS $rust_configs; do
            # each configuration links only its own objects (a C++ object with a static constructor,
            # or the Rust library with its own memcpy, would otherwise stay in every image)
            case $c in
                ref)         own="$o/adapter_ref.c.o" ;;
                ref_primask) own="$o/adapter_ref_primask.o" ;;
                etl)         own="$o/adapter_etl.cpp.o" ;;
                riot)        own="$o/adapter_riot.c.o $o/${L}_riot_sys_memarray_memarray.c.o" ;;
                threadx)     own="$o/adapter_threadx.c.o $o/tx_kernel_stubs.c.o $(ls $o/${L}_threadx_common_src_tx_block_*.o)" ;;
                cmsis_rtx)   own="$o/adapter_cmsis_rtx.c.o $o/${L}_cmsis-rtx_Source_rtx_mempool.c.o" ;;
                contiki)     own="$o/adapter_contiki.c.o $o/${L}_contiki-ng_os_lib_memb.c.o" ;;
                c_allocator) own="$o/adapter_c_allocator.c.o $o/${L}_c-allocator_src_fb_allocator.c.o $o/${L}_c-allocator_src_LockGuard.cpp.o" ;;
                lwip)        own="$o/adapter_lwip.c.o $o/shims_lwip_sys_arch.c.o $o/${L}_lwip_src_core_memp.c.o" ;;
                memorypool)  own="$o/adapter_memorypool.cpp.o" ;;
                heapless|atomic_pool) own="$o/adapter_rust.c.o $rlib" ;;
            esac
            q=const; case " $rust_configs " in *" $c "*) q= ;; esac
            arm-none-eabi-gcc $COMMONF -std=c11 -DONE="adapter_$c" -DADAPTER_CONST=$q -c cross_main.c -o "$d/o/main_$c.o"
            $LD -Wl,-Map="$d/$c.map" -o "$d/$c.elf" "$d/o/main_$c.o" $own
        done
        echo "built $core $opt"
    done
done
python3 -I sizes.py build/x > build/x/sizes.tsv
echo "sizes: build/x/sizes.tsv"
