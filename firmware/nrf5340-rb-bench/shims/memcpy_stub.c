/*
 * memcpy as newlib's memcpy-stub.c builds it when the C library is built for
 * size (PREFER_SIZE_OVER_SPEED / __OPTIMIZE_SIZE__): a plain byte loop.
 * Reported (2026-11-08, checked by the project owner, not repeated here) to
 * be what STM32CubeIDE 1.13.2 / GNU Tools for STM32 11.3 (newlib 4.2.0)
 * links on every Cortex-M, in both libc and libc_nano.
 *
 * Linked only with MEMCPY=stub (Makefile): an object that defines memcpy is
 * linked before libc, so it replaces the C library's version for the whole
 * image. Built at -Os with -fno-builtin and
 * -fno-tree-loop-distribute-patterns, so GCC keeps the loop instead of
 * turning it back into a call to memcpy.
 */
#include <stddef.h>

void *memcpy(void *__restrict dst0, const void *__restrict src0, size_t len0)
{
    char *dst = (char *)dst0;
    const char *src = (const char *)src0;
    while (len0--)
        *dst++ = *src++;
    return dst0;
}
