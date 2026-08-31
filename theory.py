"""Scoped density analysis for ByteToken.

This module computes empirical tokenizer-alphabet statistics and the elementary
fixed-width capacity bound used by the paper. It is not a formal proof that
ByteToken is globally optimal among all tokenizer-aware encodings. A
self-concatenation check is only a candidate filter; it does not prove arbitrary
heterogeneous concatenation safety.
"""
import argparse, json, math


def fixed_width_bound(alphabet_size: int) -> int:
    return math.floor(math.log2(alphabet_size)) if alphabet_size > 0 else 0


class BPEMergeGraph:
    """Historical compatibility wrapper for empirical tokenizer scans."""
    def __init__(self, tokenizer_name: str = "o200k_base"):
        import tiktoken
        self.enc = tiktoken.get_encoding(tokenizer_name); self.tokenizer_name = tokenizer_name; self.vocab_size = self.enc.n_vocab

    def discover_nonmerging_atoms(self, prefix_filter: str = " ") -> dict:
        candidates, rejected = [], []
        for token_id in range(self.vocab_size):
            try: text = self.enc.decode([token_id])
            except Exception: continue
            if prefix_filter and not text.startswith(prefix_filter): continue
            if not text or not text.isprintable(): continue
            try: stable = self.enc.encode(text + text) == [token_id, token_id]
            except Exception: stable = False
            (candidates if stable else rejected).append(token_id)
        return {"atoms": candidates, "merge_victims": rejected, "interpretation": "self-pair-stable candidates; full sequence round-trips are still required"}

    def compute_bounds(self) -> dict:
        space = self.discover_nonmerging_atoms(" "); safe = []
        for token_id in range(self.vocab_size):
            try:
                raw = self.enc.decode_single_token_bytes(token_id); text = raw.decode("utf-8", errors="strict")
                if self.enc.encode(text) == [token_id]: safe.append(token_id)
            except Exception: continue
        return {"tokenizer": self.tokenizer_name, "vocab_size": self.vocab_size, "space_prefixed_self_pair_stable": len(space["atoms"]), "space_fixed_width_bound": fixed_width_bound(len(space["atoms"])), "roundtrip_safe_ids": len(safe), "direct_id_fixed_width_bound": fixed_width_bound(len(safe)), "scope": "Bounds apply only to the fixed-symbol model; variable-length, stateful, merge-exploiting, multi-token, and provider-specific encodings are outside this calculation."}


def main():
    parser = argparse.ArgumentParser(description="Empirical ByteToken alphabet and fixed-width bound analysis"); parser.add_argument("--tokenizer", default="o200k_base"); args = parser.parse_args()
    print(json.dumps(BPEMergeGraph(args.tokenizer).compute_bounds(), indent=2, sort_keys=True))


if __name__ == "__main__": main()
