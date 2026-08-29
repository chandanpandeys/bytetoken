"""
ByteToken — Multi-Agent Inter-Process State Transport
======================================================
Demonstrates how two distributed agents (e.g., in a LangGraph / CrewAI swarm)
exchange memory snapshots or serialized embedding vectors without Base64 token bloat.

Run:
    python bytetoken/examples/agent_state_transport.py
"""

import json
import base64
import lzma
import tiktoken
import bytetoken

def count_tokens(text: str) -> int:
    enc = tiktoken.get_encoding("o200k_base")
    return len(enc.encode(text))

def simulate_agent_handoff():
    print("=" * 60)
    print("  Multi-Agent Inter-Process State Transport Demo")
    print("=" * 60)

    # 1. Agent A creates an internal execution state & embedding snapshot
    agent_a_state = {
        "task_id": "scrape_and_embed_9012",
        "scraped_entities": [
            {"entity": f"item_{i}", "score": 0.85 + (i % 10)*0.01, "attributes": [f"attr_{j}" for j in range(8)]}
            for i in range(80)
        ],
        "state_flags": {"status": "in_progress", "retry_count": 0, "sandbox_id": "sbx-8812"}
    }
    state_bytes = json.dumps(agent_a_state).encode("utf-8")
    print(f"Agent A Raw State Size:    {len(state_bytes):,} bytes\n")
    
    # 2. Base64 transport
    b64_wire = base64.b64encode(state_bytes).decode("ascii")
    b64_tokens = count_tokens(b64_wire)
    print(f"1. Base64 Wire Payload:    {b64_tokens:>6,} tokens")
    
    # 3. Standalone ByteToken-15
    bt_wire = bytetoken.encode(state_bytes, mode="standard")
    bt_tokens = count_tokens(bt_wire)
    print(f"2. ByteToken-15:           {bt_tokens:>6,} tokens ({round((1-bt_tokens/b64_tokens)*100, 1)}% fewer tokens)")
    
    # 4. LZMA + ByteToken-15 (Recommended for structured agent state)
    compressed = lzma.compress(state_bytes)
    lzma_bt_wire = bytetoken.encode(compressed, mode="standard")
    lzma_bt_tokens = count_tokens(lzma_bt_wire)
    print(f"3. LZMA + ByteToken-15:    {lzma_bt_tokens:>6,} tokens ({round((1-lzma_bt_tokens/b64_tokens)*100, 1)}% fewer tokens)")

    # 5. Agent B receives wire payload and reconstructs state
    restored_bytes = lzma.decompress(bytetoken.decode(lzma_bt_wire, mode="standard"))
    restored_state = json.loads(restored_bytes.decode("utf-8"))
    
    assert restored_state == agent_a_state, "State integrity failure!"
    print(f"\n[SUCCESS] Agent B restored {len(restored_state['scraped_entities'])} entities with 100% losslessness!")
    print("=" * 60)

if __name__ == "__main__":
    simulate_agent_handoff()
