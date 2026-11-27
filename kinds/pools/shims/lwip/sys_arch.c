/* The port's protection for lwIP's memp (SYS_ARCH_PROTECT, include/lwip/sys.h):
 * interrupts off, as lwIP's own text suggests for an embedded system without an
 * OS ("by disabling interrupts for an embedded system"). This is our port, not
 * lwIP's code: lwIP leaves sys_arch_protect to the port. */
#include "pool.h"
#include "lwip/sys.h"
sys_prot_t sys_arch_protect(void) { return pool_irq_disable(); }
void sys_arch_unprotect(sys_prot_t pval) { pool_irq_restore(pval); }
