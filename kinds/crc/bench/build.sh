#!/bin/bash
# Step 5 of the plan: the CRC benchmark image for one board and one
# configuration, built against the unchanged board support of version 2
# (firmware/common/<board>: board.h, board.mk's flags, startup.c, the flash
# linker script). Runs inside the toolchain image with the repository at
# /work (make bench). Not flashed: no board is used.
#   BOARD (default stm32g474), CONFIG (default crcany_crc32_word), OPT (-O2)
set -euo pipefail
cd "$(dirname "$0")"
BOARD=${BOARD:-stm32g474}
CONFIG=${CONFIG:-crcany_crc32_word}
OPT=${OPT:--O2}
LIBS=${LIBS:-/libs}
COMMON=../../../firmware/common/$BOARD
ARCH=$(sed -n 's/^ARCH *= *//p' "$COMMON/board.mk")
LDS=$(sed -n 's/^LD_FLASH *= *\$(COMMON)\///p' "$COMMON/board.mk")
case $CONFIG in
    *crc32*|ref32|zlib_*) REF=adapter_ref32 ;;
    *crc16*|*ccitt_ffff|crcpp_*|ref16) REF=adapter_ref16 ;;
    *) REF=adapter_ref8 ;;
esac
GEN=../build/gen/src
OUT=../build/bench/$BOARD/$CONFIG
mkdir -p "$OUT"
INC="-I. -I$COMMON -I$COMMON/.. -I.. -I$GEN -I$LIBS/zlib -I$LIBS/libcrc/include -I../shims/zephyr -I$LIBS/zephyr/include"
# The flags of the version 2 benchmark (firmware/nrf5340-rb-bench/Makefile COMMONF)
CF="$ARCH $OPT -g -Wall -Wextra -Wno-missing-field-initializers -Wno-unused-function -DNDEBUG -ffreestanding -ffunction-sections -fdata-sections -DCRC_ONESHOT_ONLY -std=c11 $INC"
arm-none-eabi-gcc $CF -DBENCH_CRC=adapter_$CONFIG -DBENCH_REF=$REF -c main.c -o "$OUT/main.o"
arm-none-eabi-gcc $CF -fno-tree-loop-distribute-patterns -c "$COMMON/startup.c" -o "$OUT/startup.o"
arm-none-eabi-gcc $CF -c ../ref_crc.c -o "$OUT/ref_crc.o"
objs="$OUT/main.o $OUT/startup.o $OUT/ref_crc.o"
case $CONFIG in
    crcany_*) arm-none-eabi-gcc $CF -c ../adapter_crcany.c -o "$OUT/adapter.o"
              for f in crc32iso_hdlc crc16ibm_3740 crc8smbus; do arm-none-eabi-gcc $CF -w -c "$GEN/$f.c" -o "$OUT/$f.o"; objs="$objs $OUT/$f.o"; done ;;
    zephyr_*) arm-none-eabi-gcc $CF -c ../adapter_zephyr.c -o "$OUT/adapter.o"
              for f in crc32_sw crc16_sw crc8_sw; do arm-none-eabi-gcc $CF -w -c "$LIBS/zephyr/subsys/crc/$f.c" -o "$OUT/$f.o"; objs="$objs $OUT/$f.o"; done ;;
    zlib_*)   arm-none-eabi-gcc $CF -c ../adapter_zlib.c -o "$OUT/adapter.o"
              arm-none-eabi-gcc $CF -w -c "$LIBS/zlib/crc32.c" -o "$OUT/zcrc32.o"; objs="$objs $OUT/zcrc32.o" ;;
    libcrc_*) arm-none-eabi-gcc $CF -c ../adapter_libcrc.c -o "$OUT/adapter.o"
              for f in crc32 crcccitt; do arm-none-eabi-gcc $CF -w -c "$LIBS/libcrc/src/$f.c" -o "$OUT/l$f.o"; objs="$objs $OUT/l$f.o"; done ;;
    *) echo "build.sh builds the C configurations; $CONFIG is not one of them" >&2; exit 2 ;;
esac
objs="$objs $OUT/adapter.o"
arm-none-eabi-gcc $ARCH $OPT -nostartfiles --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections \
    -T "$COMMON/$LDS" -Wl,-Map="$OUT/fw.map" -o "$OUT/fw.elf" $objs
arm-none-eabi-size -A -d "$OUT/fw.elf" | grep -E '^\.(isr_vector|text|init_array|data|bss|results) '
arm-none-eabi-nm "$OUT/fw.elf" | grep -E ' results$'
echo "image: $OUT/fw.elf (board $BOARD, $CONFIG against $REF, $OPT)"
