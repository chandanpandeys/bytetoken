"""Experimental heuristic selector for ByteToken string-mode transport.

This convenience layer chooses whether to apply LZMA before the standard
15-bit string encoder. It is a heuristic, not an optimizer.
"""
import lzma, math
from collections import Counter
from bytetoken.core import ByteTokenEncoder


def shannon_entropy(data: bytes) -> float:
    if not data: return 0.0
    counts = Counter(data); n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def compressibility_ratio(data: bytes) -> float:
    if not data: return 0.0
    sample = data[:1024]
    try: return 1.0 - len(lzma.compress(sample)) / len(sample)
    except Exception: return 0.0


class AdaptiveEncoder:
    MARKER_15BIT = b"\x01"; MARKER_15BIT_COMPRESSED = b"\x03"
    def __init__(self, tokenizer: str = "o200k_base"): self.tokenizer = tokenizer; self._enc15 = None
    @property
    def enc15(self):
        if self._enc15 is None: self._enc15 = ByteTokenEncoder(tokenizer=self.tokenizer, bit_width=15)
        return self._enc15
    def analyze(self, data: bytes) -> dict:
        entropy = shannon_entropy(data); ratio = compressibility_ratio(data); use_compression = len(data) >= 64 and ratio > 0.10
        mode = "15bit_compressed" if use_compression else "15bit"; reason = f"LZMA probe reduction approximately {ratio:.0%}" if use_compression else "compression probe did not justify overhead"
        stats = {"input_bytes": len(data), "shannon_entropy": round(entropy, 3), "compressibility": round(ratio, 3), "recommended_mode": mode, "reason": reason}
        try:
            import tiktoken
            tok = tiktoken.get_encoding(self.tokenizer); stats["tokens_15bit"] = len(tok.encode(self.enc15.encode(data))); stats["tokens_15bit_compressed"] = len(tok.encode(self.enc15.encode(lzma.compress(data))))
        except Exception: stats["tokens_15bit"] = stats["tokens_15bit_compressed"] = "N/A"
        return stats
    def encode(self, data: bytes) -> str:
        mode = self.analyze(data)["recommended_mode"]; payload = self.MARKER_15BIT_COMPRESSED + lzma.compress(data) if mode == "15bit_compressed" else self.MARKER_15BIT + data; return self.enc15.encode(payload)
    def decode(self, encoded: str) -> bytes:
        raw = self.enc15.decode(encoded)
        if not raw: return b""
        marker, payload = raw[:1], raw[1:]
        if marker == self.MARKER_15BIT_COMPRESSED: return lzma.decompress(payload)
        if marker == self.MARKER_15BIT: return payload
        raise ValueError("Unknown adaptive ByteToken payload marker")
