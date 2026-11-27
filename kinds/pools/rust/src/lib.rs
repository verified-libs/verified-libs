//! The C interface of the Rust pools (../adapter_rust.c builds the pool_adapter
//! of each from these functions). One pool of POOL_BLOCKS blocks of
//! POOL_BLOCK_SIZE bytes each, as pool.h; the block type is
//! `MaybeUninit<[u8; 32]>`, so that neither library copies a value into a block
//! when it hands it out. Each pool's state and blocks lie between two canary
//! arrays (`Guarded`), as POOL_GUARDED in pool.h.
#![cfg_attr(target_os = "none", no_std)]

#[cfg(target_os = "none")]
#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    loop {}
}

use core::mem::MaybeUninit;
use core::ptr::NonNull;

pub const POOL_BLOCKS: usize = 32;
pub const POOL_BLOCK_SIZE: usize = 32;
const CANARY_WORDS: usize = 4;
type Block = MaybeUninit<[u8; POOL_BLOCK_SIZE]>;

#[repr(C)]
pub struct Guarded<T> {
    pub canary_lo: [u32; CANARY_WORDS],
    pub v: T,
    pub canary_hi: [u32; CANARY_WORDS],
}

// ---------------------------------------------------------------- heapless
//
// heapless's BoxPool, with its singleton (BoxPoolImpl) and its blocks in a
// guarded static of ours instead of the one `box_pool!` declares: the macro
// expands to exactly this impl (src/pool/boxed.rs, `box_pool!`). A heapless Box
// cannot be made from a raw pointer, so the live Boxes are kept in a table
// indexed by the block's place in the array; the index is the adapter's cost,
// not heapless's, and is a few instructions on every call.

#[cfg(feature = "heapless-pool")]
mod hl {
    use super::*;
    use heapless::pool::boxed::{Box, BoxBlock, BoxPool, BoxPoolImpl};

    pub struct HlPool;
    #[repr(C)]
    pub struct State {
        pub pool: BoxPoolImpl<Block>,
        pub blocks: [BoxBlock<Block>; POOL_BLOCKS],
        pub live: [Option<Box<HlPool>>; POOL_BLOCKS],
        pub managed: bool,
    }
    pub static mut G: Guarded<State> = Guarded {
        canary_lo: [0; CANARY_WORDS],
        v: State {
            pool: BoxPoolImpl::new(),
            blocks: [const { BoxBlock::new() }; POOL_BLOCKS],
            live: [const { None }; POOL_BLOCKS],
            managed: false,
        },
        canary_hi: [0; CANARY_WORDS],
    };
    impl BoxPool for HlPool {
        type Data = Block;
        fn singleton() -> &'static BoxPoolImpl<Block> {
            unsafe { &(*core::ptr::addr_of!(G)).v.pool }
        }
    }
    fn index_of(p: usize) -> usize {
        let base = unsafe { core::ptr::addr_of!(G.v.blocks) } as usize;
        (p - base) / core::mem::size_of::<BoxBlock<Block>>()
    }
    pub fn init() {
        unsafe {
            let g = &mut *core::ptr::addr_of_mut!(G);
            for slot in g.v.live.iter_mut() {
                drop(slot.take()); // a held block goes back to the pool
            }
            if !g.v.managed {
                for b in g.v.blocks.iter_mut() {
                    HlPool::manage(&mut *(b as *mut BoxBlock<Block>));
                }
                g.v.managed = true;
            }
        }
    }
    pub fn alloc() -> usize {
        match HlPool::alloc(MaybeUninit::uninit()) {
            Ok(mut b) => {
                let p = (&mut *b) as *mut Block as usize;
                // get_mut, not indexing: no panic path (and no formatting code) in the adapter
                match unsafe { (*core::ptr::addr_of_mut!(G)).v.live.get_mut(index_of(p)) } {
                    Some(slot) => {
                        *slot = Some(b);
                        p
                    }
                    None => 0,
                }
            }
            Err(_) => 0,
        }
    }
    pub fn free(p: usize) -> u32 {
        let base = unsafe { core::ptr::addr_of!(G.v.blocks) } as usize;
        if p < base {
            return 0;
        }
        unsafe { (*core::ptr::addr_of_mut!(G)).v.live.get_mut(index_of(p)) }.and_then(|s| s.take()).map_or(0, |b| {
            drop(b);
            1
        })
    }
    pub fn region() -> (usize, usize) {
        let lo = unsafe { core::ptr::addr_of!(G.v.blocks) } as usize;
        (lo, lo + core::mem::size_of::<[BoxBlock<Block>; POOL_BLOCKS]>())
    }
    pub const ALIGN: usize = core::mem::align_of::<BoxBlock<Block>>();
}

// ------------------------------------------------------------- atomic-pool
//
// atomic-pool's Pool, with its storage in a guarded static of ours instead of
// the one `pool!` declares: the macro expands to exactly this impl
// (src/lib.rs, `pool!`). Box::into_raw and Box::from_raw carry a block across
// the C interface; no table is needed.

mod ap {
    use super::*;
    use atomic_pool::{Box, Pool, PoolStorageImpl};

    pub struct ApPool;
    type Storage = PoolStorageImpl<Block, POOL_BLOCKS, { POOL_BLOCKS.div_ceil(atomic_pool::ATOMICU32_BITS) }>;
    pub static mut G: Guarded<Storage> = Guarded { canary_lo: [0; CANARY_WORDS], v: Storage::new(), canary_hi: [0; CANARY_WORDS] };
    impl Pool for ApPool {
        type Item = Block;
        type Storage = Storage;
        fn get() -> &'static Storage {
            unsafe { &(*core::ptr::addr_of!(G)).v }
        }
    }
    pub fn alloc() -> usize {
        Box::<ApPool>::new(MaybeUninit::uninit()).map_or(0, |b| Box::into_raw(b).as_ptr() as usize)
    }
    pub fn free(p: usize) -> u32 {
        match NonNull::new(p as *mut Block) {
            Some(nn) => {
                drop(unsafe { Box::<ApPool>::from_raw(nn) });
                1
            }
            None => 0,
        }
    }
    pub fn region() -> (usize, usize) {
        let lo = unsafe { core::ptr::addr_of!(G.v) } as usize;
        (lo, lo + core::mem::size_of::<Storage>())
    }
    pub const ALIGN: usize = core::mem::align_of::<Block>();
}

// ------------------------------------------------------------- C interface

#[cfg(feature = "heapless-pool")]
#[no_mangle]
pub extern "C" fn vl_heapless_init() {
    hl::init()
}
#[cfg(feature = "heapless-pool")]
#[no_mangle]
pub extern "C" fn vl_heapless_alloc(_a: usize, _b: usize) -> usize {
    hl::alloc()
}
#[cfg(feature = "heapless-pool")]
#[no_mangle]
pub extern "C" fn vl_heapless_free(a: usize, _b: usize) -> u32 {
    hl::free(a)
}
#[cfg(feature = "heapless-pool")]
#[no_mangle]
pub extern "C" fn vl_heapless_region(lo: &mut usize, hi: &mut usize) {
    (*lo, *hi) = hl::region();
}
#[cfg(feature = "heapless-pool")]
#[no_mangle]
pub extern "C" fn vl_heapless_align() -> u32 {
    hl::ALIGN as u32
}
#[cfg(feature = "heapless-pool")]
#[no_mangle]
pub extern "C" fn vl_heapless_canaries(lo: &mut *mut u32, hi: &mut *mut u32) {
    unsafe {
        *lo = core::ptr::addr_of_mut!(hl::G.canary_lo) as *mut u32;
        *hi = core::ptr::addr_of_mut!(hl::G.canary_hi) as *mut u32;
    }
}

/// atomic-pool has no reset: init() is empty; the test gives every block back
/// at the end of each run, before the next init.
#[no_mangle]
pub extern "C" fn vl_atomic_pool_init() {}
#[no_mangle]
pub extern "C" fn vl_atomic_pool_alloc(_a: usize, _b: usize) -> usize {
    ap::alloc()
}
#[no_mangle]
pub extern "C" fn vl_atomic_pool_free(a: usize, _b: usize) -> u32 {
    ap::free(a)
}
#[no_mangle]
pub extern "C" fn vl_atomic_pool_region(lo: &mut usize, hi: &mut usize) {
    (*lo, *hi) = ap::region();
}
#[no_mangle]
pub extern "C" fn vl_atomic_pool_align() -> u32 {
    ap::ALIGN as u32
}
#[no_mangle]
pub extern "C" fn vl_atomic_pool_canaries(lo: &mut *mut u32, hi: &mut *mut u32) {
    unsafe {
        *lo = core::ptr::addr_of_mut!(ap::G.canary_lo) as *mut u32;
        *hi = core::ptr::addr_of_mut!(ap::G.canary_hi) as *mut u32;
    }
}

// ------------------------------------------------------------- Miri
//
// `make miri`: the C interface of both pools under Miri (a Rust interpreter
// that reports undefined behaviour): random allocs and frees with a fixed
// seed, each block written in full and checked at its free, capacity exactly
// POOL_BLOCKS, no block twice, every block back at the end. The host test
// (../test_pool.c) runs the same checks natively and many more steps.
#[cfg(test)]
mod tests {
    use super::*;

    fn exercise(init: extern "C" fn(), alloc: extern "C" fn(usize, usize) -> usize, free: extern "C" fn(usize, usize) -> u32) {
        init();
        let mut held: [(usize, u8); POOL_BLOCKS] = [(0, 0); POOL_BLOCKS];
        let mut n = 0usize;
        let mut rng: u32 = 0x9E37_79B9;
        let mut stamp: u8 = 0;
        for _ in 0..600 {
            rng ^= rng << 13;
            rng ^= rng >> 17;
            rng ^= rng << 5;
            if n == 0 || (n <= POOL_BLOCKS && rng & 1 == 1) {
                let p = alloc(0, 0);
                if n == POOL_BLOCKS {
                    assert_eq!(p, 0, "a block beyond POOL_BLOCKS");
                    continue;
                }
                assert_ne!(p, 0, "no block although fewer than POOL_BLOCKS are held");
                assert!(held[..n].iter().all(|&(q, _)| q != p), "a block handed out twice");
                stamp = stamp.wrapping_add(1);
                unsafe { core::ptr::write_bytes(p as *mut u8, stamp, POOL_BLOCK_SIZE) };
                held[n] = (p, stamp);
                n += 1;
            } else {
                let k = (rng as usize / 2) % n;
                let (p, s) = held[k];
                let ok = unsafe { core::slice::from_raw_parts(p as *const u8, POOL_BLOCK_SIZE) }.iter().all(|&b| b == s);
                assert!(ok, "a held block was changed");
                assert_eq!(free(p, 0), 1);
                held[k] = held[n - 1];
                n -= 1;
            }
        }
        while n > 0 {
            n -= 1;
            assert_eq!(free(held[n].0, 0), 1);
        }
        for i in 0..POOL_BLOCKS {
            held[i].0 = alloc(0, 0);
            assert_ne!(held[i].0, 0, "a block lost");
        }
        assert_eq!(alloc(0, 0), 0);
        for h in held.iter() {
            assert_eq!(free(h.0, 0), 1);
        }
    }

    // Not under Miri: there heapless's pool reaches its LL/SC path (Arm inline
    // assembly, src/pool/treiber/llsc.rs line 133, "ldrex"), which Miri cannot
    // run; the native host build takes its CAS path (treiber/cas.rs). Seen on
    // 2026-11-26; the likely cause is heapless's build-script probe for `clrex`
    // (build.rs), which is not code-generated under cargo-miri.
    #[test]
    #[cfg(feature = "heapless-pool")]
    #[cfg_attr(miri, ignore)]
    fn heapless_pool() {
        exercise(vl_heapless_init, vl_heapless_alloc, vl_heapless_free);
    }

    #[test]
    fn atomic_pool() {
        exercise(vl_atomic_pool_init, vl_atomic_pool_alloc, vl_atomic_pool_free);
    }
}
