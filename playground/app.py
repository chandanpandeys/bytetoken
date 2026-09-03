"""Optional FastAPI application for the ByteToken Playground."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .analysis import MAX_INPUT_BYTES, SUPPORTED_TOKENIZERS, analyze_payload

STATIC_DIR = Path(__file__).with_name("static")


class AnalyzeRequest(BaseModel):
    input_type: Literal["text", "base64"] = "text"
    payload: str = Field(default="", max_length=MAX_INPUT_BYTES * 2)
    tokenizer: Literal["cl100k_base", "o200k_base"] = "o200k_base"


app = FastAPI(
    title="ByteToken Playground",
    description="Measured ByteToken transport comparisons over the repository's existing APIs.",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
def config():
    return {
        "tokenizers": list(SUPPORTED_TOKENIZERS),
        "max_input_bytes": MAX_INPUT_BYTES,
        "scope": "research-prototype",
    }


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest):
    try:
        if request.input_type == "base64":
            data = base64.b64decode(request.payload, validate=True)
        else:
            data = request.payload.encode("utf-8")
        return analyze_payload(data, tokenizer_name=request.tokenizer)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the optional playground server with uvicorn."""
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            'Playground dependencies are missing. Install with pip install -e ".[playground]".'
        ) from exc
    uvicorn.run("bytetoken.playground.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
