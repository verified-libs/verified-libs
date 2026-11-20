/* Minimal stand-in for Zephyr's <zephyr/sys/util.h>, only what
 * <zephyr/sys/ring_buffer.h> (v4.5.0) uses, so the ring buffer can be built
 * outside Zephyr. Definitions as in Zephyr (sys/util_macro.h, sys/util.h). */
#pragma once
#include <stddef.h>
#ifndef MIN
#define MIN(a, b) (((a) < (b)) ? (a) : (b))
#endif
/* IS_ENABLED(CONFIG_X): 1 if CONFIG_X is defined to 1, else 0 (Zephyr's
 * Z_IS_ENABLED trick, sys/util_internal.h). */
#define Z_XXXX1 Z_YYYY,
#define IS_ENABLED(config_macro) Z_IS_ENABLED1(config_macro)
#define Z_IS_ENABLED1(config_macro) Z_IS_ENABLED2(Z_XXXX##config_macro)
#define Z_IS_ENABLED2(one_or_two_args) Z_IS_ENABLED3(one_or_two_args 1, 0)
#define Z_IS_ENABLED3(ignore_this, val, ...) val
#define BUILD_ASSERT(...) _Static_assert(__VA_ARGS__, "")
#include <zephyr/toolchain.h>
