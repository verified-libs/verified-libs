/* Minimal stand-in for Mbed's platform/mbed_assert.h: MBED_ASSERT is off
 * with NDEBUG, as in an Mbed release build. */
#pragma once
#define MBED_ASSERT(expr) ((void)0)
