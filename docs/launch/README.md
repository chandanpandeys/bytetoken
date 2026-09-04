# ByteToken launch playbook

Status: **Playground engineering complete; launch package prepared.**

This directory is the operational source of truth for the post-Reddit/Hacker News phase of ByteToken. The goal is not to make the loudest claims possible. The goal is to make the experiment easy to try, easy to reproduce, and easy to criticize.

## What we can say

- ByteToken is an experimental tokenizer-aware binary transport encoding.
- The current string-oriented 15-bit mode can use fewer `o200k_base` tokens than Base64 on the deterministic synthetic developer-like payloads in `benchmarks/benchmark_realworld.py`.
- Every benchmarked representation is losslessly decoded in the benchmark or Playground path.
- Direct-ID is a **local pre-tokenized ID representation**, not evidence that hosted model APIs accept arbitrary token IDs.
- LZMA is a separate compression layer. Compression savings must never be presented as ByteToken-only savings.
- The Playground measures transport representation cost. It does not prove that a model understands, preserves, or usefully reasons over the encoded payload.

## What we should not say

- “ByteToken compresses data.”
- “ByteToken works with all LLMs/tokenizers.”
- “Models understand ByteToken.”
- “Direct-ID works with hosted APIs.”
- “40% fewer tokens everywhere.”
- “Production-ready protocol.”

## Launch gates

1. **Repository:** merged implementation, tests, paper, benchmark, issue template. ✅
2. **CI:** Python 3.10–3.12 across Ubuntu/macOS/Windows + package + benchmark + TypeScript. ✅
3. **Playground build:** Vercel build passes. ✅
4. **Public alias:** confirm the final public `*.vercel.app`/custom URL loads `/`, `/api/config`, and a real `/api/analyze` request. ⏳
5. **No-signup trial:** required before a Show HN. ⏳ until public alias is confirmed.
6. **Distribution copy:** prepared in `DISTRIBUTION.md`. ✅
7. **Technical article:** prepared in `ARTICLE.md`. ✅
8. **Product Hunt listing kit:** prepared in `PRODUCT_HUNT.md`; launch intentionally held until the public URL and gallery are final. ✅ / held

## Recommended sequence

### Phase A — public demo

- Confirm the Vercel production/public alias.
- Test `/`, `/api/config`, and `/api/analyze` with both tokenizers.
- Test one invalid Base64 request and one payload close to the size limit.
- Capture one clean result using a deterministic sample.

### Phase B — technical distribution

1. Publish the technical article.
2. Share to **r/LLMDevs** as a disclosed free MIT-licensed open-source project and ask for benchmark/failure-case feedback.
3. Publish LinkedIn, X, Threads, and Peerlist demo-led posts using the measured benchmark, not a generic launch announcement.
4. Use Hacker News only when the public demo is accessible without signup and write the submission text personally from the factual outline in `DISTRIBUTION.md`.
5. Do **not** post to LocalLLaMA yet unless the account satisfies its participation/self-promotion requirements and the project is demonstrated in a genuinely local-model workflow.

### Phase C — feedback loop

Track feedback as GitHub issues, especially:

- tokenizer/version failure cases,
- payloads where Standard ByteToken loses to Base64,
- model/runtime APIs that genuinely accept pre-tokenized IDs,
- security/protocol concerns,
- workloads where artifact-store + retrieval is clearly better than inline transport.

Do not optimize the story around positive results only. Negative results are useful research results.

### Phase D — Product Hunt

Launch only after:

- the public Playground URL is stable,
- at least 3 strong visual/demo assets exist,
- the Playground has survived initial technical feedback,
- the listing can point to a product people can actually use.

Product Hunt currently allows makers to hunt their own product and explicitly says not to ask people to upvote; ask people to visit and comment instead.

## Source-of-truth links

- Repository: https://github.com/chandanpandeys/bytetoken
- Release: https://github.com/chandanpandeys/bytetoken/releases/tag/v0.1.0
- Paper: https://github.com/chandanpandeys/bytetoken/blob/main/paper/bytetoken_paper.md
- Playground guide: https://github.com/chandanpandeys/bytetoken/blob/main/PLAYGROUND.md
- Benchmark: https://github.com/chandanpandeys/bytetoken/blob/main/benchmarks/benchmark_realworld.py
- HN Show guidelines: https://news.ycombinator.com/showhn.html
- HN guidelines: https://news.ycombinator.com/newsguidelines.html
- Product Hunt launch guide: https://www.producthunt.com/launch
