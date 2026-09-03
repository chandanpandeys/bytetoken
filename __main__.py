"""Command-line interface for the ByteToken research prototype."""

import argparse
import base64
import os
import sys
import time

PUBLIC_MODES = ("universal", "standard", "direct_id")


def cmd_encode(args):
    import bytetoken
    with open(args.input, "rb") as f:
        data = f.read()
    start = time.perf_counter()
    encoded = bytetoken.encode(data, mode=args.mode)
    elapsed = time.perf_counter() - start
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(encoded)
        print(f"Encoded {len(data)} bytes -> {len(encoded)} characters in {elapsed * 1000:.1f}ms")
        print(f"Mode: {args.mode} | Saved to: {args.output}")
    else:
        print(encoded)
    base64_chars = len(base64.b64encode(data).decode("ascii"))
    delta = 100 * (1.0 - len(encoded) / base64_chars) if base64_chars else 0.0
    print(f"Character-length difference vs Base64: {delta:+.1f}% (not a token-count benchmark)")


def cmd_decode(args):
    import bytetoken
    with open(args.input, "r", encoding="utf-8") as f:
        encoded = f.read()
    start = time.perf_counter()
    decoded = bytetoken.decode(encoded, mode=args.mode)
    elapsed = time.perf_counter() - start
    if args.output:
        with open(args.output, "wb") as f:
            f.write(decoded)
        print(f"Decoded {len(encoded)} characters -> {len(decoded)} bytes in {elapsed * 1000:.1f}ms")
    else:
        sys.stdout.buffer.write(decoded)


def cmd_bench(args):
    from bytetoken import ByteTokenEncoder
    print(f"ByteToken local benchmark ({args.size} random bytes)")
    print("=" * 72)
    data = os.urandom(args.size)
    for bit_width in (10, 12, 14, 15):
        try:
            enc = ByteTokenEncoder(tokenizer=args.tokenizer, bit_width=bit_width)
        except ValueError:
            continue
        start = time.perf_counter(); encoded = enc.encode(data); encode_s = time.perf_counter() - start
        start = time.perf_counter(); decoded = enc.decode(encoded); decode_s = time.perf_counter() - start
        stats = enc.stats(data)
        print(f"  {bit_width}-bit: {stats['ByteToken_tokens']} tokens, {stats['bits_per_token']:.2f} bits/token, {stats['savings_vs_base64']:+.1f}% vs Base64, encode={encode_s * 1000:.1f}ms decode={decode_s * 1000:.1f}ms lossless={'YES' if decoded == data else 'NO'}")


def cmd_info(_args):
    from bytetoken import ByteTokenEncoder, UniversalByteTokenEncoder
    print("Tested string-mode configurations")
    for tokenizer in ("cl100k_base", "o200k_base"):
        enc = ByteTokenEncoder(tokenizer=tokenizer, bit_width=15)
        print(f"  {tokenizer:<16} bit_width={enc.bit_width} alphabet={enc.alphabet_size}")
    shared = UniversalByteTokenEncoder(bit_width=13)
    print(f"  shared(cl100k,o200k) bit_width={shared.bit_width} alphabet={shared.alphabet_size}")
    print("These counts are tokenizer/library-version specific.")


def cmd_profile(args):
    from bytetoken.profiler import profile_file
    report = profile_file(args.session_file, tokenizer_name=args.model)
    print(f"ByteToken Context Profiler — {args.session_file}")
    print("=" * 72)
    print(f"Total session tokens:       {report['total_tokens']:,}")
    print(f"Message turns:              {report['message_count']}")
    tool_summary = report["tool_output_summary"]
    print(f"Tool outputs:               {tool_summary['count']}")
    print(f"Tool output tokens:         {tool_summary['total_tokens']:,} ({tool_summary['pct_of_total']}%)")
    b64 = report["base64_inefficiency"]
    print(f"Detected Base64 tokens:     {b64['total_base64_tokens']:,}")
    if b64.get("potential_savings_tokens") is None:
        print("Potential ByteToken savings: not estimated automatically")
        print(f"Reason: {b64.get('note', 'requires a measured re-encode')}")
    else:
        print(f"Potential ByteToken savings: {b64['potential_savings_tokens']:,} ({b64['potential_savings_pct']}%)")
    if report["recommendations"]:
        print("\nRecommendations:")
        for recommendation in report["recommendations"]:
            print(f"  - {recommendation}")


def cmd_playground(args):
    try:
        from bytetoken.playground.app import run
    except ImportError as exc:
        raise SystemExit('Playground dependencies are missing. Install with: pip install -e ".[playground]"') from exc
    run(host=args.host, port=args.port)


def build_parser():
    parser = argparse.ArgumentParser(prog="bytetoken", description="Experimental tokenizer-aware binary transport toolkit")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("encode", help="Encode a file"); p.add_argument("input"); p.add_argument("--output", "-o"); p.add_argument("--mode", choices=PUBLIC_MODES, default="universal")
    p = sub.add_parser("decode", help="Decode a file"); p.add_argument("input"); p.add_argument("--output", "-o"); p.add_argument("--mode", choices=PUBLIC_MODES, default="universal")
    p = sub.add_parser("bench", help="Run a local synthetic benchmark"); p.add_argument("--size", type=int, default=10_000); p.add_argument("--tokenizer", default="cl100k_base")
    p = sub.add_parser("profile", help="Profile a conversation JSON file"); p.add_argument("session_file"); p.add_argument("--model", default="o200k_base")
    p = sub.add_parser("playground", help="Launch the optional local ByteToken Playground"); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8000)
    sub.add_parser("info", help="Show tested tokenizer configuration info")
    return parser


def main():
    parser = build_parser(); args = parser.parse_args()
    handlers = {"encode": cmd_encode, "decode": cmd_decode, "bench": cmd_bench, "profile": cmd_profile, "playground": cmd_playground, "info": cmd_info}
    if args.command in handlers: handlers[args.command](args)
    else: parser.print_help()


if __name__ == "__main__":
    main()
