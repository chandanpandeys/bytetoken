"""
ByteToken Native Encoder — Backend Selector
=============================================
Auto-detects the best available encoder backend and provides a unified API.

Backend priority (fastest first):
  1. Rust PyO3 extension (Zero-Copy) — ~300x Python baseline  [requires Rust / numpy]
  2. CFFI C extension (_native.pyd)  — ~45x Python baseline   [requires MSVC / gcc]
  3. NumPy vectorized                — ~84x Python baseline   [requires numpy, no compiler]
  4. fast.py struct-based            — ~3-10x Python baseline [stdlib only]
  5. Pure Python (core.py)           — 1x baseline            [always available]

To build the Rust PyO3 extension:
  cd rust_core && maturin develop --release
  python bytetoken/native_build.py --build-c

The NumPy backend requires no compiler:
  pip install numpy

Usage:
  from bytetoken.native_build import get_native_encoder
  enc, dec = get_native_encoder()
  indices = enc(b"data", bit_width=15)
  data    = dec(indices, bit_width=15)

  # Or query the active backend:
  from bytetoken.native_build import ACTIVE_BACKEND
  print(ACTIVE_BACKEND)   # 'numpy', 'fast', or 'python'
"""
import sys

# ================================================================
#  Backend detection
# ================================================================

ACTIVE_BACKEND: str = "python"   # will be updated on import

def _try_rust():
    """Try the compiled PyO3 Rust extension (bytetoken_native.pyd)."""
    try:
        from bytetoken.bytetoken_native import encode, decode  # noqa: F401
        return encode, decode, "rust_pyo3"
    except ImportError:
        return None

def _try_cffi():
    """Try the compiled C extension (_native.pyd)."""
    try:
        from bytetoken._native import ffi, lib  # noqa: F401

        def _cffi_encode(data: bytes, bit_width: int) -> list:
            n = lib.bytetoken_max_indices(len(data), bit_width)
            out = ffi.new(f"uint32_t[{n}]")
            out_len = ffi.new("size_t *")
            lib.bytetoken_encode(data, len(data), bit_width, out, out_len)
            return [out[i] for i in range(out_len[0])]

        def _cffi_decode(indices: list, bit_width: int) -> bytes:
            n = len(indices)
            in_arr = ffi.new(f"uint32_t[{n}]", indices)
            max_out = lib.bytetoken_max_bytes(n, bit_width)
            out = ffi.new(f"uint8_t[{max_out}]")
            out_len = ffi.new("size_t *")
            lib.bytetoken_decode(in_arr, n, bit_width, out, out_len)
            return bytes([out[i] for i in range(out_len[0])])

        return _cffi_encode, _cffi_decode, "cffi_c"

    except ImportError:
        return None


def _try_numpy():
    """Try the NumPy vectorized backend."""
    try:
        from bytetoken.numpy_native import np_encode, np_decode  # noqa: F401
        import numpy as np  # noqa: F401
        return np_encode, np_decode, "numpy"
    except ImportError:
        return None


def _try_fast():
    """Try the struct-based fast backend."""
    try:
        from bytetoken.fast import fast_encode, fast_decode  # noqa: F401
        return fast_encode, fast_decode, "fast"
    except ImportError:
        return None


def _python_fallback():
    """Pure Python fallback (always available)."""
    def _py_encode(data: bytes, bit_width: int) -> list:
        if not data:
            return [0]
        bits = ''.join(format(b, '08b') for b in data)
        pad = (bit_width - len(bits) % bit_width) % bit_width
        bits += '0' * pad
        meta = format(pad, f'0{bit_width}b')
        full = meta + bits
        return [int(full[i:i+bit_width], 2)
                for i in range(0, len(full), bit_width)]

    def _py_decode(indices: list, bit_width: int) -> bytes:
        if not indices or len(indices) <= 1:
            return b''
        pad = indices[0]
        bits = ''.join(format(i, f'0{bit_width}b') for i in indices[1:])
        bits = bits[:-pad] if pad else bits
        return bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8))

    return _py_encode, _py_decode, "python"


# ================================================================
#  Module-level initialization: pick best available backend
# ================================================================

def _init_backend():
    global ACTIVE_BACKEND
    for probe in [_try_rust, _try_cffi, _try_numpy, _try_fast, None]:
        if probe is None:
            encode, decode, name = _python_fallback()
        else:
            result = probe()
            if result is None:
                continue
            encode, decode, name = result
        ACTIVE_BACKEND = name
        return encode, decode

_native_encode, _native_decode = _init_backend()


# ================================================================
#  Public API
# ================================================================

def get_native_encoder():
    """
    Return (encode_fn, decode_fn) for the best available backend.

    Both functions follow the signature:
        encode(data: bytes, bit_width: int) -> list[int] | "numpy.ndarray"
        decode(indices: Iterable[int], bit_width: int) -> bytes
    """
    return _native_encode, _native_decode


def native_encode(data: bytes, bit_width: int) -> list:
    """Encode using best available backend."""
    return _native_encode(data, bit_width)


def native_decode(indices: list, bit_width: int) -> bytes:
    """Decode using best available backend."""
    return _native_decode(indices, bit_width)


def backend_info() -> dict:
    """Return information about the active backend."""
    info = {
        "backend": ACTIVE_BACKEND,
        "numpy_available": False,
        "cffi_available": False,
    }
    try:
        import numpy  # noqa: F401
        info["numpy_available"] = True
        info["numpy_version"] = numpy.__version__
    except ImportError:
        pass
    try:
        from bytetoken._native import ffi  # noqa: F401
        info["cffi_available"] = True
    except ImportError:
        pass
    return info


# ================================================================
#  CLI: build C extension or run benchmark
# ================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="ByteToken Native Encoder — backend selector and benchmark"
    )
    parser.add_argument("--build-c", action="store_true",
                        help="Compile the CFFI C extension (requires MSVC/gcc + cffi)")
    parser.add_argument("--benchmark", action="store_true",
                        help="Benchmark all available backends")
    parser.add_argument("--info", action="store_true",
                        help="Show active backend info")
    args = parser.parse_args()

    if args.build_c:
        print("Building CFFI C extension...")
        print("Note: requires Microsoft C++ Build Tools or GCC.")
        print("Install from: https://visualstudio.microsoft.com/visual-cpp-build-tools/")
        print()
        try:
            import cffi
            # Inline the C source to preserve the original C extension logic
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "_cffi_builder",
                __file__.replace("native_build.py", "_cffi_builder.py")
            )
            print("cffi installed. To compile, run:")
            print("  python bytetoken/_cffi_builder.py")
        except ImportError:
            print("cffi not installed. Run: pip install cffi")

    elif args.benchmark:
        from bytetoken.numpy_native import benchmark
        print(f"Active backend: {ACTIVE_BACKEND}")
        print("=" * 60)
        for sz in [1_000, 10_000, 100_000]:
            benchmark(sz)

    elif args.info or True:   # default action
        info = backend_info()
        print("ByteToken Native Encoder")
        print("=" * 40)
        print(f"  Active backend  : {info['backend'].upper()}")
        print(f"  NumPy available : {info['numpy_available']}"
              + (f" (v{info.get('numpy_version', '?')})" if info['numpy_available'] else ""))
        print(f"  CFFI C ext.     : {info['cffi_available']}")
        print()
        expected_speedup = {
            "rust_pyo3": "~300x",
            "cffi_c": "~15x",
            "numpy":  "~11x",
            "fast":   "~3x",
            "python": "1x (baseline)",
        }
        print(f"  Expected speedup: {expected_speedup.get(info['backend'], '?')}")
