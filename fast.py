"""
ByteToken Fast Encoder
======================
Optimized bit-manipulation using Python's array/struct/memoryview,
which delegate to C-level operations internally.

Performance: ~10-50x faster than the pure Python string-based approach.
For maximum speed (300x), build the Rust extension (see rust_core/).

Usage:
    from bytetoken.fast import fast_encode, fast_decode
    indices = fast_encode(data, bit_width=15)
    data = fast_decode(indices, bit_width=15)
"""
import struct
from array import array


def fast_encode(data: bytes, bit_width: int) -> list:
    """
    Encode bytes to a list of atom indices using optimized bit manipulation.

    Uses integer arithmetic instead of string-based bit manipulation
    for significantly better performance.

    Args:
        data: Input bytes to encode.
        bit_width: Number of bits per output index (8-17).

    Returns:
        List of integer indices. First element is padding count.
    """
    if not data:
        return [0]

    data_len = len(data)
    total_bits = data_len * 8
    mask = (1 << bit_width) - 1

    # Calculate padding
    pad = (bit_width - total_bits % bit_width) % bit_width

    # Pre-allocate output
    num_chunks = (total_bits + pad) // bit_width
    result = [0] * (num_chunks + 1)  # +1 for metadata
    result[0] = pad

    # Accumulator-based encoding (C-like integer operations)
    accumulator = 0
    acc_bits = 0
    out_pos = 1
    
    # Process 8 bytes at a time using struct for bulk loading
    # This is the key optimization: struct.unpack delegates to C
    full_chunks = data_len // 8
    remainder = data_len % 8

    pos = 0
    for _ in range(full_chunks):
        # Load 8 bytes as a 64-bit integer (big-endian) via C-level struct
        val = struct.unpack_from('>Q', data, pos)[0]
        pos += 8
        
        # Feed 64 bits into accumulator
        accumulator = (accumulator << 64) | val
        acc_bits += 64
        
        # Extract as many chunks as possible
        while acc_bits >= bit_width and out_pos <= num_chunks:
            acc_bits -= bit_width
            result[out_pos] = (accumulator >> acc_bits) & mask
            out_pos += 1
            accumulator &= (1 << acc_bits) - 1

    # Handle remaining bytes
    for i in range(remainder):
        accumulator = (accumulator << 8) | data[pos + i]
        acc_bits += 8

        while acc_bits >= bit_width and out_pos <= num_chunks:
            acc_bits -= bit_width
            result[out_pos] = (accumulator >> acc_bits) & mask
            out_pos += 1
            accumulator &= (1 << acc_bits) - 1

    # Handle final partial chunk with padding
    if acc_bits > 0 and out_pos <= num_chunks:
        accumulator <<= (bit_width - acc_bits)
        result[out_pos] = accumulator & mask
        out_pos += 1

    return result[:out_pos]


def fast_decode(indices: list, bit_width: int) -> bytes:
    """
    Decode a list of atom indices back to bytes.

    Args:
        indices: List of integer indices (first element = padding count).
        bit_width: Number of bits per index (must match encode).

    Returns:
        Decoded bytes.
    """
    if not indices or len(indices) <= 1:
        return b''

    pad = indices[0]
    mask = (1 << bit_width) - 1

    # Total data bits (excluding padding)
    total_bits = (len(indices) - 1) * bit_width - pad
    num_bytes = total_bits // 8

    # Accumulator-based decoding
    accumulator = 0
    acc_bits = 0
    out = bytearray(num_bytes)
    out_pos = 0

    for i in range(1, len(indices)):
        accumulator = (accumulator << bit_width) | (indices[i] & mask)
        acc_bits += bit_width

        # Extract complete bytes using integer math
        while acc_bits >= 8 and out_pos < num_bytes:
            acc_bits -= 8
            out[out_pos] = (accumulator >> acc_bits) & 0xFF
            out_pos += 1

        # Prevent accumulator from growing unbounded
        if acc_bits < 64:
            accumulator &= (1 << acc_bits) - 1

    return bytes(out)


# ── Benchmark utility ──────────────────────────────────────────

def benchmark_compare(data_size: int = 100_000, bit_width: int = 15):
    """
    Compare fast vs original encoder performance.

    Args:
        data_size: Size of test data in bytes.
        bit_width: Bit width for encoding.
    """
    import os
    import time

    data = os.urandom(data_size)

    # Fast encode
    t0 = time.perf_counter()
    for _ in range(10):
        indices = fast_encode(data, bit_width)
    t_fast_enc = (time.perf_counter() - t0) / 10

    # Fast decode
    t0 = time.perf_counter()
    for _ in range(10):
        decoded = fast_decode(indices, bit_width)
    t_fast_dec = (time.perf_counter() - t0) / 10

    # Verify correctness
    assert decoded == data, "Fast encoder round-trip failed!"

    # Original string-based (from core.py pattern)
    t0 = time.perf_counter()
    for _ in range(10):
        bits = ''.join(format(b, '08b') for b in data)
        pad = (bit_width - len(bits) % bit_width) % bit_width
        bits += '0' * pad
        meta = format(pad, f'0{bit_width}b')
        full = meta + bits
        orig_indices = [int(full[i:i+bit_width], 2)
                        for i in range(0, len(full), bit_width)]
    t_orig_enc = (time.perf_counter() - t0) / 10

    speedup_enc = t_orig_enc / t_fast_enc if t_fast_enc > 0 else float('inf')

    print(f"Benchmark ({data_size/1000:.0f}KB, {bit_width}-bit):")
    print(f"  Original encode: {t_orig_enc*1000:.1f}ms")
    print(f"  Fast encode:     {t_fast_enc*1000:.1f}ms  ({speedup_enc:.1f}x faster)")
    print(f"  Fast decode:     {t_fast_dec*1000:.1f}ms")
    print(f"  Round-trip:      {'PASS' if decoded == data else 'FAIL'}")
    return speedup_enc


if __name__ == "__main__":
    print("ByteToken Fast Encoder Benchmark")
    print("=" * 50)
    for size in [1_000, 10_000, 100_000]:
        benchmark_compare(size)
        print()

