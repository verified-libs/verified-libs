/* Pilot shim for RIOT's debug.h: memarray.c sets ENABLE_DEBUG 0, so DEBUG
 * prints nothing, as in RIOT. */
#pragma once
#define DEBUG(...) do { if (0) { } } while (0)
