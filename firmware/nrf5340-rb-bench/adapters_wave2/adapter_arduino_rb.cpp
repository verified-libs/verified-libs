/* Adapter: Arduino RingBufferN (ArduinoCore-API api/RingBuffer.h, 1.5.2),
 * the buffer behind Serial in several Arduino cores. Two builds of this file:
 *   default:              RingBufferN as shipped. Its maintainers say it is
 *                         not meant to be thread-safe (ArduinoCore-API issue
 *                         #195): both sides change the shared _numElems with
 *                         x = x +/- 1. Reported, not counted.
 *   -DARDUINO_SAFE=1:     SafeRingBufferN (ArduinoCore-renesas
 *                         cores/arduino/SafeRingBuffer.h, 1.6.0): read_char,
 *                         store_char and available() inside `synchronized`
 *                         (sync.h: PRIMASK saved, interrupts off, restored).
 * N = RB_SLOTS - 1: RingBufferN has no reserved slot, so this is the same
 * usable capacity as the other adapters (offsets are index % N). No block
 * API: push_n/pop_n loop over single bytes. */
#include <stdint.h>
#if defined(ARDUINO_SAFE) && ARDUINO_SAFE
#include "SafeRingBuffer.h"
#define AR(x) ards_##x
#define AR_PREFIX ards
#define AR_ADAPTER adapter_arduino_safe
#define AR_TYPE arduino::SafeRingBufferN<RB_SLOTS - 1>
#else
#include <api/RingBuffer.h>
#define AR(x) ardp_##x
#define AR_PREFIX ardp
#define AR_ADAPTER adapter_arduino_plain
#define AR_TYPE arduino::RingBufferN<RB_SLOTS - 1>
#endif
#include "bench.h"

namespace {
AR_TYPE rb;
}

extern "C" {

BENCH_ALIGN static void AR(reset)(void) { rb.clear(); }
BENCH_ALIGN static uint32_t AR(push)(uintptr_t v, uintptr_t)
{
    /* store_char drops the byte silently when full: check first. Only the
     * producer makes the buffer fuller, so the check cannot go stale. */
    if (rb.availableForStore() <= 0) return 0;
    rb.store_char(static_cast<uint8_t>(v));
    return 1;
}
BENCH_ALIGN static uint32_t AR(pop)(uintptr_t p, uintptr_t)
{
    int c = rb.read_char();
    if (c < 0) return 0;
    *reinterpret_cast<uint8_t *>(p) = static_cast<uint8_t>(c);
    return 1;
}
#define AR_LOOP_N(p) BENCH_DEFINE_LOOP_N(p)   /* expands AR_PREFIX first */
AR_LOOP_N(AR_PREFIX)

const rb_adapter AR_ADAPTER = { AR(reset), AR(push), AR(pop), AR(push_n), AR(pop_n), 0, 0 };

}
