"""
ByteToken — Artifact Store & Context Slicer
============================================
Keeps massive tool outputs (pytest logs, DB dumps, ASTs) out of the LLM context,
letting the agent retrieve only relevant lines/errors or request ByteToken-encoded wire payloads.

Usage:
    from bytetoken.store import ArtifactStore
    store = ArtifactStore()
    art_id = store.put("huge log output...")
    slice_text = store.slice(art_id, start_line=100, end_line=150)
    errors = store.extract_errors(art_id)
"""

import hashlib
import re
import time
from typing import Dict, List, Optional, Any


class ArtifactStore:
    """
    In-memory / disk-backed store for large agent artifacts.
    """

    def __init__(self):
        self._artifacts: Dict[str, Dict[str, Any]] = {}

    def put(self, content: str | bytes, mime_type: str = "text/plain", metadata: Optional[Dict] = None) -> str:
        """Store an artifact and return a unique handle."""
        if isinstance(content, str):
            data_bytes = content.encode("utf-8")
            text_val = content
        else:
            data_bytes = content
            text_val = None

        art_id = "art_" + hashlib.sha256(data_bytes).hexdigest()[:12]
        lines = text_val.splitlines() if text_val is not None else []

        self._artifacts[art_id] = {
            "id": art_id,
            "bytes": data_bytes,
            "text": text_val,
            "lines": lines,
            "line_count": len(lines),
            "size_bytes": len(data_bytes),
            "mime_type": mime_type,
            "created_at": time.time(),
            "metadata": metadata or {}
        }
        return art_id

    def get(self, art_id: str) -> Optional[Dict[str, Any]]:
        return self._artifacts.get(art_id)

    def slice(self, art_id: str, start_line: int = 1, end_line: int = 50) -> str:
        """Return a slice of lines (1-indexed)."""
        art = self.get(art_id)
        if not art or art["text"] is None:
            return f"Error: Artifact {art_id} not found or is binary."

        lines = art["lines"]
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)

        selected = lines[start_idx:end_idx]
        header = f"--- [Artifact {art_id}: lines {start_idx+1}..{end_idx} of {len(lines)}] ---\n"
        return header + "\n".join(selected)

    def search(self, art_id: str, query: str, max_results: int = 20) -> str:
        """Search for lines containing query."""
        art = self.get(art_id)
        if not art or art["text"] is None:
            return f"Error: Artifact {art_id} not found or is binary."

        matches = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        for idx, line in enumerate(art["lines"]):
            if pattern.search(line):
                matches.append(f"Line {idx+1}: {line}")
                if len(matches) >= max_results:
                    break

        if not matches:
            return f"No matches for '{query}' in artifact {art_id}."

        return f"--- [Artifact {art_id} matches for '{query}' ({len(matches)} found)] ---\n" + "\n".join(matches)

    def extract_errors(self, art_id: str) -> str:
        """Heuristically extract error, failure, and traceback blocks."""
        art = self.get(art_id)
        if not art or art["text"] is None:
            return f"Error: Artifact {art_id} not found or is binary."

        error_lines = []
        pattern = re.compile(r'(error|fail|exception|traceback|fatal|critical)', re.IGNORECASE)
        for idx, line in enumerate(art["lines"]):
            if pattern.search(line):
                # Grab a 3-line context window
                start = max(0, idx - 1)
                end = min(len(art["lines"]), idx + 2)
                block = "\n".join(f"  {i+1}: {art['lines'][i]}" for i in range(start, end))
                error_lines.append(block)
                if len(error_lines) >= 15:
                    break

        if not error_lines:
            return f"No explicit error patterns detected in artifact {art_id}."

        return f"--- [Artifact {art_id} Detected Error Blocks] ---\n" + "\n---\n".join(error_lines)
