"""
ByteToken — Production API Billing Validation
==============================================
End-to-end billing measurement with LLM APIs to verify
actual dollar savings match theoretical ByteToken projections.

Supports: OpenAI (GPT-4o), Anthropic Claude, Google Gemini.

Usage:
    # Basic validation (requires API keys in environment)
    python scripts/validate_api_billing.py

    # With specific provider
    python scripts/validate_api_billing.py --provider openai
    python scripts/validate_api_billing.py --provider anthropic
    python scripts/validate_api_billing.py --provider gemini

Environment Variables:
    OPENAI_API_KEY      — for GPT-4o validation
    ANTHROPIC_API_KEY   — for Claude 3.5 Sonnet validation
    GOOGLE_API_KEY      — for Gemini 2.5 Flash validation
"""
import os
import sys
import json
import time
import base64
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bytetoken import ByteTokenEncoder, DirectIDEncoder


# ── Test Payloads ──────────────────────────────────────────────

def generate_test_payloads():
    """Generate diverse test payloads for billing validation."""
    payloads = {}

    # 1. Random binary (incompressible baseline)
    payloads["random_1kb"] = os.urandom(1024)

    # 2. Structured JSON (high compressibility)
    json_data = json.dumps({
        "users": [
            {"id": i, "name": f"User{i}", "email": f"user{i}@example.com",
             "active": i % 2 == 0, "score": i * 1.5}
            for i in range(50)
        ]
    }).encode('utf-8')
    payloads["json_2kb"] = json_data

    # 3. Repetitive binary (sensor data simulation)
    sensor = bytearray()
    for i in range(500):
        sensor.extend(int(20 + 5 * (i % 10)).to_bytes(2, 'big'))
    payloads["sensor_1kb"] = bytes(sensor)

    # 4. Image-like data (gradient pattern)
    gradient = bytes([(i * j) % 256 for i in range(32) for j in range(32)])
    payloads["gradient_1kb"] = gradient

    return payloads


# ── Provider Validators ────────────────────────────────────────

def validate_openai(payloads: dict) -> dict:
    """Validate billing with OpenAI GPT-4o API."""
    try:
        import openai
    except ImportError:
        return {"error": "pip install openai"}

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"error": "Set OPENAI_API_KEY environment variable"}

    client = openai.OpenAI(api_key=api_key)
    results = {}

    enc15 = ByteTokenEncoder(bit_width=15)

    for name, data in payloads.items():
        # Base64 encoding (baseline)
        b64_text = base64.b64encode(data).decode('ascii')
        b64_prompt = f"Echo back this Base64 data exactly: {b64_text}"

        # ByteToken encoding
        bt_text = enc15.encode(data)
        bt_prompt = f"Echo back this ByteToken data exactly: {bt_text}"

        try:
            # Base64 request
            t0 = time.time()
            b64_resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": b64_prompt}],
                max_tokens=10,
            )
            b64_time = time.time() - t0
            b64_usage = b64_resp.usage

            # ByteToken request
            t0 = time.time()
            bt_resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": bt_prompt}],
                max_tokens=10,
            )
            bt_time = time.time() - t0
            bt_usage = bt_resp.usage

            # Calculate savings
            b64_input = b64_usage.prompt_tokens
            bt_input = bt_usage.prompt_tokens
            savings_pct = ((b64_input - bt_input) / b64_input * 100) if b64_input else 0

            # GPT-4o pricing: $2.50/1M input tokens
            price_per_token = 2.50 / 1_000_000
            b64_cost = b64_input * price_per_token
            bt_cost = bt_input * price_per_token
            cost_savings = b64_cost - bt_cost

            results[name] = {
                "base64_tokens": b64_input,
                "bytetoken_tokens": bt_input,
                "savings_pct": round(savings_pct, 1),
                "base64_cost_usd": round(b64_cost, 6),
                "bytetoken_cost_usd": round(bt_cost, 6),
                "cost_savings_usd": round(cost_savings, 6),
                "base64_latency_ms": round(b64_time * 1000),
                "bytetoken_latency_ms": round(bt_time * 1000),
                "reasoning_tokens": getattr(b64_usage, 'completion_tokens_details', {}).get('reasoning_tokens', 'N/A'),
            }
        except Exception as e:
            results[name] = {"error": str(e)}

    return {"provider": "openai", "model": "gpt-4o", "results": results}


def validate_anthropic(payloads: dict) -> dict:
    """Validate billing with Anthropic Claude API."""
    try:
        import anthropic
    except ImportError:
        return {"error": "pip install anthropic"}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "Set ANTHROPIC_API_KEY environment variable"}

    client = anthropic.Anthropic(api_key=api_key)
    results = {}

    enc15 = ByteTokenEncoder(bit_width=15)

    for name, data in payloads.items():
        b64_text = base64.b64encode(data).decode('ascii')
        bt_text = enc15.encode(data)

        try:
            b64_resp = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": f"Echo: {b64_text}"}],
            )
            bt_resp = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": f"Echo: {bt_text}"}],
            )

            b64_in = b64_resp.usage.input_tokens
            bt_in = bt_resp.usage.input_tokens
            savings = ((b64_in - bt_in) / b64_in * 100) if b64_in else 0

            # Claude pricing: $3.00/1M input tokens
            price = 3.00 / 1_000_000
            results[name] = {
                "base64_tokens": b64_in,
                "bytetoken_tokens": bt_in,
                "savings_pct": round(savings, 1),
                "cost_savings_usd": round((b64_in - bt_in) * price, 6),
            }
        except Exception as e:
            results[name] = {"error": str(e)}

    return {"provider": "anthropic", "model": "claude-3.5-sonnet", "results": results}


def validate_gemini(payloads: dict) -> dict:
    """Validate billing with Google Gemini API."""
    try:
        import google.generativeai as genai
    except ImportError:
        return {"error": "pip install google-generativeai"}

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return {"error": "Set GOOGLE_API_KEY environment variable"}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    results = {}

    enc15 = ByteTokenEncoder(bit_width=15)

    for name, data in payloads.items():
        b64_text = base64.b64encode(data).decode('ascii')
        bt_text = enc15.encode(data)

        try:
            b64_resp = model.generate_content(f"Echo: {b64_text}",
                generation_config={"max_output_tokens": 10})
            bt_resp = model.generate_content(f"Echo: {bt_text}",
                generation_config={"max_output_tokens": 10})

            b64_in = b64_resp.usage_metadata.prompt_token_count
            bt_in = bt_resp.usage_metadata.prompt_token_count
            savings = ((b64_in - bt_in) / b64_in * 100) if b64_in else 0

            results[name] = {
                "base64_tokens": b64_in,
                "bytetoken_tokens": bt_in,
                "savings_pct": round(savings, 1),
            }
        except Exception as e:
            results[name] = {"error": str(e)}

    return {"provider": "gemini", "model": "gemini-2.5-flash", "results": results}


# ── Dry Run (no API key needed) ────────────────────────────────

def dry_run(payloads: dict) -> dict:
    """Estimate savings without API calls using local tokenizer counts."""
    import tiktoken
    enc_tok = tiktoken.get_encoding("o200k_base")
    enc15 = ByteTokenEncoder(tokenizer="o200k_base", bit_width=15)
    did17 = DirectIDEncoder(tokenizer="o200k_base")

    results = {}
    for name, data in payloads.items():
        b64 = base64.b64encode(data).decode('ascii')
        bt15 = enc15.encode(data)
        bt17_ids = did17.encode(data)

        b64_tokens = len(enc_tok.encode(b64))
        bt15_tokens = len(enc_tok.encode(bt15))
        bt17_tokens = len(bt17_ids)

        # Pricing: GPT-4o $2.50/1M input
        price = 2.50 / 1_000_000

        results[name] = {
            "payload_bytes": len(data),
            "base64_tokens": b64_tokens,
            "bytetoken_15bit_tokens": bt15_tokens,
            "bytetoken_17bit_tokens": bt17_tokens,
            "savings_15bit_pct": round((b64_tokens - bt15_tokens) / b64_tokens * 100, 1),
            "savings_17bit_pct": round((b64_tokens - bt17_tokens) / b64_tokens * 100, 1),
            "cost_per_1M_calls_b64": round(b64_tokens * price * 1_000_000, 2),
            "cost_per_1M_calls_bt15": round(bt15_tokens * price * 1_000_000, 2),
            "cost_per_1M_calls_bt17": round(bt17_tokens * price * 1_000_000, 2),
        }

    return {"provider": "dry_run", "model": "o200k_base (local)", "results": results}


# ── CLI ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ByteToken API Billing Validation")
    parser.add_argument("--provider", choices=["openai", "anthropic", "gemini", "dry_run"],
                        default="dry_run", help="API provider to validate")
    args = parser.parse_args()

    print("=" * 70)
    print("  ByteToken — Production API Billing Validation")
    print("=" * 70)

    payloads = generate_test_payloads()
    print(f"\n  Test payloads: {', '.join(payloads.keys())}")
    print(f"  Provider:      {args.provider}\n")

    validators = {
        "openai": validate_openai,
        "anthropic": validate_anthropic,
        "gemini": validate_gemini,
        "dry_run": dry_run,
    }

    result = validators[args.provider](payloads)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return

    print(f"  Model: {result['model']}\n")
    print("-" * 70)

    for name, stats in result["results"].items():
        if "error" in stats:
            print(f"  {name}: ERROR - {stats['error']}")
            continue

        print(f"\n  {name} ({stats.get('payload_bytes', '?')} bytes):")
        for key, val in stats.items():
            if key != "payload_bytes":
                print(f"    {key}: {val}")
    print("\n" + "=" * 70)

    # Save results
    out_file = f"validation_{args.provider}_{int(time.time())}.json"
    with open(out_file, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"  Results saved to: {out_file}")


if __name__ == "__main__":
    main()
