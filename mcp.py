"""Experimental MCP-oriented wire helpers.

This module does not implement or register an MCP server.  It provides a local
function decorator that can wrap sufficiently large return values in explicit
ByteToken transport metadata, plus a matching deterministic decoder.

Whether such a representation is useful in a real MCP deployment depends on
where tokenization occurs.  If a client/server can exchange raw bytes or an
artifact reference outside model context, that is often preferable.
"""

import functools
import json
import lzma
from typing import Any, Callable, Dict

import bytetoken
from bytetoken.store import ArtifactStore

# Kept for backwards compatibility with earlier experiments. ArtifactStore is
# currently an in-memory prototype; this is not durable process-shared storage.
GLOBAL_STORE = ArtifactStore()

WIRE_ENCODING = "bytetoken-15"
WIRE_MODE = "standard"
WIRE_TOKENIZER = "cl100k_base"


def mcp_tool(compress: bool = True, threshold_bytes: int = 1024):
    """Wrap large local tool results in explicit ByteToken wire metadata.

    Dict/list values are serialized as JSON; strings are UTF-8 encoded; bytes
    are used directly. Values below ``threshold_bytes`` are returned unchanged.
    When ``compress`` is true, LZMA is applied before ByteToken encoding.

    This helper models a transport boundary; it does not prove that putting the
    resulting string through a generative model is lossless.
    """
    if threshold_bytes < 0:
        raise ValueError("threshold_bytes must be non-negative")

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)

            if isinstance(result, (dict, list)):
                raw_bytes = json.dumps(
                    result, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            elif isinstance(result, str):
                raw_bytes = result.encode("utf-8")
            elif isinstance(result, bytes):
                raw_bytes = result
            else:
                return result

            if len(raw_bytes) < threshold_bytes:
                return result

            payload_bytes = lzma.compress(raw_bytes) if compress else raw_bytes
            encoded = bytetoken.encode(payload_bytes, mode=WIRE_MODE)

            return {
                "_bytetoken_wire": True,
                "encoding": WIRE_ENCODING,
                "mode": WIRE_MODE,
                "tokenizer": WIRE_TOKENIZER,
                "compressed": bool(compress),
                "compression": "lzma" if compress else None,
                "original_bytes": len(raw_bytes),
                "encoded_input_bytes": len(payload_bytes),
                "wire_chars": len(encoded),
                "payload": encoded,
            }

        return wrapper

    return decorator


def decode_mcp_response(response: Dict[str, Any]) -> bytes:
    """Decode a response created by :func:`mcp_tool` back to raw bytes."""
    if not isinstance(response, dict) or not response.get("_bytetoken_wire"):
        raise ValueError("Payload is not a ByteToken wire-wrapped response")

    if response.get("encoding") != WIRE_ENCODING:
        raise ValueError(f"Unsupported ByteToken wire encoding: {response.get('encoding')!r}")
    if response.get("mode", WIRE_MODE) != WIRE_MODE:
        raise ValueError(f"Unsupported ByteToken wire mode: {response.get('mode')!r}")
    if response.get("tokenizer", WIRE_TOKENIZER) != WIRE_TOKENIZER:
        raise ValueError(
            f"Unsupported ByteToken wire tokenizer: {response.get('tokenizer')!r}"
        )

    encoded = response.get("payload")
    if not isinstance(encoded, str):
        raise ValueError("ByteToken wire payload must be a string")

    # IMPORTANT: the encoder above uses standard mode.  Earlier versions called
    # bytetoken.decode() without a mode, which selected the universal decoder
    # and could corrupt/fail the round-trip.
    raw = bytetoken.decode(encoded, mode=WIRE_MODE)

    compression = response.get("compression")
    if response.get("compressed"):
        if compression != "lzma":
            raise ValueError(f"Unsupported compression: {compression!r}")
        return lzma.decompress(raw)
    if compression is not None:
        raise ValueError("Uncompressed response must not declare compression")
    return raw
