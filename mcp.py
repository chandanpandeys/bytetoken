"""
ByteToken — Model Context Protocol (MCP) Integration
======================================================
Provides drop-in tool decorators and an MCP server enabling agents to:
1. Return ByteToken wire-compressed binary/structured payloads across MCP.
2. Externalize large tool outputs to an artifact store and return lightweight handles.
3. Selectively search/slice artifacts without blowing up active context.

Usage:
    from bytetoken.mcp import mcp_tool, create_mcp_server
"""

import functools
import json
import lzma
from typing import Callable, Any, Dict, Union
import bytetoken
from bytetoken.store import ArtifactStore

# Global shared store instance for local MCP tool sessions
GLOBAL_STORE = ArtifactStore()


def mcp_tool(compress: bool = True, threshold_bytes: int = 1024):
    """
    Decorator for MCP tool functions.
    
    If the return payload exceeds threshold_bytes:
    - If structured text/dict, compresses via LZMA and encodes with ByteToken
    - If raw bytes, encodes with ByteToken to prevent Base64 BPE fragmentation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)
            
            # Serialize to bytes
            if isinstance(result, dict) or isinstance(result, list):
                raw_bytes = json.dumps(result).encode("utf-8")
                is_json = True
            elif isinstance(result, str):
                raw_bytes = result.encode("utf-8")
                is_json = False
            elif isinstance(result, bytes):
                raw_bytes = result
                is_json = False
            else:
                return result

            if len(raw_bytes) < threshold_bytes:
                return result

            # Apply ByteToken Wire Transport
            if compress:
                compressed = lzma.compress(raw_bytes)
                encoded = bytetoken.encode(compressed, mode="standard")
                return {
                    "_bytetoken_wire": True,
                    "compressed": True,
                    "compression": "lzma",
                    "encoding": "bytetoken-15",
                    "original_bytes": len(raw_bytes),
                    "compressed_bytes": len(compressed),
                    "wire_chars": len(encoded),
                    "payload": encoded
                }
            encoded = bytetoken.encode(raw_bytes, mode="standard")
            return {
                "_bytetoken_wire": True,
                "compressed": False,
                "compression": None,
                "encoding": "bytetoken-15",
                "original_bytes": len(raw_bytes),
                "wire_chars": len(encoded),
                "payload": encoded
            }

        return wrapper
    return decorator


def decode_mcp_response(response: Dict[str, Any]) -> bytes:
    """Decode a ByteToken wire-wrapped response back to raw bytes."""
    if not isinstance(response, dict) or not response.get("_bytetoken_wire"):
        raise ValueError("Payload is not a ByteToken wire-wrapped response.")

    encoded = response["payload"]
    raw = bytetoken.decode(encoded)
    if response.get("compressed"):
        return lzma.decompress(raw)
    return raw
