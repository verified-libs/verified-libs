/* SET=nordic only: the parts of an nrf_ringbuf single-byte call, timed like
 * the libraries (push = the producer's part, pop = the consumer's), to show
 * where its cycles go. Not libraries: decode.py names them "part: ...", and
 * the comparison page leaves them out.
 *   atomics: nrf_atomic_flag_set_fetch + nrf_atomic_flag_clear, the flag
 *            every cpy_put / cpy_get takes and gives back
 *   memcpy1: the C library's memcpy of one byte, as cpy_put / cpy_get call it
 *   len0:    nrf_ringbuf_cpy_put / cpy_get with length 0: the flag, the index
 *            arithmetic and a zero-byte memcpy, no data */
#include <string.h>
#include "nrf_ringbuf.h"
#include "bench.h"

NRF_RINGBUF_DEF(prb, RB_SLOTS);
static nrf_atomic_flag_t flag;
static uint8_t slot;

BENCH_ALIGN static void parts_reset(void) { nrf_ringbuf_init(&prb); flag = 0; }
BENCH_ALIGN static uint32_t at_op(uintptr_t a, uintptr_t b)
{
    (void)a; (void)b;
    uint32_t was = nrf_atomic_flag_set_fetch(&flag);
    (void)nrf_atomic_flag_clear(&flag);
    return was == 0;
}
BENCH_ALIGN static uint32_t mc_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    uint8_t b = (uint8_t)v;
    memcpy(&slot, &b, 1);
    return 1;
}
BENCH_ALIGN static uint32_t mc_pop(uintptr_t p, uintptr_t u) { (void)u; memcpy((uint8_t *)p, &slot, 1); return 1; }
BENCH_ALIGN static uint32_t l0_push(uintptr_t v, uintptr_t u)
{
    (void)u;
    uint8_t b = (uint8_t)v;
    size_t len = 0;
    return nrf_ringbuf_cpy_put(&prb, &b, &len) == NRF_SUCCESS;
}
BENCH_ALIGN static uint32_t l0_pop(uintptr_t p, uintptr_t u)
{
    (void)u;
    size_t len = 0;
    return nrf_ringbuf_cpy_get(&prb, (uint8_t *)p, &len) == NRF_SUCCESS;
}

const rb_adapter part_nrf_atomics = { parts_reset, at_op, at_op, 0, 0, 0, 0, 0, 0, 0, 0 };
const rb_adapter part_memcpy1     = { parts_reset, mc_push, mc_pop, 0, 0, 0, 0, 0, 0, 0, 0 };
const rb_adapter part_nrf_len0    = { parts_reset, l0_push, l0_pop, 0, 0, 0, 0, 0, 0, 0, 0 };
