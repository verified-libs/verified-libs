# The CRC kind (README.md). Runs inside the toolchain image (run.sh), with the
# libraries fetched by fetch.sh mounted at LIBS.
#   make refcheck   checks of the reference itself (ref_check.py)
#   make test       the host test (test_crc.c), built twice: plain (-O2) and
#                   with the address and undefined-behaviour sanitizers
#   make cross      every configuration for the four cores at -Os and -O2, and
#                   their sizes (cross.sh, sizes.py)
#   make bench      the benchmark image for one board (bench/build.sh; needs the
#                   repository at /work, as run.sh mounts it), not flashed
#   make proof      the CBMC proofs for CRC-32 (proof/run.sh)
#   make miri       the Rust adapter's own test under Miri (nightly, with the
#                   image's prebuilt Miri sysroot; toolchain/README.md)
LIBS ?= /libs
WARN := -Wall -Wextra

# Include directories: ours, the libraries', and the two shims.
INC := -I. -I$(LIBS)/etl/include -I$(LIBS)/zlib -I$(LIBS)/libcrc/include \
       -Ishims/zephyr -I$(LIBS)/zephyr/include -Ishims/acecrc -I$(LIBS)/acecrc/src -I$(LIBS)/crcpp/inc -Ibuild/gen/src

# The libraries' own source files, each with an object name of its own.
LIBSRC_zlib_crc32      := $(LIBS)/zlib/crc32.c
LIBSRC_libcrc_crc32    := $(LIBS)/libcrc/src/crc32.c
LIBSRC_libcrc_crcccitt := $(LIBS)/libcrc/src/crcccitt.c
LIBSRC_zephyr_crc32    := $(LIBS)/zephyr/subsys/crc/crc32_sw.c
LIBSRC_zephyr_crc16    := $(LIBS)/zephyr/subsys/crc/crc16_sw.c
LIBSRC_zephyr_crc8     := $(LIBS)/zephyr/subsys/crc/crc8_sw.c
LIBSRC_crcany_crc32    := build/gen/src/crc32iso_hdlc.c
LIBSRC_crcany_crc16    := build/gen/src/crc16ibm_3740.c
LIBSRC_crcany_crc8     := build/gen/src/crc8smbus.c
LIBSRC_acecrc_crc8     := $(LIBS)/acecrc/src/ace_crc/crc8_byte.cpp
LIBOBJ := zlib_crc32 libcrc_crc32 libcrc_crcccitt zephyr_crc32 zephyr_crc16 zephyr_crc8 crcany_crc32 crcany_crc16 crcany_crc8 acecrc_crc8

OWN_C   := ref_crc.c adapters_broken.c adapter_zlib.c adapter_libcrc.c adapter_zephyr.c adapter_crcany.c adapter_rust.c test_crc.c
OWN_CXX := adapter_etl.cpp adapter_acecrc.cpp adapter_crcpp.cpp
HDRS    := crc.h adapters.h ref_crc.h build/gen/ok

# crcany's generated code (generated.lock): crcadd built from the pinned
# sources, run on crcany.models, the output checked against the hashes.
CRCANY_SRC := $(addprefix $(LIBS)/crcany/,crcadd.c crcgen.c crc.c model.c)
build/gen/ok: crcany.models generated.lock
	mkdir -p build/gen
	gcc -O2 -std=c99 -w -o build/gen/crcadd $(CRCANY_SRC)
	cd build/gen && ./crcadd -l -4 < ../../crcany.models
	cd build/gen/src && grep -v '^#' ../../../generated.lock | sha256sum --quiet -c
	touch $@

# zlib's braided code takes 8-byte words on the host (x86-64) and 4-byte words
# on the boards: another loop and other tables. The host test links a second
# build of crc32.c with the boards' word size (the library's own Z_TESTW) under
# the library's own name prefix (Z_PREFIX), with its own adapter
# (adapter_zlib.c, ZLIB_W4). "make test" checks the size of its braid table:
# 4 tables of 256 entries of 4 bytes (the host's own build: 8 tables), as in
# the boards' images.
ZLIB_W4 := -DZ_TESTW=4 -DZ_PREFIX -DZLIB_W4

# Host builds: V = host (plain) | asan (sanitizers).
FLAGS_host := -O2 -g
FLAGS_asan := -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -fno-sanitize-recover=all
define host_variant
build/$(1)/%.o: %.c $(HDRS) | build/$(1)
	gcc $(FLAGS_$(1)) $(WARN) $(INC) -c $$< -o $$@
build/$(1)/%.o: %.cpp $(HDRS) | build/$(1)
	g++ -std=c++17 $(FLAGS_$(1)) $(WARN) $(INC) -c $$< -o $$@
build/$(1)/lib_%.o: build/gen/ok | build/$(1)
	$$(if $$(filter %.cpp,$$(LIBSRC_$$*)),g++ -std=c++17,gcc) $(FLAGS_$(1)) -w $(INC) -c $$(LIBSRC_$$*) -o $$@
build/$(1)/lib_zlib_crc32_w4.o: build/gen/ok | build/$(1)
	gcc $(FLAGS_$(1)) -w $(INC) $(ZLIB_W4) -c $(LIBSRC_zlib_crc32) -o $$@
build/$(1)/adapter_zlib_w4.o: adapter_zlib.c $(HDRS) | build/$(1)
	gcc $(FLAGS_$(1)) $(WARN) $(INC) $(ZLIB_W4) -c $$< -o $$@
build/$(1)/test_crc: $(addprefix build/$(1)/,$(OWN_C:.c=.o) $(OWN_CXX:.cpp=.o)) \
                     $(addprefix build/$(1)/lib_,$(addsuffix .o,$(LIBOBJ))) build/rust/release/libvl_crc_rust.a \
                     build/$(1)/lib_zlib_crc32_w4.o build/$(1)/adapter_zlib_w4.o
	g++ $(FLAGS_$(1)) -o $$@ $$^ -lpthread -ldl
endef
$(eval $(call host_variant,host))
$(eval $(call host_variant,asan))

# The Rust configuration, for the host (x86_64) as a static library.
build/rust/release/libvl_crc_rust.a: rust/Cargo.toml rust/Cargo.lock rust/src/lib.rs
	cd rust && cargo build -q --offline --locked --release --target-dir $(CURDIR)/build/rust

test: build/host/test_crc build/asan/test_crc
	@nm -S build/host/lib_zlib_crc32_w4.o | grep -q ' 0*1000 [rR] crc_braid_table$$' \
	    || { echo "zlib with 4-byte words: crc_braid_table is not 4096 bytes"; exit 1; }
	@nm -S build/host/lib_zlib_crc32.o | grep -q ' 0*2000 [rR] crc_braid_table$$' \
	    || { echo "zlib as the host builds it: crc_braid_table is not 8192 bytes"; exit 1; }
	@echo "== plain build (-O2)"
	./build/host/test_crc
	@echo "== with the address and undefined-behaviour sanitizers"
	./build/asan/test_crc

cross: build/gen/ok
	LIBS=$(LIBS) bash cross.sh

bench: build/gen/ok
	LIBS=$(LIBS) bash bench/build.sh

proof: build/gen/ok
	LIBS=$(LIBS) bash proof/run.sh

miri:
	cd rust && MIRI_SYSROOT=/root/.cache/miri cargo +nightly-2026-11-05 miri test -q --offline --locked --target-dir $(CURDIR)/build/miri

build/host/ref_check: ref_check.c ref_crc.c ref_crc.h crc.h | build/host
	gcc -O2 -g $(WARN) -I. -o $@ ref_check.c ref_crc.c
build/host/ref_check_wrong%: ref_check.c ref_crc.c ref_crc.h crc.h | build/host
	gcc -O2 -g $(WARN) -I. -DREF_WRONG=$* -o $@ ref_check.c ref_crc.c
refcheck: build/host/ref_check $(addprefix build/host/ref_check_wrong,1 2 3 4)
	python3 -I ref_check.py

build/host build/asan:
	mkdir -p $@
clean:
	rm -rf build
.PHONY: refcheck test cross bench proof miri clean
