"""Publication-surface regression tests."""

import json
from pathlib import Path
import subprocess
import sys

import bytetoken
from bytetoken import DirectIDEncoder
from bytetoken.mcp import decode_mcp_response, mcp_tool


def test_release_version_is_research_preview():
    assert bytetoken.__version__ == "0.1.0"


def test_public_universal_default_roundtrip():
    payload = b"public universal default round-trip"
    encoded = bytetoken.encode(payload)
    assert bytetoken.decode(encoded) == payload
    assert bytetoken._get_encoder("universal").bit_width == 13


def test_mcp_wire_uses_matching_standard_decoder():
    @mcp_tool(compress=True, threshold_bytes=1)
    def tool():
        return {"records": [{"id": i, "value": "x" * 10} for i in range(20)]}
    wrapped = tool()
    assert wrapped["_bytetoken_wire"] is True
    assert wrapped["mode"] == "standard"
    assert wrapped["tokenizer"] == "cl100k_base"
    restored = json.loads(decode_mcp_response(wrapped).decode("utf-8"))
    assert len(restored["records"]) == 20


def test_direct_id_json_wrapper_is_not_the_id_transport_itself():
    encoder = DirectIDEncoder(tokenizer="cl100k_base", bit_width=16)
    payload = b"direct-id representation"
    ids = encoder.encode(payload); text = encoder.encode_to_string(payload)
    assert isinstance(ids, list); assert json.loads(text) == ids
    assert encoder.decode(ids) == payload; assert encoder.decode_from_string(text) == payload


def test_playground_analysis_uses_measured_counts_and_separates_compression():
    from bytetoken.playground.analysis import _direct_encoder, _standard_encoder, analyze_payload

    payload = b'{"records":[' + b'{"value":"repeat repeat repeat"},' * 32 + b']}'
    report = analyze_payload(payload, "cl100k_base")
    reps = {item["id"]: item for item in report["representations"]}
    assert report["input"]["tokenizer"] == "cl100k_base"
    assert reps["base64"]["tokens"] > 0
    assert reps["bytetoken_standard"]["bit_width"] == 15
    assert reps["direct_id"]["kind"] == "local token-ID representation"
    assert _standard_encoder("cl100k_base").decode(_standard_encoder("cl100k_base").encode(payload)) == payload
    direct = _direct_encoder("cl100k_base")
    assert direct.decode(direct.encode(payload)) == payload
    assert report["compression"]["algorithm"] == "lzma"


def test_playground_request_boundary_accepts_text_and_base64():
    import base64
    from bytetoken.playground.app import AnalyzeRequest, analyze, config

    text_report = analyze(AnalyzeRequest(input_type="text", payload="hello ByteToken", tokenizer="o200k_base"))
    assert text_report["input"]["bytes"] == len("hello ByteToken".encode("utf-8"))

    raw = b"\x00\xffbinary\x10payload"
    encoded = base64.b64encode(raw).decode("ascii")
    binary_report = analyze(AnalyzeRequest(input_type="base64", payload=encoded, tokenizer="cl100k_base"))
    assert binary_report["input"]["bytes"] == len(raw)
    assert config()["max_input_bytes"] > 0


def test_playground_cli_is_registered_without_starting_server():
    from bytetoken.__main__ import build_parser

    args = build_parser().parse_args(["playground", "--host", "127.0.0.1", "--port", "9000"])
    assert args.command == "playground"
    assert args.host == "127.0.0.1"
    assert args.port == 9000


def test_cli_standard_roundtrip(tmp_path):
    source = tmp_path / "payload.bin"; encoded = tmp_path / "payload.bt"; restored = tmp_path / "restored.bin"
    source.write_bytes(b"cli publication smoke test\x00\xff")
    subprocess.run([sys.executable, "-m", "bytetoken", "encode", str(source), "--mode", "standard", "-o", str(encoded)], check=True, capture_output=True, text=True)
    subprocess.run([sys.executable, "-m", "bytetoken", "decode", str(encoded), "--mode", "standard", "-o", str(restored)], check=True, capture_output=True, text=True)
    assert restored.read_bytes() == source.read_bytes()


def test_profiler_cli_does_not_format_unknown_savings_as_number(tmp_path):
    session = tmp_path / "session.json"
    session.write_text(json.dumps({"messages": [{"role": "user", "content": "hello"}]}), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "bytetoken", "profile", str(session)], check=True, capture_output=True, text=True)
    assert "not estimated automatically" in result.stdout


def test_internal_or_speculative_release_material_is_absent():
    forbidden = ["evaluation", "learning_hub", "gpt5_scanner.py", "blt_bridge.py", "dropout_analysis.py", "examples/function_calling_integration.py", "examples/gemini_transport_validation.py", "rust_core/build.log"]
    assert not [path for path in forbidden if Path(path).exists()]
