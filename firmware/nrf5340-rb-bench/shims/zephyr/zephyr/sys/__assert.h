/* Minimal stand-in for Zephyr's <zephyr/sys/__assert.h>: assertions off, as
 * in a Zephyr build with CONFIG_ASSERT=n. */
#pragma once
#define __ASSERT(test, fmt, ...) ((void)0)
#define __ASSERT_NO_MSG(test) ((void)0)
