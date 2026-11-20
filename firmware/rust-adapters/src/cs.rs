//! The critical-section implementation. Used by embassy-sync's
//! CriticalSectionRawMutex, by bbqueue on Cortex-M0+ (no compare-and-swap)
//! and by portable-atomic for heapless's mpmc::Queue there.
//!
//! One core (every board but the RP2350): mask interrupts with PRIMASK and
//! restore the previous state, which is what the cortex-m crate's
//! `critical-section-single-core` feature does (written out here so that the
//! build needs no further crates).
//!
//! Two cores (RP2350, built with `--cfg vl_two_cores`): PRIMASK as above and
//! a spin lock between the cores, as a multi-core critical-section
//! implementation for the RP2350 provides (the HALs use a hardware or
//! software spin lock). This one is a software lock (an atomic swap,
//! LDAEX/STREX in SRAM), like the Pico SDK's default spin locks on the
//! RP2350 (erratum RP2350-E2 concerns the SIO hardware spin locks). Nested
//! sections on one core take the lock once (a depth count per core).
//! Without the lock between the cores, embassy-sync's Pipe panics on two
//! cores ("already borrowed": its state is in a RefCell), observed
//! 2026-11-13 as a stalled SMP stress test.
//!
//! Host (built with `--cfg vl_host`, only for ../../verify/contract): the
//! contract check's interrupt-mask flag instead of PRIMASK, through two C
//! functions it provides.
#[cfg(not(vl_host))]
use core::arch::asm;
use core::sync::atomic::{Ordering, compiler_fence};

struct Cs;
critical_section::set_impl!(Cs);

#[cfg(vl_host)]
unsafe extern "C" {
    fn vl_host_irq_save() -> u32;
    fn vl_host_irq_restore(p: u32);
}

#[cfg(vl_host)]
#[inline(always)]
unsafe fn mask() -> bool {
    unsafe { vl_host_irq_save() == 0 } // interrupts were enabled
}

#[cfg(not(vl_host))]
#[inline(always)]
unsafe fn mask() -> bool {
    let primask: u32;
    unsafe {
        asm!("mrs {}, PRIMASK", out(reg) primask, options(nomem, nostack, preserves_flags));
        asm!("cpsid i", options(nomem, nostack, preserves_flags));
    }
    primask & 1 == 0 // interrupts were enabled
}

#[cfg(vl_two_cores)]
mod two {
    use core::sync::atomic::{AtomicBool, Ordering};
    pub static LOCK: AtomicBool = AtomicBool::new(false);
    pub static mut DEPTH: [u32; 2] = [0; 2];
    /// SIO CPUID (RP2350): 0 on core 0, 1 on core 1.
    #[inline(always)]
    pub fn core() -> usize {
        unsafe { (0xd000_0000 as *const u32).read_volatile() as usize & 1 }
    }
    #[inline(always)]
    pub fn take() {
        let c = core();
        unsafe {
            if DEPTH[c] == 0 {
                while LOCK.swap(true, Ordering::Acquire) {
                    while LOCK.load(Ordering::Relaxed) {}
                }
            }
            DEPTH[c] += 1;
        }
    }
    #[inline(always)]
    pub fn give() {
        let c = core();
        unsafe {
            DEPTH[c] -= 1;
            if DEPTH[c] == 0 {
                LOCK.store(false, Ordering::Release);
            }
        }
    }
}

unsafe impl critical_section::Impl for Cs {
    unsafe fn acquire() -> critical_section::RawRestoreState {
        let was_enabled = unsafe { mask() };
        compiler_fence(Ordering::SeqCst);
        #[cfg(vl_two_cores)]
        two::take();
        was_enabled
    }
    unsafe fn release(was_enabled: critical_section::RawRestoreState) {
        #[cfg(vl_two_cores)]
        two::give();
        compiler_fence(Ordering::SeqCst);
        if was_enabled {
            #[cfg(not(vl_host))]
            unsafe { asm!("cpsie i", options(nomem, nostack, preserves_flags)) };
            #[cfg(vl_host)]
            unsafe { vl_host_irq_restore(0) };
        }
    }
}
