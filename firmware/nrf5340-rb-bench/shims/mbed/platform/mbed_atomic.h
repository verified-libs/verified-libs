/* Minimal stand-in for Mbed's platform/mbed_atomic.h: the one function
 * CircularBuffer uses, as Mbed CE mbed-os-7.1.0 defines it
 * (internal/mbed_atomic_impl.h, DO_MBED_LOCKFREE_LOADSTORE: a plain load
 * then MBED_BARRIER(), which mbed_toolchain.h defines as a compiler
 * barrier on a single CPU). */
#pragma once
#include <stdbool.h>
static inline bool core_util_atomic_load_bool(const volatile bool *valuePtr)
{
    bool value = *valuePtr;
    __asm volatile("" ::: "memory");
    return value;
}
