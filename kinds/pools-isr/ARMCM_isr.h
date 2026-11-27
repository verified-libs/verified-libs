/* The device header CMSIS-RTX includes (CMSIS_device_header), for the
 * concurrency check (contract.c): a copy of ../pools/shims/host/ARMCM_host.h (the
 * first series' host header, which stays as it is) with one change. There,
 * PRIMASK is a variable of the header beside the test's counted flag, which is
 * right for one context; with an interrupt at every instruction it is not: an
 * interrupt could come between the two (inside __disable_irq, which is one
 * instruction on a Cortex-M) and read a PRIMASK that main has set and the
 * flag has not. Here PRIMASK is the check's own flag, the one
 * pool_irq_disable/pool_irq_restore set: __get_PRIMASK reads it,
 * __disable_irq sets it, __enable_irq clears it (and takes an interrupt held
 * pending), each one step, as cpsid and cpsie are. Everything else is as in
 * ARMCM_host.h. */
#ifndef ARMCM_HOST_H
#define ARMCM_HOST_H
#include <stdint.h>

#define __STATIC_INLINE static inline
#define __STATIC_FORCEINLINE static inline __attribute__((always_inline))
#define __WEAK __attribute__((weak))
#define __ASM __asm__
#define __NO_RETURN __attribute__((__noreturn__))
#define __USED __attribute__((used))
#define __ALIGNED(x) __attribute__((aligned(x)))
#define __INLINE inline
#define __PACKED __attribute__((packed))

unsigned pool_irq_disable(void);
void pool_irq_restore(unsigned was);
unsigned pool_irq_state(void);
static inline uint32_t __get_PRIMASK(void) { return pool_irq_state(); }
static inline void __disable_irq(void) { (void)pool_irq_disable(); }
static inline void __enable_irq(void) { pool_irq_restore(0); }

static inline uint32_t __get_IPSR(void) { return 0; }
static inline uint32_t __get_CONTROL(void) { return 0; }
static inline void __set_CONTROL(uint32_t v) { (void)v; }
static inline uint32_t __get_BASEPRI(void) { return 0; }
static inline uint32_t NVIC_GetPriorityGrouping(void) { return 0; }
typedef struct { volatile uint32_t ICSR; volatile uint32_t SHPR[3]; } host_SCB_Type;
static host_SCB_Type host_scb;
#define SCB (&host_scb)
#define SCB_ICSR_PENDSVSET_Msk (1UL << 28)
#define SCB_ICSR_PENDSVCLR_Msk (1UL << 27)
typedef enum { NonMaskableInt_IRQn = -14, SVCall_IRQn = -5, PendSV_IRQn = -2, SysTick_IRQn = -1 } IRQn_Type;
/* __CLZ: used by svcRtxMemoryPoolNew (the kernel's object creation, not
 * called here); the same meaning as the Arm instruction, 32 for 0. */
static inline uint32_t __CLZ(uint32_t v) { return v ? (uint32_t)__builtin_clz(v) : 32u; }
#endif
