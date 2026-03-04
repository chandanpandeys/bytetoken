import time
import os
from bytetoken.native_build import _python_fallback, native_encode, native_decode, ACTIVE_BACKEND

def run_bench(size=100_000, bit_width=15):
    data = os.urandom(size)
    print(f"Backend: {ACTIVE_BACKEND}")
    
    # Pure Python
    py_enc, py_dec, _ = _python_fallback()
    t0 = time.perf_counter()
    for _ in range(5):
        orig_indices = py_enc(data, bit_width)
    py_t = (time.perf_counter() - t0) / 5
    print(f"Pure Python: {py_t*1000:.2f} ms")

    # Native (C)
    t0 = time.perf_counter()
    for _ in range(100):
        c_indices = native_encode(data, bit_width)
    c_t = (time.perf_counter() - t0) / 100
    print(f"Native C:    {c_t*1000:.2f} ms")
    
    speedup = py_t / c_t if c_t > 0 else float('inf')
    print(f"Speedup:     {speedup:.1f}x")

if __name__ == "__main__":
    run_bench()
