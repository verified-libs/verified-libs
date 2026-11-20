#!/bin/bash
# Flash and RAM per library for 1 ring buffer, 3 identical ones (capacity
# 128 each) and 3 of different capacity (64, 128, 256), at -Os and -O2, on
# the board's flash image. Each buffer is its own module (one copy of the
# library's benchmark adapter); the library's own .c objects are linked once.
# Writes results.tsv and report.md to OUTDIR (default ~/lab-runs/size-<UTC>).
# Usage (on lib-lab1): bash size.sh            (BOARD=nrf5340 default)
set -euo pipefail
cd "$(dirname "$0")"
IMG=verified-libs/toolchain:2026-11-05
BOARD=${BOARD:-nrf5340}
OUTDIR=${OUTDIR:-$HOME/lab-runs/size-$(date -u +%Y%m%dT%H%M%SZ)}
mkdir -p "$OUTDIR"
bash ../nrf5340-rb-bench/fetch-libs.sh > "$OUTDIR/libs_pinned.txt"
{ echo "image: $IMG"; podman run --rm "$IMG" arm-none-eabi-gcc --version | head -1; } > "$OUTDIR/toolchain.txt"

podman run --rm -i -v "$PWD/..":/work:Z -w /work/nrf5340-rb-bench -e BOARD="$BOARD" "$IMG" bash -s > "$OUTDIR/results.tsv" 2> "$OUTDIR/build.log" <<'INNER'
set -eu
# name | adapter object (bench Makefile target) | adapter symbol | library objects
LIBS='pxq|build/adapter_pxq.o|adapter_pxq|
lwrb|build/adapter_lwrb.o|adapter_lwrb|build/lwrb.o
AndersKaloer|build/adapter_anders.o|adapter_anders|build/anders_ringbuffer.o
jnk0le|build/adapter_jnk0le.o|adapter_jnk0le|
ETL queue_spsc_isr|build/adapter_etl.o|adapter_etl_isr|
ETL queue_spsc_atomic|build/adapter_etl.o|adapter_etl_atomic|
QP LFRB|build/w2_qp_lfrb.o|adapter_qp_lfrb|build/qp_ring_buf.o
Embedded Artistry (threadsafe)|build/w2_ea_cbuf.o|adapter_ea_cbuf|build/ea_circular_buffer.o
ece-mohammad|build/w2_ece.o|adapter_ece|build/ece_ring_buffer.o
micoring (SPSC)|build/w2_micoring.o|adapter_micoring|build/micoring_mring.o
kostyk348 lf_spsc|build/w2_kostyk.o|adapter_kostyk|
diffstorm|build/w2_diffstorm.o|adapter_diffstorm|build/diffstorm_cb.o
RIOT tsrb|build/w2_riot_tsrb.o|adapter_riot_tsrb|build/riot_tsrb.o
Contiki-NG|build/w2_contiki.o|adapter_contiki|build/contiki_ringbuf.o
rigtorp|build/w2_rigtorp.o|adapter_rigtorp|
wizard97 as shipped|build/w2_wizard97_plain.o|adapter_wizard97_plain|
wizard97 + PRIMASK|build/w2_wizard97_primask.o|adapter_wizard97_primask|
polycratia|build/w2_polycratia.o|adapter_polycratia|
rt-spsc|build/w2_rtspsc.o|adapter_rtspsc|
TinyUSB tu_fifo|build/w2_tinyusb.o|adapter_tinyusb|build/tinyusb_fifo.o
Zephyr ring_buf|build/w2_zephyr.o|adapter_zephyr|
Zephyr ring_buf, CONFIG_SMP|build/w2_zephyr_smp.o|adapter_zephyr_smp|
DNedic lockfree spsc::RingBuf|build/w2_lockfree.o|adapter_lockfree|
ETL queue_spsc_locked|build/w2_etl_locked.o|adapter_etl_locked|
FreeRTOS stream buffer|build/w2_freertos_sb.o|adapter_freertos_sb|build/freertos_stream_buffer.o build/freertos_shim.o
NuttX circbuf|build/w2_nuttx_circbuf.o|adapter_nuttx_circbuf|build/nuttx_circbuf.o
Arduino RingBufferN as shipped|build/w2_arduino_plain.o|adapter_arduino_plain|
Arduino SafeRingBufferN|build/w2_arduino_safe.o|adapter_arduino_safe|
RT-Thread rt_ringbuffer, no lock|build/w2_rtthread_plain.o|adapter_rtthread_plain|build/rtthread_ringbuffer.o
RT-Thread rt_ringbuffer + interrupt lock|build/w2_rtthread_locked.o|adapter_rtthread_locked|build/rtthread_ringbuffer.o
Mbed CE CircularBuffer|build/w2_mbed_cb.o|adapter_mbed_cb|
moodycamel ReaderWriterQueue|build/w2_moodycamel.o|adapter_moodycamel|
pxq Topology::None|build/sc_pxq_none.o|adapter_pxq_none|
ETL etl::queue|build/sc_etl_queue.o|adapter_etl_queue|'
# every adapter symbol is renamed in every copy, so a module that defines
# two adapters (adapter_etl.cpp) does not clash with its other copies
ALLSYMS=$(echo "$LIBS" | cut -d'|' -f3 | sort -u)
COMMON=../common/$BOARD
LD=$(sed -n 's/^LD_FLASH *= *\$(COMMON)\///p' $COMMON/board.mk)
ARCH=$(sed -n 's/^ARCH *= *//p' $COMMON/board.mk)
S=/tmp/size; rm -rf $S; mkdir -p $S
echo -e "lib\topt\tvariant\ttext\tdata\tbss"
for OPT in -Os -O2; do
  make clean >/dev/null; make -s BOARD=$BOARD OPT=$OPT >/dev/null 2>&2
  arm-none-eabi-gcc $ARCH $OPT -g -Wall -Wextra -DNDEBUG -ffreestanding -ffunction-sections -fdata-sections \
      -I. -I$COMMON -c ../rb-size/size_main.c -DK=0 -o $S/main0.o
  link() {  # out, objects...
    local out=$1; shift
    arm-none-eabi-g++ $ARCH $OPT -nostartfiles --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections \
        -T $COMMON/$LD build/startup.o "$@" build/bench_heap.o build/bench_heap_cpp.o -o $out
  }
  link $S/base.elf $S/main0.o
  read -r t d b _ < <(arm-none-eabi-size -B $S/base.elf | tail -1)
  echo -e "baseline\t$OPT\tK=0\t$t\t$d\t$b"
  echo "$LIBS" | while IFS='|' read -r name obj sym libobjs; do
    cmd=$(make -s -n -B BOARD=$BOARD OPT=$OPT $obj | grep -E '^arm-none-eabi-g(cc|\+\+) ' | tail -1)
    for v in "1 128" "3 128 128 128" "3 64 128 256"; do
      set -- $v; k=$1; shift
      objs=""; defs="-DK=$k"; i=0
      for cap in "$@"; do
        ren=""; for s in $ALLSYMS; do ren="$ren -D$s=${s}_$i"; done
        o=$S/copy_$i.o
        eval "${cmd% -o *} -DBENCH_NO_ALIGN -DRB_SLOTS=$cap $ren -o $o" >&2
        objs="$objs $o"; defs="$defs -DADAPTER_$i=${sym}_$i"; i=$((i + 1))
      done
      arm-none-eabi-gcc $ARCH $OPT -g -DNDEBUG -ffreestanding -ffunction-sections -fdata-sections \
          -I. -I$COMMON $defs -c ../rb-size/size_main.c -o $S/main.o
      link $S/probe.elf $S/main.o $objs $libobjs >&2
      read -r t d b _ < <(arm-none-eabi-size -B $S/probe.elf | tail -1)
      variant="K=$k cap=$(echo "$@" | tr ' ' '/')"
      echo -e "$name\t$OPT\t$variant\t$t\t$d\t$b"
    done
  done
done
INNER
{ python3 summarize.py "$OUTDIR/results.tsv"; echo "Toolchain:"; sed 's/^/    /' "$OUTDIR/toolchain.txt"; } > "$OUTDIR/report.md"
echo "report: $OUTDIR/report.md"
