#!/bin/bash
# Run the GenMC model checks in the pinned toolchain image.
# Uses the library sources fetched by ../../firmware/nrf5340-rb-bench/fetch-libs.sh.
# Each check states its expected outcome. Passing libraries come with
# negative controls (deliberately broken variants that MUST fail); findings
# come with the smallest change that makes them pass, which locates them.
# If any outcome differs from the expectation, the run fails.
# Usage (on lib-lab1): bash run.sh
set -euo pipefail
cd "$(dirname "$0")"
IMG=verified-libs/toolchain:2026-11-05
bash ../../firmware/nrf5340-rb-bench/fetch-libs.sh >/dev/null
LIBS=firmware/nrf5340-rb-bench/build/libs
LWRB=$LIBS/lwrb/lwrb/src
DS=$LIBS/diffstorm-cb-547d0812/src
DSNEW=$LIBS/diffstorm-cb/src

# lwrb mutant: every release store becomes relaxed (copy; original untouched)
mkdir -p build/mutant/lwrb
sed 's/memory_order_release/memory_order_relaxed/g' "../../$LWRB/lwrb/lwrb.c" > build/mutant/lwrb/lwrb.c

# diffstorm variants (copies; original untouched):
#  ds_ow:     the overwrite-flag load at cb.c:373 uses the library's own
#             CB_ATOMIC_LOAD_OW (1-byte) instead of a 32-bit load
#  ds_ow_acq: ds_ow + one barrier after the consumer's index loads
mkdir -p build/ds_ow build/ds_ow_acq
sed '373s/CB_ATOMIC_LOAD(&cb_ptr->overwrite)/CB_ATOMIC_LOAD_OW(cb_ptr)/' "../../$DS/cb.c" > build/ds_ow/cb.c
grep -q 'CB_ATOMIC_LOAD_OW(cb_ptr)) {' build/ds_ow/cb.c || { echo "ds_ow: patch did not apply" >&2; exit 1; }
awk '/^cb_result_t cb_remove_ex\(/{inr=1}
     inr && /CbIndex current_in = CB_ATOMIC_LOAD\(&cb_ptr->in\);/{print; print "    CB_MEMORY_BARRIER(); /* added: acquire ordering */"; inr=0; next}
     {print}' build/ds_ow/cb.c > build/ds_ow_acq/cb.c
grep -q 'added: acquire ordering' build/ds_ow_acq/cb.c || { echo "ds_ow_acq: patch did not apply" >&2; exit 1; }
for d in ds_ow ds_ow_acq; do cp ../../$DS/*.h build/$d/; done

# Atomics-based SPSC libraries (spsc_c.c / spsc_cxx.cpp), each with two
# mutants (copies; originals untouched): every release store becomes relaxed
# ("rel"), or every acquire load becomes relaxed ("acq"), in C11/C++11 and
# GCC __atomic spelling. Both must fail.
M=build/mut
rm -rf $M
mut() {  # lib, kind (rel|acq), source file, path inside the include dir
    local d=$M/$1-$2/$(dirname "$4") s
    mkdir -p "$d"
    if [ "$2" = rel ]; then s='s/memory_order_release/memory_order_relaxed/g; s/__ATOMIC_RELEASE/__ATOMIC_RELAXED/g'
    else s='s/memory_order_acquire/memory_order_relaxed/g; s/__ATOMIC_ACQUIRE/__ATOMIC_RELAXED/g'; fi
    sed "$s" "../../$3" > "$d/$(basename "$4")"
    ! cmp -s "../../$3" "$d/$(basename "$4")" || { echo "mutant $1-$2: no change" >&2; exit 1; }
}
for k in rel acq; do
    mut jnk0le $k $LIBS/jnk0le-ringbuffer/ringbuffer.hpp ringbuffer.hpp
    mut rigtorp $k $LIBS/rigtorp-spscqueue/include/rigtorp/SPSCQueue.h rigtorp/SPSCQueue.h
    # ETL headers include each other by relative path: copy the whole tree.
    mkdir -p $M/etl-$k && cp -r ../../$LIBS/etl/include/etl $M/etl-$k/
    mut etl $k $LIBS/etl/include/etl/queue_spsc_atomic.h etl/queue_spsc_atomic.h
    mut polycratia $k $LIBS/polycratia-spscring/include/spscring/spscring.hpp spscring/spscring.hpp
    mut rtspsc $k $LIBS/rt-spsc/include/rtq/spsc_queue.hpp rtq/spsc_queue.hpp
    mut kostyk $k $LIBS/kostyk-lockfree/include/lockfree.h lockfree.h
    mut qp $k $LIBS/qp-lfrb/src/ring_buf.c ring_buf.c
    cp ../../$LIBS/qp-lfrb/src/ring_buf.h $M/qp-$k/
    mut micoring $k $LIBS/micoring/src/mring.c mring.c
    mut lwrb $k $LWRB/lwrb/lwrb.c lwrb/lwrb.c
    mut zephyr $k $LIBS/zephyr-ringbuf/include/zephyr/sys/ring_buffer.h zephyr/sys/ring_buffer.h
    # lockfree's headers include each other by relative path: copy the tree.
    mkdir -p $M/lockfree-$k && cp -r ../../$LIBS/lockfree-dnedic/lockfree $M/lockfree-$k/
    mut lockfree $k $LIBS/lockfree-dnedic/lockfree/spsc/ring_buf_impl.hpp lockfree/spsc/ring_buf_impl.hpp
    mkdir -p $M/lfmpmc-$k && cp -r ../../$LIBS/lockfree-dnedic/lockfree $M/lfmpmc-$k/
    mut lfmpmc $k $LIBS/lockfree-dnedic/lockfree/mpmc/queue_impl.hpp lockfree/mpmc/queue_impl.hpp
done

# ETL queue_mpmc_mutex control: a copy of ETL whose etl::mutex does not lock.
rm -rf build/mpmc-nolock && mkdir -p build/mpmc-nolock && cp -r ../../$LIBS/etl/include/etl build/mpmc-nolock/
python3 -I - build/mpmc-nolock/etl/mutex/mutex_gcc_sync.h <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
old = "      while (__sync_lock_test_and_set(&flag, 1U))\n      {\n      }"
assert old in s, "mutex patch did not apply"
open(p, "w").write(s.replace(old, "      /* mutant: does not lock */"))
PY

podman run --rm -v "$PWD/../..":/work:Z -w /work "$IMG" bash -c "
  check() {  # name, expect (pass|fail), test file, extra args...
    name=\$1; expect=\$2; file=\$3; shift 3
    out=\$(genmc --rc11 \${GOPTS:-} -- \"\$@\" verify/genmc/\$file 2>&1 || true)
    if echo \"\$out\" | grep -q 'No errors were detected'; then got=pass; else got=fail; fi
    execs=\$(echo \"\$out\" | sed -n 's/Number of complete executions explored: //p')
    # A pass with 0 complete executions checked nothing (bounds too tight).
    [ \$got = pass ] && [ \"\${execs:-0}\" = 0 ] && got=vacuous
    err=\$(echo \"\$out\" | grep -m1 -E '^Error|violation|race|Mixed-size' || true)
    printf '%-52s expect %-4s got %-4s executions %-6s %s\n' \"\$name\" \$expect \$got \"\${execs:--}\" \"\$err\"
    [ \$got = \$expect ] || { echo \"\$out\" | tail -n 8 | sed 's/^/    | /'; return 1; }
  }
  ok=0
  echo '== lwrb'
  check 'lwrb v3.3.0 (C11 atomics)'                    pass lwrb_spsc.c -I$LWRB/include -I$LWRB || ok=1
  check 'control: LWRB_DISABLE_ATOMIC'                 fail lwrb_spsc.c -DLWRB_DISABLE_ATOMIC -I$LWRB/include -I$LWRB || ok=1
  check 'control: release -> relaxed mutant'           fail lwrb_spsc.c -I$LWRB/include -Iverify/genmc/build/mutant || ok=1
  echo '== diffstorm cb (findings, see ../findings/)'
  check 'diffstorm 547d0812 as is'                     fail diffstorm_spsc.c -I$DS || ok=1
  check 'diffstorm 11e05d6 (fixed upstream) as is'     pass diffstorm_spsc.c -I$DSNEW || ok=1
  check 'diffstorm, 1-byte overwrite load only'        fail diffstorm_spsc.c -Iverify/genmc/build/ds_ow || ok=1
  check 'diffstorm, 1-byte overwrite load + acquire'   pass diffstorm_spsc.c -Iverify/genmc/build/ds_ow_acq || ok=1
  # C++: verify/genmc/shims first (libstdc++ vs. GenMC's own libc headers).
  CXX='-std=c++17 -fno-exceptions -Iverify/genmc/shims'
  M=verify/genmc/build/mut
  lib() {  # label, -D name, test file, include args (the mutant dir goes first)
    label=\$1; def=\$2; file=\$3; shift 3
    flags=\"\"; case \$file in *.cpp) flags=\$CXX;; esac
    [ \$def = POLYCRATIA ] && flags=\"-std=c++17 -Iverify/genmc/shims\"   # needs exceptions
    low=\$(echo \$def | tr A-Z a-z)
    check \"\$label\"                        pass \$file \$flags -DLIB_\$def \"\$@\" || ok=1
    check \"control: \$low release -> relaxed\" fail \$file \$flags -DLIB_\$def -I\$M/\$low-rel \"\$@\" || ok=1
    check \"control: \$low acquire -> relaxed\" fail \$file \$flags -DLIB_\$def -I\$M/\$low-acq \"\$@\" || ok=1
  }
  echo '== atomics-based SPSC libraries'
  lib 'jnk0le Ringbuffer 9efa07ff'       JNK0LE     spsc_cxx.cpp -I$LIBS/jnk0le-ringbuffer
  check 'control: jnk0le fake_tso=true (single-core mode)' fail spsc_cxx.cpp \$CXX -DLIB_JNK0LE -DJNK_FAKE_TSO=true -I$LIBS/jnk0le-ringbuffer || ok=1
  lib 'rigtorp SPSCQueue 59a6a938'        RIGTORP    spsc_cxx.cpp -I$LIBS/rigtorp-spscqueue/include
  lib 'ETL queue_spsc_atomic 20.49.0'    ETL        spsc_cxx.cpp -I$LIBS/etl/include
  lib 'polycratia spscring 9d2445a5'     POLYCRATIA spsc_cxx.cpp -I$LIBS/polycratia-spscring/include
  lib 'rt-spsc 5454de55'                 RTSPSC     spsc_cxx.cpp -I$LIBS/rt-spsc/include
  lib 'kostyk348 lf_spsc 38649b8f'       KOSTYK     spsc_c.c     -I$LIBS/kostyk-lockfree/include
  lib 'QuantumLeaps LFRB 0d6354a1'       QP         spsc_c.c     -I$LIBS/qp-lfrb/src
  # micoring: generated SPSC-mode config (fetch-libs.sh) next to mring.h.
  lib 'micoring a6f91ee2 (SPSC mode)'    MICORING   spsc_c.c     -Ifirmware/nrf5340-rb-bench/build/gen/micoring -I$LIBS/micoring/src
  lib 'Zephyr ring_buf v4.5.0 (CONFIG_SMP)' ZEPHYR   spsc_c.c     -Ifirmware/nrf5340-rb-bench/shims/zephyr -I$LIBS/zephyr-ringbuf/include
  lib 'DNedic lockfree 3.0.1 spsc::RingBuf' LOCKFREE  spsc_cxx.cpp -I$LIBS/lockfree-dnedic
  # Optional further checks: every verify/genmc/extra/*.sh, sourced here
  # (same check function, LIBS and ok).
  for x in verify/genmc/extra/*.sh; do [ -f \"\$x\" ] && . \"\$x\"; done
  echo '== block and zero-copy APIs (block_c.c / block_cxx.cpp)'
  # Positive check, both mutants (release -> relaxed, acquire -> relaxed;
  # must fail), and for multi-byte APIs four reachability probes that must
  # fail (full, partial write, empty, partial read: see block_probe.h).
  # Bounds: N=7 bytes, 6 calls per thread where the state space allows it,
  # else the defaults in the test files (N=5).
  BIG='-DN=7 -DMAXCALLS=6'
  blk() {  # label, -D name, test file, mutant dir name, probes (yes|no), bounds, include args
    label=\$1; def=\$2; file=\$3; mdir=\$4; probes=\$5; bounds=\$6; shift 6
    flags=\"\"; case \$file in *.cpp) flags=\$CXX;; esac
    [ \$def = POLYCRATIA_N ] && flags=\"-std=c++17 -Iverify/genmc/shims\"   # needs exceptions
    check \"\$label\"                          pass \$file \$flags \$bounds -DLIB_\$def \"\$@\" || ok=1
    check \"control: \$label, release -> relaxed\" fail \$file \$flags \$bounds -DLIB_\$def -I\$M/\$mdir-rel \"\$@\" || ok=1
    check \"control: \$label, acquire -> relaxed\" fail \$file \$flags \$bounds -DLIB_\$def -I\$M/\$mdir-acq \"\$@\" || ok=1
    if [ \$probes = yes ]; then
      for pr in FULL PARTIAL_W EMPTY PARTIAL_R; do
        check \"probe \$pr reachable: \$label\" fail \$file \$flags \$bounds -DLIB_\$def -DPROBE_\$pr \"\$@\" || ok=1
      done
    fi
  }
  LW=\"-I$LWRB/include -I$LWRB\"
  MR=\"-Ifirmware/nrf5340-rb-bench/build/gen/micoring -I$LIBS/micoring/src\"
  blk 'lwrb write/read, multi-byte'        LWRB_BLOCK     block_c.c   lwrb       yes \"\$BIG\" \$LW
  check 'probe WRAP reachable: lwrb write/read'   fail block_c.c \$BIG -DLIB_LWRB_BLOCK -DPROBE_WRAP \$LW || ok=1
  blk 'lwrb zero-copy (linear block)'      LWRB_ZC        block_c.c   lwrb       yes \"\$BIG\" \$LW
  check 'probe WRAP reachable: lwrb zero-copy'    fail block_c.c \$BIG -DLIB_LWRB_ZC -DPROBE_WRAP \$LW || ok=1
  blk 'jnk0le writeBuff/readBuff'          JNK0LE_BUFF    block_cxx.cpp jnk0le   yes \"\$BIG\" -I$LIBS/jnk0le-ringbuffer
  blk 'jnk0le peek + remove'               JNK0LE_PEEK    block_cxx.cpp jnk0le   no  '' -I$LIBS/jnk0le-ringbuffer
  blk 'polycratia try_push_n/try_pop_n'    POLYCRATIA_N   block_cxx.cpp polycratia yes \"\$BIG\" -I$LIBS/polycratia-spscring/include
  blk 'micoring push_many/pop_many'        MICORING_MANY  block_c.c   micoring   yes '' \$MR
  blk 'micoring peek + pop(NULL)'          MICORING_PEEK  block_c.c   micoring   no  '' \$MR
  blk 'ETL front(value) + pop()'           ETL_FRONT      block_cxx.cpp etl      no  '' -I$LIBS/etl/include
  blk 'ETL empty() + front() ref + pop()'  ETL_FRONT_REF  block_cxx.cpp etl      no  '' -I$LIBS/etl/include
  ZR=\"-Ifirmware/nrf5340-rb-bench/shims/zephyr -I$LIBS/zephyr-ringbuf/include\"
  blk 'Zephyr put/get, multi-byte (SMP)'    ZEPHYR_BLOCK   block_c.c   zephyr     yes \"\$BIG\" \$ZR
  blk 'Zephyr zero-copy put_ptr/get_ptr (SMP)' ZEPHYR_ZC   block_c.c   zephyr     yes \"\$BIG\" \$ZR
  blk 'lockfree RingBuf bulk Write/Read'    LOCKFREE_BULK  block_cxx.cpp lockfree yes \"\$BIG\" -I$LIBS/lockfree-dnedic
  echo '== MPMC: ETL queue_mpmc_mutex, threads (mpmc_cxx.cpp)'
  # Its documented mode: threads, the queue's own mutex (a spin lock on the
  # __sync builtins; -DETL_NO_STD_MUTEX selects it, as on bare metal). 2+2
  # threads do not finish in 20 min, so 2 producers + 1 consumer and
  # 1 producer + 2 consumers, each with the no-lock control and probes.
  EM=\"\$CXX -DETL_NO_STD_MUTEX -DLIB_ETL_MPMC\"
  for cfg in '-DNP=2 -DNC=1 -DK=2' '-DNP=1 -DNC=2 -DK=4'; do
    check \"ETL queue_mpmc_mutex 20.49.0, \$cfg\"         pass mpmc_cxx.cpp \$EM \$cfg -I$LIBS/etl/include || ok=1
    check \"control: mutex that does not lock, \$cfg\"      fail mpmc_cxx.cpp \$EM \$cfg -Iverify/genmc/build/mpmc-nolock || ok=1
    check \"probe FULL reachable, \$cfg\"                   fail mpmc_cxx.cpp \$EM \$cfg -DPROBE_FULL -I$LIBS/etl/include || ok=1
    check \"probe EMPTY reachable, \$cfg\"                  fail mpmc_cxx.cpp \$EM \$cfg -DPROBE_EMPTY -I$LIBS/etl/include || ok=1
  done
  echo '== MPMC: DNedic lockfree 3.0.1 mpmc::Queue, threads (mpmc_cxx.cpp)'
  # Lock-free (CAS on the read/write counters, a per-slot sequence count).
  # Its capacity must be a power of 2 above 2, so CAP=4; K is chosen so the
  # queue still runs full (6 values). RETRY=2: with 3 the 2+1 and 1+2 runs
  # did not finish in 40 min. Push also returns false while another producer
  # is writing the slot (not only when full); the retries cover that.
  LM=\"\$CXX -DLIB_LOCKFREE_MPMC -DCAP=4 -DRETRY=2\"
  for cfg in '-DNP=2 -DNC=1 -DK=3' '-DNP=1 -DNC=2 -DK=6'; do
    check \"lockfree mpmc::Queue 3.0.1, \$cfg\"            pass mpmc_cxx.cpp \$LM \$cfg -I$LIBS/lockfree-dnedic || ok=1
    check \"control: lockfree mpmc release -> relaxed, \$cfg\" fail mpmc_cxx.cpp \$LM \$cfg -I\$M/lfmpmc-rel || ok=1
    check \"control: lockfree mpmc acquire -> relaxed, \$cfg\" fail mpmc_cxx.cpp \$LM \$cfg -I\$M/lfmpmc-acq || ok=1
    check \"probe FULL reachable, lockfree, \$cfg\"         fail mpmc_cxx.cpp \$LM \$cfg -DPROBE_FULL -I$LIBS/lockfree-dnedic || ok=1
    check \"probe EMPTY reachable, lockfree, \$cfg\"        fail mpmc_cxx.cpp \$LM \$cfg -DPROBE_EMPTY -I$LIBS/lockfree-dnedic || ok=1
  done
  exit \$ok
"
