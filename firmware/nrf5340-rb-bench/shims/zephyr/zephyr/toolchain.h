/* Minimal stand-in for Zephyr's <zephyr/toolchain.h> (GCC/Clang parts used by
 * sys/ring_buffer.h): as in Zephyr's toolchain/gcc.h. */
#pragma once
#ifndef ALWAYS_INLINE
#define ALWAYS_INLINE inline __attribute__((always_inline))
#endif
#ifndef __deprecated
#define __deprecated __attribute__((deprecated))
#endif
#ifndef __noinit
#define __noinit __attribute__((section(".noinit")))
#endif
#define compiler_barrier() __asm__ __volatile__("" ::: "memory")
