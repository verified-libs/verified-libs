/* Adapter: QuantumLeaps/lock-free-ring-buffer (C11 atomics). No block API. */
#include "ring_buf.h"
#include "bench.h"

static RingBuf rb;
static RingBufElement sto[RB_SLOTS];

BENCH_ALIGN static void qp_reset(void) { RingBuf_ctor(&rb, sto, RB_SLOTS); }
BENCH_ALIGN static uint32_t qp_push(uintptr_t v, uintptr_t u) { (void)u; return RingBuf_put(&rb, (RingBufElement)v); }
BENCH_ALIGN static uint32_t qp_pop(uintptr_t p, uintptr_t u) { (void)u; return RingBuf_get(&rb, (RingBufElement *)p); }
BENCH_DEFINE_LOOP_N(qp)

const rb_adapter adapter_qp_lfrb = { qp_reset, qp_push, qp_pop, qp_push_n, qp_pop_n, 0, 0 };
