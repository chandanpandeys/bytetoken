"""
ByteToken Protocol
==================
Token-efficient binary encoding for LLM context windows.
Achieves high token density on the tested tokenizer configurations.
Optimality claims are scoped to the encoding model and tokenizer defined in the paper.

Quick Start::

    import bytetoken

    encoded = bytetoken.encode(b"binary data")        # universal mode
    decoded = bytetoken.decode(encoded)                # lossless

Modes::

    encoded = bytetoken.encode(b"data", mode="universal")   # 13-bit, all LLMs
    encoded = bytetoken.encode(b"data", mode="standard")    # 15-bit, OpenAI
    encoded = bytetoken.encode(b"data", mode="direct_id")   # highest-density mode

Advanced (class-based)::

    from bytetoken import DirectIDEncoder
    did = DirectIDEncoder()
    ids = did.encode(b"data")  # -> List[int]

    from bytetoken import ErrorDetectingEncoder
    enc = ErrorDetectingEncoder(did)  # adds CRC-32 verification

    from bytetoken.adaptive import AdaptiveEncoder
    enc = AdaptiveEncoder()           # auto-selects optimal mode

    from bytetoken.blt_bridge import BLTBridge
    bridge = BLTBridge()              # multi-model bridge (11 architectures)

    from bytetoken.native_build import native_encode, ACTIVE_BACKEND
    fast = native_encode(b"data", bit_width=15)  # numpy-accelerated (11x faster)
    print(ACTIVE_BACKEND)             # 'numpy', 'fast', or 'python'
"""

from bytetoken.core import (
    ByteTokenEncoder,
    UniversalByteTokenEncoder,
    DirectIDEncoder,
    SentencePieceByteTokenEncoder,
    ErrorDetectingEncoder,
)
from bytetoken.profiler import ContextProfiler, profile_file
from bytetoken.store import ArtifactStore
from bytetoken.mcp import mcp_tool, decode_mcp_response

__version__ = "1.0.0"
__all__ = [
    "encode", "decode",
    "ByteTokenEncoder", "UniversalByteTokenEncoder", "DirectIDEncoder",
    "SentencePieceByteTokenEncoder", "ErrorDetectingEncoder",
    "ContextProfiler", "profile_file", "ArtifactStore",
    "mcp_tool", "decode_mcp_response",
    "native_encode", "native_decode", "backend_info", "ACTIVE_BACKEND",
]

from bytetoken.native_build import (
    native_encode, native_decode, backend_info, ACTIVE_BACKEND
)

# Cache encoder instances (they're expensive to construct due to vocab scan)
_encoder_cache = {}


def _get_encoder(mode: str, **kwargs):
    """Get or create a cached encoder for the given mode."""
    cache_key = mode
    if cache_key not in _encoder_cache:
        if mode == "universal":
            _encoder_cache[cache_key] = UniversalByteTokenEncoder()
        elif mode == "standard":
            _encoder_cache[cache_key] = ByteTokenEncoder()
        elif mode == "direct_id":
            _encoder_cache[cache_key] = DirectIDEncoder()
        else:
            raise ValueError(
                f"Unknown mode '{mode}'. Choose from: 'universal', 'standard', 'direct_id'"
            )
    return _encoder_cache[cache_key]


def encode(data: bytes, mode: str = "universal") -> str:
    """Encode binary data into a ByteToken token string.

    Args:
        data: Raw bytes to encode.
        mode: Encoding mode — 'universal' (13-bit, all LLMs),
              'standard' (15-bit, OpenAI), or 'direct_id' (17-bit, max density).

    Returns:
        Encoded string that can be sent through an LLM context window.
    """
    enc = _get_encoder(mode)
    if mode == "direct_id":
        return enc.encode_to_string(data)
    return enc.encode(data)


def decode(data: str, mode: str = "universal") -> bytes:
    """Decode a ByteToken-encoded string back to raw bytes.

    Args:
        data: ByteToken-encoded string.
        mode: Must match the mode used for encoding.

    Returns:
        Original binary data (lossless).
    """
    enc = _get_encoder(mode)
    if mode == "direct_id":
        return enc.decode_from_string(data)
    return enc.decode(data)

