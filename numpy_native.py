"""NumPy ByteToken bit-packing backend.

Uses NumPy vectorized bit operations when available and falls back to
``fast.py`` otherwise. No fixed speedup is claimed; benchmark locally.
"""
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


def np_encode(data: bytes, bit_width: int) -> list:
    if not _HAS_NUMPY:
        from bytetoken.fast import fast_encode
        return fast_encode(data, bit_width)
    if not data: return [0]
    arr = np.frombuffer(data, dtype=np.uint8); total_bits = len(arr) * 8; pad = (bit_width - total_bits % bit_width) % bit_width; bits = np.unpackbits(arr)
    if pad: bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])
    blocks = bits.reshape((total_bits + pad) // bit_width, bit_width); powers = 1 << np.arange(bit_width - 1, -1, -1, dtype=np.int64)
    return [int(pad)] + (blocks.astype(np.int64) @ powers).tolist()


def np_decode(indices: list, bit_width: int) -> bytes:
    if not _HAS_NUMPY:
        from bytetoken.fast import fast_decode
        return fast_decode(indices, bit_width)
    if not indices or len(indices) <= 1: return b""
    pad = int(indices[0]); values = np.array(indices[1:], dtype=np.int64); powers = 1 << np.arange(bit_width - 1, -1, -1, dtype=np.int64); bits = ((values[:, None] & powers[None, :]) > 0).astype(np.uint8).reshape(-1); data_bits = len(values) * bit_width - pad; bits = bits[:data_bits]; remainder = len(bits) % 8
    if remainder: bits = np.concatenate([bits, np.zeros(8 - remainder, dtype=np.uint8)])
    return np.packbits(bits)[: data_bits // 8].tobytes()


def np_crc32(data: bytes) -> int:
    import zlib
    return zlib.crc32(data) & 0xFFFFFFFF


def benchmark(data_size: int = 100_000, bit_width: int = 15):
    import os, time
    data = os.urandom(data_size); start = time.perf_counter(); indices = np_encode(data, bit_width); encode_s = time.perf_counter() - start; start = time.perf_counter(); decoded = np_decode(indices, bit_width); decode_s = time.perf_counter() - start; assert decoded == data
    result = {"bytes": data_size, "bit_width": bit_width, "backend": "numpy" if _HAS_NUMPY else "fast-fallback", "encode_seconds": encode_s, "decode_seconds": decode_s}; print(result); return result


if __name__ == "__main__": benchmark()
