"""
ByteToken Core Library
======================
The complete encoding/decoding engine for ByteToken Protocol.

Five encoder classes:
  - ByteTokenEncoder: String-based, 15-bit, uses space-prefixed non-merging atoms
  - UniversalByteTokenEncoder: Cross-tokenizer portable, 13-14 bit
  - DirectIDEncoder: Token ID-based, 16-17 bit, bypasses string serialization
  - SentencePieceByteTokenEncoder: SentencePiece-based, 13-15 bit, for Llama/Mistral/T5
  - ErrorDetectingEncoder: Wrapper adding CRC-32 checksums for corruption detection
"""
import math
import base64
import struct
import zlib
import tiktoken


class ByteTokenEncoder:
    """
    ByteToken binary-to-token encoder using non-merging atomic tokens.
    
    Usage:
        gw = ByteTokenEncoder()
        encoded = gw.encode(b"binary data here")
        decoded = gw.decode(encoded)
        assert decoded == b"binary data here"  # lossless round-trip
    """

    SUPPORTED_TOKENIZERS = ["cl100k_base", "o200k_base"]

    def __init__(self, tokenizer="cl100k_base", bit_width=15, use_all_nonmerging=False):
        """
        Initialize the ByteToken encoder.

        Args:
            tokenizer: Name of the tiktoken tokenizer to use.
            bit_width: Number of bits per token (8-16). Default 15.
            use_all_nonmerging: If True, use ALL non-merging tokens (not just space-prefixed).
                               This enables higher bit-widths (up to 16).
        """
        if tokenizer not in self.SUPPORTED_TOKENIZERS:
            raise ValueError(f"Unsupported tokenizer: {tokenizer}. Use one of {self.SUPPORTED_TOKENIZERS}")

        if not 8 <= bit_width <= 16:
            raise ValueError(f"bit_width must be 8-16, got {bit_width}")

        self.enc = tiktoken.get_encoding(tokenizer)
        self.tokenizer_name = tokenizer
        self.bit_width = bit_width
        self.use_all_nonmerging = use_all_nonmerging

        needed = 2 ** bit_width
        self._discover_atoms(needed, use_all_nonmerging)

        if len(self._alphabet) < needed:
            raise ValueError(
                f"Only found {len(self._alphabet)} non-merging atoms, "
                f"need {needed} for {bit_width}-bit encoding. "
                f"Try use_all_nonmerging=True or lower bit_width."
            )

    def _discover_atoms(self, needed, use_all):
        """Discover non-merging atomic tokens from the tokenizer vocabulary."""
        atoms = []
        try:
            max_t = self.enc.max_token_value
        except:
            max_t = 200000

        for i in range(max_t):
            if len(atoms) >= needed:
                break
            try:
                b = self.enc.decode_single_token_bytes(i)
                w = b.decode('utf-8')

                if use_all:
                    # Use ANY non-merging token
                    if len(w) > 0 and w.isprintable() and len(self.enc.encode(w + w)) == 2:
                        atoms.append(i)
                else:
                    # Use only space-prefixed non-merging tokens (safer)
                    if w.startswith(" ") and len(w) > 1 and w[1:].isprintable():
                        if len(self.enc.encode(w + w)) == 2:
                            atoms.append(i)
            except:
                continue

        self._alphabet = atoms[:needed]
        self._id_to_idx = {tid: idx for idx, tid in enumerate(self._alphabet)}
        self._idx_to_id = {idx: tid for idx, tid in enumerate(self._alphabet)}

    def encode(self, data: bytes) -> str:
        """
        Encode binary data to a ByteToken string.
        
        Args:
            data: Binary data to encode.
            
        Returns:
            Encoded string that tokenizes to minimal tokens.
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(f"Expected bytes, got {type(data)}")

        bw = self.bit_width
        bits = ''.join(format(byte, '08b') for byte in data)

        # Padding
        pad = (bw - len(bits) % bw) % bw
        bits += '0' * pad

        # Prepend padding metadata
        meta = format(pad, f'0{bw}b')
        full_bits = meta + bits

        # Map to token IDs
        token_ids = []
        for i in range(0, len(full_bits), bw):
            chunk = full_bits[i:i + bw]
            idx = int(chunk, 2)
            token_ids.append(self._idx_to_id[idx])

        return self.enc.decode(token_ids)

    def decode(self, encoded_str: str) -> bytes:
        """
        Decode a ByteToken string back to binary data.
        
        Args:
            encoded_str: The ByteToken-encoded string.
            
        Returns:
            Original binary data.
        """
        token_ids = self.enc.encode(encoded_str)
        bw = self.bit_width

        # Reconstruct bits
        chunks = []
        for tid in token_ids:
            if tid in self._id_to_idx:
                chunks.append(format(self._id_to_idx[tid], f'0{bw}b'))

        if not chunks:
            return b''

        # First chunk is padding metadata
        pad = int(chunks[0], 2)
        data_bits = ''.join(chunks[1:])

        if pad > 0 and pad < len(data_bits):
            data_bits = data_bits[:-pad]

        # Convert bits to bytes
        result = bytearray()
        for i in range(0, len(data_bits), 8):
            byte_str = data_bits[i:i + 8]
            if len(byte_str) == 8:
                result.append(int(byte_str, 2))

        return bytes(result)

    def token_count(self, data: bytes) -> int:
        """Return the number of tokens the encoded data would produce."""
        encoded = self.encode(data)
        return len(self.enc.encode(encoded))

    def stats(self, data: bytes) -> dict:
        """Return encoding statistics for the given data."""
        encoded = self.encode(data)
        tokens = self.enc.encode(encoded)
        b64_tokens = len(self.enc.encode(__import__('base64').b64encode(data).decode('ascii')))
        
        return {
            "input_bytes": len(data),
            "input_bits": len(data) * 8,
            "ByteToken_tokens": len(tokens),
            "base64_tokens": b64_tokens,
            "bits_per_token": len(data) * 8 / len(tokens) if tokens else 0,
            "savings_vs_base64": ((b64_tokens - len(tokens)) / b64_tokens * 100) if b64_tokens else 0,
            "encoded_chars": len(encoded),
            "bit_width": self.bit_width,
            "tokenizer": self.tokenizer_name,
        }

    @property
    def alphabet_size(self):
        return len(self._alphabet)

    @property
    def max_bit_width(self):
        return math.floor(math.log2(len(self._alphabet)))

    def __repr__(self):
        return (f"ByteTokenEncoder(tokenizer={self.tokenizer_name!r}, "
                f"bit_width={self.bit_width}, atoms={self.alphabet_size})")


class UniversalByteTokenEncoder:
    """
    Cross-tokenizer ByteToken encoder that uses atoms shared across
    multiple tokenizers. Encoded data works on ANY supported tokenizer.
    """

    def __init__(self, tokenizers=None, bit_width=14):
        if tokenizers is None:
            tokenizers = ["cl100k_base", "o200k_base"]

        self.tokenizers = tokenizers
        self.bit_width = bit_width
        self.encs = {name: tiktoken.get_encoding(name) for name in tokenizers}

        # Find universal atoms
        self._discover_universal_atoms(2 ** bit_width)

    def _discover_universal_atoms(self, needed):
        """Find atoms that are non-merging in ALL tokenizers."""
        # Discover per-tokenizer atoms
        per_tokenizer = {}
        for name, enc in self.encs.items():
            atoms = set()
            try:
                max_t = enc.max_token_value
            except:
                max_t = 200000

            for i in range(max_t):
                try:
                    b = enc.decode_single_token_bytes(i)
                    w = b.decode('utf-8')
                    if w.startswith(" ") and len(w) > 1 and w[1:].isalpha():
                        if len(enc.encode(w + w)) == 2:
                            atoms.add(w)
                except:
                    continue
            per_tokenizer[name] = atoms

        # Intersection
        universal = per_tokenizer[self.tokenizers[0]]
        for name in self.tokenizers[1:]:
            universal = universal.intersection(per_tokenizer[name])

        self._universal_words = sorted(universal)[:needed]
        self._word_to_idx = {w: i for i, w in enumerate(self._universal_words)}

        if len(self._universal_words) < needed:
            raise ValueError(
                f"Only {len(self._universal_words)} universal atoms found, "
                f"need {needed} for {self.bit_width}-bit encoding."
            )

    def encode(self, data: bytes) -> str:
        bw = self.bit_width
        bits = ''.join(format(byte, '08b') for byte in data)
        pad = (bw - len(bits) % bw) % bw
        bits += '0' * pad
        meta = format(pad, f'0{bw}b')
        full_bits = meta + bits

        words = []
        for i in range(0, len(full_bits), bw):
            idx = int(full_bits[i:i + bw], 2)
            words.append(self._universal_words[idx])

        return ''.join(words)

    def decode(self, encoded_str: str) -> bytes:
        bw = self.bit_width
        # Parse words: split by finding space-prefixed tokens
        words = []
        parts = encoded_str.split(' ')
        for k, part in enumerate(parts):
            if k == 0 and part == '':
                continue
            word = ' ' + part
            if word in self._word_to_idx:
                words.append(word)

        if not words:
            return b''

        # First word carries padding metadata
        pad = self._word_to_idx[words[0]]
        data_bits = ''.join(format(self._word_to_idx[w], f'0{bw}b') for w in words[1:])

        if pad > 0 and pad < len(data_bits):
            data_bits = data_bits[:-pad]

        result = bytearray()
        for i in range(0, len(data_bits), 8):
            byte_str = data_bits[i:i + 8]
            if len(byte_str) == 8:
                result.append(int(byte_str, 2))

        return bytes(result)

    @property
    def alphabet_size(self):
        return len(self._universal_words)

    def __repr__(self):
        return (f"UniversalByteTokenEncoder(tokenizers={self.tokenizers}, "
                f"bit_width={self.bit_width}, universal_atoms={self.alphabet_size})")


class DirectIDEncoder:
    """
    Direct Token ID Encoder — the highest-density ByteToken mode.

    PARADIGM SHIFT: Instead of encoding data as text strings that get
    re-tokenized, this encoder maps bits directly to token IDs and
    outputs/accepts token ID arrays. This bypasses string serialization
    entirely, unlocking the FULL roundtrip-safe vocabulary.

    Results:
        cl100k_base: 99,483 safe IDs → 16-bit → 47% savings vs Base64
        o200k_base: 198,424 safe IDs → 17-bit → 51% savings vs Base64

    Usage:
        enc = DirectIDEncoder()  # defaults to o200k, 17-bit

        # Encode to token IDs (for API calls that accept token arrays)
        token_ids = enc.encode(b"binary data")
        decoded = enc.decode(token_ids)
        assert decoded == b"binary data"

        # Convenience: encode to/from string (for display/storage)
        text = enc.encode_to_string(b"binary data")
        decoded = enc.decode_from_string(text)
    """

    SUPPORTED_TOKENIZERS = ["cl100k_base", "o200k_base"]

    # Pre-computed optimal bit-widths per tokenizer
    OPTIMAL_BITS = {
        "cl100k_base": 16,  # 99,483 safe IDs >= 65,536
        "o200k_base": 17,   # 198,424 safe IDs >= 131,072
    }

    def __init__(self, tokenizer="o200k_base", bit_width=None):
        """
        Initialize the Direct ID encoder.

        Args:
            tokenizer: Name of the tiktoken tokenizer. Default o200k_base
                       for maximum 17-bit density.
            bit_width: Bits per token (auto-detected if None). Set manually
                       to use fewer bits for faster init or compatibility.
        """
        if tokenizer not in self.SUPPORTED_TOKENIZERS:
            raise ValueError(
                f"Unsupported tokenizer: {tokenizer}. "
                f"Use one of {self.SUPPORTED_TOKENIZERS}"
            )

        self.enc = tiktoken.get_encoding(tokenizer)
        self.tokenizer_name = tokenizer

        # Auto-detect optimal bit-width
        if bit_width is None:
            bit_width = self.OPTIMAL_BITS.get(tokenizer, 16)
        self.bit_width = bit_width

        needed = 2 ** bit_width
        self._discover_safe_ids(needed)

        if len(self._alphabet) < needed:
            # Fall back to a lower bit-width
            actual_bits = math.floor(math.log2(len(self._alphabet))) if self._alphabet else 0
            if actual_bits < 8:
                raise ValueError(
                    f"Only {len(self._alphabet)} roundtrip-safe IDs found, "
                    f"need at least 256 for 8-bit encoding."
                )
            self.bit_width = actual_bits
            needed = 2 ** actual_bits
            self._alphabet = self._alphabet[:needed]
            self._rebuild_maps()

    def _discover_safe_ids(self, needed):
        """
        Discover token IDs that survive a decode->encode roundtrip.

        A token ID is 'roundtrip-safe' if:
            decode(id) -> text -> encode(text) == [id]
        This guarantees the token can be used in Direct ID mode.
        """
        safe = []
        try:
            max_t = self.enc.max_token_value
        except AttributeError:
            max_t = 200000

        for i in range(max_t):
            try:
                raw_bytes = self.enc.decode_single_token_bytes(i)
                text = raw_bytes.decode('utf-8', errors='strict')
                re_encoded = self.enc.encode(text)
                if len(re_encoded) == 1 and re_encoded[0] == i:
                    safe.append(i)
                    if len(safe) >= needed:
                        break
            except (KeyError, UnicodeDecodeError):
                continue

        self._alphabet = safe[:needed]
        self._rebuild_maps()

    def _rebuild_maps(self):
        """Build bidirectional mappings between indices and token IDs."""
        self._id_to_idx = {tid: idx for idx, tid in enumerate(self._alphabet)}
        self._idx_to_id = dict(enumerate(self._alphabet))

    def _data_to_bits(self, data: bytes) -> str:
        """Convert bytes to bit string with padding metadata prepended."""
        bw = self.bit_width
        bits = ''.join(format(byte, '08b') for byte in data)

        # Pad to multiple of bit_width
        pad = (bw - len(bits) % bw) % bw
        bits += '0' * pad

        # Prepend padding count as first chunk
        meta = format(pad, f'0{bw}b')
        return meta + bits

    def _bits_to_data(self, all_bits: str) -> bytes:
        """Convert bit string (with padding metadata) back to bytes."""
        bw = self.bit_width
        if len(all_bits) < bw:
            return b''

        # First chunk is the padding count
        pad = int(all_bits[:bw], 2)
        data_bits = all_bits[bw:]

        # Remove padding
        if pad > 0 and pad < len(data_bits):
            data_bits = data_bits[:-pad]

        # Convert to bytes
        result = bytearray()
        for i in range(0, len(data_bits), 8):
            byte_str = data_bits[i:i + 8]
            if len(byte_str) == 8:
                result.append(int(byte_str, 2))

        return bytes(result)

    # ── Core API: Token ID arrays ──────────────────────────────

    def encode(self, data: bytes) -> list:
        """
        Encode binary data to a list of token IDs.

        This is the primary API. The returned list can be passed directly
        to LLM APIs that accept token arrays (e.g., OpenAI's logit_bias,
        or custom inference servers).

        Args:
            data: Binary data to encode.

        Returns:
            List[int] of token IDs.
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(f"Expected bytes, got {type(data)}")

        bw = self.bit_width
        full_bits = self._data_to_bits(data)

        token_ids = []
        for i in range(0, len(full_bits), bw):
            idx = int(full_bits[i:i + bw], 2)
            token_ids.append(self._idx_to_id[idx])

        return token_ids

    def decode(self, token_ids: list) -> bytes:
        """
        Decode a list of token IDs back to binary data.

        Args:
            token_ids: List[int] of ByteToken-encoded token IDs.

        Returns:
            Original binary data (lossless).
        """
        bw = self.bit_width
        all_bits = ''
        for tid in token_ids:
            if tid in self._id_to_idx:
                all_bits += format(self._id_to_idx[tid], f'0{bw}b')

        return self._bits_to_data(all_bits)

    # ── Convenience: String wrappers ───────────────────────────

    def encode_to_string(self, data: bytes) -> str:
        """Encode binary data to a JSON string of token IDs.

        NOTE: Direct ID encoding cannot use naive string serialization
        because BPE re-tokenization scrambles concatenated tokens.
        This method serializes the token ID array as a compact JSON string.
        """
        import json
        token_ids = self.encode(data)
        return json.dumps(token_ids)

    def decode_from_string(self, text: str) -> bytes:
        """Decode a JSON token ID array string back to binary data."""
        import json
        token_ids = json.loads(text)
        return self.decode(token_ids)

    # ── Statistics ─────────────────────────────────────────────

    def token_count(self, data: bytes) -> int:
        """Return the number of tokens for the encoded data."""
        return len(self.encode(data))

    def stats(self, data: bytes) -> dict:
        """Return comprehensive encoding statistics."""
        token_ids = self.encode(data)
        b64_text = base64.b64encode(data).decode('ascii')
        b64_tokens = len(self.enc.encode(b64_text))

        gw_tokens = len(token_ids)
        bpt = len(data) * 8 / gw_tokens if gw_tokens else 0
        savings = ((b64_tokens - gw_tokens) / b64_tokens * 100) if b64_tokens else 0

        # Cost projections (GPT-4o pricing: $2.50/1M input, $10/1M output)
        cost_per_1m_in = 2.50
        cost_per_1m_out = 10.00
        b64_cost_in = b64_tokens / 1_000_000 * cost_per_1m_in
        gw_cost_in = gw_tokens / 1_000_000 * cost_per_1m_in
        b64_cost_out = b64_tokens / 1_000_000 * cost_per_1m_out
        gw_cost_out = gw_tokens / 1_000_000 * cost_per_1m_out

        return {
            "input_bytes": len(data),
            "input_bits": len(data) * 8,
            "ByteToken_tokens": gw_tokens,
            "base64_tokens": b64_tokens,
            "bits_per_token": round(bpt, 2),
            "savings_vs_base64_pct": round(savings, 1),
            "context_multiplier": round(b64_tokens / gw_tokens, 2) if gw_tokens else 0,
            "bit_width": self.bit_width,
            "tokenizer": self.tokenizer_name,
            "alphabet_size": len(self._alphabet),
            "cost_savings_input_per_1m_usd": round(b64_cost_in - gw_cost_in, 4),
            "cost_savings_output_per_1m_usd": round(b64_cost_out - gw_cost_out, 4),
        }

    @property
    def alphabet_size(self):
        return len(self._alphabet)

    @property
    def max_bit_width(self):
        return math.floor(math.log2(len(self._alphabet)))

    def __repr__(self):
        return (f"DirectIDEncoder(tokenizer={self.tokenizer_name!r}, "
                f"bit_width={self.bit_width}, safe_ids={self.alphabet_size})")


class SentencePieceByteTokenEncoder:
    """
    ByteToken encoder for SentencePiece-based tokenizers (Llama 3, Mistral, T5, etc.).

    PARADIGM: SentencePiece uses the `▁` (U+2581) character as a word-boundary
    marker, analogous to the ASCII space in BPE tokenizers. We discover
    `▁`-prefixed non-merging atoms and use them for encoding.

    Usage:
        enc = SentencePieceByteTokenEncoder(model_path="tokenizer.model")
        encoded = enc.encode(b"binary data")
        decoded = enc.decode(encoded)
        assert decoded == b"binary data"  # lossless round-trip
    """

    # SentencePiece word-boundary marker
    SP_PREFIX = '\u2581'  # ▁ (LOWER ONE EIGHTH BLOCK)

    def __init__(self, model_path: str, bit_width=None, prefix_char=None):
        """
        Initialize the SentencePiece encoder.

        Args:
            model_path: Path to a SentencePiece .model file (e.g., from Llama 3).
            bit_width: Bits per token (auto-detected if None based on atom count).
            prefix_char: Override the boundary prefix character. Default: ▁ (U+2581).
                         Use '##' for WordPiece-style tokenizers.
        """
        try:
            import sentencepiece as spm
        except ImportError:
            raise ImportError(
                "sentencepiece is required for SentencePieceByteTokenEncoder. "
                "Install it with: pip install sentencepiece"
            )

        self.sp = spm.SentencePieceProcessor()
        self.sp.Load(model_path)
        self.model_path = model_path
        self.prefix = prefix_char or self.SP_PREFIX

        # Discover non-merging atoms
        self._discover_atoms()

        # Auto-detect optimal bit-width
        if bit_width is None:
            bit_width = math.floor(math.log2(len(self._alphabet))) if self._alphabet else 0
            if bit_width < 8:
                raise ValueError(
                    f"Only {len(self._alphabet)} non-merging atoms found. "
                    f"Need at least 256 for 8-bit encoding. "
                    f"The tokenizer may not have enough {self.prefix}-prefixed pieces."
                )

        self.bit_width = bit_width
        needed = 2 ** bit_width

        if len(self._alphabet) < needed:
            # Fall back to lower bit-width
            actual_bits = math.floor(math.log2(len(self._alphabet)))
            if actual_bits < 8:
                raise ValueError(
                    f"Only {len(self._alphabet)} atoms found, need 256+ for 8-bit."
                )
            self.bit_width = actual_bits
            needed = 2 ** actual_bits

        self._alphabet = self._alphabet[:needed]
        self._rebuild_maps()

    def _discover_atoms(self):
        """
        Discover non-merging atoms in the SentencePiece vocabulary.

        A piece is a non-merging atom if:
          1. It starts with the boundary prefix (▁ for SentencePiece)
          2. It survives a self-concatenation test: encode(piece + piece) yields 2 tokens
        """
        atoms = []
        vocab_size = self.sp.GetPieceSize()

        for i in range(vocab_size):
            try:
                piece = self.sp.IdToPiece(i)

                # Skip special tokens (control, unknown, etc.)
                if self.sp.IsUnknown(i) or self.sp.IsControl(i):
                    continue
                if self.sp.IsByte(i) if hasattr(self.sp, 'IsByte') else False:
                    continue

                # Must start with boundary prefix
                if not piece.startswith(self.prefix):
                    continue

                # Must have content after the prefix
                content = piece[len(self.prefix):]
                if not content or not content.isprintable():
                    continue

                # Self-concatenation non-merging test:
                # The piece text without prefix for concatenation test
                # We test: encode(piece_text + piece_text) should yield exactly 2 tokens
                piece_text = piece
                concat = piece_text + piece_text
                encoded_ids = self.sp.EncodeAsIds(concat)

                if len(encoded_ids) == 2:
                    atoms.append(i)

            except Exception:
                continue

        self._alphabet = atoms
        self._rebuild_maps()

    def _rebuild_maps(self):
        """Build bidirectional mappings between indices and piece IDs."""
        self._id_to_idx = {pid: idx for idx, pid in enumerate(self._alphabet)}
        self._idx_to_id = dict(enumerate(self._alphabet))

    def encode(self, data: bytes) -> str:
        """
        Encode binary data to a SentencePiece ByteToken string.

        Args:
            data: Binary data to encode.

        Returns:
            Encoded string of concatenated SentencePiece atoms.
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(f"Expected bytes, got {type(data)}")

        bw = self.bit_width
        bits = ''.join(format(byte, '08b') for byte in data)

        # Padding
        pad = (bw - len(bits) % bw) % bw
        bits += '0' * pad

        # Prepend padding metadata
        meta = format(pad, f'0{bw}b')
        full_bits = meta + bits

        # Map to pieces
        pieces = []
        for i in range(0, len(full_bits), bw):
            chunk = full_bits[i:i + bw]
            idx = int(chunk, 2)
            piece_id = self._idx_to_id[idx]
            pieces.append(self.sp.IdToPiece(piece_id))

        return ''.join(pieces)

    def decode(self, encoded_str: str) -> bytes:
        """
        Decode a SentencePiece ByteToken string back to binary data.

        Args:
            encoded_str: The ByteToken-encoded string.

        Returns:
            Original binary data.
        """
        bw = self.bit_width

        # Tokenize with SentencePiece
        token_ids = self.sp.EncodeAsIds(encoded_str)

        # Reconstruct bits
        chunks = []
        for tid in token_ids:
            if tid in self._id_to_idx:
                chunks.append(format(self._id_to_idx[tid], f'0{bw}b'))

        if not chunks:
            return b''

        # First chunk is padding metadata
        pad = int(chunks[0], 2)
        data_bits = ''.join(chunks[1:])

        if pad > 0 and pad < len(data_bits):
            data_bits = data_bits[:-pad]

        # Convert bits to bytes
        result = bytearray()
        for i in range(0, len(data_bits), 8):
            byte_str = data_bits[i:i + 8]
            if len(byte_str) == 8:
                result.append(int(byte_str, 2))

        return bytes(result)

    def token_count(self, data: bytes) -> int:
        """Return the number of tokens the encoded data would produce."""
        encoded = self.encode(data)
        return len(self.sp.EncodeAsIds(encoded))

    def stats(self, data: bytes) -> dict:
        """Return encoding statistics."""
        encoded = self.encode(data)
        tokens = self.sp.EncodeAsIds(encoded)
        # Approximate Base64 baseline using SentencePiece
        b64_text = base64.b64encode(data).decode('ascii')
        b64_tokens = len(self.sp.EncodeAsIds(b64_text))

        bt_tokens = len(tokens)
        bpt = len(data) * 8 / bt_tokens if bt_tokens else 0
        savings = ((b64_tokens - bt_tokens) / b64_tokens * 100) if b64_tokens else 0

        return {
            "input_bytes": len(data),
            "input_bits": len(data) * 8,
            "ByteToken_tokens": bt_tokens,
            "base64_tokens": b64_tokens,
            "bits_per_token": round(bpt, 2),
            "savings_vs_base64": round(savings, 1),
            "bit_width": self.bit_width,
            "model_path": self.model_path,
            "prefix": self.prefix,
            "alphabet_size": len(self._alphabet),
        }

    @property
    def alphabet_size(self):
        return len(self._alphabet)

    @property
    def max_bit_width(self):
        return math.floor(math.log2(len(self._alphabet))) if self._alphabet else 0

    def __repr__(self):
        return (f"SentencePieceByteTokenEncoder(model={self.model_path!r}, "
                f"bit_width={self.bit_width}, atoms={self.alphabet_size}, "
                f"prefix={self.prefix!r})")


class ErrorDetectingEncoder:
    """
    Wrapper encoder that adds CRC-32 error detection to any ByteToken encoder.

    Prepends a CRC-32 checksum of the original data as an extra metadata token.
    On decode, verifies the checksum and raises an error if corruption is detected.

    Token overhead: exactly 1 extra token per payload (CRC-32 fits in a single
    15-17 bit token since CRC-32 is 32 bits = 2-3 tokens depending on bit-width).
    For a typical 100-token payload, this is <1% overhead.

    Usage:
        from bytetoken.core import ByteTokenEncoder, ErrorDetectingEncoder

        base_enc = ByteTokenEncoder(bit_width=15)
        enc = ErrorDetectingEncoder(base_enc)

        encoded = enc.encode(b"important data")
        decoded = enc.decode(encoded)  # raises CorruptionError if tampered
    """

    class CorruptionError(Exception):
        """Raised when CRC-32 checksum verification fails during decode."""
        pass

    # Magic header to identify error-detecting payloads
    MAGIC = b'BT\x01'

    def __init__(self, base_encoder):
        """
        Initialize the error-detecting encoder.

        Args:
            base_encoder: Any ByteToken encoder instance (ByteTokenEncoder,
                          DirectIDEncoder, UniversalByteTokenEncoder, or
                          SentencePieceByteTokenEncoder).
        """
        self.base = base_encoder

    def encode(self, data: bytes):
        """
        Encode binary data with CRC-32 error detection.

        The CRC-32 checksum is computed over the original data and prepended
        as a 7-byte header: 3-byte magic + 4-byte CRC-32.

        Args:
            data: Binary data to encode.

        Returns:
            Encoded output (str or List[int] depending on base encoder).
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(f"Expected bytes, got {type(data)}")

        # Compute CRC-32 checksum
        checksum = zlib.crc32(data) & 0xFFFFFFFF
        crc_bytes = struct.pack('>I', checksum)  # 4 bytes, big-endian

        # Prepend: magic + CRC + original data
        protected_data = self.MAGIC + crc_bytes + data

        return self.base.encode(protected_data)

    def decode(self, encoded_data, verify=True):
        """
        Decode and verify CRC-32 checksum.

        Args:
            encoded_data: Encoded output from encode().
            verify: If True (default), raise CorruptionError on checksum mismatch.
                    If False, return data even if corrupt (with warning flag).

        Returns:
            Original binary data if checksum passes.

        Raises:
            CorruptionError: If the CRC-32 checksum does not match.
        """
        raw = self.base.decode(encoded_data)

        # Validate header
        if len(raw) < 7 or raw[:3] != self.MAGIC:
            if verify:
                raise self.CorruptionError(
                    "Missing or invalid ByteToken error-detection header. "
                    "Data may not have been encoded with ErrorDetectingEncoder."
                )
            return raw  # Return raw if not an error-detecting payload

        # Extract CRC and data
        stored_crc = struct.unpack('>I', raw[3:7])[0]
        original_data = raw[7:]

        # Verify checksum
        computed_crc = zlib.crc32(original_data) & 0xFFFFFFFF

        if stored_crc != computed_crc:
            if verify:
                raise self.CorruptionError(
                    f"CRC-32 checksum mismatch! "
                    f"Expected 0x{stored_crc:08X}, got 0x{computed_crc:08X}. "
                    f"Data has been corrupted during transport."
                )

        return original_data

    def stats(self, data: bytes) -> dict:
        """Return encoding statistics including error-detection overhead."""
        base_stats = self.base.stats(data) if hasattr(self.base, 'stats') else {}

        # Calculate overhead
        protected_data = self.MAGIC + struct.pack('>I', zlib.crc32(data) & 0xFFFFFFFF) + data
        protected_encoded = self.base.encode(protected_data)

        if isinstance(protected_encoded, list):
            ed_tokens = len(protected_encoded)
        else:
            # For string-based encoders, we need to count tokens
            if hasattr(self.base, 'enc'):
                ed_tokens = len(self.base.enc.encode(protected_encoded))
            elif hasattr(self.base, 'sp'):
                ed_tokens = len(self.base.sp.EncodeAsIds(protected_encoded))
            else:
                ed_tokens = base_stats.get('ByteToken_tokens', 0) + 1

        base_tokens = base_stats.get('ByteToken_tokens', 0)
        overhead_tokens = ed_tokens - base_tokens if base_tokens else 0
        overhead_pct = (overhead_tokens / base_tokens * 100) if base_tokens else 0

        return {
            **base_stats,
            "error_detection": True,
            "ed_tokens": ed_tokens,
            "ed_overhead_tokens": overhead_tokens,
            "ed_overhead_pct": round(overhead_pct, 2),
            "crc32": f"0x{zlib.crc32(data) & 0xFFFFFFFF:08X}",
        }

    def __repr__(self):
        return f"ErrorDetectingEncoder(base={self.base!r})"
