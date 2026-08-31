# ByteToken release checklist

This checklist is intentionally public: it records the minimum evidence required before a ByteToken release is described as reproducible.

- [ ] CI passes on supported Python versions and operating systems.
- [ ] Package build and metadata checks pass.
- [ ] Paper LaTeX build passes.
- [ ] Public CLI smoke tests pass.
- [ ] README, Markdown paper, and LaTeX paper use the same scope and terminology.
- [ ] Benchmarks identify synthetic versus externally sourced data.
- [ ] Compression savings are reported separately from binary-to-token representation savings.
- [ ] Direct-ID results are described as local token-ID representation results unless a target inference API explicitly accepts pre-tokenized IDs.
- [ ] No internal launch plans, evaluator prompts, generated build logs, or speculative provider capability tables are tracked.
- [ ] Release notes identify the exact commit and tokenizer/library versions used for reported measurements.

A checked release is still an experimental research release unless explicitly stated otherwise.
