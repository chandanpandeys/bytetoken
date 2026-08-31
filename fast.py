"""Alternative pure-Python ByteToken bit-packing backend.

Performance depends on Python version, payload size, platform and workload.
Benchmark on the target environment instead of assuming a fixed speedup factor.
"""
import struct


def fast_encode(data: bytes, bit_width: int) -> list:
    if not data: return [0]
    total_bits = len(data) * 8; mask = (1 << bit_width) - 1; pad = (bit_width - total_bits % bit_width) % bit_width; num_chunks = (total_bits + pad) // bit_width
    result = [0] * (num_chunks + 1); result[0] = pad; accumulator = acc_bits = 0; out_pos = 1; pos = 0
    for _ in range(len(data) // 8):
        value = struct.unpack_from(">Q", data, pos)[0]; pos += 8; accumulator = (accumulator << 64) | value; acc_bits += 64
        while acc_bits >= bit_width and out_pos <= num_chunks:
            acc_bits -= bit_width; result[out_pos] = (accumulator >> acc_bits) & mask; out_pos += 1; accumulator &= (1 << acc_bits) - 1
    for value in data[pos:]:
        accumulator = (accumulator << 8) | value; acc_bits += 8
        while acc_bits >= bit_width and out_pos <= num_chunks:
            acc_bits -= bit_width; result[out_pos] = (accumulator >> acc_bits) & mask; out_pos += 1; accumulator &= (1 << acc_bits) - 1
    if acc_bits > 0 and out_pos <= num_chunks: result[out_pos] = (accumulator << (bit_width - acc_bits)) & mask; out_pos += 1
    return result[:out_pos]


def fast_decode(indices: list, bit_width: int) -> bytes:
    if not indices or len(indices) <= 1: return b""
    pad = int(indices[0]); mask = (1 << bit_width) - 1; total_bits = (len(indices) - 1) * bit_width - pad; num_bytes = total_bits // 8; accumulator = acc_bits = out_pos = 0; out = bytearray(num_bytes)
    for value in indices[1:]:
        accumulator = (accumulator << bit_width) | (int(value) & mask); acc_bits += bit_width
        while acc_bits >= 8 and out_pos < num_bytes:
            acc_bits -= 8; out[out_pos] = (accumulator >> acc_bits) & 0xFF; out_pos += 1
        if acc_bits < 64: accumulator &= (1 << acc_bits) - 1
    return bytes(out)


def benchmark_compare(data_size: int = 100_000, bit_width: int = 15):
    import os, time
    data = os.urandom(data_size); start = time.perf_counter(); indices = fast_encode(data, bit_width); encode_s = time.perf_counter() - start; start = time.perf_counter(); decoded = fast_decode(indices, bit_width); decode_s = time.perf_counter() - start; assert decoded == data
    result = {"bytes": data_size, "bit_width": bit_width, "encode_seconds": encode_s, "decode_seconds": decode_s}; print(result); return result


if __name__ == "__main__": benchmark_compare()
