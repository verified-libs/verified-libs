/* Version 1 of the benchmark: the libraries that share one image, per set
 * (run.sh SET=...), and size.sh's firmware with a single configuration.
 * Read by main.c when it is not built for one configuration (BENCH_ONE);
 * the images of one configuration are not built from this file. */
#pragma once

#ifdef BENCH_ONLY   /* size.sh: a firmware with one configuration, to measure what it adds; never run */
#define NLIBS 1u
extern const rb_adapter adapter_none;   /* size_none.c: no library at all */
#define BENCH_LIBS &BENCH_ONLY

#elif defined(BENCH_MP)   /* SET=mp: the modes for more than one producer or consumer */
#define NLIBS 10u
/* each mode next to the library's SPSC configuration, timed in the same
 * firmware; tsrb and wizard97 + PRIMASK are the same code in every mode
 * (stress test of the modes: ../rb-mp-stress) */
#define BENCH_LIBS \
    &adapter_baseline, &adapter_pxq, &adapter_pxq_mpsc, &adapter_pxq_spmc, &adapter_pxq_mpmc, \
    &adapter_lockfree, &adapter_lockfree_mpmc, &adapter_riot_tsrb, &adapter_wizard97_primask, \
    &adapter_heapless_mpmc

#elif defined(BENCH_RUST)   /* SET=rust: the Rust libraries (../rust-adapters) */
#define NLIBS 5u
/* a firmware of their own: the SPSC set fills the SAM D20's RAM; baseline
 * and pxq as a reference against that set */
#define BENCH_LIBS \
    &adapter_baseline, &adapter_pxq, &adapter_heapless, &adapter_bbqueue, &adapter_embassy_pipe

#elif defined(BENCH_NORDIC)   /* SET=nordic: nrf_ringbuf, nRF5340 only (Nordic's licence) */
#define NLIBS 6u
extern const rb_adapter adapter_nrf_ringbuf, part_nrf_atomics, part_memcpy1, part_nrf_len0;
/* a firmware of its own, for the nRF5340 only; baseline and pxq as a
 * reference against the SPSC set; then where nrf_ringbuf's single-byte
 * cycles go (adapters_nordic/parts_nrf_ringbuf.c) */
#define BENCH_LIBS \
    &adapter_baseline, &adapter_pxq, &adapter_nrf_ringbuf, \
    &part_nrf_atomics, &part_memcpy1, &part_nrf_len0

#else
#define NLIBS 37u
#define BENCH_LIBS \
    &adapter_baseline, &adapter_pxq, &adapter_lwrb, &adapter_anders, \
    &adapter_jnk0le, &adapter_etl_isr, &adapter_etl_atomic, \
    &adapter_qp_lfrb, &adapter_ea_cbuf, &adapter_ece, &adapter_micoring, \
    &adapter_kostyk, &adapter_diffstorm, &adapter_riot_tsrb, &adapter_contiki, \
    &adapter_rigtorp, &adapter_wizard97_plain, &adapter_wizard97_primask, \
    &adapter_polycratia, &adapter_rtspsc, &adapter_tinyusb, \
    &adapter_zephyr, &adapter_zephyr_smp, &adapter_lockfree, &adapter_etl_locked, \
    &adapter_freertos_sb, &adapter_nuttx_circbuf, &adapter_arduino_plain, &adapter_arduino_safe, \
    &adapter_rtthread_plain, &adapter_rtthread_locked, &adapter_mbed_cb, &adapter_moodycamel, \
    /* single-context variants */ \
    &adapter_pxq_none, &adapter_micoring_sc, &adapter_ea_cbuf_plain, &adapter_etl_queue
#endif
