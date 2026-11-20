/* rb_adapter tables for the Rust ring buffers (src/lib.rs): the harness
 * calls the Rust functions directly through these pointers, as it calls
 * the C and C++ adapters' functions. */
#include "bench.h"

#define RUST_OPS(p)                                                           \
    void p##_reset(void);                                                     \
    uint32_t p##_push(uintptr_t, uintptr_t), p##_pop(uintptr_t, uintptr_t),  \
        p##_push_n(uintptr_t, uintptr_t), p##_pop_n(uintptr_t, uintptr_t);
RUST_OPS(hl)
RUST_OPS(hlm)
RUST_OPS(bbq)
RUST_OPS(emb)
uint32_t bbq_dma_wr_acquire(uintptr_t, uintptr_t), bbq_dma_wr_commit(uintptr_t, uintptr_t),
    bbq_dma_rd_acquire(uintptr_t, uintptr_t), bbq_dma_rd_release(uintptr_t, uintptr_t);

const rb_adapter adapter_heapless = { hl_reset, hl_push, hl_pop, hl_push_n, hl_pop_n, 0, 0 };
const rb_adapter adapter_heapless_mpmc = { hlm_reset, hlm_push, hlm_pop, hlm_push_n, hlm_pop_n, 0, 0 };
const rb_adapter adapter_bbqueue = { bbq_reset, bbq_push, bbq_pop, bbq_push_n, bbq_pop_n, 0, 0,
                                     bbq_dma_wr_acquire, bbq_dma_wr_commit, bbq_dma_rd_acquire, bbq_dma_rd_release };
const rb_adapter adapter_embassy_pipe = { emb_reset, emb_push, emb_pop, emb_push_n, emb_pop_n, 0, 0 };
