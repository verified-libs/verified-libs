/* The host build of CMSIS-RTX's pool (check 1 of the pool pre-checks): the
 * device header RTX includes (CMSIS_device_header), for x86-64 instead of a
 * Cortex-M. It is the only thing that differs from the Cortex-M build; the
 * library files are compiled as they are.
 *
 * The host build is the Armv6-M variant (the compiler line defines
 * __ARM_ARCH_6M__, so rtx_core_cm.h sets EXCLUSIVE_ACCESS to 0): the pool's
 * free list with interrupts off, the C code a Cortex-M0+ runs. The LDREX/STREX
 * variant is inline assembly for Arm and does not run here (check 2).
 *
 * What it gives, and what RTX uses it for:
 *   - __get_PRIMASK, __disable_irq, __enable_irq: the pool's interrupt-off
 *     section. "Interrupts off" is a flag, counted through the pilot test's
 *     pilot_irq_disable/pilot_irq_restore, as the ThreadX host port does.
 *   - __get_IPSR, __get_CONTROL, __set_CONTROL, __get_BASEPRI, __CLZ, IRQn_Type,
 *     NVIC_GetPriorityGrouping, SCB (SHPR, ICSR): used only by inline
 *     functions of rtx_core_cm.h that the pool's three functions do not call
 *     (IsException, SetPendSV and the like); they are here so that the header
 *     compiles. They return 0, and SCB is an unused variable.
 *   - __STATIC_INLINE, __WEAK, __ASM, __NO_RETURN: the compiler macros of
 *     cmsis_compiler.h for gcc. Inline assembly in functions the pool does
 *     not call is never emitted. */
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

unsigned pilot_irq_disable(void);
void pilot_irq_restore(unsigned was);
static uint32_t host_primask;
static inline uint32_t __get_PRIMASK(void) { return host_primask; }
static inline void __disable_irq(void) { host_primask = 1; (void)pilot_irq_disable(); }
static inline void __enable_irq(void) { host_primask = 0; pilot_irq_restore(0); }

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
