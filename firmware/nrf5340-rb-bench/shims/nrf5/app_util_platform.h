/* Shim for the nRF5 SDK's app_util_platform.h (SoftDevice and interrupt
 * priority helpers): nrf_ringbuf.c includes it only for app_util.h's
 * UNUSED_RETURN_VALUE; the critical-region macros are used by nrf_atomic.c
 * only on cores without LDREX/STREX, not on the Cortex-M33. */
#pragma once
#include "app_util.h"
