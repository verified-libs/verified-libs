/* Interface between the benchmark driver (main.c) and one adapter per
 * library. Every adapter offers the same operations on a byte ring buffer
 * with RB_SLOTS slots (RB_SLOTS - 1 usable). All operations share one
 * signature, so they are timed by the very same code (time_call in main.c):
 *   push:   a = the byte to push                  -> 1 on success
 *   pop:    a = address of a uint8_t to fill      -> 1 on success
 *   push_n: a = source address,      b = count    -> bytes pushed
 *   pop_n:  a = destination address, b = count    -> bytes popped
 */
#pragma once
#include <stdint.h>

#ifndef RB_SLOTS
#define RB_SLOTS 128   /* the size probe (../rb-size) builds 64 and 256 too */
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef uint32_t (*rb_op)(uintptr_t a, uintptr_t b);

typedef struct {
    void  (*reset)(void);
    rb_op push, pop, push_n, pop_n;
    /* Optional: variants to call from interrupt context, for libraries with
     * a separate ISR API (ETL queue_spsc_isr). NULL = use push/pop. */
    rb_op isr_push, isr_pop;
    /* Optional zero-copy (DMA-style) API, NULL if the library has none:
     *   dma_wr_acquire: a = address of a uint8_t* to receive the write area,
     *                   b = max bytes wanted -> contiguous bytes available
     *   dma_wr_commit:  a = bytes written -> bytes committed
     *   dma_rd_acquire: a = address of a const uint8_t* for the read area,
     *                   b = max bytes wanted -> contiguous bytes readable
     *   dma_rd_release: a = bytes consumed -> bytes released */
    rb_op dma_wr_acquire, dma_wr_commit, dma_rd_acquire, dma_rd_release;
} rb_adapter;

/* The adapters. Not read by an image of one configuration (main.c
 * BENCH_ONE), which names its own; the adapters' own files read the list
 * (it gives the C++ ones their external linkage). */
#ifndef BENCH_ONE
extern const rb_adapter adapter_pxq;
extern const rb_adapter adapter_lwrb;
extern const rb_adapter adapter_anders;
extern const rb_adapter adapter_jnk0le;
extern const rb_adapter adapter_etl_isr;
extern const rb_adapter adapter_etl_atomic;
/* wave 2 */
extern const rb_adapter adapter_qp_lfrb;
extern const rb_adapter adapter_ea_cbuf;
extern const rb_adapter adapter_ece;
extern const rb_adapter adapter_micoring;
extern const rb_adapter adapter_kostyk;
extern const rb_adapter adapter_diffstorm;
extern const rb_adapter adapter_riot_tsrb;
extern const rb_adapter adapter_contiki;
extern const rb_adapter adapter_rigtorp;
extern const rb_adapter adapter_wizard97_plain;
extern const rb_adapter adapter_wizard97_primask;
extern const rb_adapter adapter_polycratia;
extern const rb_adapter adapter_rtspsc;
extern const rb_adapter adapter_tinyusb;
/* wave 3 (2026-11-12) */
extern const rb_adapter adapter_zephyr;
extern const rb_adapter adapter_zephyr_smp;
extern const rb_adapter adapter_lockfree;
extern const rb_adapter adapter_etl_locked;
extern const rb_adapter adapter_freertos_sb;
extern const rb_adapter adapter_nuttx_circbuf;
extern const rb_adapter adapter_arduino_plain;
extern const rb_adapter adapter_arduino_safe;
extern const rb_adapter adapter_rtthread_plain;
extern const rb_adapter adapter_rtthread_locked;
extern const rb_adapter adapter_mbed_cb;
extern const rb_adapter adapter_moodycamel;
/* single-context variants (adapters_sc/): benchmark only, never shared */
extern const rb_adapter adapter_pxq_none;
extern const rb_adapter adapter_pxq_mpsc, adapter_pxq_spmc, adapter_pxq_mpmc, adapter_lockfree_mpmc;
/* Rust (../rust-adapters) */
extern const rb_adapter adapter_heapless, adapter_heapless_mpmc, adapter_bbqueue, adapter_embassy_pipe;
extern const rb_adapter adapter_micoring_sc;
extern const rb_adapter adapter_ea_cbuf_plain;
extern const rb_adapter adapter_etl_queue;
#endif

#ifdef BENCH_NO_ALIGN   /* size probe: no padding between the adapter functions */
#define BENCH_ALIGN __attribute__((noinline))
#else
#define BENCH_ALIGN __attribute__((noinline, aligned(32), section(".text.bench_adapter")))
#endif

/* For libraries without a block API: push_n/pop_n as a loop over the
 * adapter's own single-byte push/pop, the same for every such library. */
#define BENCH_DEFINE_LOOP_N(prefix)                                              \
    BENCH_ALIGN static uint32_t prefix##_push_n(uintptr_t p, uintptr_t n)        \
    {                                                                            \
        const uint8_t *s = (const uint8_t *)p;                                   \
        uint32_t i = 0;                                                          \
        while (i < n && prefix##_push(s[i], 0)) i++;                             \
        return i;                                                                \
    }                                                                            \
    BENCH_ALIGN static uint32_t prefix##_pop_n(uintptr_t p, uintptr_t n)         \
    {                                                                            \
        uint8_t *d = (uint8_t *)p;                                               \
        uint32_t i = 0;                                                          \
        while (i < n && prefix##_pop((uintptr_t)&d[i], 0)) i++;                  \
        return i;                                                                \
    }

#ifdef __cplusplus
}
#endif
