/* The CMSIS-Core header C_Allocator's ALLOC_LOCK_CMSIS_RTOS2 option includes
 * (src/LockGuard.cpp:104-113 at 497b465), for the concurrency check on the
 * host (kinds/pools-isr/contract.c, CAL_LOCK;
 * site/content/method-pools.md, "C_Allocator twice"). The option uses three
 * functions of CMSIS-Core; here they are the check's own interrupts-off flag,
 * as kinds/pools-isr/ARMCM_isr.h makes them for CMSIS-RTX:
 *   __get_PRIMASK   reads the flag (mrs primask);
 *   __disable_irq   sets it (cpsid i), one step;
 *   __set_PRIMASK   puts the saved value back (msr primask) and, when that
 *                   value is 0, takes an interrupt held pending.
 * With CAL_LOCK_BROKEN, __disable_irq does nothing: the control, which the
 * check must catch. On the boards the option takes CMSIS 6's own header. */
#ifndef VL_CAL_LOCK_CMSIS_COMPILER_H
#define VL_CAL_LOCK_CMSIS_COMPILER_H
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif
unsigned pool_irq_disable(void);
void pool_irq_restore(unsigned was);
unsigned pool_irq_state(void);
#ifdef __cplusplus
}
#endif

static inline uint32_t __get_PRIMASK(void) { return pool_irq_state(); }
#if CAL_LOCK_BROKEN
static inline void __disable_irq(void) {}
#else
static inline void __disable_irq(void) { (void)pool_irq_disable(); }
#endif
static inline void __set_PRIMASK(uint32_t v) { pool_irq_restore((unsigned)v); }
#endif
