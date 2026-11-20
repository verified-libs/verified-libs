/* Minimal port layer for FreeRTOS's stream_buffer.c without the scheduler.
 * Types as in FreeRTOS's GCC/ARM_CM* ports (portable/GCC/ARM_CM4F/portmacro.h,
 * V11.3.3). Critical sections: interrupts masked with PRIMASK (the real
 * Cortex-M3+ ports raise BASEPRI to configMAX_SYSCALL_INTERRUPT_PRIORITY,
 * which masks the same interrupts for an ISR allowed to call FreeRTOS APIs;
 * the M0+ ports use PRIMASK as here). Unlike the real ports, the nesting
 * count starts at 0, so critical sections work before a scheduler exists. */
#pragma once
#include <stdint.h>
#define portCHAR        char
#define portFLOAT       float
#define portDOUBLE      double
#define portLONG        long
#define portSHORT       short
#define portSTACK_TYPE  uint32_t
#define portBASE_TYPE   long
typedef portSTACK_TYPE StackType_t;
typedef long BaseType_t;
typedef unsigned long UBaseType_t;
typedef uint32_t TickType_t;
#define portMAX_DELAY              ((TickType_t)0xffffffffUL)
#define portTICK_TYPE_IS_ATOMIC    1
#define portSTACK_GROWTH           (-1)
#define portTICK_PERIOD_MS         ((TickType_t)1000 / configTICK_RATE_HZ)
#define portBYTE_ALIGNMENT         8
#define portDONT_DISCARD           __attribute__((used))
#define portNOP()                  __asm volatile("nop")
#define portINLINE                 __inline
#define portFORCE_INLINE           inline __attribute__((always_inline))
#define portMEMORY_BARRIER()       __asm volatile("" ::: "memory")
#define portYIELD()                do { } while (0)
#define portEND_SWITCHING_ISR(x)   do { (void)(x); } while (0)
#define portYIELD_FROM_ISR(x)      portEND_SWITCHING_ISR(x)
extern void vPortEnterCritical(void);
extern void vPortExitCritical(void);
extern uint32_t ulPortSetInterruptMask(void);
extern void vPortClearInterruptMask(uint32_t);
#define portENTER_CRITICAL()                      vPortEnterCritical()
#define portEXIT_CRITICAL()                       vPortExitCritical()
#define portDISABLE_INTERRUPTS()                  __asm volatile("cpsid i" ::: "memory")
#define portENABLE_INTERRUPTS()                   __asm volatile("cpsie i" ::: "memory")
#define portSET_INTERRUPT_MASK_FROM_ISR()         ulPortSetInterruptMask()
#define portCLEAR_INTERRUPT_MASK_FROM_ISR(x)      vPortClearInterruptMask(x)
#define portTASK_FUNCTION_PROTO(vFunction, pvParameters) void vFunction(void *pvParameters)
#define portTASK_FUNCTION(vFunction, pvParameters)       void vFunction(void *pvParameters)
