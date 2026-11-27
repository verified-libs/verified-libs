/* CMSIS-RTX's pool with EXCLUSIVE_ACCESS 1, the variant the Cortex-M4, M7 and
 * M33 boards run, for the host check (contract.c). Included after rtx_lib.h
 * (whose host build, with __ARM_ARCH_6M__, set EXCLUSIVE_ACCESS 0 and left out
 * the Arm assembly) and before RTX's own osRtxMemoryPoolAlloc/Free, which are
 * copied unchanged (../pools/extract.py). It switches those two to their
 * LDREX/STREX path and gives them the four functions of rtx_core_cm.h they
 * call there (v5.9.1, b566de4, Source/rtx_core_cm.h: atomic_inc32 lines
 * 706-735, atomic_dec32 821-850, atomic_link_get 931-964, atomic_link_put
 * 969-1001), transliterated into C on the exclusive-monitor model
 * (excl_host.h): one statement per instruction, the instruction in the
 * comment. That the transliteration matches the assembly is a reading, not a
 * check; the board sweep runs the assembly itself.
 *
 * RTX_EXCL_BROKEN=1: the control. atomic_link_get goes on as if its STREX had
 * stored, whatever it returned; the check must catch it. */
#undef EXCLUSIVE_ACCESS
#define EXCLUSIVE_ACCESS 1
#include "excl_host.h"
#ifndef RTX_EXCL_BROKEN
#define RTX_EXCL_BROKEN 0
#endif

static inline uint32_t atomic_inc32(uint32_t *mem)
{
    uint32_t ret, val;
    for (;;) {
        ret = vl_ldrex32(mem);                                   /* 1: ldrex ret,[mem] */
        val = ret + 1u;                                          /*    adds  val,ret,#1 */
        if (vl_strex32(val, mem) == 0) return ret;               /*    strex res,val,[mem]; cbz res,2f; b 1b */
    }
}
static inline uint32_t atomic_dec32(uint32_t *mem)
{
    uint32_t ret, val;
    for (;;) {
        ret = vl_ldrex32(mem);                                   /* 1: ldrex ret,[mem] */
        val = ret - 1u;                                          /*    subs  val,ret,#1 */
        if (vl_strex32(val, mem) == 0) return ret;               /*    strex res,val,[mem]; cbz res,2f; b 1b */
    }
}
static inline void *atomic_link_get(void **root)
{
    uintptr_t ret, val;
    for (;;) {
        ret = vl_ldrexp((volatile uintptr_t *)root);             /* 1: ldrex ret,[root] */
        if (ret == 0) { vl_clrex(); return 0; }                  /*    cbnz ret,2f; clrex; b 3f */
        val = *(volatile uintptr_t *)ret;                        /* 2: ldr   val,[ret] */
        uint32_t res = vl_strexp(val, (volatile uintptr_t *)root);   /* strex res,val,[root] */
        if (res == 0 || RTX_EXCL_BROKEN) return (void *)ret;     /*    cbz res,3f; b 1b */
    }
}
static inline void atomic_link_put(void **root, void *link)
{
    uintptr_t v1, v2;
    for (;;) {
        v1 = *(volatile uintptr_t *)root;                        /* 1: ldr   val1,[root] */
        *(volatile uintptr_t *)link = v1;                        /*    str   val1,[link] */
        __asm__ volatile("" ::: "memory");                       /*    dmb */
        v1 = vl_ldrexp((volatile uintptr_t *)root);              /*    ldrex val1,[root] */
        v2 = *(volatile uintptr_t *)link;                        /*    ldr   val2,[link] */
        if (v2 != v1) continue;                                  /*    cmp val2,val1; bne 1b */
        if (vl_strexp((uintptr_t)link, (volatile uintptr_t *)root) == 0) return;   /* strex; cbz res,2f; b 1b */
    }
}
