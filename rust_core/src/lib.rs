//! ByteToken Native Core — Rust Implementation
//! =============================================
//! High-performance bit-manipulation for ByteToken encode/decode.
//! Compiled as a Python extension via PyO3.
//!
//! Build: `maturin develop` (requires maturin: `pip install maturin`)

use pyo3::prelude::*;
use pyo3::types::PyBytes;
use numpy::{IntoPyArray, PyArray1};

/// Encode raw bytes into atom indices using bit-chunking.
///
/// Returns a numpy array where the first element is padding count.
#[pyfunction]
#[pyo3(signature = (data, bit_width))]
fn encode<'py>(py: Python<'py>, data: &[u8], bit_width: u32) -> Bound<'py, PyArray1<u32>> {
    if data.is_empty() {
        return vec![0].into_pyarray_bound(py);
    }

    let total_bits = data.len() * 8;
    let bw = bit_width as usize;
    let mask = (1u32 << bw) - 1;

    // Calculate padding
    let pad = (bw - total_bits % bw) % bw;
    let num_chunks = (total_bits + pad) / bw;

    // Pre-allocate output and get raw pointer for zero-cost writes
    let mut result: Vec<u32> = vec![0; num_chunks + 1];
    
    unsafe {
        let ptr = result.as_mut_ptr();
        *ptr = pad as u32; // metadata
        let mut out_pos = 1;

        if bw == 15 {
            let mut chunks = data.chunks_exact(15);
            for chunk in &mut chunks {
                let mut buf = [0u8; 16];
                buf[1..16].copy_from_slice(chunk);
                let val = u128::from_be_bytes(buf);
                
                *ptr.add(out_pos) = ((val >> 105) as u32) & 0x7FFF;
                *ptr.add(out_pos+1) = ((val >> 90) as u32) & 0x7FFF;
                *ptr.add(out_pos+2) = ((val >> 75) as u32) & 0x7FFF;
                *ptr.add(out_pos+3) = ((val >> 60) as u32) & 0x7FFF;
                *ptr.add(out_pos+4) = ((val >> 45) as u32) & 0x7FFF;
                *ptr.add(out_pos+5) = ((val >> 30) as u32) & 0x7FFF;
                *ptr.add(out_pos+6) = ((val >> 15) as u32) & 0x7FFF;
                *ptr.add(out_pos+7) = (val as u32) & 0x7FFF;
                out_pos += 8;
            }
            
            // handle remainder using the generic accumulator logic
            let mut accumulator: u64 = 0;
            let mut acc_bits: usize = 0;
            for &byte in chunks.remainder() {
                accumulator = (accumulator << 8) | byte as u64;
                acc_bits += 8;
                while acc_bits >= 15 {
                    acc_bits -= 15;
                    *ptr.add(out_pos) = ((accumulator >> acc_bits) as u32) & 0x7FFF;
                    out_pos += 1;
                    accumulator &= (1u64 << acc_bits) - 1;
                }
            }
            if acc_bits > 0 {
                accumulator <<= 15 - acc_bits;
                *ptr.add(out_pos) = (accumulator as u32) & 0x7FFF;
            }
        } else {
            // generic fallback
            let mut accumulator: u128 = 0;
            let mut acc_bits: usize = 0;

            let mut chunks = data.chunks_exact(8);
            for chunk in &mut chunks {
                let val = u64::from_be_bytes(chunk.try_into().unwrap());
                accumulator = (accumulator << 64) | (val as u128);
                acc_bits += 64;

                while acc_bits >= bw {
                    acc_bits -= bw;
                    *ptr.add(out_pos) = ((accumulator >> acc_bits) as u32) & mask;
                    out_pos += 1;
                    accumulator &= (1u128 << acc_bits) - 1;
                }
            }
            
            for &byte in chunks.remainder() {
                accumulator = (accumulator << 8) | byte as u128;
                acc_bits += 8;

                while acc_bits >= bw {
                    acc_bits -= bw;
                    *ptr.add(out_pos) = ((accumulator >> acc_bits) as u32) & mask;
                    out_pos += 1;
                    accumulator &= (1u128 << acc_bits) - 1;
                }
            }

            if acc_bits > 0 {
                accumulator <<= bw - acc_bits;
                *ptr.add(out_pos) = (accumulator as u32) & mask;
            }
        }
    }

    result.into_pyarray_bound(py)
}

/// Decode atom indices back to raw bytes.
///
/// First element of indices must be the padding count.
#[pyfunction]
fn decode(py: Python, indices: Vec<u32>, bit_width: u32) -> PyObject {
    if indices.len() <= 1 {
        return PyBytes::new_bound(py, &[]).into();
    }

    let pad = indices[0] as usize;
    let bw = bit_width as usize;
    let mask = (1u32 << bw) - 1;

    let total_bits = (indices.len() - 1) * bw;
    let data_bits = if pad < total_bits { total_bits - pad } else { 0 };
    let num_bytes = data_bits / 8;

    let mut result = Vec::with_capacity(num_bytes);
    let mut accumulator: u64 = 0;
    let mut acc_bits: usize = 0;

    for &idx in &indices[1..] {
        accumulator = (accumulator << bw) | (idx & mask) as u64;
        acc_bits += bw;

        while acc_bits >= 8 && result.len() < num_bytes {
            acc_bits -= 8;
            result.push(((accumulator >> acc_bits) & 0xFF) as u8);
            accumulator &= (1u64 << acc_bits) - 1;
        }
    }

    PyBytes::new_bound(py, &result).into()
}

/// Calculate CRC-32 checksum.
#[pyfunction]
fn crc32(data: &[u8]) -> u32 {
    crc32fast::hash(data)
}

/// Python module definition.
#[pymodule]
fn bytetoken_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode, m)?)?;
    m.add_function(wrap_pyfunction!(decode, m)?)?;
    m.add_function(wrap_pyfunction!(crc32, m)?)?;
    Ok(())
}
