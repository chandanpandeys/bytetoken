"""Local MCP-style wrapper demonstration.

Exercises ByteToken's deterministic local wrapper and in-memory artifact store.
It does not create a network MCP server or test model-mediated copy-through.
"""
import json
from bytetoken.mcp import decode_mcp_response, mcp_tool
from bytetoken.store import ArtifactStore

store = ArtifactStore()

@mcp_tool(compress=True, threshold_bytes=512)
def fetch_user_database(limit: int = 100) -> dict:
    return {"status": "success", "records": [{"id": i, "name": f"Developer_{i}", "roles": ["developer"]} for i in range(limit)]}


def analyze_ci_logs(raw_log: str) -> dict:
    artifact_id = store.put(raw_log, mime_type="text/plain")
    return {"artifact_id": artifact_id, "total_lines": store.get(artifact_id)["line_count"], "error_summary": store.extract_errors(artifact_id)}


def main():
    response = fetch_user_database(limit=50); restored = json.loads(decode_mcp_response(response).decode("utf-8")); print(f"Restored {len(restored['records'])} mock records in the local wrapper.")
    mock_log = "\n".join("FATAL ERROR: database timeout" if i == 42 else f"Step {i}: OK" for i in range(500)); analysis = analyze_ci_logs(mock_log); print(f"Artifact handle: {analysis['artifact_id']}"); print(f"Error slice:\n{analysis['error_summary']}")


if __name__ == "__main__": main()
