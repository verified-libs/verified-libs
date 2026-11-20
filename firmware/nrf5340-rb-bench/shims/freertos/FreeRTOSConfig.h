/* FreeRTOSConfig.h for building FreeRTOS's stream_buffer.c alone (no
 * scheduler): static allocation only, task notifications on (the stream
 * buffer uses them to wake a blocked task; with zero timeouts and no tasks
 * none is ever blocked), assertions off as in a release build. */
#pragma once
#define configUSE_PREEMPTION                  1
#define configCPU_CLOCK_HZ                    64000000u   /* not used by the stream buffer */
#define configTICK_RATE_HZ                    1000u
#define configMAX_PRIORITIES                  2
#define configMINIMAL_STACK_SIZE              128
#define configTICK_TYPE_WIDTH_IN_BITS         TICK_TYPE_WIDTH_32_BITS
#define configUSE_IDLE_HOOK                   0
#define configUSE_TICK_HOOK                   0
#define configSUPPORT_STATIC_ALLOCATION       1
#define configSUPPORT_DYNAMIC_ALLOCATION      0
#define configUSE_TASK_NOTIFICATIONS          1
#define configTASK_NOTIFICATION_ARRAY_ENTRIES 1
#define configUSE_STREAM_BUFFERS              1
#define configUSE_SB_COMPLETED_CALLBACK       0
#define configUSE_TRACE_FACILITY              0
#define configUSE_MUTEXES                     0
#define configUSE_TIMERS                      0
