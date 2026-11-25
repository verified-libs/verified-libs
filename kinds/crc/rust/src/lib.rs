//! The crc crate's CRC-32/ISO-HDLC with a table of 256 entries (`Table<1>`,
//! the crate's default), behind a C interface for the CRC kind's adapter
//! (adapter_rust.c). The table is computed at compile time (`Crc::new` is a
//! `const fn`) and lies in flash on a board.
//!
//! On a board (target_os = "none") the crate is `no_std` with a panic handler
//! that stops; on the host it links the standard library, for the host test
//! and Miri.
#![cfg_attr(target_os = "none", no_std)]

#[cfg(target_os = "none")]
#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    loop {}
}

use crc::{Crc, Digest, Table, CRC_32_ISO_HDLC};

static CRC32: Crc<u32, Table<1>> = Crc::<u32, Table<1>>::new(&CRC_32_ISO_HDLC);
static mut DIGEST: Option<Digest<'static, u32, Table<1>>> = None;

/// # Safety
/// `ptr` must point to `len` readable bytes (or `len` is 0).
#[no_mangle]
pub unsafe extern "C" fn vl_crc_rs_crc32(ptr: *const u8, len: usize) -> u32 {
    let bytes = if len == 0 { &[][..] } else { core::slice::from_raw_parts(ptr, len) };
    CRC32.checksum(bytes)
}

/// Starts a message (one at a time).
#[no_mangle]
pub extern "C" fn vl_crc_rs_begin() {
    unsafe { *core::ptr::addr_of_mut!(DIGEST) = Some(CRC32.digest()) };
}

/// # Safety
/// As `vl_crc_rs_crc32`; `vl_crc_rs_begin` was called first.
#[no_mangle]
pub unsafe extern "C" fn vl_crc_rs_update(ptr: *const u8, len: usize) {
    let bytes = if len == 0 { &[][..] } else { core::slice::from_raw_parts(ptr, len) };
    if let Some(d) = (*core::ptr::addr_of_mut!(DIGEST)).as_mut() {
        d.update(bytes);
    }
}

/// The CRC of every byte since `vl_crc_rs_begin`.
#[no_mangle]
pub extern "C" fn vl_crc_rs_final() -> u32 {
    match unsafe { (*core::ptr::addr_of_mut!(DIGEST)).take() } {
        Some(d) => d.finalize(),
        None => 0,
    }
}

#[cfg(test)]
mod tests {
    // Run under Miri (run.sh miri): the C interface against the catalogue's
    // check value, in one call and in two parts, with lengths that are not a
    // multiple of a word.
    use super::*;
    #[test]
    fn check_and_parts() {
        let m = b"123456789";
        assert_eq!(unsafe { vl_crc_rs_crc32(m.as_ptr(), m.len()) }, 0xCBF4_3926);
        for k in 0..=m.len() {
            vl_crc_rs_begin();
            unsafe {
                vl_crc_rs_update(m.as_ptr(), k);
                vl_crc_rs_update(m.as_ptr().add(k), m.len() - k);
            }
            assert_eq!(vl_crc_rs_final(), 0xCBF4_3926);
        }
        assert_eq!(unsafe { vl_crc_rs_crc32(core::ptr::null(), 0) }, 0);
    }
}
