/*
 * rb-size: flash and RAM taken by K ring buffers of one library.
 * K (0, 1, 3) copies of the library's benchmark adapter are linked, each
 * compiled as its own module with its own buffer (adapter symbols renamed
 * ADAPTER_0..2 on the command line, capacity RB_SLOTS per copy). main()
 * uses every operation of every copy once through the adapter table, so
 * nothing is optimised away. K = 0 is the baseline that is subtracted.
 */
#include <stdint.h>
#include "bench.h"

#ifndef K
#define K 0
#endif
#if K >= 1
extern const rb_adapter ADAPTER_0;
#endif
#if K >= 2
extern const rb_adapter ADAPTER_1;
#endif
#if K >= 3
extern const rb_adapter ADAPTER_2;
#endif

static const rb_adapter *volatile tab[3] = {
#if K >= 1
    &ADAPTER_0,
#endif
#if K >= 2
    &ADAPTER_1,
#endif
#if K >= 3
    &ADAPTER_2,
#endif
};

volatile uint32_t sink;

int main(void)
{
    for (uint32_t k = 0; k < K; k++) {
        const rb_adapter *a = tab[k];
        uint8_t b = 0, blk[4] = {1, 2, 3, 4};
        a->reset();
        sink += a->push(1, 0);
        sink += a->pop((uintptr_t)&b, 0);
        sink += a->push_n((uintptr_t)blk, 4);
        sink += a->pop_n((uintptr_t)blk, 4);
        sink += b;
    }
    for (;;) {}
}
