"""
ByteToken — Model Context Protocol (MCP) Server Example
=========================================================
Demonstrates how an MCP tool server uses ByteToken to prevent BPE fragmentation
when returning large database query results, diffs, or images.

Run:
    python bytetoken/examples/mcp_server_example.py
"""

import json
import bytetoken
from bytetoken.mcp import mcp_tool, decode_mcp_response
from bytetoken.store import ArtifactStore

store = ArtifactStore()


# 1. MCP Tool that returns a large JSON table (auto-compressed on the wire)
@mcp_tool(compress=True, threshold_bytes=512)
def fetch_user_database(limit: int = 100) -> dict:
    """Mock tool returning 100 user records over MCP."""
    return {
        "status": "success",
        "records": [
            {
                "id": i,
                "name": f"Developer_{i}",
                "email": f"dev{i}@enterprise.internal",
                "roles": ["admin", "developer", "mcp-operator"],
                "permissions": ["read", "write", "deploy", "audit"]
            }
            for i in range(limit)
        ]
    }


# 2. MCP Tool that stores massive logs in ArtifactStore and returns a slice
def analyze_ci_logs(raw_log: str) -> dict:
    """Stores a 50,000 line log in ArtifactStore and returns only the summary + handle."""
    art_id = store.put(raw_log, mime_type="text/plain")
    errors = store.extract_errors(art_id)
    
    return {
        "artifact_id": art_id,
        "total_lines": store.get(art_id)["line_count"],
        "error_summary": errors,
        "instructions_for_model": f"Use store.slice('{art_id}', start_line, end_line) if you need more lines."
    }


def main():
    print("--- 1. Wire-Optimized MCP Tool Call ---")
    response = fetch_user_database(limit=50)
    print(f"Tool returned wire response keys: {list(response.keys())}")
    print(f"Original JSON payload size:       {response['original_bytes']:,} bytes")
    print(f"ByteToken wire string length:     {response['wire_chars']:,} characters")
    
    # Decoding on the client agent side
    decoded_bytes = decode_mcp_response(response)
    restored_json = json.loads(decoded_bytes.decode('utf-8'))
    print(f"Client decoded successfully:      {len(restored_json['records'])} records restored lossless!")

    print("\n--- 2. Out-of-Context Artifact Store Slicing ---")
    mock_log = "\n".join([f"Step {i}: OK" if i != 42 else "FATAL ERROR: Database connection timed out at pool.py:108" for i in range(500)])
    analysis = analyze_ci_logs(mock_log)
    print(f"Stored artifact handle:           {analysis['artifact_id']}")
    print(f"Total lines kept out of prompt:   {analysis['total_lines']}")
    print(f"Extracted error block returned:\n{analysis['error_summary']}")


if __name__ == "__main__":
    main()
