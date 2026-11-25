#!/bin/bash
# Step 4 of the plan: every configuration (and the reference) compiled for the
# four cores of the six boards at -Os and -O2, with the compiler flags of the
# version 2 benchmark (firmware/nrf5340-rb-bench/Makefile, COMMONF; the
# soft-float ABI of every board's board.mk), each linked into an ELF of its
# own that calls only its one-shot call (cross_main.c, CRC_ONESHOT_ONLY).
# Runs inside the toolchain image (make cross). Output: build/x/<core>/<opt>/
# <config>.elf and .map, and build/x/sizes.tsv (sizes.py). Never run on a board.
set -euo pipefail
cd "$(dirname "$0")"
LIBS=${LIBS:-/libs}
GEN=build/gen/src
CONFIGS="ref32 ref16 ref8
etl_crc32_t256 crcany_crc32_byte libcrc_crc32 rust_crc32_table1 etl_crc32_t16 zephyr_crc32_ieee
crcany_crc32_word zlib_crc32 crcany_crc32_bit
etl_crc16_t256 crcany_crc16_byte libcrc_ccitt_ffff crcpp_ccittfalse_table etl_crc16_t16 zephyr_crc16_itu_t
etl_crc8_t256 crcany_crc8_byte acecrc_crc8_byte etl_crc8_t16 zephyr_crc8_ccitt"
INC="-I. -I$LIBS/etl/include -I$LIBS/zlib -I$LIBS/libcrc/include -Ishims/zephyr -I$LIBS/zephyr/include
     -Ishims/acecrc -I$LIBS/acecrc/src -I$LIBS/crcpp/inc -I$GEN"
OWN_C="ref_crc.c adapter_zlib.c adapter_libcrc.c adapter_zephyr.c adapter_crcany.c adapter_rust.c"
OWN_CXX="adapter_etl.cpp adapter_acecrc.cpp adapter_crcpp.cpp"
LIB_C="$LIBS/zlib/crc32.c $LIBS/libcrc/src/crc32.c $LIBS/libcrc/src/crcccitt.c
       $LIBS/zephyr/subsys/crc/crc32_sw.c $LIBS/zephyr/subsys/crc/crc16_sw.c $LIBS/zephyr/subsys/crc/crc8_sw.c
       $GEN/crc32iso_hdlc.c $GEN/crc16ibm_3740.c $GEN/crc8smbus.c"
LIB_CXX="$LIBS/acecrc/src/ace_crc/crc8_byte.cpp"

for core in m0plus m4 m7 m33; do
    case $core in
        m0plus) cpu=cortex-m0plus; rt=thumbv6m-none-eabi ;;
        m4)     cpu=cortex-m4;     rt=thumbv7em-none-eabi ;;
        m7)     cpu=cortex-m7;     rt=thumbv7em-none-eabi ;;
        m33)    cpu=cortex-m33;    rt=thumbv8m.main-none-eabi ;;
    esac
    ARCH="-mcpu=$cpu -mthumb -mfloat-abi=soft"
    for opt in -Os -O2; do
        d=build/x/$core/${opt#-}
        mkdir -p "$d/o"
        COMMONF="$ARCH $opt -g -Wall -Wextra -Wno-unused-function -DNDEBUG -DCRC_ONESHOT_ONLY -ffreestanding -ffunction-sections -fdata-sections $INC"
        objs=""
        for f in $OWN_C $LIB_C; do
            o=$d/o/$(echo "$f" | tr '/' '_' | sed 's/^_*//').o
            arm-none-eabi-gcc $COMMONF -std=c11 -w -c "$f" -o "$o"
            objs="$objs $o"
        done
        for f in $OWN_CXX $LIB_CXX; do
            o=$d/o/$(echo "$f" | tr '/' '_' | sed 's/^_*//').o
            # without -ffreestanding, as the bench builds its C++ adapters
            # (firmware/nrf5340-rb-bench/Makefile: filter-out -ffreestanding)
            arm-none-eabi-g++ ${COMMONF/-ffreestanding/} -std=c++20 -fno-exceptions -fno-rtti -fno-threadsafe-statics -w -c "$f" -o "$o"
            objs="$objs $o"
        done
        # The Rust configuration: the crate for the core's soft-float target,
        # opt-level from the C build's (-Os -> s, -O2 -> 2), as common/rust.mk.
        ( cd rust && CARGO_PROFILE_RELEASE_OPT_LEVEL=${opt#-O} RUSTFLAGS="-C target-cpu=$cpu" \
            cargo build -q --offline --locked --release --target $rt --target-dir "$OLDPWD/$d/rust" )
        rlib=$d/rust/$rt/release/libvl_crc_rust.a
        LD="arm-none-eabi-g++ $ARCH $opt --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections"
        arm-none-eabi-gcc $COMMONF -std=c11 -c cross_main.c -o "$d/o/main_none.o"
        $LD -Wl,-Map="$d/none.map" -o "$d/none.elf" "$d/o/main_none.o"
        for c in $CONFIGS; do
            arm-none-eabi-gcc $COMMONF -std=c11 -DONE="adapter_$c" -c cross_main.c -o "$d/o/main_$c.o"
            extra=""
            [ "$c" = rust_crc32_table1 ] && extra="$rlib"
            $LD -Wl,-Map="$d/$c.map" -o "$d/$c.elf" "$d/o/main_$c.o" $objs $extra
        done
        echo "built $core $opt"
    done
done
python3 -I sizes.py build/x > build/x/sizes.tsv
echo "sizes: build/x/sizes.tsv"
