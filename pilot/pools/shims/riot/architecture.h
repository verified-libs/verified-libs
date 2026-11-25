/* Pilot shim for RIOT's core header, only what sys/memarray/memarray.c
 * uses: the printf format of size_t in its DEBUG lines. */
#pragma once
#include <inttypes.h>
#include <stdbool.h>
#define PRIuSIZE "zu"
