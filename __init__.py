"""ByteToken public API.

ByteToken is an experimental tokenizer-aware binary transport encoding. The
implementation provides deterministic local encode/decode primitives; it does
not imply that a language model will understand or reproduce an encoded
payload, and compatibility is specific to the tokenizer/interface being used.

The high-level ``universal`` mode is deliberately conservative: it uses a
13-bit alphabet shared by the tested ``cl100k_base`` and ``o200k_base``
tiktoken encodings. The class name ``UniversalByteTokenEncoder`` is retained
for API compatibility; it is not a claim of compatibility with every LLM.
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
from bytetoken.native_build import (
    native_encode,
    native_decode,
    backend_info,
    ACTIVE_BACKEND,
)

__version__ = "0.1.0"

__all__ = [
    "encode", "decode", "ByteTokenEncoder", "UniversalByteTokenEncoder",
    "DirectIDEncoder", "SentencePieceByteTokenEncoder", "ErrorDetectingEncoder",
    "ContextProfiler", "profile_file", "ArtifactStore", "mcp_tool",
    "decode_mcp_response", "native_encode", "native_decode", "backend_info",
    "ACTIVE_BACKEND",
]

_encoder_cache = {}


def _get_encoder(mode: str):
    if mode not in _encoder_cache:
        if mode == "universal":
            _encoder_cache[mode] = UniversalByteTokenEncoder(bit_width=13)
        elif mode == "standard":
            _encoder_cache[mode] = ByteTokenEncoder(tokenizer="cl100k_base", bit_width=15)
        elif mode == "direct_id":
            _encoder_cache[mode] = DirectIDEncoder(tokenizer="o200k_base")
        else:
            raise ValueError(f"Unknown mode {mode!r}. Choose 'universal', 'standard', or 'direct_id'.")
    return _encoder_cache[mode]


def encode(data: bytes, mode: str = "universal") -> str:
    """Encode bytes using a supported high-level ByteToken mode.

    The high-level ``direct_id`` form is JSON text for compatibility with this
    string-returning API. It is not the high-density Direct-ID representation.
    Use ``DirectIDEncoder.encode`` for ``list[int]`` and only with an interface
    that explicitly documents pre-tokenized input IDs.
    """
    enc = _get_encoder(mode)
    return enc.encode_to_string(data) if mode == "direct_id" else enc.encode(data)


def decode(data: str, mode: str = "universal") -> bytes:
    """Decode data produced by :func:`encode` using the same mode."""
    enc = _get_encoder(mode)
    return enc.decode_from_string(data) if mode == "direct_id" else enc.decode(data)
