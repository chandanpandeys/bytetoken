# ByteToken

[![CI](https://github.com/chandanpandeys/bytetoken/actions/workflows/ci.yml/badge.svg)](https://github.com/chandanpandeys/bytetoken/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Experimental tokenizer-aware binary transport for tokenized LLM interfaces.**

ByteToken explores a narrow systems question:

> If arbitrary bytes **must** cross a tokenizer-backed text or token interface, can a tokenizer-aware encoding use fewer tokens than conventional Base64?

The project builds fixed-width binary encodings from tokenizer vocabulary items that are empirically validated for the required round-trip boundary conditions. It is a **transport encoding**, not a compression algorithm and not a way for an LLM to understand arbitrary binary data.

## Status

**Research prototype / alpha software.**

The current implementation and paper focus primarily on OpenAI `tiktoken` encodings (`cl100k_base` and `o200k_base`). Results are tokenizer- and version-specific. Cross-provider behavior, hosted-API support for pre-tokenized IDs, model copy-through fidelity, production cost savings, and accelerator speedups must be measured separately for each deployment.

## What is implemented

| Mode | Representation | Current scope | Notes |
|---|---|---|---|
| Standard | tokenizer-stable text | `cl100k_base`, `o200k_base` | Fixed-width encoding using space-prefixed candidate atoms; 15-bit is the conservative default. |
| Universal | shared tokenizer-stable text | intersection of tested `cl100k_base` and `o200k_base` atoms | Intended for portability **between the tested tiktoken encodings**, not "all LLMs". The public high-level default uses 13 bits. |
| Direct ID | `list[int]` token IDs | local/compatible token-ID interfaces | Can reach 16–17 bits per token in the tested vocabularies. Current hosted text APIs should not be assumed to accept arbitrary pre-tokenized ID arrays. |
| SentencePiece | text | included test SentencePiece model | Experimental compatibility path; not a claim covering every SentencePiece model. |
| Error detecting | wrapper | any supported inner encoder | Adds CRC-32 corruption detection. CRC detects errors; it does not correct them. |

The `DirectIDEncoder.encode_to_string()` helper serializes IDs as JSON for storage/debugging. That JSON representation is **not** the high-density Direct-ID transport representation.

## Installation

ByteToken is not currently presented here as a published PyPI release. Install from the repository:

```bash
git clone https://github.com/chandanpandeys/bytetoken.git
cd bytetoken
python -m pip install -e ".[all,dev]"
```

Run the tests:

```bash
python -m pytest tests.py tests_publication.py -v
```

## Playground

**[Open the public ByteToken Playground →](https://bytetoken-playground-kcwc.vercel.app)**

The optional ByteToken Playground turns the research prototype into an interactive measurement surface. Paste UTF-8 text or Base64 bytes, choose `cl100k_base` or `o200k_base`, and compare the same payload across Base64, ByteToken Standard 15-bit, the shared 13-bit text mode, Direct-ID local token IDs, and LZMA-assisted transports.

The Playground reports measured token counts, encode/decode latency, keeps compression savings separate from ByteToken savings, and verifies each displayed encode → decode path byte-for-byte against the original payload.

```bash
python -m pip install -e ".[playground]"
bytetoken playground
```

For local use, open `http://127.0.0.1:8000`. See [PLAYGROUND.md](PLAYGROUND.md) for deployment and scope details. Unexpected results can be reported through the dedicated Playground issue template.

## Quick start

```python
import bytetoken

payload = b"arbitrary binary data"

encoded = bytetoken.encode(payload, mode="standard")
decoded = bytetoken.decode(encoded, mode="standard")

assert decoded == payload
```

### Direct ID mode

```python
from bytetoken import DirectIDEncoder

encoder = DirectIDEncoder(tokenizer="o200k_base")
token_ids = encoder.encode(b"binary data")
restored = encoder.decode(token_ids)

assert restored == b"binary data"
```

`token_ids` are a local token-ID representation. Whether they can be supplied directly to a model depends on the inference interface. A hosted text/content API should not be assumed to accept arbitrary pre-tokenized IDs unless its documentation explicitly says so.

## Benchmarking

The repository includes:

```bash
python benchmarks/benchmark_realworld.py
```

Despite the historical filename, the benchmark generates **deterministic synthetic developer-like payloads** (JSON, pytest-style output, CSV, source code, logs, an embedding vector, and a deterministic random-byte control). The encoder and token counter now use the same declared `o200k_base` tokenizer. It reports:

- Base64 token counts;
- ByteToken-15 token counts;
- Direct-ID-17 local representation counts;
- LZMA + Base64;
- LZMA + ByteToken-15; and
- LZMA + Direct-ID-17 local representation counts.

This distinction matters: on structured data, conventional compression can account for most of the total reduction. ByteToken should be evaluated as the **binary-to-token representation layer**, while LZMA/zstd/Brotli/etc. should be evaluated as separate compression layers.

For publishable comparisons, use the same source bytes and target tokenizer for every method and report both token count and encode/decode latency.

## Scope of the theoretical claim

For a fixed set of independently decodable, concatenation-safe symbols `A`, a fixed-width code can carry at most

`floor(log2(|A|))`

bits per emitted symbol. ByteToken reaches that elementary bound by selecting `2^b` validated symbols and mapping each `b`-bit chunk to one symbol.

This is **not** a proof that ByteToken is globally optimal among every conceivable tokenizer-aware encoding. Variable-length codes, stateful encodings, delimiters, multi-token codewords, or model-/API-specific mechanisms are outside that model.

## Important non-goals

ByteToken does **not**:

- make an LLM reason directly over compressed or encoded bytes;
- guarantee that a generative model will reproduce a long encoded sequence unchanged;
- make arbitrary binaries safe to place in prompts;
- replace object/artifact storage when a payload can be referenced instead of sent through model context;
- provide error correction;
- prove one alphabet works across every BPE, SentencePiece, WordPiece, or multimodal tokenizer;
- make Direct-ID mode usable through an API that only accepts text/content items.

For many agent systems, an artifact store plus selective retrieval is cheaper than transporting the full payload at all. The cheapest token is the one that never enters model context.

## Repository layout

```text
bytetoken/
├── core.py                    # encoder implementations
├── adaptive.py                # experimental compression/mode selection
├── profiler.py                # context/payload diagnostics
├── store.py                   # in-memory artifact-store prototype
├── mcp.py                     # experimental MCP-oriented wire wrapper
├── playground/                # measured FastAPI playground + static UI
├── benchmarks/                # controlled benchmark scripts
├── examples/                  # deterministic local demonstration
├── formal/                    # formal specification work (partial)
├── paper/                     # canonical manuscript sources + compiled PDF
├── rust_core/                 # experimental native backend
├── tests.py                   # core Python test suite
└── tests_publication.py       # public-surface regression tests
```

The Lean material in `formal/` is a **formal specification/proof work in progress**. It should not be described as a complete machine-checked proof of concrete tokenizer behavior while placeholders or axiomatized tokenizer assumptions remain.

## Research paper

The publication-oriented manuscript is available in both compiled and source forms:

- **[Paper PDF](paper/bytetoken_paper.pdf)**
- [Markdown paper](paper/bytetoken_paper.md)
- [LaTeX source](paper/bytetoken_paper.tex)
- [Bibliography](paper/references.bib)

The paper workflow compiles the LaTeX source, validates the build, uploads a CI artifact, and refreshes the stable PDF on `main` when manuscript sources change.

## Reproducibility checklist

Before treating a result as evidence for a new tokenizer or deployment:

1. pin the tokenizer/library version;
2. record the exact alphabet construction rule;
3. test full encode → transport representation → decode round-trips;
4. compare against Base64 and compressed Base64 on identical bytes;
5. report the target tokenizer used for counting;
6. separate compression savings from encoding savings;
7. report latency and environment;
8. do not infer hosted-API compatibility from local token-ID experiments.

## Security

Encoded data is still data. Applications should apply their normal authorization, size limits, malware/content handling, and decompression-bomb protections before decoding or processing untrusted payloads.

See [SECURITY.md](SECURITY.md).

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and open an issue before making large protocol or benchmark changes.

## Citation

If you build on the current research prototype, cite the repository and pin the commit or release you evaluated:

```bibtex
@software{pandey2026bytetoken,
  author  = {Chandan Pandey},
  title   = {ByteToken: Tokenizer-Aware Binary Transport for Tokenized LLM Interfaces},
  year    = {2026},
  url     = {https://github.com/chandanpandeys/bytetoken},
  note    = {Research prototype; cite the evaluated commit or release}
}
```

## License

MIT
