#!/bin/bash
# Check 1 of the pool pre-checks, inside the toolchain image: compile
# CMSIS-RTX's rtx_mempool.c as it is, with the adapter, for a Cortex-M4
# (Armv7E-M: the LDREX/STREX path), a Cortex-M33 (Armv8-M main) and a
# Cortex-M0+ (Armv6-M: interrupts off), and link each with --gc-sections.
# Prints per core: the symbols the link could not find (what the rest of
# the kernel would have to give), the pool functions that were kept, and
# the instructions of the lock-free path in the image.
#   bash cross.sh      (in the image, the repository at /work, LIBS at /libs)
set -uo pipefail
cd "$(dirname "$0")"
LIBS=${LIBS:-/libs}
OUT=build
mkdir -p "$OUT"
INC="-I. -I../pools -Ishims -I$LIBS/cmsis-rtx/Include -I$LIBS/cmsis-rtx/Source -I$LIBS/cmsis-rtx/Config \
 -I$LIBS/cmsis6/CMSIS/Core/Include -I$LIBS/cmsis6/CMSIS/RTOS2/Include"
rc=0
for core in cortex-m4:ARMCM4:ARMCM4_FP cortex-m33:ARMCM33:ARMCM33_DSP_FP cortex-m0plus:ARMCM0plus:ARMCM0P; do
    IFS=: read -r cpu dev macro <<<"$core"
    d=$OUT/$cpu; mkdir -p "$d"
    # OS_EVR_MEMORY=0: RTX_Config.h's own switch for the pool's Event Recorder calls ("RTOS Event
    # Generation, Memory Management"); with it at 1 they are calls of rtx_evr.c, whose functions are
    # empty when the project has no Event Recorder.
    CF="-mcpu=$cpu -mthumb -Os -ffunction-sections -fdata-sections -Wall -DOS_EVR_MEMORY=0 -D$macro -DCMSIS_device_header=\"$dev.h\" \
 $INC -I$LIBS/cortex-dfp/Device/$dev/Include"
    ok=1
    for f in "$LIBS/cmsis-rtx/Source/rtx_mempool.c" adapter_cmsis_rtx.c cross_main.c; do
        # shellcheck disable=SC2086
        arm-none-eabi-gcc $CF -c "$f" -o "$d/$(basename "${f%.c}").o" 2>"$d/$(basename "${f%.c}").err" ||
            { echo "$cpu: $(basename "$f") does not compile:"; sed 's/^/  /' "$d/$(basename "${f%.c}").err" | head -n 20; ok=0; }
    done
    [ $ok = 1 ] || { rc=1; continue; }
    # shellcheck disable=SC2086
    arm-none-eabi-gcc -mcpu=$cpu -mthumb --specs=nosys.specs -Wl,--gc-sections -Wl,-Map,"$d/pool.map" \
        "$d"/*.o -o "$d/pool.elf" 2>"$d/link.err"
    lrc=$?
    und=$(grep -o "undefined reference to \`[^']*'" "$d/link.err" | sort -u | sed "s/undefined reference to //")
    echo "$cpu ($dev): link $([ $lrc = 0 ] && echo ok || echo FAILED)"
    echo "  undefined: ${und:-none}"
    [ $lrc = 0 ] || { rc=1; continue; }
    echo "  pool functions kept: $(arm-none-eabi-nm "$d/pool.elf" | grep -o 'osRtx[A-Za-z]*' | sort -u | tr '\n' ' ')"
    echo "  exclusive-access instructions: $(arm-none-eabi-objdump -d "$d/pool.elf" | grep -oE '\s(ldrex|strex|clrex|cpsid|cpsie|dmb)\b' | sort | uniq -c | tr -s ' \n' ' ')"
done
exit $rc
