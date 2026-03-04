"""
ByteToken CLI
=============
Command-line interface for ByteToken Protocol encoding/decoding.

Usage:
    python -m bytetoken encode <input_file> [--output <output_file>] [--mode universal|standard|adaptive|direct_id]
    python -m bytetoken decode <input_file> [--output <output_file>] [--mode universal|standard|adaptive|direct_id]
    python -m bytetoken bench [--size 100000]
    python -m bytetoken info
"""
import argparse
import sys
import os
import time
import base64


def cmd_encode(args):
    import bytetoken
    
    with open(args.input, 'rb') as f:
        data = f.read()

    t0 = time.perf_counter()
    encoded = bytetoken.encode(data, mode=args.mode)
    elapsed = time.perf_counter() - t0

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(encoded)
        print(f"Encoded {len(data)} bytes -> {len(encoded)} chars in {elapsed*1000:.1f}ms")
        print(f"Mode: {args.mode} | Saved to: {args.output}")
    else:
        print(encoded)
        
    base64_len = len(base64.b64encode(data).decode('utf-8'))
    savings = 100 * (1.0 - len(encoded)/base64_len) if base64_len else 0
    print(f"Compression vs Base64 payload length: {savings:+.1f}%")

def cmd_decode(args):
    import bytetoken

    with open(args.input, 'r', encoding='utf-8') as f:
        encoded = f.read()

    t0 = time.perf_counter()
    decoded = bytetoken.decode(encoded, mode=args.mode)
    elapsed = time.perf_counter() - t0

    if args.output:
        with open(args.output, 'wb') as f:
            f.write(decoded)
        print(f"Decoded {len(encoded)} chars -> {len(decoded)} bytes in {elapsed*1000:.1f}ms")
    else:
        sys.stdout.buffer.write(decoded)

def cmd_bench(args):
    from bytetoken import ByteTokenEncoder
    
    print(f"ByteToken Benchmark ({args.size} bytes random binary)")
    print("=" * 70)

    data = os.urandom(args.size)

    for bw in [10, 12, 14, 15]:
        try:
            gw = ByteTokenEncoder(tokenizer=args.tokenizer, bit_width=bw)
        except ValueError:
            continue

        t0 = time.perf_counter()
        encoded = gw.encode(data)
        enc_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        decoded = gw.decode(encoded)
        dec_time = time.perf_counter() - t0

        stats = gw.stats(data)
        ok = "YES" if decoded == data else "NO"

        print(f"  {bw}-bit: {stats['ByteToken_tokens']} tokens, "
              f"{stats['bits_per_token']:.2f} bits/tok, "
              f"{stats['savings_vs_base64']:+.1f}% vs B64, "
              f"enc={enc_time*1000:.1f}ms dec={dec_time*1000:.1f}ms "
              f"lossless={ok}")


def cmd_info(args):
    from bytetoken import ByteTokenEncoder
    
    for tok in ["cl100k_base", "o200k_base"]:
        for use_all in [False, True]:
            label = f"{tok} ({'all' if use_all else 'space-prefix'})"
            try:
                gw = ByteTokenEncoder(tokenizer=tok, bit_width=15, use_all_nonmerging=use_all)
                print(f"  {label:<40} atoms={gw.alphabet_size:>6}, "
                      f"max_bits={gw.max_bit_width}")
            except ValueError as e:
                print(f"  {label:<40} {e}")


def main():
    parser = argparse.ArgumentParser(
        prog='ByteToken',
        description='ByteToken Protocol: Token-efficient binary encoding for LLMs'
    )
    sub = parser.add_subparsers(dest='command')

    p_enc = sub.add_parser('encode', help='Encode a file')
    p_enc.add_argument('input', help='Input file to encode')
    p_enc.add_argument('--output', '-o', help='Output file')
    p_enc.add_argument('--mode', choices=['universal', 'standard', 'direct_id', 'adaptive'], default='universal', help='Encoding mode')

    # decode
    p_dec = sub.add_parser('decode', help='Decode a file')
    p_dec.add_argument('input', help='Input file to decode')
    p_dec.add_argument('--output', '-o', help='Output file')
    p_dec.add_argument('--mode', choices=['universal', 'standard', 'direct_id', 'adaptive'], default='universal', help='Encoding mode')

    # bench
    p_bench = sub.add_parser('bench', help='Run a quick benchmark')
    p_bench.add_argument('--size', type=int, default=10000, help='Payload size in bytes')
    p_bench.add_argument('--tokenizer', default='cl100k_base', help='Tokenizer name')

    # info
    sub.add_parser('info', help='Show tokenizer info and atom counts')

    args = parser.parse_args()
    if args.command == 'encode':
        cmd_encode(args)
    elif args.command == 'decode':
        cmd_decode(args)
    elif args.command == 'bench':
        cmd_bench(args)
    elif args.command == 'info':
        cmd_info(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
