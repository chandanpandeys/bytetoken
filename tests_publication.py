"""Publication-surface regression tests.

These tests cover public API/documentation invariants that previously drifted
away from the implementation.
"""

import json

import bytetoken
from bytetoken import DirectIDEncoder
from bytetoken.mcp import decode_mcp_response, mcp_tool


def test_public_universal_default_roundtrip():
    payload = b"public universal default round-trip"
    encoded = bytetoken.encode(payload)
    assert bytetoken.decode(encoded) == payload
    # The public default is intentionally the conservative shared 13-bit mode.
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
    assert restored["records"][0]["id"] == 0
    assert len(restored["records"]) == 20


def test_direct_id_json_wrapper_is_not_the_id_transport_itself():
    encoder = DirectIDEncoder(tokenizer="cl100k_base", bit_width=16)
    payload = b"direct-id representation"

    ids = encoder.encode(payload)
    text = encoder.encode_to_string(payload)

    assert isinstance(ids, list)
    assert json.loads(text) == ids
    assert encoder.decode(ids) == payload
    assert encoder.decode_from_string(text) == payload
