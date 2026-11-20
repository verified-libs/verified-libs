# LIBC=: whose memcpy, memmove, memset and memcmp the firmware links (the
# only C library functions the bench firmware uses, build/flash/fw.map).
# The objects that define them are taken from that library's archive for
# the board's core (common/libc-objs.sh) and linked ahead of newlib-nano,
# which still provides the rest; harness and libraries are unchanged.
#   newlib-nano  (default) Debian arm-none-eabi newlib-nano: nothing changes
#   newlib       Debian arm-none-eabi full newlib
#   picolibc     Zephyr SDK 1.0.1 picolibc (its default libc; speed build)
#   picolibc-atfe, llvmlibc   Arm Toolchain for Embedded 23.1: picolibc and
#                LLVM libc as ATfE ships them (size builds; Cortex-M0+ and
#                M33 only: ATfE has no soft-float M4/M7 variant)
# The last three need toolchain image 2026-11-16. Included after ARCH; the
# build directory is cleaned before every build (run.sh), so the archive
# below is always new.
LIBC ?= newlib-nano
LIBC_A =
ifneq ($(LIBC),newlib-nano)
ATFE_RT = /opt/atfe/lib/clang-runtimes
ATFE_V  = $(if $(findstring cortex-m0plus,$(ARCH)),armv6m_soft_nofp_size,$(if $(findstring cortex-m33,$(ARCH)),armv8m.main_soft_nofp_unaligned_size,))
ifeq ($(LIBC),newlib)
LIBC_SRC = $(shell arm-none-eabi-gcc $(ARCH) -print-file-name=libc.a)
LIBC_TOOLS = arm-none-eabi-nm arm-none-eabi-ar
else ifeq ($(LIBC),picolibc)
LIBC_SRC = $(shell /opt/zephyr-sdk/arm-zephyr-eabi/bin/arm-zephyr-eabi-gcc $(ARCH) -print-file-name=libc.a)
LIBC_TOOLS = arm-none-eabi-nm arm-none-eabi-ar
else ifeq ($(LIBC),picolibc-atfe)
LIBC_SRC = $(if $(ATFE_V),$(ATFE_RT)/arm-none-eabi/$(ATFE_V)/lib/libc.a,$(error LIBC=picolibc-atfe: no ATfE variant for this core))
LIBC_TOOLS = /opt/atfe/bin/llvm-nm /opt/atfe/bin/llvm-ar
else ifeq ($(LIBC),llvmlibc)
LIBC_SRC = $(if $(ATFE_V),$(ATFE_RT)/llvmlibc/arm-none-eabi/$(ATFE_V)/lib/libc.a,$(error LIBC=llvmlibc: no ATfE variant for this core))
LIBC_TOOLS = /opt/atfe/bin/llvm-nm /opt/atfe/bin/llvm-ar
else
$(error LIBC must be newlib-nano, newlib, picolibc, picolibc-atfe or llvmlibc)
endif
LIBC_A = build/libc-$(LIBC).a
$(LIBC_A): | build
	test -f "$(LIBC_SRC)" || { echo "LIBC=$(LIBC): $(LIBC_SRC) not found (toolchain image 2026-11-16?)" >&2; exit 1; }
	arm-none-eabi-ar rcs $@ $$(sh $(COMMON)/../libc-objs.sh "$(LIBC_SRC)" build/libc-objs $(LIBC_TOOLS))
endif
