/* lwIP's architecture header for the pools kind: the standard types, and
 * assertions that stop the program (lwIP's asserts stay on, its default):
 * abort() on the host, a loop on a board, so that the port brings no C library
 * code of its own into the image. */
#pragma once
#include <stdint.h>
#include <stdlib.h>
typedef unsigned sys_prot_t;
#define LWIP_PLATFORM_DIAG(x) do {} while (0)
#if defined(__arm__)
#define LWIP_PLATFORM_ASSERT(x) do { for (;;) {} } while (0)
#else
#define LWIP_PLATFORM_ASSERT(x) abort()
#endif
