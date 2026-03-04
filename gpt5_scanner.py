"""
ByteToken — GPT-5 Tokenizer Compatibility Scanner
===================================================
Scans any new tokenizer variant for ByteToken compatibility by:
1. Discovering non-merging atoms (space-prefixed and all printable)
2. Characterizing the atom set (count, bit-width, prefix distribution)
3. Validating round-trip encoding at the discovered optimal bit-width
4. Comparing against previous tokenizer baselines (cl100k, o200k)

This scanner is designed to run immediately when a new tokenizer
(e.g., GPT-5's 'o200k_harmony') becomes available in tiktoken.

Usage:
    python -m bytetoken.gpt5_scanner                        # scan all known tokenizers
    python -m bytetoken.gpt5_scanner --tokenizer o200k_base # scan specific one
"""
import os
import sys
import math
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def scan_tokenizer(tokenizer_name: str) -> dict:
    """
    Comprehensive scan of a tokenizer for ByteToken compatibility.

    Returns a detailed report of atom discovery, non-merging validation,
    and optimal bit-width characterization.
    """
    import tiktoken

    try:
        enc = tiktoken.get_encoding(tokenizer_name)
    except Exception as e:
        return {"tokenizer": tokenizer_name, "error": str(e)}

    vocab_size = enc.n_vocab
    report = {
        "tokenizer": tokenizer_name,
        "vocab_size": vocab_size,
        "scan_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # ── Phase 1: Discover all space-prefixed atoms ──────────────

    space_prefixed = []
    space_nonmerging = []

    for i in range(vocab_size):
        try:
            token_str = enc.decode([i])
        except Exception:
            continue

        if not token_str.startswith(' ') or len(token_str) < 2:
            continue
        if not token_str.isprintable():
            continue

        space_prefixed.append(i)

        # Non-merging test: A+A must tokenize to exactly 2 tokens
        concat = token_str + token_str
        try:
            ids = enc.encode(concat)
            if len(ids) == 2:
                space_nonmerging.append(i)
        except Exception:
            pass

    report["space_prefixed_count"] = len(space_prefixed)
    report["space_nonmerging_count"] = len(space_nonmerging)

    if len(space_nonmerging) >= 2:
        max_bw_space = int(math.log2(len(space_nonmerging)))
        report["space_optimal_bit_width"] = max_bw_space
        report["space_usable_atoms"] = 2 ** max_bw_space
    else:
        report["space_optimal_bit_width"] = 0
        report["space_usable_atoms"] = 0

    # ── Phase 2: Discover ALL non-merging atoms ─────────────────

    all_nonmerging = []
    for i in range(vocab_size):
        try:
            token_str = enc.decode([i])
        except Exception:
            continue
        if not token_str.isprintable() or len(token_str) < 1:
            continue
        concat = token_str + token_str
        try:
            ids = enc.encode(concat)
            if len(ids) == 2:
                all_nonmerging.append(i)
        except Exception:
            pass

    report["all_nonmerging_count"] = len(all_nonmerging)
    if len(all_nonmerging) >= 2:
        max_bw_all = int(math.log2(len(all_nonmerging)))
        report["all_optimal_bit_width"] = max_bw_all
        report["all_usable_atoms"] = 2 ** max_bw_all
    else:
        report["all_optimal_bit_width"] = 0
        report["all_usable_atoms"] = 0

    # ── Phase 3: DirectID roundtrip-safe discovery ──────────────

    safe_ids = []
    for i in range(vocab_size):
        try:
            decoded = enc.decode([i])
            re_encoded = enc.encode(decoded)
            if len(re_encoded) == 1 and re_encoded[0] == i:
                safe_ids.append(i)
        except Exception:
            pass

    report["roundtrip_safe_ids"] = len(safe_ids)
    if len(safe_ids) >= 2:
        max_bw_did = int(math.log2(len(safe_ids)))
        report["directid_optimal_bit_width"] = max_bw_did
        report["directid_usable_atoms"] = 2 ** max_bw_did
    else:
        report["directid_optimal_bit_width"] = 0
        report["directid_usable_atoms"] = 0

    # ── Phase 4: N-gram non-merging validation ──────────────────

    import random
    random.seed(42)

    # Take a sample of space_nonmerging atoms for N-gram test
    sample_atoms = space_nonmerging[:min(200, len(space_nonmerging))]
    ngram_results = {}

    for n in [2, 3, 4, 5]:
        passed = 0
        failed = 0
        for _ in range(500):
            chosen = random.choices(sample_atoms, k=n)
            concat = ''.join(enc.decode([c]) for c in chosen)
            ids = enc.encode(concat)
            if len(ids) == n:
                passed += 1
            else:
                failed += 1
        ngram_results[f"window_{n}"] = {
            "passed": passed,
            "failed": failed,
            "rate": round(passed / (passed + failed) * 100, 2) if (passed + failed) else 0,
        }

    report["ngram_validation"] = ngram_results

    # ── Phase 5: Round-trip encoding test ───────────────────────

    if report.get("space_optimal_bit_width", 0) >= 8:
        from bytetoken.core import ByteTokenEncoder
        try:
            bt = ByteTokenEncoder(tokenizer=tokenizer_name,
                                  bit_width=min(report["space_optimal_bit_width"], 15))
            test_data = os.urandom(200)
            encoded = bt.encode(test_data)
            decoded = bt.decode(encoded)
            report["roundtrip_test"] = "PASS" if decoded == test_data else "FAIL"
        except Exception as e:
            report["roundtrip_test"] = f"ERROR: {e}"
    else:
        report["roundtrip_test"] = "SKIP (insufficient atoms)"

    # ── Phase 6: Comparison baseline ────────────────────────────

    report["comparison_notes"] = {
        "cl100k_baseline": {"space_nonmerging": 48702, "directid_safe": 100069, "max_bw": 16},
        "o200k_baseline": {"space_nonmerging": 56000, "directid_safe": 199470, "max_bw": 17},
    }

    return report


def scan_all_available():
    """Scan all available tokenizers including potential GPT-5 variants."""
    import tiktoken

    # Known tokenizers
    known = ["cl100k_base", "o200k_base"]

    # Potential GPT-5 tokenizer names to probe
    gpt5_candidates = [
        "o200k_harmony",      # Speculated name
        "o200k_v2",           # Version increment
        "o300k_base",         # Larger vocab
        "cl200k_base",        # Larger cl-family
        "gpt5_base",          # Direct naming
    ]

    results = {}

    print("=" * 70)
    print("  ByteToken GPT-5 Tokenizer Compatibility Scanner")
    print("=" * 70)

    # Scan known tokenizers
    print("\n[1] Known Tokenizers:\n")
    for tok in known:
        print(f"  Scanning {tok}...", end=" ", flush=True)
        result = scan_tokenizer(tok)
        results[tok] = result
        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            print(f"OK (space={result['space_nonmerging_count']}, "
                  f"did={result['roundtrip_safe_ids']}, "
                  f"max_bw={result.get('directid_optimal_bit_width', '?')})")

    # Probe GPT-5 candidates
    print("\n[2] Probing GPT-5 Candidates:\n")
    found_new = False
    for tok in gpt5_candidates:
        print(f"  Probing {tok}...", end=" ", flush=True)
        result = scan_tokenizer(tok)
        if "error" in result:
            print(f"not found")
        else:
            found_new = True
            results[tok] = result
            print(f"FOUND! (vocab={result['vocab_size']}, "
                  f"space_nm={result['space_nonmerging_count']}, "
                  f"did={result['roundtrip_safe_ids']})")

    if not found_new:
        print("\n  No new GPT-5 tokenizers detected yet.")
        print("  Re-run this scanner when new tiktoken models are released:")
        print("    pip install --upgrade tiktoken")
        print("    python -m bytetoken.gpt5_scanner")

    # Summary comparison table
    print("\n[3] Compatibility Summary:\n")
    print(f"  {'Tokenizer':<20} {'Vocab':>8} {'Space NM':>10} {'DID Safe':>10} "
          f"{'Max BW':>8} {'Round-trip':>10}")
    print("  " + "-" * 68)
    for tok, r in results.items():
        if "error" in r:
            continue
        print(f"  {tok:<20} {r['vocab_size']:>8,} "
              f"{r['space_nonmerging_count']:>10,} "
              f"{r['roundtrip_safe_ids']:>10,} "
              f"{r.get('directid_optimal_bit_width', '?'):>8} "
              f"{r.get('roundtrip_test', 'N/A'):>10}")

    # N-gram safety
    print("\n[4] N-gram Safety (space-prefixed atoms):\n")
    for tok, r in results.items():
        if "error" in r or "ngram_validation" not in r:
            continue
        ngram = r["ngram_validation"]
        print(f"  {tok}: ", end="")
        for w, stats in ngram.items():
            print(f"{w}={stats['rate']}% ", end="")
        print()

    print("\n" + "=" * 70)

    # Save to JSON
    out_file = f"tokenizer_scan_{int(time.time())}.json"
    with open(out_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"  Full results saved to: {out_file}")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ByteToken Tokenizer Scanner")
    parser.add_argument("--tokenizer", type=str, default=None,
                        help="Specific tokenizer to scan")
    args = parser.parse_args()

    if args.tokenizer:
        result = scan_tokenizer(args.tokenizer)
        print(json.dumps(result, indent=2))
    else:
        scan_all_available()
