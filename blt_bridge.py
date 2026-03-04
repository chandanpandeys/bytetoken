"""
ByteToken — BLT Bridge Protocol
================================
Hybrid encoding layer that works with BOTH BPE-tokenized models
AND byte-level (BLT) models through a unified API.

The bridge detects the model type and automatically selects:
  - ByteToken encoding for BPE models (token-level optimization)
  - Raw byte pass-through for BLT models (no tokenizer to optimize)
  - Graceful degradation with automatic fallback

This is the August 2026 milestone.

Usage:
    from bytetoken.blt_bridge import BLTBridge

    bridge = BLTBridge()
    payload = bridge.encode(data, model="gpt-4o")       # ByteToken mode
    payload = bridge.encode(data, model="blt-llama")     # Raw byte mode
    payload = bridge.encode(data, model="auto")          # Auto-detect

    decoded = bridge.decode(payload)
"""
import os
import sys
import json
import math
import base64
from dataclasses import dataclass, field
from typing import Optional, Union, List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class ModelProfile:
    """Profile describing a model's tokenization characteristics."""
    name: str
    tokenizer_type: str        # "bpe", "sentencepiece", "byte_level", "none"
    tokenizer_name: str        # e.g., "o200k_base", "llama3_sp", "raw_bytes"
    supports_token_ids: bool   # Can we pass raw token ID arrays?
    max_context: int           # Maximum context window in tokens/bytes
    byte_level: bool           # Is this a BLT/byte-level model?
    notes: str = ""

    @property
    def best_encoding(self) -> str:
        """Determine the best ByteToken encoding for this model."""
        if self.byte_level:
            return "raw_bytes"
        elif self.supports_token_ids and self.tokenizer_type == "bpe":
            return "direct_id_17bit"
        elif self.tokenizer_type == "bpe":
            return "bytetoken_15bit"
        elif self.tokenizer_type == "sentencepiece":
            return "sentencepiece"
        else:
            return "base64_fallback"


# ── Model Registry ────────────────────────────────────────────

MODEL_REGISTRY: Dict[str, ModelProfile] = {
    # OpenAI models (BPE)
    "gpt-4o": ModelProfile(
        name="GPT-4o", tokenizer_type="bpe", tokenizer_name="o200k_base",
        supports_token_ids=True, max_context=128_000, byte_level=False,
    ),
    "gpt-4o-mini": ModelProfile(
        name="GPT-4o Mini", tokenizer_type="bpe", tokenizer_name="o200k_base",
        supports_token_ids=True, max_context=128_000, byte_level=False,
    ),
    "gpt-5": ModelProfile(
        name="GPT-5", tokenizer_type="bpe", tokenizer_name="o200k_harmony",
        supports_token_ids=True, max_context=256_000, byte_level=False,
        notes="Reasoning tokens billed separately",
    ),
    # Anthropic models (BPE-like)
    "claude-3.5-sonnet": ModelProfile(
        name="Claude 3.5 Sonnet", tokenizer_type="bpe", tokenizer_name="claude_bpe",
        supports_token_ids=False, max_context=200_000, byte_level=False,
    ),
    "claude-4-opus": ModelProfile(
        name="Claude 4 Opus", tokenizer_type="bpe", tokenizer_name="claude_bpe_v2",
        supports_token_ids=False, max_context=500_000, byte_level=False,
    ),
    # Google models
    "gemini-2.5-flash": ModelProfile(
        name="Gemini 2.5 Flash", tokenizer_type="sentencepiece",
        tokenizer_name="gemini_sp",
        supports_token_ids=False, max_context=1_000_000, byte_level=False,
    ),
    # Meta BLT models (byte-level)
    "blt-llama-8b": ModelProfile(
        name="BLT-Llama 8B", tokenizer_type="byte_level",
        tokenizer_name="raw_bytes",
        supports_token_ids=False, max_context=512_000, byte_level=True,
        notes="Byte Latent Transformer — no tokenizer",
    ),
    "blt-llama-70b": ModelProfile(
        name="BLT-Llama 70B", tokenizer_type="byte_level",
        tokenizer_name="raw_bytes",
        supports_token_ids=False, max_context=512_000, byte_level=True,
        notes="Byte Latent Transformer — no tokenizer",
    ),
    # Open-source SentencePiece models
    "llama-3-8b": ModelProfile(
        name="Llama 3 8B", tokenizer_type="sentencepiece",
        tokenizer_name="llama3_sp",
        supports_token_ids=True, max_context=128_000, byte_level=False,
    ),
    "mistral-7b": ModelProfile(
        name="Mistral 7B", tokenizer_type="sentencepiece",
        tokenizer_name="mistral_sp",
        supports_token_ids=True, max_context=32_000, byte_level=False,
    ),
    # Aleph Alpha T-Free (no tokenizer)
    "t-free": ModelProfile(
        name="T-Free", tokenizer_type="none", tokenizer_name="none",
        supports_token_ids=False, max_context=128_000, byte_level=True,
        notes="Token-free architecture — operates on raw characters",
    ),
}


@dataclass
class BridgePayload:
    """Self-describing payload container for the BLT bridge."""
    encoding: str              # "bytetoken_15bit", "direct_id_17bit", "raw_bytes", etc.
    data: Union[str, bytes, List[int]]  # Encoded data
    model: str                 # Target model name
    original_size: int         # Original data size in bytes
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        data_repr = self.data if isinstance(self.data, str) else (
            base64.b64encode(self.data).decode() if isinstance(self.data, bytes)
            else self.data
        )
        return {
            "encoding": self.encoding,
            "data": data_repr,
            "model": self.model,
            "original_size": self.original_size,
            "metadata": self.metadata,
        }


class BLTBridge:
    """
    Unified bridge for encoding binary data across BPE and byte-level models.

    Automatically detects the target model type and selects the optimal
    encoding strategy: ByteToken for BPE models, raw bytes for BLT models.
    """

    def __init__(self):
        self._encoders = {}

    def get_profile(self, model: str) -> ModelProfile:
        """Look up a model's profile from the registry."""
        model_lower = model.lower().replace(" ", "-")
        if model_lower in MODEL_REGISTRY:
            return MODEL_REGISTRY[model_lower]

        # Fuzzy match
        for key, profile in MODEL_REGISTRY.items():
            if model_lower in key or key in model_lower:
                return profile

        raise ValueError(
            f"Unknown model '{model}'. Known models: {list(MODEL_REGISTRY.keys())}"
        )

    def _get_bpe_encoder(self, tokenizer_name: str):
        """Lazy-load a BPE encoder."""
        if tokenizer_name not in self._encoders:
            from bytetoken.core import ByteTokenEncoder
            # Use o200k_base as default for unknown BPE tokenizers
            tok = tokenizer_name if tokenizer_name in ["cl100k_base", "o200k_base"] else "o200k_base"
            self._encoders[tokenizer_name] = ByteTokenEncoder(tokenizer=tok, bit_width=15)
        return self._encoders[tokenizer_name]

    def _get_directid_encoder(self, tokenizer_name: str):
        """Lazy-load a DirectID encoder."""
        key = f"did_{tokenizer_name}"
        if key not in self._encoders:
            from bytetoken.core import DirectIDEncoder
            tok = tokenizer_name if tokenizer_name in ["cl100k_base", "o200k_base"] else "o200k_base"
            self._encoders[key] = DirectIDEncoder(tokenizer=tok)
        return self._encoders[key]

    def encode(self, data: bytes, model: str = "gpt-4o") -> BridgePayload:
        """
        Encode binary data optimally for the target model.

        Args:
            data: Raw bytes to encode.
            model: Target model name (e.g., "gpt-4o", "blt-llama-8b").

        Returns:
            BridgePayload containing the encoded data and metadata.
        """
        profile = self.get_profile(model)
        encoding = profile.best_encoding

        if encoding == "raw_bytes":
            # BLT models: pass raw bytes directly
            return BridgePayload(
                encoding="raw_bytes",
                data=data,
                model=model,
                original_size=len(data),
                metadata={
                    "model_type": "byte_level",
                    "notes": profile.notes,
                    "optimization": "none (native byte processing)",
                },
            )

        elif encoding == "direct_id_17bit":
            # BPE with token ID support: maximum density
            enc = self._get_directid_encoder(profile.tokenizer_name)
            token_ids = enc.encode(data)
            return BridgePayload(
                encoding="direct_id_17bit",
                data=token_ids,
                model=model,
                original_size=len(data),
                metadata={
                    "tokens": len(token_ids),
                    "bits_per_token": round(len(data) * 8 / len(token_ids), 2),
                    "tokenizer": profile.tokenizer_name,
                },
            )

        elif encoding == "bytetoken_15bit":
            # BPE without token ID support: string encoding
            enc = self._get_bpe_encoder(profile.tokenizer_name)
            encoded_str = enc.encode(data)
            return BridgePayload(
                encoding="bytetoken_15bit",
                data=encoded_str,
                model=model,
                original_size=len(data),
                metadata={
                    "tokenizer": profile.tokenizer_name,
                    "encoded_length": len(encoded_str),
                },
            )

        elif encoding == "sentencepiece":
            # SentencePiece models: fall back to 15-bit BPE
            # (full SP encoder requires model file)
            enc = self._get_bpe_encoder("o200k_base")
            encoded_str = enc.encode(data)
            return BridgePayload(
                encoding="bytetoken_15bit_compat",
                data=encoded_str,
                model=model,
                original_size=len(data),
                metadata={
                    "note": "Using BPE compat mode (SP model file not loaded)",
                    "tokenizer": profile.tokenizer_name,
                },
            )

        else:
            # Fallback: Base64
            b64 = base64.b64encode(data).decode('ascii')
            return BridgePayload(
                encoding="base64_fallback",
                data=b64,
                model=model,
                original_size=len(data),
                metadata={"note": "No ByteToken optimization available"},
            )

    def decode(self, payload: BridgePayload) -> bytes:
        """Decode a BridgePayload back to raw bytes."""
        if payload.encoding == "raw_bytes":
            return payload.data if isinstance(payload.data, bytes) else bytes(payload.data)

        elif payload.encoding == "direct_id_17bit":
            profile = self.get_profile(payload.model)
            enc = self._get_directid_encoder(profile.tokenizer_name)
            return enc.decode(payload.data)

        elif payload.encoding in ("bytetoken_15bit", "bytetoken_15bit_compat"):
            profile = self.get_profile(payload.model)
            tok = profile.tokenizer_name
            enc = self._get_bpe_encoder(tok if tok in ["cl100k_base", "o200k_base"] else "o200k_base")
            return enc.decode(payload.data)

        elif payload.encoding == "base64_fallback":
            return base64.b64decode(payload.data)

        else:
            raise ValueError(f"Unknown encoding: {payload.encoding}")

    def compare_models(self, data: bytes) -> dict:
        """Compare encoding efficiency across all registered models."""
        results = {}
        for model_name, profile in MODEL_REGISTRY.items():
            try:
                payload = self.encode(data, model=model_name)
                if payload.encoding == "raw_bytes":
                    tokens = len(data)  # bytes = "tokens" for BLT
                    bpt = 8.0
                elif isinstance(payload.data, list):
                    tokens = len(payload.data)
                    bpt = len(data) * 8 / tokens if tokens else 0
                else:
                    # Estimate tokens for string encodings
                    tokens = payload.metadata.get("tokens", len(str(payload.data)) // 4)
                    bpt = len(data) * 8 / tokens if tokens else 0

                results[model_name] = {
                    "encoding": payload.encoding,
                    "tokens_or_bytes": tokens,
                    "bits_per_unit": round(bpt, 2),
                    "model_type": profile.tokenizer_type,
                    "byte_level": profile.byte_level,
                }
            except Exception as e:
                results[model_name] = {"error": str(e)}

        return results


# ── Multi-Token Prediction Analyzer ───────────────────────────

class MultiTokenPredictionAnalyzer:
    """
    Analyzes whether ByteToken atoms remain independently decodable
    under multi-token prediction (MTP) inference.

    MTP models predict N tokens simultaneously. If atoms are predicted
    as a group, the non-merging property must hold not just pairwise
    but across N-token windows.

    This is part of the August 2026 milestone.
    """

    def __init__(self, tokenizer: str = "o200k_base"):
        import tiktoken
        self.enc = tiktoken.get_encoding(tokenizer)
        self.tokenizer = tokenizer

    def test_n_token_independence(self, atoms: list, n: int = 3, trials: int = 1000) -> dict:
        """
        Test if atoms remain independently decodable in N-token windows.

        For MTP with window_size=N, we concatenate N random atoms and verify
        that tokenization produces exactly N tokens.

        Args:
            atoms: List of atom strings to test.
            n: MTP window size (typically 2-4).
            trials: Number of random N-tuples to test.

        Returns:
            dict with pass rate and any failures.
        """
        import random
        random.seed(42)

        passed = 0
        failed = 0
        failures = []

        for _ in range(min(trials, len(atoms) ** n)):
            selected = random.choices(atoms, k=n)
            concat = ''.join(selected)
            token_ids = self.enc.encode(concat)

            if len(token_ids) == n:
                passed += 1
            else:
                failed += 1
                if len(failures) < 10:
                    failures.append({
                        "atoms": selected,
                        "expected_tokens": n,
                        "actual_tokens": len(token_ids),
                        "token_ids": token_ids,
                    })

        total = passed + failed
        return {
            "window_size": n,
            "trials": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 2) if total else 0,
            "failures_sample": failures,
            "verdict": "SAFE" if failed == 0 else f"UNSAFE ({failed} failures)",
        }

    def full_analysis(self, max_window: int = 5) -> dict:
        """
        Run comprehensive MTP compatibility analysis.

        Tests all window sizes from 2 to max_window.
        """
        from bytetoken.core import ByteTokenEncoder

        enc = ByteTokenEncoder(tokenizer=self.tokenizer, bit_width=15)
        # Get the atom strings
        atoms = [enc.enc.decode([enc._alphabet[i]]) for i in range(min(100, len(enc._alphabet)))]

        results = {
            "tokenizer": self.tokenizer,
            "num_atoms_tested": len(atoms),
            "windows": {},
        }

        for n in range(2, max_window + 1):
            result = self.test_n_token_independence(atoms, n=n)
            results["windows"][f"mtp_{n}"] = result

        # Overall verdict
        all_safe = all(
            r["failed"] == 0 for r in results["windows"].values()
        )
        results["overall_verdict"] = (
            "ByteToken atoms are MTP-SAFE up to window=" + str(max_window)
            if all_safe else
            "WARNING: Some atoms merge under multi-token prediction"
        )

        return results


# ── Multimodal Tokenizer Analyzer ─────────────────────────────

class MultimodalTokenizerAnalyzer:
    """
    Framework for analyzing non-merging property in multimodal tokenizers.

    Multimodal tokenizers (GPT-4V, Gemini, Claude 3) encode text, images,
    and audio into a shared vocabulary space. This analyzer checks whether
    ByteToken's non-merging property extends to multimodal token IDs.

    This is the September 2026 milestone framework.
    """

    def __init__(self):
        self.results = {}

    def analyze_text_vocab_partition(self, tokenizer_name: str = "o200k_base") -> dict:
        """
        Analyze the text portion of a multimodal tokenizer's vocabulary.

        Identifies which token ID ranges are used for:
        - Text tokens (our current ByteToken atoms)
        - Reserved/special tokens
        - Potential multimodal slots (high-ID ranges)
        """
        import tiktoken
        enc = tiktoken.get_encoding(tokenizer_name)

        total_vocab = enc.n_vocab
        text_tokens = 0
        special_tokens = 0
        printable_tokens = 0
        space_prefixed = 0

        # Sample the vocabulary
        for i in range(min(total_vocab, 200_000)):
            try:
                decoded = enc.decode([i])
                text_tokens += 1
                if decoded.isprintable():
                    printable_tokens += 1
                if decoded.startswith(' '):
                    space_prefixed += 1
            except Exception:
                special_tokens += 1

        return {
            "tokenizer": tokenizer_name,
            "total_vocab_size": total_vocab,
            "text_tokens": text_tokens,
            "special_tokens": special_tokens,
            "printable_tokens": printable_tokens,
            "space_prefixed_tokens": space_prefixed,
            "multimodal_slots_estimate": total_vocab - text_tokens - special_tokens,
            "text_coverage_pct": round(text_tokens / total_vocab * 100, 1),
            "notes": (
                "Multimodal tokens (image patches, audio frames) typically occupy "
                "high-ID ranges above the text vocabulary. ByteToken atoms must "
                "not overlap with these reserved ranges."
            ),
        }

    def check_atom_multimodal_safety(self, tokenizer_name: str = "o200k_base") -> dict:
        """
        Verify that ByteToken atoms don't conflict with multimodal token ranges.
        """
        from bytetoken.core import ByteTokenEncoder, DirectIDEncoder

        enc15 = ByteTokenEncoder(tokenizer=tokenizer_name, bit_width=15)
        did = DirectIDEncoder(tokenizer=tokenizer_name)

        import tiktoken
        tok = tiktoken.get_encoding(tokenizer_name)

        # Get atom ID ranges
        string_atoms = list(enc15.alphabet.values()) if hasattr(enc15, 'alphabet') else []
        did_atoms = list(did._safe_ids) if hasattr(did, '_safe_ids') else []

        # Heuristic: multimodal tokens are typically in the top 10% of vocab
        vocab_size = tok.n_vocab
        multimodal_threshold = int(vocab_size * 0.9)

        atoms_in_multimodal_range = sum(1 for a in did_atoms if a >= multimodal_threshold)

        return {
            "tokenizer": tokenizer_name,
            "vocab_size": vocab_size,
            "multimodal_threshold": multimodal_threshold,
            "total_did_atoms": len(did_atoms),
            "atoms_in_multimodal_range": atoms_in_multimodal_range,
            "safe": atoms_in_multimodal_range == 0,
            "verdict": (
                "SAFE: No ByteToken atoms in estimated multimodal range"
                if atoms_in_multimodal_range == 0 else
                f"WARNING: {atoms_in_multimodal_range} atoms may conflict with multimodal tokens"
            ),
        }

    def generate_report(self) -> dict:
        """Generate a comprehensive multimodal safety report."""
        report = {
            "title": "ByteToken Multimodal Tokenizer Safety Analysis",
            "date": "2026-09",
            "tokenizers": {},
        }

        for tok_name in ["cl100k_base", "o200k_base"]:
            report["tokenizers"][tok_name] = {
                "vocab_partition": self.analyze_text_vocab_partition(tok_name),
                "atom_safety": self.check_atom_multimodal_safety(tok_name),
            }

        return report


# ── CLI Demo ───────────────────────────────────────────────────

if __name__ == "__main__":
    import json as _json

    print("=" * 65)
    print("  ByteToken BLT Bridge Protocol Demo")
    print("=" * 65)

    bridge = BLTBridge()
    data = os.urandom(500)

    print("\n[1] Model Comparison (500 bytes random data):\n")
    comparison = bridge.compare_models(data)
    for model, stats in comparison.items():
        if "error" in stats:
            continue
        print(f"  {model:25s} | {stats['encoding']:25s} | "
              f"{stats['tokens_or_bytes']:6d} units | "
              f"{stats['bits_per_unit']:5.1f} bpt")

    print(f"\n[2] Round-trip verification:\n")
    for model in ["gpt-4o", "blt-llama-8b", "claude-3.5-sonnet"]:
        payload = bridge.encode(data, model=model)
        decoded = bridge.decode(payload)
        status = "PASS" if decoded == data else "FAIL"
        print(f"  {model:25s} [{payload.encoding}] -> {status}")

    print(f"\n[3] Multi-Token Prediction Analysis:\n")
    mtp = MultiTokenPredictionAnalyzer()
    mtp_results = mtp.full_analysis(max_window=4)
    for window, result in mtp_results["windows"].items():
        print(f"  {window}: {result['pass_rate']}% pass "
              f"({result['passed']}/{result['trials']}) -> {result['verdict']}")
    print(f"  Overall: {mtp_results['overall_verdict']}")

    print(f"\n[4] Multimodal Safety Check:\n")
    mm = MultimodalTokenizerAnalyzer()
    for tok in ["cl100k_base", "o200k_base"]:
        safety = mm.check_atom_multimodal_safety(tok)
        print(f"  {tok}: {safety['verdict']}")

    print("\n" + "=" * 65)
