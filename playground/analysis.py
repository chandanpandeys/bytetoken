"""Measured comparison helpers for the ByteToken Playground."""

from __future__ import annotations

import base64
import functools
import lzma
import time
from typing import Any, Dict

import tiktoken

from bytetoken.core import ByteTokenEncoder, DirectIDEncoder, UniversalByteTokenEncoder

SUPPORTED_TOKENIZERS = ("cl100k_base", "o200k_base")
MAX_INPUT_BYTES = 256 * 1024


@functools.lru_cache(maxsize=None)
def _tokenizer(name: str):
    if name not in SUPPORTED_TOKENIZERS:
        raise ValueError(f"Unsupported tokenizer: {name}")
    return tiktoken.get_encoding(name)


@functools.lru_cache(maxsize=None)
def _standard_encoder(name: str) -> ByteTokenEncoder:
    return ByteTokenEncoder(tokenizer=name, bit_width=15)


@functools.lru_cache(maxsize=1)
def _universal_encoder() -> UniversalByteTokenEncoder:
    return UniversalByteTokenEncoder(bit_width=13)


@functools.lru_cache(maxsize=None)
def _direct_encoder(name: str) -> DirectIDEncoder:
    return DirectIDEncoder(tokenizer=name)


def _text_metrics(text: str, tokenizer_name: str) -> Dict[str, Any]:
    enc = _tokenizer(tokenizer_name)
    return {
        "chars": len(text),
        "utf8_bytes": len(text.encode("utf-8")),
        "tokens": len(enc.encode(text)),
    }


def _timed(fn):
    started = time.perf_counter()
    value = fn()
    return value, (time.perf_counter() - started) * 1000.0


def _savings(reference_tokens: int, candidate_tokens: int) -> float | None:
    if not reference_tokens:
        return None
    return round((reference_tokens - candidate_tokens) / reference_tokens * 100.0, 2)


def analyze_payload(data: bytes, tokenizer_name: str = "o200k_base") -> Dict[str, Any]:
    """Compare ByteToken representations against Base64 on identical bytes.

    Token counts are measured with ``tokenizer_name``. Compression is reported
    separately so the UI does not attribute LZMA savings to ByteToken itself.
    Every transport shown in the playground is decoded back to the original
    payload so the report can expose a measured lossless round-trip result.
    Direct-ID counts describe the local token-ID representation only.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes-like")
    data = bytes(data)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError(f"Payload exceeds {MAX_INPUT_BYTES} byte playground limit")
    if tokenizer_name not in SUPPORTED_TOKENIZERS:
        raise ValueError(f"Unsupported tokenizer: {tokenizer_name}")

    base64_text, base64_ms = _timed(lambda: base64.b64encode(data).decode("ascii"))
    base64_metrics = _text_metrics(base64_text, tokenizer_name)
    base64_restored, base64_decode_ms = _timed(lambda: base64.b64decode(base64_text, validate=True))

    standard = _standard_encoder(tokenizer_name)
    standard_text, standard_ms = _timed(lambda: standard.encode(data))
    standard_metrics = _text_metrics(standard_text, tokenizer_name)
    standard_restored, standard_decode_ms = _timed(lambda: standard.decode(standard_text))

    universal = _universal_encoder()
    universal_text, universal_ms = _timed(lambda: universal.encode(data))
    universal_metrics = _text_metrics(universal_text, tokenizer_name)
    universal_restored, universal_decode_ms = _timed(lambda: universal.decode(universal_text))

    direct = _direct_encoder(tokenizer_name)
    direct_ids, direct_ms = _timed(lambda: direct.encode(data))
    direct_restored, direct_decode_ms = _timed(lambda: direct.decode(direct_ids))

    compressed, compress_ms = _timed(lambda: lzma.compress(data))
    compressed_b64, compressed_b64_ms = _timed(
        lambda: base64.b64encode(compressed).decode("ascii")
    )
    compressed_b64_metrics = _text_metrics(compressed_b64, tokenizer_name)
    compressed_b64_restored, compressed_b64_decode_ms = _timed(
        lambda: lzma.decompress(base64.b64decode(compressed_b64, validate=True))
    )

    compressed_standard, compressed_standard_ms = _timed(
        lambda: standard.encode(compressed)
    )
    compressed_standard_metrics = _text_metrics(compressed_standard, tokenizer_name)
    compressed_standard_restored, compressed_standard_decode_ms = _timed(
        lambda: lzma.decompress(standard.decode(compressed_standard))
    )

    baseline_tokens = base64_metrics["tokens"]
    roundtrips = {
        "base64": base64_restored == data,
        "bytetoken_standard": standard_restored == data,
        "bytetoken_universal": universal_restored == data,
        "direct_id": direct_restored == data,
        "lzma_base64": compressed_b64_restored == data,
        "lzma_bytetoken_standard": compressed_standard_restored == data,
    }

    return {
        "input": {
            "bytes": len(data),
            "bits": len(data) * 8,
            "tokenizer": tokenizer_name,
            "preview_utf8": data[:240].decode("utf-8", errors="replace"),
            "truncated_preview": len(data) > 240,
        },
        "verification": {
            "all_roundtrips_ok": all(roundtrips.values()),
            "roundtrips": roundtrips,
        },
        "representations": [
            {
                "id": "base64",
                "label": "Base64",
                "kind": "text transport",
                **base64_metrics,
                "encode_ms": round(base64_ms, 3),
                "decode_ms": round(base64_decode_ms, 3),
                "roundtrip_ok": roundtrips["base64"],
                "savings_vs_base64_pct": 0.0,
                "preview": base64_text[:320],
            },
            {
                "id": "bytetoken_standard",
                "label": "ByteToken Standard 15-bit",
                "kind": "tokenizer-stable text",
                **standard_metrics,
                "encode_ms": round(standard_ms, 3),
                "decode_ms": round(standard_decode_ms, 3),
                "roundtrip_ok": roundtrips["bytetoken_standard"],
                "savings_vs_base64_pct": _savings(baseline_tokens, standard_metrics["tokens"]),
                "preview": standard_text[:320],
                "bit_width": 15,
            },
            {
                "id": "bytetoken_universal",
                "label": "ByteToken Shared 13-bit",
                "kind": "shared tokenizer-stable text",
                **universal_metrics,
                "encode_ms": round(universal_ms, 3),
                "decode_ms": round(universal_decode_ms, 3),
                "roundtrip_ok": roundtrips["bytetoken_universal"],
                "savings_vs_base64_pct": _savings(baseline_tokens, universal_metrics["tokens"]),
                "preview": universal_text[:320],
                "bit_width": 13,
            },
            {
                "id": "direct_id",
                "label": f"Direct ID {direct.bit_width}-bit",
                "kind": "local token-ID representation",
                "tokens": len(direct_ids),
                "chars": None,
                "utf8_bytes": None,
                "encode_ms": round(direct_ms, 3),
                "decode_ms": round(direct_decode_ms, 3),
                "roundtrip_ok": roundtrips["direct_id"],
                "savings_vs_base64_pct": _savings(baseline_tokens, len(direct_ids)),
                "preview": direct_ids[:24],
                "bit_width": direct.bit_width,
                "warning": "Not a text representation; hosted APIs must explicitly accept token IDs.",
            },
        ],
        "compression": {
            "algorithm": "lzma",
            "compressed_bytes": len(compressed),
            "byte_reduction_pct": round((1 - len(compressed) / len(data)) * 100.0, 2) if data else 0.0,
            "compression_ms": round(compress_ms, 3),
            "base64": {
                **compressed_b64_metrics,
                "encode_ms": round(compressed_b64_ms, 3),
                "decode_ms": round(compressed_b64_decode_ms, 3),
                "roundtrip_ok": roundtrips["lzma_base64"],
                "savings_vs_uncompressed_base64_pct": _savings(
                    baseline_tokens, compressed_b64_metrics["tokens"]
                ),
            },
            "bytetoken_standard": {
                **compressed_standard_metrics,
                "encode_ms": round(compressed_standard_ms, 3),
                "decode_ms": round(compressed_standard_decode_ms, 3),
                "roundtrip_ok": roundtrips["lzma_bytetoken_standard"],
                "savings_vs_uncompressed_base64_pct": _savings(
                    baseline_tokens, compressed_standard_metrics["tokens"]
                ),
            },
        },
        "notes": [
            "All text token counts use the selected tokenizer on the exact displayed transport text.",
            "Every displayed transport is decoded and compared byte-for-byte with the original payload.",
            "Direct-ID is counted as local token IDs, not its JSON debug/storage wrapper.",
            "LZMA results are separated because compression and binary-to-token encoding are different layers.",
            "This playground measures transport representation, not model understanding or copy-through fidelity.",
        ],
    }
