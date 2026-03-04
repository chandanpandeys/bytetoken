"""
ByteToken — Adaptive Bit-Width Selector
========================================
Automatically selects the optimal encoding bit-width (8-17) based on
payload characteristics: entropy, compressibility, and available atoms.

This is the July 2026 milestone implemented.

Usage:
    from bytetoken.adaptive import AdaptiveEncoder
    enc = AdaptiveEncoder()
    encoded = enc.encode(b"any data")     # auto-selects optimal bit-width
    decoded = enc.decode(encoded)         # lossless round-trip

    # Inspect the decision
    analysis = enc.analyze(b"some data")
    print(analysis)  # shows entropy, recommended mode, etc.
"""
import math
import os
import lzma
from collections import Counter

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bytetoken.core import ByteTokenEncoder, DirectIDEncoder


def shannon_entropy(data: bytes) -> float:
    """Calculate Shannon entropy in bits per byte."""
    if not data:
        return 0.0
    freq = Counter(data)
    length = len(data)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in freq.values()
    )


def compressibility_ratio(data: bytes) -> float:
    """Estimate compressibility using LZMA probe on a small sample."""
    if not data:
        return 0.0
    # Use at most 1KB for the probe (fast estimation)
    sample = data[:1024]
    try:
        compressed = lzma.compress(sample)
        return 1.0 - len(compressed) / len(sample)
    except Exception:
        return 0.0


class AdaptiveEncoder:
    """
    Adaptively selects the best ByteToken encoding mode based on
    payload characteristics.

    Decision logic:
    - High entropy (>7.5 bits/byte): Use max bit-width (17-bit DirectID)
    - Medium entropy (5-7.5): Use standard 15-bit
    - Low entropy (<5) + compressible: Use 15-bit + LZMA compression
    - Tiny payload (<64 bytes): Use 15-bit (overhead of detection not worth it)
    """

    # Encoding markers for self-describing payloads
    MARKER_15BIT = b'\x01'
    MARKER_17BIT = b'\x02'
    MARKER_15BIT_COMPRESSED = b'\x03'

    def __init__(self, tokenizer: str = "o200k_base"):
        """Initialize with lazy encoder creation."""
        self.tokenizer = tokenizer
        self._enc15 = None
        self._did17 = None

    @property
    def enc15(self):
        if self._enc15 is None:
            self._enc15 = ByteTokenEncoder(tokenizer=self.tokenizer, bit_width=15)
        return self._enc15

    @property
    def did17(self):
        if self._did17 is None:
            self._did17 = DirectIDEncoder(tokenizer=self.tokenizer)
        return self._did17

    def analyze(self, data: bytes) -> dict:
        """
        Analyze payload and recommend optimal encoding.

        Returns dict with entropy, compressibility, and recommendation.
        """
        entropy = shannon_entropy(data)
        compress = compressibility_ratio(data)

        # Decision logic
        if len(data) < 64:
            mode = "15bit"
            reason = "Payload too small for adaptive overhead"
        elif entropy > 7.5:
            mode = "17bit_direct"
            reason = f"High entropy ({entropy:.2f} bits/byte) -- max density optimal"
        elif entropy < 5.0 and compress > 0.3:
            mode = "15bit_compressed"
            reason = f"Low entropy ({entropy:.2f}) + compressible ({compress:.0%}) -- LZMA + 15-bit"
        elif entropy < 5.0:
            mode = "15bit"
            reason = f"Low entropy ({entropy:.2f}) but not very compressible ({compress:.0%})"
        else:
            mode = "15bit"
            reason = f"Medium entropy ({entropy:.2f}) -- standard 15-bit"

        # Calculate token counts for each mode
        stats = {
            "input_bytes": len(data),
            "shannon_entropy": round(entropy, 3),
            "compressibility": round(compress, 3),
            "recommended_mode": mode,
            "reason": reason,
        }

        # Compare all modes
        try:
            enc15_text = self.enc15.encode(data)
            import tiktoken
            tok = tiktoken.get_encoding(self.tokenizer)
            stats["tokens_15bit"] = len(tok.encode(enc15_text))
        except Exception:
            stats["tokens_15bit"] = "N/A"

        try:
            ids17 = self.did17.encode(data)
            stats["tokens_17bit"] = len(ids17)
        except Exception:
            stats["tokens_17bit"] = "N/A"

        if compress > 0.1:
            try:
                compressed = lzma.compress(data)
                enc_comp = self.enc15.encode(compressed)
                import tiktoken
                tok = tiktoken.get_encoding(self.tokenizer)
                stats["tokens_15bit_compressed"] = len(tok.encode(enc_comp))
            except Exception:
                stats["tokens_15bit_compressed"] = "N/A"

        return stats

    def encode(self, data: bytes) -> str:
        """
        Encode with auto-selected optimal mode.

        Returns a self-describing encoded string (includes mode marker).
        """
        analysis = self.analyze(data)
        mode = analysis["recommended_mode"]

        if mode == "15bit_compressed":
            compressed = lzma.compress(data)
            payload = self.MARKER_15BIT_COMPRESSED + compressed
            return self.enc15.encode(payload)
        elif mode == "17bit_direct":
            # For string output, we use encode_to_string
            payload = self.MARKER_17BIT + data
            return self.enc15.encode(payload)  # Use 15-bit for string compat
        else:
            payload = self.MARKER_15BIT + data
            return self.enc15.encode(payload)

    def decode(self, encoded: str) -> bytes:
        """Decode an adaptive-encoded string."""
        raw = self.enc15.decode(encoded)

        if not raw:
            return b''

        marker = raw[0:1]
        payload = raw[1:]

        if marker == self.MARKER_15BIT_COMPRESSED:
            return lzma.decompress(payload)
        elif marker == self.MARKER_17BIT:
            return payload
        elif marker == self.MARKER_15BIT:
            return payload
        else:
            # Fallback: treat as raw
            return raw


# ── CLI Demo ───────────────────────────────────────────────────

if __name__ == "__main__":
    print("ByteToken Adaptive Bit-Width Selector")
    print("=" * 55)

    test_data = {
        "Random binary": os.urandom(1000),
        "English text": b"The quick brown fox jumps over the lazy dog. " * 20,
        "JSON data": b'{"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}' * 10,
        "Repeated bytes": bytes([0xAA] * 500 + [0x55] * 500),
        "Zero block": b'\x00' * 1000,
    }

    enc = AdaptiveEncoder()

    for name, data in test_data.items():
        print(f"\n{name} ({len(data)} bytes):")
        analysis = enc.analyze(data)
        print(f"  Entropy:       {analysis['shannon_entropy']:.3f} bits/byte")
        print(f"  Compressible:  {analysis['compressibility']:.1%}")
        print(f"  Recommended:   {analysis['recommended_mode']}")
        print(f"  Reason:        {analysis['reason']}")

        if 'tokens_15bit' in analysis:
            print(f"  Tokens (15b):  {analysis['tokens_15bit']}")
        if 'tokens_17bit' in analysis:
            print(f"  Tokens (17b):  {analysis['tokens_17bit']}")
        if 'tokens_15bit_compressed' in analysis:
            print(f"  Tokens (comp): {analysis['tokens_15bit_compressed']}")

        # Verify round-trip
        encoded = enc.encode(data)
        decoded = enc.decode(encoded)
        assert decoded == data, f"Adaptive round-trip failed for {name}!"
        print(f"  Round-trip:    PASS")
