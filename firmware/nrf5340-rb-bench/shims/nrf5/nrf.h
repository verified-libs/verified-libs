/* Shim for the nRF5 SDK's nrf.h (modules/nrfx/mdk), which pulls in the
 * device headers and CMSIS: the ring buffer and atomics need only the core
 * version, to take their LDREX/STREX path (nrf_atomic_internal.h). The
 * nRF5340 application core is a Cortex-M33. */
#pragma once
#include <stdint.h>
#ifndef __CORTEX_M
#define __CORTEX_M 33U
#endif
/* CMSIS intrinsic used by an inline helper in app_util.h (CMSIS defines it
 * the same way for GCC) */
#ifndef __REV
#define __REV(x) __builtin_bswap32(x)
#endif
