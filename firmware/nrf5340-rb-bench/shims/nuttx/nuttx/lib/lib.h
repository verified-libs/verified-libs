/* Minimal stand-in for NuttX's <nuttx/lib/lib.h>: lib_malloc/lib_free are
 * only used when circbuf_init gets no buffer, or by resize/uninit; the
 * adapter always passes its own buffer, so these are never called (and the
 * linker drops the functions that would). */
#pragma once
#include <stdlib.h>
#include <string.h>   /* memcpy, memset: NuttX's lib.h pulls them in */
#define lib_malloc(n) malloc(n)
#define lib_free(p) free(p)
