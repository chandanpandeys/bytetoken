"""Deterministic local ByteToken transport demonstration.

This example deliberately makes no LLM/API claim. It compares representations
under one declared tokenizer and verifies local lossless round-trips.

Run from the repository root after installing the package:

    python examples/local_transport_demo.py
"""

import base64
import json
import lzma

import tiktoken

from bytetoken import ByteTokenEncoder

TOKENIZER = "o200k_base"


def token_count(text: str) -> int:
    return len(tiktoken.get_encoding(TOKENIZER).encode(text))


def main() -> None:
    payload = json.dumps(
        {
            "kind": "synthetic-demo",
            "records": [
                {"id": i, "status": "ok", "value": i * 17}
                for i in range(100)
            ],
        },
        sort_keys=True,
    ).encode("utf-8")

    encoder = ByteTokenEncoder(tokenizer=TOKENIZER, bit_width=15)

    b64 = base64.b64encode(payload).decode("ascii")
    bt = encoder.encode(payload)
    assert encoder.decode(bt) == payload

    compressed = lzma.compress(payload)
    lzma_b64 = base64.b64encode(compressed).decode("ascii")
    lzma_bt = encoder.encode(compressed)
    assert lzma.decompress(encoder.decode(lzma_bt)) == payload

    print(f"Tokenizer:        {TOKENIZER}")
    print(f"Input bytes:      {len(payload)}")
    print(f"Base64 tokens:    {token_count(b64)}")
    print(f"ByteToken tokens: {token_count(bt)}")
    print(f"LZMA+B64 tokens:  {token_count(lzma_b64)}")
    print(f"LZMA+BT tokens:   {token_count(lzma_bt)}")
    print("Round-trip:       OK")


if __name__ == "__main__":
    main()
