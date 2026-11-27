#!/bin/bash
# Check 1 of the pool pre-checks, the host part, inside the toolchain image:
# CMSIS-RTX's three pool functions, cut out of rtx_mempool.c byte for byte
# (extract.py: the rest of the file calls the kernel through SVC macros bound
# to Arm registers and does not compile for x86-64), built for x86-64 as the
# Armv6-M variant (interrupts off; shims/host/ARMCM_host.h says what that
# header gives), with the pilot's host test (../pools/test_pool.c) beside the
# reference and the two broken pools.
#   bash host.sh      (in the image, the repository at /work, LIBS at /libs)
set -uo pipefail
cd "$(dirname "$0")"
LIBS=${LIBS:-/libs}
d=build/host; mkdir -p "$d"
INC="-I. -I../pools -Ishims -Ishims/host -I$LIBS/cmsis-rtx/Include -I$LIBS/cmsis-rtx/Source -I$LIBS/cmsis-rtx/Config \
 -I$LIBS/cmsis6/CMSIS/RTOS2/Include"
CF="-O2 -g -Wall -ffunction-sections -fdata-sections -D__ARM_ARCH_6M__=1 -DOS_EVR_MEMORY=0 -DCMSIS_device_header=\"ARMCM_host.h\" -DPOOL_TEST_CMSIS_RTX $INC"
set -e
# shellcheck disable=SC2086
python3 -I extract.py "$LIBS/cmsis-rtx/Source/rtx_mempool.c" $d/rtx_mempool_pool.c
# shellcheck disable=SC2086
gcc $CF -c $d/rtx_mempool_pool.c -o $d/rtx_mempool_pool.o
# shellcheck disable=SC2086
gcc $CF -c adapter_cmsis_rtx.c -o $d/adapter_cmsis_rtx.o
# shellcheck disable=SC2086
gcc $CF -c ../pools/test_pool.c -o $d/test_pool.o
gcc -O2 -g -Wall -I../pools -c ../pools/adapter_ref.c -o $d/adapter_ref.o
gcc -O2 -g -Wall -I../pools -DPOOL_BROKEN=1 -c ../pools/adapter_ref.c -o $d/broken_double.o
gcc -O2 -g -Wall -I../pools -DPOOL_BROKEN=2 -c ../pools/adapter_ref.c -o $d/broken_lost.o
gcc -Wl,--gc-sections -o $d/test_pool $d/*.o
set +e
./$d/test_pool
