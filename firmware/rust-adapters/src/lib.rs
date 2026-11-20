//! Adapters for the Rust ring buffers under test, with the C interface of
//! ../nrf5340-rb-bench/bench.h (rb_op: two pointer-sized arguments, u32
//! result). adapters.c builds the rb_adapter tables from these functions, so
//! the harness calls them through the same function pointers as the C and
//! C++ adapters, and they are timed by the same code.
//!
//! Every queue keeps RB_SLOTS - 1 bytes usable, like the other adapters,
//! except heapless's mpmc::Queue, whose size must be a power of two
//! (RB_SLOTS). push_n/pop_n: where a library has no block call, a loop over
//! the adapter's own single-byte push/pop (as BENCH_DEFINE_LOOP_N in C);
//! where a library's block call may move fewer bytes than fit (bbqueue's
//! grants stop at the end of the buffer, embassy-sync's Pipe says to call it
//! in a loop), it is called again until it moves nothing more.
#![no_std]
// One instance of each queue lives in a static, as in the C adapters; the
// harness calls push from one context and pop from the other.
#![allow(static_mut_refs)]

mod cs;

use core::mem::MaybeUninit;
use core::ptr::{addr_of, addr_of_mut};

/// RB_SLOTS of the C build (bench.h), passed by the Makefile.
const RB_SLOTS: usize = parse(match option_env!("VL_RB_SLOTS") {
    Some(s) => s,
    None => "128",
});
const fn parse(s: &str) -> usize {
    let b = s.as_bytes();
    let mut i = 0;
    let mut v = 0;
    while i < b.len() {
        v = v * 10 + (b[i] - b'0') as usize;
        i += 1;
    }
    v
}

#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    // The harness notices a board that stops answering ("stalled").
    loop {}
}

unsafe fn put(p: usize, v: u8) {
    unsafe { *(p as *mut u8) = v }
}
unsafe fn src<'a>(p: usize, n: usize) -> &'a [u8] {
    unsafe { core::slice::from_raw_parts(p as *const u8, n) }
}
unsafe fn dst<'a>(p: usize, n: usize) -> &'a mut [u8] {
    unsafe { core::slice::from_raw_parts_mut(p as *mut u8, n) }
}

macro_rules! loop_n {
    ($push_n:ident, $pop_n:ident, $push:ident, $pop:ident) => {
        #[unsafe(no_mangle)]
        #[inline(never)]
        pub extern "C" fn $push_n(p: usize, n: usize) -> u32 {
            let s = unsafe { src(p, n) };
            let mut i = 0;
            while i < n && $push(s[i] as usize, 0) != 0 {
                i += 1;
            }
            i as u32
        }
        #[unsafe(no_mangle)]
        #[inline(never)]
        pub extern "C" fn $pop_n(p: usize, n: usize) -> u32 {
            let mut i = 0;
            while i < n && $pop(p + i, 0) != 0 {
                i += 1;
            }
            i as u32
        }
    };
}

// ---- heapless 0.9.1 spsc::Queue<u8, RB_SLOTS> (capacity N - 1), split into
// Producer (push side) and Consumer (pop side) as its documentation shows.
mod hl {
    use super::*;
    use heapless::spsc::{Consumer, Producer, Queue};
    pub static mut Q: Queue<u8, RB_SLOTS> = Queue::new();
    pub static mut P: MaybeUninit<Producer<'static, u8>> = MaybeUninit::uninit();
    pub static mut C: MaybeUninit<Consumer<'static, u8>> = MaybeUninit::uninit();
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn hl_reset() {
    unsafe {
        addr_of_mut!(hl::Q).write(heapless::spsc::Queue::new());
        let (p, c) = (*addr_of_mut!(hl::Q)).split();
        hl::P.write(p);
        hl::C.write(c);
    }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn hl_push(v: usize, _: usize) -> u32 {
    unsafe { hl::P.assume_init_mut().enqueue(v as u8).is_ok() as u32 }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn hl_pop(p: usize, _: usize) -> u32 {
    match unsafe { hl::C.assume_init_mut().dequeue() } {
        Some(b) => {
            unsafe { put(p, b) };
            1
        }
        None => 0,
    }
}
loop_n!(hl_push_n, hl_pop_n, hl_push, hl_pop);

// ---- heapless 0.9.1 mpmc::Queue<u8, RB_SLOTS> (N a power of two, capacity
// N). Lock-free with compare-and-swap; on Cortex-M0+ through portable-atomic
// (feature portable-atomic-critical-section), as heapless documents.
static HLM: heapless::mpmc::Queue<u8, RB_SLOTS> = heapless::mpmc::Queue::new();
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn hlm_reset() {
    unsafe { (addr_of!(HLM) as *mut heapless::mpmc::Queue<u8, RB_SLOTS>).write(heapless::mpmc::Queue::new()) }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn hlm_push(v: usize, _: usize) -> u32 {
    HLM.enqueue(v as u8).is_ok() as u32
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn hlm_pop(p: usize, _: usize) -> u32 {
    match HLM.dequeue() {
        Some(b) => {
            unsafe { put(p, b) };
            1
        }
        None => 0,
    }
}
loop_n!(hlm_push_n, hlm_pop_n, hlm_push, hlm_pop);

// ---- bbqueue 0.6.1, stream producer/consumer on inline storage, polling
// (no async). Coordination: atomics (the "Churrasco" flavour) where the core
// has compare-and-swap, else critical sections ("Jerk"), as bbqueue selects
// by target_has_atomic.
mod bbq {
    use bbqueue::prod_cons::stream::{StreamGrantR, StreamGrantW};
    #[cfg(target_has_atomic = "ptr")]
    pub type Q = bbqueue::nicknames::Churrasco<{ super::RB_SLOTS - 1 }>;
    #[cfg(not(target_has_atomic = "ptr"))]
    pub type Q = bbqueue::nicknames::Jerk<{ super::RB_SLOTS - 1 }>;
    pub static mut BB: Q = Q::new();
    pub static mut WG: Option<StreamGrantW<&'static Q>> = None;
    pub static mut RG: Option<StreamGrantR<&'static Q>> = None;
    pub fn bb() -> &'static Q {
        unsafe { &*core::ptr::addr_of!(BB) }
    }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn bbq_reset() {
    unsafe {
        // no grant is alive here: forget them, then a fresh queue
        core::mem::forget(bbq::WG.take());
        core::mem::forget(bbq::RG.take());
        addr_of_mut!(bbq::BB).write(bbq::Q::new());
    }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn bbq_push(v: usize, _: usize) -> u32 {
    match bbq::bb().stream_producer().grant_exact(1) {
        Ok(mut g) => {
            g[0] = v as u8;
            g.commit(1);
            1
        }
        Err(_) => 0,
    }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn bbq_pop(p: usize, _: usize) -> u32 {
    match bbq::bb().stream_consumer().read() {
        Ok(g) => {
            unsafe { put(p, g[0]) };
            g.release(1);
            1
        }
        Err(_) => 0,
    }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn bbq_push_n(p: usize, n: usize) -> u32 {
    let s = unsafe { src(p, n) };
    let prod = bbq::bb().stream_producer();
    let mut done = 0;
    while done < n {
        match prod.grant_max_remaining(n - done) {
            Ok(mut g) => {
                let k = g.len();
                g.copy_from_slice(&s[done..done + k]);
                g.commit(k);
                done += k;
            }
            Err(_) => break,
        }
    }
    done as u32
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn bbq_pop_n(p: usize, n: usize) -> u32 {
    let d = unsafe { dst(p, n) };
    let cons = bbq::bb().stream_consumer();
    let mut done = 0;
    while done < n {
        match cons.read() {
            Ok(g) => {
                let k = g.len().min(n - done);
                d[done..done + k].copy_from_slice(&g[..k]);
                g.release(k);
                done += k;
            }
            Err(_) => break,
        }
    }
    done as u32
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn bbq_dma_wr_acquire(pp: usize, max: usize) -> u32 {
    match bbq::bb().stream_producer().grant_max_remaining(max) {
        Ok(mut g) => {
            let n = g.len();
            unsafe {
                *(pp as *mut *mut u8) = g.as_mut_ptr();
                bbq::WG = Some(g);
            }
            n as u32
        }
        Err(_) => 0,
    }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn bbq_dma_wr_commit(n: usize, _: usize) -> u32 {
    match unsafe { bbq::WG.take() } {
        Some(g) => {
            let k = n.min(g.len());
            g.commit(k);
            k as u32
        }
        None => 0,
    }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn bbq_dma_rd_acquire(pp: usize, max: usize) -> u32 {
    match bbq::bb().stream_consumer().read() {
        Ok(g) => {
            let n = g.len().min(max);
            unsafe {
                *(pp as *mut *const u8) = g.as_ptr();
                bbq::RG = Some(g);
            }
            n as u32
        }
        Err(_) => 0,
    }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn bbq_dma_rd_release(n: usize, _: usize) -> u32 {
    match unsafe { bbq::RG.take() } {
        Some(g) => {
            let k = n.min(g.len());
            g.release(k);
            k as u32
        }
        None => 0,
    }
}

// ---- embassy-sync 0.8.0 Pipe<CriticalSectionRawMutex, RB_SLOTS - 1>: a byte
// pipe whose state is guarded by a critical section (interrupts masked on
// this core: src/cs.rs). try_write / try_read are its non-async calls.
type Pipe = embassy_sync::pipe::Pipe<embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex, { RB_SLOTS - 1 }>;
static mut EMB: Pipe = Pipe::new();
fn emb() -> &'static Pipe {
    unsafe { &*addr_of!(EMB) }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn emb_reset() {
    unsafe { addr_of_mut!(EMB).write(Pipe::new()) }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn emb_push(v: usize, _: usize) -> u32 {
    emb().try_write(&[v as u8]).unwrap_or(0) as u32
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn emb_pop(p: usize, _: usize) -> u32 {
    let mut b = [0u8; 1];
    match emb().try_read(&mut b) {
        Ok(1) => {
            unsafe { put(p, b[0]) };
            1
        }
        _ => 0,
    }
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn emb_push_n(p: usize, n: usize) -> u32 {
    let s = unsafe { src(p, n) };
    let mut done = 0;
    while done < n {
        match emb().try_write(&s[done..]) {
            Ok(k) => done += k,
            Err(_) => break,
        }
    }
    done as u32
}
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn emb_pop_n(p: usize, n: usize) -> u32 {
    let d = unsafe { dst(p, n) };
    let mut done = 0;
    while done < n {
        match emb().try_read(&mut d[done..]) {
            Ok(k) => done += k,
            Err(_) => break,
        }
    }
    done as u32
}
