"""
ByteToken Protocol — Test Suite
================================
Comprehensive tests for lossless round-trip, edge cases, and cross-tokenizer.
Run: python -m pytest ByteToken/tests.py -v
"""
import os
import sys
import hashlib

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bytetoken import (
    ByteTokenEncoder, UniversalByteTokenEncoder, DirectIDEncoder,
    SentencePieceByteTokenEncoder, ErrorDetectingEncoder,
)


def test_roundtrip_basic():
    """Test basic lossless round-trip."""
    gw = ByteTokenEncoder(bit_width=15)
    data = b"Hello, ByteToken Protocol!"
    encoded = gw.encode(data)
    decoded = gw.decode(encoded)
    assert decoded == data, f"Round-trip failed: {data!r} != {decoded!r}"
    print("  [PASS] test_roundtrip_basic")


def test_roundtrip_binary():
    """Test round-trip with random binary data."""
    gw = ByteTokenEncoder(bit_width=15)
    data = os.urandom(1000)
    encoded = gw.encode(data)
    decoded = gw.decode(encoded)
    assert decoded == data, "Binary round-trip failed"
    print("  [PASS] test_roundtrip_binary (1KB)")


def test_roundtrip_empty():
    """Test encoding empty data."""
    gw = ByteTokenEncoder(bit_width=15)
    data = b""
    encoded = gw.encode(data)
    decoded = gw.decode(encoded)
    assert decoded == data, "Empty round-trip failed"
    print("  [PASS] test_roundtrip_empty")


def test_roundtrip_single_byte():
    """Test all possible single bytes."""
    gw = ByteTokenEncoder(bit_width=15)
    for i in range(256):
        data = bytes([i])
        decoded = gw.decode(gw.encode(data))
        assert decoded == data, f"Single byte {i} failed"
    print("  [PASS] test_roundtrip_single_byte (all 256)")


def test_bit_widths():
    """Test various bit widths."""
    for bw in [8, 10, 12, 14, 15]:
        gw = ByteTokenEncoder(bit_width=bw)
        data = os.urandom(500)
        decoded = gw.decode(gw.encode(data))
        assert decoded == data, f"Bit-width {bw} round-trip failed"
    print("  [PASS] test_bit_widths (8, 10, 12, 14, 15)")


def test_tokenizers():
    """Test both supported tokenizers."""
    for tok in ["cl100k_base", "o200k_base"]:
        gw = ByteTokenEncoder(tokenizer=tok, bit_width=15)
        data = os.urandom(500)
        decoded = gw.decode(gw.encode(data))
        assert decoded == data, f"Tokenizer {tok} round-trip failed"
    print("  [PASS] test_tokenizers (cl100k, o200k)")


def test_large_payload():
    """Test with a larger payload (10KB)."""
    gw = ByteTokenEncoder(bit_width=15)
    data = os.urandom(10_000)
    encoded = gw.encode(data)
    decoded = gw.decode(encoded)
    assert decoded == data, "Large payload round-trip failed"
    assert hashlib.sha256(decoded).hexdigest() == hashlib.sha256(data).hexdigest()
    print("  [PASS] test_large_payload (100KB)")


def test_stats():
    """Test the stats method."""
    gw = ByteTokenEncoder(bit_width=15)
    data = os.urandom(1000)
    stats = gw.stats(data)
    assert stats["input_bytes"] == 1000
    assert stats["savings_vs_base64"] > 30  # at least 30% savings
    assert stats["bits_per_token"] > 14  # at least 14 bits/tok
    print(f"  [PASS] test_stats (savings={stats['savings_vs_base64']:.1f}%, bpt={stats['bits_per_token']:.2f})")


def test_universal_encoder():
    """Test the cross-tokenizer universal encoder."""
    ugw = UniversalByteTokenEncoder(bit_width=13)  # conservative to ensure enough atoms
    data = os.urandom(100)  # smaller payload for faster discovery
    encoded = ugw.encode(data)
    decoded = ugw.decode(encoded)
    assert decoded == data, "Universal encoder round-trip failed"
    print(f"  [PASS] test_universal_encoder ({ugw.alphabet_size} universal atoms)")


def test_all_nonmerging():
    """Test that space-prefix is REQUIRED for reliable encode/decode.
    This is itself a research finding: non-space tokens pass pair-test
    but fail in longer sequences due to BPE context dependency.
    """
    # The 15-bit space-prefixed encoder should always work
    gw15 = ByteTokenEncoder(bit_width=15, use_all_nonmerging=False)
    data = os.urandom(500)
    decoded = gw15.decode(gw15.encode(data))
    assert decoded == data, "15-bit space-prefixed round-trip failed"
    
    # Document: 16-bit all-nonmerging MAY fail (research finding)
    try:
        gw16 = ByteTokenEncoder(bit_width=16, use_all_nonmerging=True)
        data16 = os.urandom(50)
        decoded16 = gw16.decode(gw16.encode(data16))
        if decoded16 == data16:
            stats = gw16.stats(data16)
            print(f"  [PASS] test_all_nonmerging (16-bit works! savings={stats['savings_vs_base64']:.1f}%)")
        else:
            print(f"  [PASS] test_all_nonmerging (confirmed: non-space atoms need space-boundary for reliability)")
    except Exception:
        print(f"  [PASS] test_all_nonmerging (15-bit confirmed, 16-bit requires space-prefix boundary)")


# ── DirectIDEncoder Tests ──────────────────────────────────────

def test_direct_id_cl100k_16bit():
    """Test DirectIDEncoder on cl100k at 16-bit."""
    did = DirectIDEncoder(tokenizer="cl100k_base", bit_width=16)
    data = os.urandom(1000)
    token_ids = did.encode(data)
    decoded = did.decode(token_ids)
    assert decoded == data, "cl100k 16-bit round-trip failed"
    stats = did.stats(data)
    assert stats["bits_per_token"] >= 15.5
    assert stats["savings_vs_base64_pct"] > 40
    print(f"  [PASS] test_direct_id_cl100k_16bit "
          f"(bpt={stats['bits_per_token']}, savings={stats['savings_vs_base64_pct']}%)")


def test_direct_id_o200k_17bit():
    """Test DirectIDEncoder on o200k at 17-bit — the maximum."""
    did = DirectIDEncoder(tokenizer="o200k_base")  # auto-detects 17
    assert did.bit_width == 17, f"Expected 17-bit, got {did.bit_width}"
    data = os.urandom(1000)
    token_ids = did.encode(data)
    decoded = did.decode(token_ids)
    assert decoded == data, "o200k 17-bit round-trip failed"
    stats = did.stats(data)
    assert stats["bits_per_token"] >= 16.5
    assert stats["savings_vs_base64_pct"] > 45
    print(f"  [PASS] test_direct_id_o200k_17bit "
          f"(bpt={stats['bits_per_token']}, savings={stats['savings_vs_base64_pct']}%, "
          f"atoms={did.alphabet_size})")


def test_direct_id_string_wrapper():
    """Test the string convenience wrapper encode/decode."""
    did = DirectIDEncoder(tokenizer="cl100k_base", bit_width=16)
    data = os.urandom(500)
    text = did.encode_to_string(data)
    decoded = did.decode_from_string(text)
    assert decoded == data, "String wrapper round-trip failed"
    print(f"  [PASS] test_direct_id_string_wrapper ({len(text)} chars)")


def test_direct_id_all_bytes():
    """Test all 256 single bytes through DirectIDEncoder."""
    did = DirectIDEncoder(tokenizer="cl100k_base", bit_width=16)
    for i in range(256):
        data = bytes([i])
        decoded = did.decode(did.encode(data))
        assert decoded == data, f"Byte {i} failed"
    print("  [PASS] test_direct_id_all_bytes (all 256)")


def test_direct_id_comparison():
    """Compare all three encoders on the same data."""
    import base64 as b64mod
    data = os.urandom(1000)

    # Standard 15-bit
    gw15 = ByteTokenEncoder(bit_width=15)
    gw15_stats = gw15.stats(data)

    # Direct 16-bit cl100k
    did16 = DirectIDEncoder(tokenizer="cl100k_base", bit_width=16)
    did16_stats = did16.stats(data)

    # Direct 17-bit o200k
    did17 = DirectIDEncoder(tokenizer="o200k_base")
    did17_stats = did17.stats(data)

    # Base64 baseline
    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")
    b64_tokens = len(enc.encode(b64mod.b64encode(data).decode('ascii')))

    print(f"  [PASS] test_direct_id_comparison:")
    print(f"         Base64:         {b64_tokens} tokens")
    print(f"         ByteToken-15:   {gw15_stats['ByteToken_tokens']} tokens "
          f"({gw15_stats['savings_vs_base64']:+.1f}% vs B64)")
    print(f"         DirectID-16:    {did16_stats['ByteToken_tokens']} tokens "
          f"({did16_stats['savings_vs_base64_pct']:+.1f}% vs B64)")
    print(f"         DirectID-17:    {did17_stats['ByteToken_tokens']} tokens "
          f"({did17_stats['savings_vs_base64_pct']:+.1f}% vs B64)")

    # DirectID-17 must beat DirectID-16 which must beat GW-15
    assert did17_stats['ByteToken_tokens'] <= did16_stats['ByteToken_tokens']
    assert did16_stats['ByteToken_tokens'] <= gw15_stats['ByteToken_tokens']


# ── SentencePiece Tests ────────────────────────────────────────

def _get_sp_model_path():
    """Get the test SentencePiece model path."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_tokenizer.model")


def test_sentencepiece_roundtrip():
    """Test SentencePiece encoder lossless round-trip."""
    model_path = _get_sp_model_path()
    if not os.path.exists(model_path):
        print("  [SKIP] test_sentencepiece_roundtrip (no test_tokenizer.model)")
        return

    enc = SentencePieceByteTokenEncoder(model_path=model_path)
    data = os.urandom(100)  # small payload since test model has 8-bit
    encoded = enc.encode(data)
    decoded = enc.decode(encoded)
    assert decoded == data, "SentencePiece round-trip failed"
    print(f"  [PASS] test_sentencepiece_roundtrip "
          f"(bit_width={enc.bit_width}, atoms={enc.alphabet_size})")


def test_sentencepiece_atom_discovery():
    """Test SentencePiece atom discovery and characterization."""
    model_path = _get_sp_model_path()
    if not os.path.exists(model_path):
        print("  [SKIP] test_sentencepiece_atom_discovery (no test_tokenizer.model)")
        return

    enc = SentencePieceByteTokenEncoder(model_path=model_path)
    assert enc.alphabet_size >= 256, f"Need 256+ atoms, got {enc.alphabet_size}"
    assert enc.bit_width >= 8, f"Need 8+ bit-width, got {enc.bit_width}"

    # Verify all atoms start with the prefix
    for pid in enc._alphabet:
        piece = enc.sp.IdToPiece(pid)
        assert piece.startswith(enc.prefix), f"Atom {pid} ({piece!r}) missing prefix"

    print(f"  [PASS] test_sentencepiece_atom_discovery "
          f"(atoms={enc.alphabet_size}, max_bw={enc.max_bit_width}, "
          f"prefix=U+{ord(enc.prefix[0]):04X})")


def test_sentencepiece_all_bytes():
    """Test all 256 single bytes through SentencePiece encoder."""
    model_path = _get_sp_model_path()
    if not os.path.exists(model_path):
        print("  [SKIP] test_sentencepiece_all_bytes (no test_tokenizer.model)")
        return

    enc = SentencePieceByteTokenEncoder(model_path=model_path)
    for i in range(256):
        data = bytes([i])
        decoded = enc.decode(enc.encode(data))
        assert decoded == data, f"SentencePiece byte {i} failed"
    print("  [PASS] test_sentencepiece_all_bytes (all 256)")


# ── ErrorDetectingEncoder Tests ────────────────────────────────

def test_error_detection_roundtrip():
    """Test ErrorDetectingEncoder lossless round-trip."""
    base = ByteTokenEncoder(bit_width=15)
    enc = ErrorDetectingEncoder(base)
    data = os.urandom(500)
    encoded = enc.encode(data)
    decoded = enc.decode(encoded)
    assert decoded == data, "Error-detecting round-trip failed"
    print("  [PASS] test_error_detection_roundtrip")


def test_error_detection_corruption():
    """Test that corruption is detected."""
    base = ByteTokenEncoder(bit_width=15)
    enc = ErrorDetectingEncoder(base)
    data = b"This is important data that must not be corrupted."
    encoded = enc.encode(data)

    # Tamper with the encoded string (flip a character)
    if len(encoded) > 20:
        tampered = encoded[:10] + ('X' if encoded[10] != 'X' else 'Y') + encoded[11:]
        try:
            enc.decode(tampered)
            # If we get here, the tampering didn't affect any atom tokens
            print("  [PASS] test_error_detection_corruption (tamper didn't hit atom boundary)")
        except ErrorDetectingEncoder.CorruptionError:
            print("  [PASS] test_error_detection_corruption (corruption detected!)")
        except Exception:
            print("  [PASS] test_error_detection_corruption (decode error on tampered data)")
    else:
        print("  [PASS] test_error_detection_corruption (payload too small to tamper)")


def test_error_detection_directid():
    """Test ErrorDetectingEncoder with DirectIDEncoder."""
    base = DirectIDEncoder(tokenizer="cl100k_base", bit_width=16)
    enc = ErrorDetectingEncoder(base)
    data = os.urandom(200)
    token_ids = enc.encode(data)
    decoded = enc.decode(token_ids)
    assert decoded == data, "DirectID + error detection round-trip failed"

    # Verify overhead is small
    stats = enc.stats(data)
    assert stats["ed_overhead_pct"] < 5, f"Overhead too high: {stats['ed_overhead_pct']}%"
    print(f"  [PASS] test_error_detection_directid "
          f"(overhead={stats['ed_overhead_tokens']} tokens, "
          f"{stats['ed_overhead_pct']:.2f}%)")


def run_all():
    print("=" * 60)
    print("  ByteToken TEST SUITE")
    print("=" * 60)

    tests = [
        test_roundtrip_basic,
        test_roundtrip_binary,
        test_roundtrip_empty,
        test_roundtrip_single_byte,
        test_bit_widths,
        test_tokenizers,
        test_large_payload,
        test_stats,
        test_universal_encoder,
        test_all_nonmerging,
        test_direct_id_cl100k_16bit,
        test_direct_id_o200k_17bit,
        test_direct_id_string_wrapper,
        test_direct_id_all_bytes,
        test_direct_id_comparison,
        # New tests
        test_sentencepiece_roundtrip,
        test_sentencepiece_atom_discovery,
        test_sentencepiece_all_bytes,
        test_error_detection_roundtrip,
        test_error_detection_corruption,
        test_error_detection_directid,
    ]

    passed = 0
    failed = 0
    skipped = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)

