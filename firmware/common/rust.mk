# Rust ring buffers (../rust-adapters) as one static library for the board's
# core, built with the toolchain image's rustc/cargo (image 2026-11-13 or
# later: it has the soft-float Cortex-M targets) and linked like the C
# objects. Included by the firmware Makefiles; they add $(RUST_OBJS) to their
# objects only in the sets that list a Rust adapter.
#   target:     the soft-float target of the board's core (the C code is
#               -mfloat-abi=soft everywhere), -C target-cpu as the C -mcpu
#   opt-level:  from the C build's OPT (-O2 -> 2, -Os -> s, ...)
#   functions:  aligned to 32 bytes, as BENCH_ALIGN does for the C adapters
#   VL_RB_SLOTS: the C build's RB_SLOTS (bench.h; -DRB_SLOTS=... in EXTRA)
RUST_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../rust-adapters)
ifneq ($(filter $(BOARD),samd20 stm32g0b1),)
RUST_TARGET = thumbv6m-none-eabi
RUST_CPU    = cortex-m0plus
else ifeq ($(BOARD),stm32g474)
RUST_TARGET = thumbv7em-none-eabi
RUST_CPU    = cortex-m4
else ifeq ($(BOARD),stm32h723)
RUST_TARGET = thumbv7em-none-eabi
RUST_CPU    = cortex-m7
else
RUST_TARGET = thumbv8m.main-none-eabi
RUST_CPU    = cortex-m33
endif
# RP2350: two cores, the critical section also locks between them (src/cs.rs)
RUST_CFG     = $(if $(filter rp2350,$(BOARD)), --cfg vl_two_cores)
RUST_OPT     = $(or $(patsubst -O%,%,$(lastword $(filter -O%,$(OPT)))),2)
RUST_SLOTS   = $(or $(patsubst -DRB_SLOTS=%,%,$(lastword $(filter -DRB_SLOTS=%,$(EXTRA) $(CFLAGS)))),128)
RUST_LIB     = build/rust/$(RUST_TARGET)/release/libvl_rust_adapters.a
RUST_OBJS    = build/rust_adapters.o
# Link tail: the C library before the Rust archive, so that memcpy & co. come
# from the C library (newlib-nano) for the C and the Rust code alike;
# compiler_builtins' weak copies in the archive are then not used.
# -u: pull the C library's definitions in before the archive is scanned, also
# where only Rust code calls them.
RUST_MEMSYMS = memcpy memmove memset memcmp __aeabi_memcpy __aeabi_memcpy4 __aeabi_memcpy8 \
               __aeabi_memmove __aeabi_memmove4 __aeabi_memmove8 __aeabi_memset __aeabi_memset4 \
               __aeabi_memset8 __aeabi_memclr __aeabi_memclr4 __aeabi_memclr8
# (-Wl,-lc_nano: gcc's nano.specs would move a plain -lc to the end; the
# firmware links newlib-nano, --specs=nano.specs)
RUST_LINK    = $(addprefix -Wl$(comma)-u$(comma),$(RUST_MEMSYMS)) -Wl,-lc_nano $(RUST_LIB)
comma := ,
# MEMCPY=rust (an experiment, records -memcpyrust): the archive alone, so the
# memory functions are compiler_builtins', as a pure Rust firmware has them,
# for the C code of that firmware too.
RUST_LINK_OWN = $(RUST_LIB)

# cargo decides itself whether anything changed
$(RUST_LIB): FORCE | build
	cd $(RUST_DIR) && VL_RB_SLOTS=$(RUST_SLOTS) CARGO_PROFILE_RELEASE_OPT_LEVEL=$(RUST_OPT) \
	    RUSTFLAGS="-C target-cpu=$(RUST_CPU) $(if $(filter 1,$(SIZE)),,-C llvm-args=-align-all-functions=5)$(RUST_CFG)" \
	    cargo build -q --offline --locked --release --target $(RUST_TARGET) --target-dir $(CURDIR)/build/rust
build/rust_adapters.o: $(RUST_DIR)/adapters_rust.c $(BENCH)/bench.h | build
	arm-none-eabi-gcc $(CFLAGS) -I$(BENCH) -c $< -o $@
FORCE:
.PHONY: FORCE
