/* Interrupt masking on the host, for the contract check (contract.cpp).
 * vl_masked plays PRIMASK: while it is set, an interrupt point is held
 * pending and taken when the mask is cleared, as a Cortex-M takes a pending
 * interrupt right after "msr primask" / "cpsie i". */
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif
extern volatile uint32_t vl_masked;
void vl_irq_unmasked(void);   /* runs the interrupts held pending */

static inline uint32_t host_irq_save(void)
{
    uint32_t p = vl_masked;
    vl_masked = 1;
    __asm__ volatile("" ::: "memory");
    return p;
}
static inline void host_irq_restore(uint32_t p)
{
    __asm__ volatile("" ::: "memory");
    vl_masked = p;
    if (!p) vl_irq_unmasked();
}
extern volatile int vl_in_isr;   /* set while the contract check runs an interrupt's call */
/* The Cortex-M instructions, as hostify.py rewrites them */
static inline uint32_t vl_get_ipsr(void) { return vl_in_isr ? 16u : 0u; }   /* exception number of an IRQ, else 0 */
static inline uint32_t vl_get_primask(void) { return vl_masked; }
static inline void vl_cpsid(void) { vl_masked = 1; __asm__ volatile("" ::: "memory"); }
static inline void vl_cpsie(void) { __asm__ volatile("" ::: "memory"); vl_masked = 0; vl_irq_unmasked(); }
static inline void vl_set_primask(uint32_t p) { __asm__ volatile("" ::: "memory"); vl_masked = p; if (!p) vl_irq_unmasked(); }
#ifdef __cplusplus
}
/* LockImpl for pxq's Topology::MPSC/SPMC/MPMC (the interface of its
 * PrimaskLock: lock() returns the old state, unlock() restores it). */
struct HostLock {
    static inline uint32_t lock() { return host_irq_save(); }
    static inline void unlock(uint32_t p) { host_irq_restore(p); }
};
#endif
