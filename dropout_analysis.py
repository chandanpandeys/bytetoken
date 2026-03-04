"""
ByteToken — BPE-Dropout Robustness Analysis
=============================================
Simulates BPE-dropout (stochastic merge rule skipping) to verify that
ByteToken's non-merging atoms remain stable under dropout-style
tokenization variants.

This resolves Limitation #7 from §9.2 of the paper.

BPE-dropout (Provilkov et al., 2020) randomly skips merge operations 
during training, making models robust to multiple tokenizations. We 
simulate this by accessing tiktoken's internal merge table and applying
probabilistic merge skipping.

Usage:
    python -m bytetoken.dropout_analysis                      # full analysis
    python -m bytetoken.dropout_analysis --rate 0.1           # specific dropout rate
    python -m bytetoken.dropout_analysis --tokenizer cl100k_base
"""
import os
import sys
import math
import random
import time
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class BPEDropoutSimulator:
    """
    Simulates BPE-dropout by performing BPE merging with stochastic
    rule skipping on raw byte sequences.
    
    Instead of relying on tiktoken's compiled C tokenizer (which doesn't
    support dropout), we re-implement the BPE merge loop in Python with
    dropout support using tiktoken's merge rankings.
    """

    def __init__(self, tokenizer_name: str = "o200k_base"):
        import tiktoken
        self.enc = tiktoken.get_encoding(tokenizer_name)
        self.tokenizer_name = tokenizer_name
        
        # Extract the merge rankings from tiktoken
        # tiktoken stores merges as: bytes -> rank (lower rank = higher priority)
        self._mergeable_ranks = self.enc._mergeable_ranks
        # Build reverse lookup: rank -> token bytes
        self._rank_to_bytes = {v: k for k, v in self._mergeable_ranks.items()}

    def _bpe_merge(self, tokens: List[bytes], dropout_rate: float = 0.0,
                   rng: Optional[random.Random] = None) -> List[bytes]:
        """
        Perform BPE merging with optional dropout.
        
        Args:
            tokens: List of byte sequences (initial: one byte each)
            dropout_rate: Probability of skipping each merge (0.0 = standard BPE)
            rng: Random number generator for reproducibility
            
        Returns:
            List of merged byte sequences (final tokens)
        """
        if rng is None:
            rng = random.Random()
        
        if len(tokens) <= 1:
            return tokens

        while True:
            # Find the best (lowest rank) merge among adjacent pairs
            best_rank = float('inf')
            best_idx = -1
            
            for i in range(len(tokens) - 1):
                pair = tokens[i] + tokens[i + 1]
                rank = self._mergeable_ranks.get(pair, float('inf'))
                if rank < best_rank:
                    best_rank = rank
                    best_idx = i
            
            if best_idx == -1 or best_rank == float('inf'):
                break  # No more merges possible
            
            # BPE-dropout: randomly skip this merge
            if dropout_rate > 0 and rng.random() < dropout_rate:
                # Skip this merge — mark pair as "unmerged" for this round
                # We need to find the NEXT best merge that isn't this one
                # Simple approach: try all merges, skip randomly
                applied_any = False
                candidates = []
                
                for i in range(len(tokens) - 1):
                    pair = tokens[i] + tokens[i + 1]
                    rank = self._mergeable_ranks.get(pair, float('inf'))
                    if rank != float('inf'):
                        candidates.append((rank, i))
                
                candidates.sort()
                
                for rank, idx in candidates:
                    if rng.random() >= dropout_rate:
                        # Apply this merge
                        merged = tokens[idx] + tokens[idx + 1]
                        tokens = tokens[:idx] + [merged] + tokens[idx + 2:]
                        applied_any = True
                        break
                
                if not applied_any:
                    break
            else:
                # Standard merge: apply the best merge
                merged = tokens[best_idx] + tokens[best_idx + 1]
                tokens = tokens[:best_idx] + [merged] + tokens[best_idx + 2:]
        
        return tokens

    def tokenize_with_dropout(self, text: str, dropout_rate: float = 0.1,
                              rng: Optional[random.Random] = None) -> List[int]:
        """
        Tokenize text using BPE with dropout.
        
        Returns list of token IDs (using tiktoken's ranking as ID mapping).
        """
        if rng is None:
            rng = random.Random()
        
        # Convert to bytes, then split into individual bytes
        raw_bytes = text.encode('utf-8')
        tokens = [bytes([b]) for b in raw_bytes]
        
        # Apply BPE merging with dropout
        merged = self._bpe_merge(tokens, dropout_rate=dropout_rate, rng=rng)
        
        # Convert back to token IDs
        ids = []
        for tok_bytes in merged:
            if tok_bytes in self._mergeable_ranks:
                ids.append(self._mergeable_ranks[tok_bytes])
            else:
                # Unknown merge result — encode each byte separately
                for b in tok_bytes:
                    ids.append(self._mergeable_ranks.get(bytes([b]), b))
        
        return ids

    def test_atom_stability(self, atom_ids: List[int], dropout_rate: float = 0.1,
                            trials: int = 100, seed: int = 42) -> Dict:
        """
        Test whether non-merging atoms remain atomic under BPE-dropout.
        
        For each atom, run multiple dropout trials and check:
        1. Does the atom still tokenize as a single token?
        2. Does self-concatenation still produce exactly 2 tokens?
        """
        rng = random.Random(seed)
        
        results = {
            "dropout_rate": dropout_rate,
            "trials_per_atom": trials,
            "atoms_tested": 0,
            "atoms_stable": 0,
            "atoms_fragile": 0,
            "stability_details": [],
        }

        sample_atoms = atom_ids[:min(200, len(atom_ids))]
        
        for atom_id in sample_atoms:
            try:
                atom_str = self.enc.decode([atom_id])
            except Exception:
                continue
            
            results["atoms_tested"] += 1
            
            single_failures = 0
            concat_failures = 0
            
            for _ in range(trials):
                # Test 1: Does atom tokenize as single token?
                dropout_ids = self.tokenize_with_dropout(atom_str, dropout_rate, rng)
                if len(dropout_ids) != 1:
                    single_failures += 1
                
                # Test 2: Does self-concat produce 2 tokens?
                concat = atom_str + atom_str
                concat_ids = self.tokenize_with_dropout(concat, dropout_rate, rng)
                if len(concat_ids) != 2:
                    concat_failures += 1
            
            is_stable = (single_failures == 0 and concat_failures == 0)
            if is_stable:
                results["atoms_stable"] += 1
            else:
                results["atoms_fragile"] += 1
                if len(results["stability_details"]) < 20:
                    results["stability_details"].append({
                        "atom_id": atom_id,
                        "atom_str": repr(atom_str),
                        "single_failure_rate": round(single_failures / trials * 100, 1),
                        "concat_failure_rate": round(concat_failures / trials * 100, 1),
                    })
        
        tested = results["atoms_tested"]
        results["stability_rate"] = round(
            results["atoms_stable"] / tested * 100, 2
        ) if tested else 0
        
        # Classification
        if results["stability_rate"] >= 99.5:
            results["verdict"] = "DROPOUT-SAFE: >99.5% of atoms stable"
        elif results["stability_rate"] >= 95:
            results["verdict"] = f"MOSTLY-SAFE: {results['stability_rate']}% stable"
        else:
            results["verdict"] = f"DROPOUT-FRAGILE: only {results['stability_rate']}% stable"
        
        return results

    def full_analysis(self, dropout_rates: List[float] = None,
                      trials: int = 100) -> Dict:
        """
        Run comprehensive BPE-dropout analysis across multiple rates.
        """
        if dropout_rates is None:
            dropout_rates = [0.0, 0.05, 0.1, 0.2, 0.3]
        
        # Discover space-prefixed non-merging atoms using standard BPE
        space_atoms = []
        for i in range(self.enc.n_vocab):
            try:
                tok_str = self.enc.decode([i])
            except Exception:
                continue
            if not tok_str.startswith(' ') or len(tok_str) < 2:
                continue
            if not tok_str.isprintable():
                continue
            concat = tok_str + tok_str
            try:
                ids = self.enc.encode(concat)
                if len(ids) == 2:
                    space_atoms.append(i)
            except Exception:
                pass

        report = {
            "tokenizer": self.tokenizer_name,
            "total_space_atoms": len(space_atoms),
            "atoms_sampled": min(200, len(space_atoms)),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "dropout_results": {},
        }

        for rate in dropout_rates:
            print(f"    Testing dropout={rate}...", end=" ", flush=True)
            result = self.test_atom_stability(
                space_atoms, dropout_rate=rate, trials=trials
            )
            report["dropout_results"][f"rate_{rate}"] = result
            print(f"{result['stability_rate']}% stable ({result['verdict']})")

        # Compute dropout-safe bit-width
        # = max bit-width where ALL atoms are stable at moderate dropout
        moderate_result = report["dropout_results"].get("rate_0.1", {})
        stable_count = moderate_result.get("atoms_stable", 0)
        report["dropout_safe_bit_width"] = (
            int(math.log2(stable_count)) if stable_count >= 2 else 0
        )
        report["standard_bit_width"] = (
            int(math.log2(len(space_atoms))) if len(space_atoms) >= 2 else 0
        )
        report["bit_width_reduction"] = (
            report["standard_bit_width"] - report["dropout_safe_bit_width"]
        )

        return report


# ── CLI ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import argparse

    parser = argparse.ArgumentParser(description="ByteToken BPE-Dropout Analysis")
    parser.add_argument("--tokenizer", default="o200k_base")
    parser.add_argument("--rate", type=float, default=None,
                        help="Specific dropout rate to test")
    parser.add_argument("--trials", type=int, default=100,
                        help="Monte Carlo trials per atom")
    args = parser.parse_args()

    print("=" * 70)
    print("  ByteToken BPE-Dropout Robustness Analysis")
    print("=" * 70)

    sim = BPEDropoutSimulator(args.tokenizer)

    rates = [args.rate] if args.rate else None
    report = sim.full_analysis(dropout_rates=rates, trials=args.trials)

    print(f"\n  Summary for {report['tokenizer']}:")
    print(f"    Total space-prefixed atoms: {report['total_space_atoms']:,}")
    print(f"    Standard bit-width:         {report['standard_bit_width']}")
    print(f"    Dropout-safe bit-width:     {report['dropout_safe_bit_width']}")
    print(f"    Bit-width reduction:        {report['bit_width_reduction']}")

    if report["dropout_results"]:
        print(f"\n  Dropout Sweep:")
        print(f"    {'Rate':<10} {'Stable':>8} {'Fragile':>8} {'Rate%':>8} {'Verdict'}")
        print(f"    {'─' * 60}")
        for key, res in report["dropout_results"].items():
            rate = key.replace("rate_", "")
            print(f"    {rate:<10} {res['atoms_stable']:>8} {res['atoms_fragile']:>8} "
                  f"{res['stability_rate']:>7.1f}% {res['verdict']}")

    # Show fragile atoms if any
    for key, res in report["dropout_results"].items():
        if res["stability_details"]:
            print(f"\n  Fragile atoms at {key}:")
            for detail in res["stability_details"][:5]:
                print(f"    ID={detail['atom_id']}: {detail['atom_str']} "
                      f"(single_fail={detail['single_failure_rate']}%, "
                      f"concat_fail={detail['concat_failure_rate']}%)")

    print(f"\n{'=' * 70}")
