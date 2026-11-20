/* Minimal stand-in for NuttX's generated <nuttx/config.h>: only what
 * libs/libc/misc/lib_circbuf.c and include/nuttx/circbuf.h use outside
 * NuttX. FAR is empty on ARM (as in NuttX's compiler.h); DEBUGASSERT is off,
 * as in a NuttX build without CONFIG_DEBUG_ASSERTIONS (the release case,
 * like -DNDEBUG for the other libraries). */
#pragma once
#define FAR
#define DEBUGASSERT(x) ((void)0)
#include <errno.h>
