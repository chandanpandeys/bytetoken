"""
ByteToken Real-World Benchmark
================================
Tests ByteToken vs Base64 on realistic payloads that developers
actually encounter in agent workflows (JSON API, pytest logs, CSV, code, embeddings).

Measures ACTUAL token counts using tiktoken (o200k_base).
Run:
    python bytetoken/benchmarks/benchmark_realworld.py
"""
import sys, os, json, base64, time, lzma
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tiktoken
from bytetoken.core import ByteTokenEncoder, DirectIDEncoder

def count_tokens(text: str, encoding_name: str = "o200k_base") -> int:
    enc = tiktoken.get_encoding(encoding_name)
    return len(enc.encode(text))

def generate_realistic_payloads():
    payloads = {}

    # 1. JSON API Response (e.g., from an MCP tool server querying a DB)
    api_response = {
        "status": "success",
        "data": {
            "users": [
                {"id": i, "name": f"User_{i}", "email": f"user{i}@company.com",
                 "role": "developer" if i % 3 == 0 else "viewer",
                 "last_login": f"2026-08-{(i % 28) + 1:02d}T14:30:00Z",
                 "metadata": {"projects": [f"proj-{j}" for j in range(5)],
                             "commits": i * 47}}
                for i in range(100)
            ],
            "pagination": {"page": 1, "total": 2847, "per_page": 100}
        }
    }
    payloads["JSON API Response (100 users)"] = json.dumps(api_response).encode()

    # 2. Pytest Output (typical CI/CD tool output)
    pytest_lines = ["=" * 60, "PYTEST SESSION STARTS", "=" * 60, "platform linux -- Python 3.12.0", ""]
    for i in range(50):
        if i % 10 == 7:
            pytest_lines.append(f"FAILED tests/test_auth.py::test_login_{i} - AssertionError: expected 200 got 401")
            pytest_lines.append(f"  File \"tests/test_auth.py\", line {100+i}, in test_login_{i}")
            pytest_lines.append(f"    assert response.status_code == 200")
            pytest_lines.append(f"  AssertionError: 401 != 200")
        else:
            pytest_lines.append(f"PASSED tests/test_auth.py::test_login_{i}")
    pytest_lines.extend(["", "=" * 60, "5 failed, 45 passed in 12.34s", "=" * 60])
    payloads["Pytest Output (50 tests)"] = "\n".join(pytest_lines).encode()

    # 3. CSV Data (e.g., analytics export from a tool)
    csv_lines = ["timestamp,user_id,action,duration_ms,status,endpoint"]
    for i in range(500):
        csv_lines.append(f"2026-08-27T{i//60:02d}:{i%60:02d}:00Z,user_{i%50},GET,{50+i*3},200,/api/v2/data")
    payloads["CSV Analytics (500 rows)"] = "\n".join(csv_lines).encode()

    # 4. Python Source Code
    code_lines = ['"""Authentication module for the API gateway."""', "import hashlib", "import hmac", "import time", "from typing import Optional, Dict", "", ""]
    for i in range(30):
        code_lines.extend([
            f"def validate_token_{i}(token: str, secret: str) -> bool:",
            f'    """Validate JWT token #{i}."""',
            f"    if not token or len(token) < 32:",
            f"        return False",
            f"    parts = token.split('.')",
            f"    if len(parts) != 3:",
            f"        return False",
            f"    payload = base64.b64decode(parts[1])",
            f"    return hmac.compare_digest(",
            f"        hmac.new(secret.encode(), parts[0].encode() + b'.' + parts[1].encode(), hashlib.sha256).hexdigest(),",
            f"        parts[2]",
            f"    )",
            f"",
        ])
    payloads["Python Source (~30 functions)"] = "\n".join(code_lines).encode()

    # 5. Docker/Compiler Log
    log_lines = []
    for i in range(200):
        log_lines.append(f"[2026-08-27T14:{i//60:02d}:{i%60:02d}.{i*7%1000:03d}Z] INFO  Building layer {i+1}/200")
        if i % 40 == 39:
            log_lines.append(f"[2026-08-27T14:{i//60:02d}:{i%60:02d}.{i*7%1000:03d}Z] WARN  Deprecated package detected: libfoo-{i}")
    payloads["Docker Build Log (200 steps)"] = "\n".join(log_lines).encode()

    # 6. Binary blob
    payloads["Binary Blob (5KB random)"] = os.urandom(5000)

    # 7. Embedding vector
    import struct
    embedding = struct.pack(f'{768}f', *[0.1 * (i % 100 - 50) for i in range(768)])
    payloads["Embedding Vector (768-dim float32)"] = embedding

    return payloads


def benchmark_payload(name: str, data: bytes):
    enc_15 = ByteTokenEncoder(bit_width=15)
    enc_did = DirectIDEncoder(tokenizer="o200k_base", bit_width=17)

    results = {"name": name, "raw_bytes": len(data)}

    b64_str = base64.b64encode(data).decode('ascii')
    b64_tokens = count_tokens(b64_str)
    results["base64_chars"] = len(b64_str)
    results["base64_tokens"] = b64_tokens

    bt15_str = enc_15.encode(data)
    bt15_tokens = count_tokens(bt15_str)
    results["bytetoken15_chars"] = len(bt15_str)
    results["bytetoken15_tokens"] = bt15_tokens
    results["bt15_savings_vs_b64"] = round((1 - bt15_tokens / b64_tokens) * 100, 1) if b64_tokens > 0 else 0

    compressed = lzma.compress(data)
    lzma_bt15_str = enc_15.encode(compressed)
    lzma_bt15_tokens = count_tokens(lzma_bt15_str)
    results["lzma_ratio"] = round(len(compressed) / len(data) * 100, 1) if len(data) > 0 else 0
    results["lzma_bt15_tokens"] = lzma_bt15_tokens
    results["lzma_bt15_savings_vs_b64"] = round((1 - lzma_bt15_tokens / b64_tokens) * 100, 1) if b64_tokens > 0 else 0

    lzma_b64_str = base64.b64encode(compressed).decode('ascii')
    lzma_b64_tokens = count_tokens(lzma_b64_str)
    results["lzma_b64_tokens"] = lzma_b64_tokens
    results["lzma_b64_savings_vs_b64"] = round((1 - lzma_b64_tokens / b64_tokens) * 100, 1) if b64_tokens > 0 else 0

    did_indices = enc_did.encode(data)
    did_token_count = len(did_indices) if isinstance(did_indices, list) else did_indices.count(' ') + 1
    results["did17_tokens"] = did_token_count

    did_lzma = enc_did.encode(compressed)
    did_lzma_count = len(did_lzma) if isinstance(did_lzma, list) else did_lzma.count(' ') + 1
    results["lzma_did17_tokens"] = did_lzma_count
    results["lzma_did17_savings_vs_b64"] = round((1 - did_lzma_count / b64_tokens) * 100, 1) if b64_tokens > 0 else 0

    return results


def main():
    print("=" * 90)
    print("  BYTETOKEN REAL-WORLD BENCHMARK (o200k_base)")
    print("=" * 90)

    payloads = generate_realistic_payloads()
    all_results = []

    for name, data in payloads.items():
        r = benchmark_payload(name, data)
        all_results.append(r)
        print(f"\n--- {name} ({len(data):,} bytes) ---")
        print(f"  Base64:                {r['base64_tokens']:>8,} tokens")
        print(f"  ByteToken-15:          {r['bytetoken15_tokens']:>8,} tokens  ({r['bt15_savings_vs_b64']:>5.1f}% vs B64)")
        print(f"  LZMA + Base64:         {r['lzma_b64_tokens']:>8,} tokens  ({r['lzma_b64_savings_vs_b64']:>5.1f}% vs B64)")
        print(f"  LZMA + ByteToken-15:   {r['lzma_bt15_tokens']:>8,} tokens  ({r['lzma_bt15_savings_vs_b64']:>5.1f}% vs B64)")
        print(f"  LZMA + DirectID-17:    {r['lzma_did17_tokens']:>8,} tokens  ({r['lzma_did17_savings_vs_b64']:>5.1f}% vs B64)")

    print("\n" + "=" * 90)
    print("  SUMMARY TABLE")
    print("=" * 90)
    print(f"  {'Payload':<35} {'Bytes':>8} {'B64':>8} {'BT-15':>8} {'LZMA+B64':>8} {'LZMA+BT15':>9} {'LZMA+DID17':>10}")
    print("  " + "-" * 88)
    for r in all_results:
        print(f"  {r['name']:<35} {r['raw_bytes']:>8,} {r['base64_tokens']:>8,} {r['bytetoken15_tokens']:>8,} {r['lzma_b64_tokens']:>8,} {r['lzma_bt15_tokens']:>9,} {r['lzma_did17_tokens']:>10,}")

    print("\n  SAVINGS vs Base64:")
    print(f"  {'Payload':<35} {'BT-15':>8} {'LZMA+B64':>8} {'LZMA+BT15':>9} {'LZMA+DID17':>10}")
    print("  " + "-" * 70)
    for r in all_results:
        print(f"  {r['name']:<35} {r['bt15_savings_vs_b64']:>7.1f}% {r['lzma_b64_savings_vs_b64']:>7.1f}% {r['lzma_bt15_savings_vs_b64']:>8.1f}% {r['lzma_did17_savings_vs_b64']:>9.1f}%")


if __name__ == "__main__":
    main()
