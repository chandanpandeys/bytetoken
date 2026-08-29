"""
ByteToken — Agent Context Profiler
===================================
Analyzes AI agent conversation logs and prompts to diagnose context bloat,
repetitive tool outputs, and serialization waste.

Usage:
    python -m bytetoken profile session.json
    bytetoken profile session.json --model o200k_base
"""

import json
import re
import sys
from typing import Dict, List, Any, Optional
import tiktoken


class ContextProfiler:
    """
    Profiles an LLM conversation or agent execution trace to detect
    preventable context waste.
    """

    def __init__(self, tokenizer_name: str = "o200k_base"):
        self.tokenizer_name = tokenizer_name
        self.enc = tiktoken.get_encoding(tokenizer_name)

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        try:
            return len(self.enc.encode(text))
        except Exception:
            return len(text) // 4

    def profile_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Profile a standard list of chat completion messages:
        [{"role": "user", "content": "..."}, {"role": "assistant", "tool_calls": [...]}, ...]
        """
        total_tokens = 0
        role_breakdown = {"system": 0, "user": 0, "assistant": 0, "tool": 0}
        tool_outputs = []
        base64_blobs = []

        # Regex for potential base64 chunks (>100 chars)
        b64_pattern = re.compile(r'(?:[A-Za-z0-9+/]{4}){25,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?')

        for idx, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "") or ""
            if isinstance(content, list):
                text_content = " ".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            else:
                text_content = str(content)

            tok_count = self.count_tokens(text_content)
            total_tokens += tok_count
            if role in role_breakdown:
                role_breakdown[role] += tok_count

            # Check for tool call responses
            if role == "tool" or "tool_call_id" in msg:
                tool_outputs.append({
                    "index": idx,
                    "tokens": tok_count,
                    "length_chars": len(text_content),
                    "preview": text_content[:120] + "..." if len(text_content) > 120 else text_content
                })

            # Check for embedded Base64
            matches = b64_pattern.findall(text_content)
            for m in matches:
                b64_toks = self.count_tokens(m)
                if b64_toks > 50:
                    base64_blobs.append({
                        "message_index": idx,
                        "base64_tokens": b64_toks,
                        "approx_bytes": int(len(m) * 0.75),
                        "estimated_bytetoken_tokens": int(b64_toks * 0.62)
                    })

        tool_tokens_total = sum(t["tokens"] for t in tool_outputs)
        b64_tokens_total = sum(b["base64_tokens"] for b in base64_blobs)
        b64_savings_potential = sum(b["base64_tokens"] - b["estimated_bytetoken_tokens"] for b in base64_blobs)

        return {
            "total_tokens": total_tokens,
            "message_count": len(messages),
            "role_breakdown": role_breakdown,
            "tool_output_summary": {
                "count": len(tool_outputs),
                "total_tokens": tool_tokens_total,
                "pct_of_total": round(tool_tokens_total / total_tokens * 100, 1) if total_tokens else 0,
            },
            "base64_inefficiency": {
                "detected_blobs": len(base64_blobs),
                "total_base64_tokens": b64_tokens_total,
                "potential_savings_tokens": b64_savings_potential,
                "potential_savings_pct": round(b64_savings_potential / b64_tokens_total * 100, 1) if b64_tokens_total else 0
            },
            "recommendations": self._generate_recommendations(total_tokens, tool_tokens_total, b64_tokens_total)
        }

    def _generate_recommendations(self, total: int, tool_toks: int, b64_toks: int) -> List[str]:
        recs = []
        if tool_toks > total * 0.5 and tool_toks > 2000:
            recs.append(
                f"Tool outputs account for {round(tool_toks/total*100)}% of your session tokens. "
                f"Consider externalizing large outputs via bytetoken.store."
            )
        if b64_toks > 500:
            recs.append(
                f"Detected {b64_toks:,} tokens in raw Base64 strings. "
                f"ByteToken wire encoding can save ~38% of these tokens."
            )
        if total > 50000:
            recs.append(
                "High cumulative context length. Ensure prompt caching breakpoints are active."
            )
        return recs


def profile_file(file_path: str, tokenizer_name: str = "o200k_base") -> Dict[str, Any]:
    """Profile a JSON file containing message lists or agent conversation traces."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data if isinstance(data, list) else data.get("messages", [])
    profiler = ContextProfiler(tokenizer_name)
    return profiler.profile_messages(messages)
