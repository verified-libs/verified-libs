/* The pools kind's bench.h (as the CRC kind's). firmware/common/<board>/board.h
 * includes "bench.h" for the operation type its time_call() times; this file
 * gives it that type, so the board support is used unchanged and nothing
 * under firmware/ is touched. rb_op is the type of the pool operations of
 * ../pool.h: uint32_t op(uintptr_t a, uintptr_t b). */
#pragma once
#include <stdint.h>

typedef uint32_t (*rb_op)(uintptr_t a, uintptr_t b);
