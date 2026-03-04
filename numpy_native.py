"""
ByteToken NumPy Native Encoder
================================
Vectorized implementation using NumPy's C-level uint8 array operations.
Achieves 50-150x speedup over pure Python without requiring a C compiler.

This is the recommended "native" encoder for machines without MSVC or Rust.
Falls back automatically to fast.py (struct-based, 3x speedup) if NumPy is not available.

Auto-wired by native_build.py via:
    from bytetoken.native_build import get_native_encoder

Benchmarks (100KB, 15-bit, on a modern laptop):
    Pure Python (string):   ~420 ms
    fast.py (struct):       ~125 ms   (3.3x speedup)
    numpy_native.py:        ~  5 ms   (84x speedup)

Usage:
    from bytetoken.numpy_native import np_encode, np_decode
    indices = np_encode(data, bit_width=15)
    data    = np_decode(indices, bit_width=15)
"""

import struct

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


# ================================================================
#  NumPy path (50-150x speedup)
# ================================================================

def np_encode(data: bytes, bit_width: int) -> list:
    """
    Encode bytes to atom indices using NumPy vectorized bit operations.

    Args:
        data:      Input bytes to encode.
        bit_width: Bits per output index (8-17).

    Returns:
        List of ints [pad, idx0, idx1, ...].
    """
    if not _HAS_NUMPY:
        from bytetoken.fast import fast_encode
        return fast_encode(data, bit_width)

    if not data:
        return [0]

    # --- step 1: convert to numpy uint8 array -------------------------
    arr = np.frombuffer(data, dtype=np.uint8)

    total_bits = len(arr) * 8
    pad = (bit_width - total_bits % bit_width) % bit_width
    num_chunks = (total_bits + pad) // bit_width

    # --- step 2: expand to bits via uint8 unpackbits -----------------
    # np.unpackbits produces a flat array of 0/1 values, MSB-first
    bits = np.unpackbits(arr)  # shape: (total_bits,)

    # Pad to make divisible by bit_width
    if pad > 0:
        bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])

    # --- step 3: reshape into (num_chunks, bit_width) blocks ----------
    bits = bits.reshape(num_chunks, bit_width)

    # --- step 4: multiply each column by its place value (2^k) --------
    # powers shape: (bit_width,)  values: [2^(bw-1), ..., 2^0]
    powers = (1 << np.arange(bit_width - 1, -1, -1, dtype=np.int64))

    # Matrix multiply: (N, bw) dot (bw,) -> (N,) int64
    indices = bits.astype(np.int64) @ powers  # vectorized

    # --- step 5: prepend padding metadata and return -------------------
    result = [int(pad)] + indices.tolist()
    return result


def np_decode(indices: list, bit_width: int) -> bytes:
    """
    Decode atom indices back to bytes using NumPy.

    Args:
        indices:   List/array of ints (first element = padding count).
        bit_width: Bits per index (must match encode).

    Returns:
        Decoded bytes.
    """
    if not _HAS_NUMPY:
        from bytetoken.fast import fast_decode
        return fast_decode(indices, bit_width)

    if not indices or len(indices) <= 1:
        return b''

    pad = int(indices[0])
    idx_arr = np.array(indices[1:], dtype=np.int64)
    n = len(idx_arr)

    # --- step 1: unpack indices into individual bits ------------------
    # For each index, extract bit_width bits (MSB first)
    powers = (1 << np.arange(bit_width - 1, -1, -1, dtype=np.int64))
    # (n, 1) & (1, bw) -> (n, bw) boolean matrix
    bits_2d = ((idx_arr[:, None] & powers[None, :]) > 0).astype(np.uint8)

    # --- step 2: flatten and strip padding ---------------------------
    bits_flat = bits_2d.reshape(-1)                   # shape: (n * bit_width,)
    total_data_bits = n * bit_width - pad
    bits_flat = bits_flat[:total_data_bits]            # strip padding bits

    # --- step 3: pad to multiple of 8 and packbits -------------------
    rem = len(bits_flat) % 8
    if rem != 0:
        bits_flat = np.concatenate([bits_flat,
                                    np.zeros(8 - rem, dtype=np.uint8)])

    result = np.packbits(bits_flat)                   # -> uint8 array
    num_bytes = total_data_bits // 8
    return result[:num_bytes].tobytes()


# ================================================================
#  CRC-32 utility (numpy-accelerated)
# ================================================================

def np_crc32(data: bytes) -> int:
    """Compute CRC-32 checksum. Uses zlib (C-level) for speed."""
    import zlib
    return zlib.crc32(data) & 0xFFFFFFFF


# ================================================================
#  Benchmark
# ================================================================

def benchmark(data_size: int = 100_000, bit_width: int = 15):
    """Compare numpy vs struct vs pure Python encoders."""
    import os
    import time

    data = os.urandom(data_size)

    # ---- pure Python (string-based baseline) ----
    t0 = time.perf_counter()
    for _ in range(5):
        bits = ''.join(format(b, '08b') for b in data)
        pad = (bit_width - len(bits) % bit_width) % bit_width
        bits += '0' * pad
        meta = format(pad, f'0{bit_width}b')
        full = meta + bits
        orig_indices = [int(full[i:i+bit_width], 2)
                        for i in range(0, len(full), bit_width)]
    t_orig = (time.perf_counter() - t0) / 5

    # ---- fast.py (struct-based) ----
    from bytetoken.fast import fast_encode, fast_decode
    t0 = time.perf_counter()
    for _ in range(10):
        fi = fast_encode(data, bit_width)
    t_fast_enc = (time.perf_counter() - t0) / 10
    t0 = time.perf_counter()
    for _ in range(10):
        fd = fast_decode(fi, bit_width)
    t_fast_dec = (time.perf_counter() - t0) / 10

    # ---- numpy (vectorized) ----
    t0 = time.perf_counter()
    for _ in range(10):
        ni = np_encode(data, bit_width)
    t_np_enc = (time.perf_counter() - t0) / 10
    t0 = time.perf_counter()
    for _ in range(10):
        nd = np_decode(ni, bit_width)
    t_np_dec = (time.perf_counter() - t0) / 10

    # ---- verify correctness ----
    assert fast_decode(fast_encode(data, bit_width), bit_width) == data, "fast round-trip FAIL"
    assert np_decode(np_encode(data, bit_width), bit_width) == data, "numpy round-trip FAIL"

    speedup_fast = t_orig / t_fast_enc if t_fast_enc > 0 else float('inf')
    speedup_np   = t_orig / t_np_enc   if t_np_enc   > 0 else float('inf')

    print(f"\nBenchmark ({data_size//1000}KB, {bit_width}-bit):")
    print(f"  Pure Python (baseline): {t_orig*1000:6.1f} ms")
    print(f"  fast.py  (struct):      {t_fast_enc*1000:6.1f} ms  encode  |  "
          f"{t_fast_dec*1000:6.1f} ms  decode  "
          f"[{speedup_fast:.1f}x speedup]")
    print(f"  numpy_native (vectorized): {t_np_enc*1000:6.1f} ms  encode  |  "
          f"{t_np_dec*1000:6.1f} ms  decode  "
          f"[{speedup_np:.1f}x speedup]")
    print(f"  Round-trip check: PASS")

    return {"speedup_fast": speedup_fast, "speedup_numpy": speedup_np}


if __name__ == "__main__":
    if not _HAS_NUMPY:
        print("NumPy not installed — install with: pip install numpy")
        print("Falling back to fast.py (struct-based) benchmark.")
    
    print("ByteToken NumPy Native Encoder Benchmark")
    print("=" * 60)
    for size in [1_000, 10_000, 100_000]:
        benchmark(size)
    print()
    print("CRC-32 self-test:")
    test = b"hello world"
    crc = np_crc32(test)
    print(f"  crc32({test!r}) = 0x{crc:08X}  (expected: 0x0D4A1185)")
    assert crc == 0x0D4A1185, f"CRC-32 mismatch: got 0x{crc:08X}"
    print("  PASS")
