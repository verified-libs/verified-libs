/* Minimal stand-in for RT-Thread's kernel headers (rtdef.h, rtconfig.h,
 * rtthread.h, rtdevice.h), only what components/drivers/ipc/ringbuffer.c
 * and its header use. Types and macros as in RT-Thread's rtdef.h for a
 * 32-bit ARM target; RT_ALIGN_SIZE 8 (the Kconfig default); rt_memcpy is
 * memcpy (as with RT_KSERVICE_USING_STDLIB); RT_ASSERT off (no
 * RT_USING_DEBUG); no heap (RT_USING_HEAP not set). */
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>
typedef int8_t rt_int8_t;   typedef uint8_t rt_uint8_t;
typedef int16_t rt_int16_t; typedef uint16_t rt_uint16_t;
typedef int32_t rt_int32_t; typedef uint32_t rt_uint32_t;
typedef int rt_bool_t;      typedef long rt_base_t; typedef unsigned long rt_ubase_t;
typedef rt_ubase_t rt_size_t;
#define rt_inline static __inline
#define RT_NULL 0
#define RT_ALIGN_SIZE 8
#define RT_ALIGN_DOWN(size, align) ((size) & ~((align) - 1))
#define RT_ASSERT(EX) ((void)0)
#define RTM_EXPORT(symbol)
#define rt_memcpy memcpy
