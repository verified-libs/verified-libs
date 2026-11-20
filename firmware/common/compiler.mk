# Compiler for the libraries under test and their adapters (CC_LIB, CXX_LIB).
# COMPILER=gcc (default): arm-none-eabi-gcc/g++ from the toolchain image.
# COMPILER=clang: the image's clang/clang++ for target arm-none-eabi, against
#   the same newlib and libstdc++ headers that arm-none-eabi-gcc uses (the
#   multilib for $(ARCH)). newlib's C headers come after clang's own builtin
#   headers (-idirafter), so stdint.h, stddef.h and stdatomic.h are clang's. The harness (main.c, startup, the negative control, the
#   heap shims) stays gcc, and the link stays arm-none-eabi-g++ with the same
#   newlib-nano, so the library code is the only thing that changes.
# COMPILER=st-gcc: ST's GNU Tools for STM32 (STM32CubeCLT) for the libraries,
#   with its own headers; COMPILER=st-clang: ST's Arm Clang (starm-clang) with
#   the same flags and GNU headers as COMPILER=clang. Both need the local image
#   verified-libs/toolchain-st (../../toolchain/st) and, by ST's licence, an
#   STM32 board; the run scripts pick the image and refuse other boards.
#   COMPILER=st-clang-omax: st-clang with ST's Omax preset (--config=Omax.cfg:
#   -O3 plus LLVM inlining/unrolling options, as STM32CubeIDE's "Omax"); the
#   run scripts require OPT=-O3 so that the preset's -O3 stays in force.
# COMPILER=atfe: Arm Toolchain for Embedded's clang (ATfE 23.1.0, image
#   2026-11-16, /opt/atfe) in place of the image's clang, otherwise exactly as
#   COMPILER=clang (GNU headers, gcc link): only the compiler changes.
# COMPILER=zephyr-gcc: the Zephyr SDK's arm-zephyr-eabi-gcc/g++ (SDK 1.0.1,
#   GCC 14.3.0, image 2026-11-16, /opt/zephyr-sdk) with its own headers, as a
#   Zephyr application builds; the link stays arm-none-eabi-g++ (same GCC
#   major version, same AAPCS; -fshort-enums as arm-none-eabi).
# Included by the bench, stress and mp-stress Makefiles after ARCH and LTO
# are set.
COMPILER ?= gcc
LD_LIB_EXTRA =
LIB_RT_OBJS =
ifeq ($(COMPILER),gcc)
CC_LIB   = arm-none-eabi-gcc
CXX_LIB  = arm-none-eabi-g++
else ifeq ($(COMPILER),zephyr-gcc)
CC_LIB   = /opt/zephyr-sdk/arm-zephyr-eabi/bin/arm-zephyr-eabi-gcc -fshort-enums
CXX_LIB  = /opt/zephyr-sdk/arm-zephyr-eabi/bin/arm-zephyr-eabi-g++ -fshort-enums
ifeq ($(LTO),1)
$(error LTO=1 mixes GCC versions (Zephyr SDK 14.3 objects, Debian 14.2 link); use COMPILER=zephyr-gcc with LTO=0)
endif
else ifeq ($(COMPILER),st-gcc)
CC_LIB   = /opt/st/gnu-tools-for-stm32/bin/arm-none-eabi-gcc
CXX_LIB  = /opt/st/gnu-tools-for-stm32/bin/arm-none-eabi-g++
ifeq ($(LTO),1)
$(error LTO=1 mixes GCC versions (ST 14.3 objects, Debian 14.2 link); use COMPILER=st-gcc with LTO=0)
endif
else ifneq ($(filter clang atfe st-clang st-clang-omax,$(COMPILER)),)
ifeq ($(LTO),1)
$(error LTO=1 is gcc LTO; clang objects cannot take part in it. Use COMPILER=clang with LTO=0)
endif
ARM_SYS   = /usr/lib/arm-none-eabi
ARM_MULTI := $(shell arm-none-eabi-gcc $(ARCH) -print-multi-directory)
GCC_VER   := $(shell arm-none-eabi-gcc -dumpversion)
# -fshort-enums: arm-none-eabi-gcc uses variable-size enums (AAPCS "short
# enums" variant); clang defaults to 32-bit enums for arm-none-eabi.
CLANG_T   = --target=arm-none-eabi -nostdlibinc -fshort-enums
CLANG_BIN = $(if $(filter st-clang%,$(COMPILER)),/opt/st/st-arm-clang/bin/starm-clang,$(if $(filter atfe,$(COMPILER)),/opt/atfe/bin/clang,clang))
# starm-clang looks for its own multilib (newlib, libc++) and warns when the
# flags match none; it is not used here (GNU headers, gcc link).
ifneq ($(filter st-clang% atfe,$(COMPILER)),)
CLANG_T  += -Wno-missing-multilib
endif
ifeq ($(COMPILER),st-clang-omax)
CLANG_T  += --config=Omax.cfg
endif
CC_LIB    = $(CLANG_BIN) $(CLANG_T) -idirafter $(ARM_SYS)/include
CXX_LIB   = $(CLANG_BIN)++ $(CLANG_T) -isystem $(ARM_SYS)/include/c++/$(GCC_VER) \
            -isystem $(ARM_SYS)/include/c++/$(GCC_VER)/arm-none-eabi/$(ARM_MULTI) \
            -isystem $(ARM_SYS)/include/c++/$(GCC_VER)/backward -idirafter $(ARM_SYS)/include
# polycratia needs exceptions (try/catch). Its clang object refers to the ARM
# EH personality routine, which pulls in libgcc's unwinder, and that wants the
# .ARM.exidx bounds from the linker script. Nothing throws in these tests, so
# clang builds get an empty table here; the linker scripts (shared with the
# gcc builds) stay unchanged.
LD_LIB_EXTRA = -Wl,--defsym=__exidx_start=0 -Wl,--defsym=__exidx_end=0
# On ARMv6-M clang turns atomic loads and stores into library calls that the
# toolchain does not ship; armv6m_atomic.c (built with gcc) provides them with
# the code gcc inlines. Each Makefile adds $(LIB_RT_OBJS) to its objects.
ifneq ($(findstring cortex-m0plus,$(ARCH)),)
LIB_RT_OBJS = build/armv6m_atomic.o
_vl_goal := $(.DEFAULT_GOAL)
build/armv6m_atomic.o: $(dir $(lastword $(MAKEFILE_LIST)))armv6m_atomic.c | build
	arm-none-eabi-gcc $(ARCH) $(OPT) -Wall -Wextra -ffunction-sections -c $< -o $@
.DEFAULT_GOAL := $(_vl_goal)
endif
else
$(error COMPILER must be gcc, clang, atfe, zephyr-gcc, st-gcc, st-clang or st-clang-omax)
endif
