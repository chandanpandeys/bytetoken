# ByteToken 0.1.0 — research preview

ByteToken 0.1.0 is an experimental research preview of tokenizer-aware binary transport.

This release is intentionally scoped. It demonstrates deterministic local encode/decode behavior for the tested tokenizer configurations and a fixed-alphabet density construction. It does not claim universal LLM compatibility, model understanding of encoded bytes, lossless model-mediated copy-through, production cost savings, or generic hosted-API support for arbitrary token-ID arrays.

The included developer-payload benchmark is synthetic. Compression and binary-to-token representation effects are reported separately in the paper and should be evaluated separately in downstream work.

For reproducibility, cite the exact release/commit and record the `tiktoken` version and encoding used.
