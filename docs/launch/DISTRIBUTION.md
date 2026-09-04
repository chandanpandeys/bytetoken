# ByteToken distribution package

Use the final public Playground URL in place of `PLAYGROUND_URL` before publishing. Keep the GitHub repository as the durable source link.

The objective is **feedback and falsification**, not generic promotion. Do not ask for stars, upvotes, reposts, or leaderboard support.

## Shared factual core

- ByteToken is an experimental tokenizer-aware binary transport encoding.
- Standard mode in the current deterministic `o200k_base` benchmark uses 15-bit symbols.
- Example: synthetic JSON API payload: Base64 18,252 tokens → ByteToken 11,493 tokens, a measured 37.0% reduction.
- Example: synthetic build logs: Base64 9,804 → ByteToken 5,974, a measured 39.1% reduction.
- Direct-ID is local only and must not be presented as hosted-API support.
- Compression is separate. LZMA results are always labeled separately.
- The Playground performs real tokenizer counts and verifies byte-for-byte round trips.
- MIT licensed, public repository, research preview.

---

## LinkedIn — primary launch post

I kept running into a weird transport problem while thinking about LLM and agent context: binary data usually becomes text before it reaches a tokenizer, and Base64 was designed to survive text systems, not to minimize tokenizer tokens.

So I built ByteToken as an experiment around a different question: what happens if the transport alphabet itself is chosen from tokenizer-stable vocabulary elements?

I have now built a Playground where you can paste a payload and compare the exact same bytes across Base64, ByteToken Standard, a shared-alphabet mode, Direct-ID research mode, and LZMA-assisted variants. It uses real `cl100k_base` / `o200k_base` token counts and decodes every representation back to the original bytes to verify the round trip.

On the deterministic synthetic benchmark with `o200k_base`, one JSON API payload goes from 18,252 Base64 tokens to 11,493 ByteToken-15 tokens, and a build-log payload goes from 9,804 to 5,974. Those are benchmark results, not a claim that every workload gets the same reduction.

The part I care about now is finding where the idea breaks.

Does an artifact store make inline binary transport unnecessary for your agent workflow? Is there a tokenizer where the alphabet assumption fails? Is there a runtime that genuinely accepts pre-tokenized IDs? Are there security or protocol problems I have missed?

Playground: PLAYGROUND_URL
GitHub: https://github.com/chandanpandeys/bytetoken

ByteToken is still a research prototype, and I would rather collect counterexamples than turn one benchmark into a universal claim.

---

## X — concise post

I built a Playground for ByteToken, an experiment in tokenizer-aware binary transport for LLM/agent interfaces.

Synthetic JSON benchmark (`o200k_base`):
Base64: 18,252 tokens
ByteToken-15: 11,493
→ 37.0% fewer tokens
→ byte-for-byte round trip verified

Not compression. Not “LLMs understand binary.” Direct-ID is local-only research.

Try your own payload: PLAYGROUND_URL
Code: https://github.com/chandanpandeys/bytetoken

---

## X — technical thread outline

### Post 1

Base64 solves binary-through-text transport. It was never designed around BPE token cost.

I built ByteToken to test a different transport alphabet: tokenizer-stable vocabulary elements.

The Playground is now usable: PLAYGROUND_URL

### Post 2

One deterministic synthetic JSON case under `o200k_base`:

18,252 Base64 tokens
→ 11,493 ByteToken-15 tokens
→ 37.0% reduction

Build logs: 9,804 → 5,974 (39.1%).

Every displayed path is decoded and compared byte-for-byte.

### Post 3

Important distinction: ByteToken is an encoding layer, not compression.

For deterministic random bytes:
Base64 = 4,569 tokens
LZMA + Base64 = 4,619
ByteToken-15 = 2,668

LZMA actually hurts Base64 on that control.

### Post 4

There is also Direct-ID research mode, but I keep it visually separate because token-ID arrays are not text and this does NOT imply hosted APIs accept arbitrary pre-tokenized input IDs.

### Post 5

What I want now is failure cases:
- tokenizers where the assumptions break
- real/anonymized agent payloads
- runtimes with explicit token-ID input
- cases where artifact-store + retrieval is simply the better architecture

Repo: https://github.com/chandanpandeys/bytetoken

---

## Threads

Base64 is great at getting binary through text systems, but what happens when the next layer is a tokenizer?

That question became ByteToken. I have now built an interactive Playground that measures the same payload as Base64 vs tokenizer-aware ByteToken representations using real `cl100k_base` / `o200k_base` counts, and it verifies every encode → decode path byte-for-byte.

A deterministic synthetic JSON benchmark under `o200k_base` goes from 18,252 Base64 tokens to 11,493 with ByteToken-15 (37.0% fewer). This is not compression and I am deliberately keeping the claims narrow.

I want people to try payloads where it fails, not just the happy path.

PLAYGROUND_URL
https://github.com/chandanpandeys/bytetoken

---

## Peerlist

### Title

ByteToken Playground — measure binary transport cost in tokenizer tokens

### Description

I built an interactive Playground for ByteToken, an experimental tokenizer-aware binary transport encoding. Paste text or Base64 bytes, choose `o200k_base` or `cl100k_base`, and compare Base64, ByteToken Standard, shared-alphabet ByteToken, Direct-ID research mode, and separately labeled LZMA variants. Every displayed transport is decoded back to the original payload for byte-for-byte verification.

Deterministic synthetic benchmark example under `o200k_base`: JSON API payload 18,252 Base64 tokens → 11,493 ByteToken-15 tokens (37.0% fewer).

The project is MIT licensed and still a research preview. Feedback I want most: tokenizer failure cases, benchmark criticism, real/anonymized agent payloads, and cases where artifact-store/retrieval architectures make this transport unnecessary.

Playground: PLAYGROUND_URL
GitHub: https://github.com/chandanpandeys/bytetoken

---

## Reddit — r/LLMDevs

Current r/LLMDevs policy explicitly allows sharing free open-source projects without prior moderator approval. Keep the author disclosure and do not disguise this as a neutral recommendation.

### Suggested title

I built an open-source tokenizer-aware binary transport experiment; looking for failure cases

### Body

Disclosure: I built this project. It is MIT licensed, free/open source, and there is no paid version.

The experiment is called ByteToken. The question behind it is pretty narrow: when binary payloads have to cross a tokenized LLM/agent interface, can a representation built from tokenizer-stable vocabulary elements use fewer tokenizer tokens than Base64?

I have added an interactive Playground so the result is not just a benchmark table. You can paste a payload, choose `o200k_base` or `cl100k_base`, compare Base64 / ByteToken Standard / shared-alphabet ByteToken / Direct-ID research mode, and see a byte-for-byte round-trip check for every representation. LZMA is shown separately because compression and representation are different layers.

On the deterministic synthetic developer-payload benchmark under `o200k_base`:

- JSON API: Base64 18,252 tokens → ByteToken-15 11,493 (37.0% fewer)
- build logs: 9,804 → 5,974 (39.1% fewer)
- random 5 KB bytes: Base64 4,569 → ByteToken-15 2,668; LZMA+Base64 is 4,619, so compression actually hurts that control

I am not claiming that models understand ByteToken, that every tokenizer gets these savings, or that Direct-ID token arrays can be sent to arbitrary hosted APIs.

What I would really like from people here is the opposite of launch-day praise: payloads/tokenizers where this loses, benchmark methodology criticism, runtimes that genuinely accept explicit token IDs, and examples where artifact storage + selective retrieval makes inline transport the wrong abstraction entirely.

Playground: PLAYGROUND_URL
Repo: https://github.com/chandanpandeys/bytetoken
Benchmark source: https://github.com/chandanpandeys/bytetoken/blob/main/benchmarks/benchmark_realworld.py

---

## Reddit — LocalLLaMA HOLD

**Do not publish ByteToken there yet.**

Current moderation requires self-promotion to remain a small minority of account activity (recent moderator explanations describe a 90/10 participation/self-promotion expectation), with meaningful participation rather than quota-filling. Recent moderation also removes projects whose local-model relevance is incidental.

Only revisit LocalLLaMA after both are true:

1. the account clearly satisfies the participation expectation; and
2. ByteToken has a concrete local-model/local-tokenizer demo, not merely a theoretical connection.

When those gates are met, write the post for that community rather than reusing the r/LLMDevs copy.

---

## Hacker News — human-written factual outline only

**Do not paste AI-generated submission/comment text into Hacker News.** Current HN guidelines explicitly say not to post generated or AI-edited text. Use the facts below and write the submission yourself.

### Show HN readiness

- Public Playground directly usable without signup/email gate.
- Link should point to the working demo, not a blog post or landing page.
- You personally built/worked on the project and are available to discuss it.
- Your HN account should be an actual community account, not used primarily for promotion; HN is currently restricting Show HN submissions from users who are not familiar with the community.
- Do not ask anyone to upvote or comment.

### Possible factual title shape to rewrite yourself

`Show HN: ByteToken – tokenizer-aware binary transport with a measured playground`

Do not copy that mechanically if it does not sound like you.

### Facts to cover in your own first comment / submission text

- You were investigating token overhead when binary data is serialized as Base64 before a tokenized interface.
- ByteToken uses tokenizer-stable vocabulary elements as a fixed-width symbol alphabet.
- Standard mode currently uses 15-bit symbols for the tested tokenizer setup.
- The Playground compares identical bytes and verifies decode round trips.
- Example deterministic synthetic JSON result: Base64 18,252 vs ByteToken 11,493 tokens under `o200k_base`.
- Compression is deliberately reported separately.
- Direct-ID is deliberately labeled local-only.
- The research question now is architectural: when is inline encoding useful vs artifact-store/retrieval references?
- Ask for counterexamples and protocol criticism.

### Avoid

- marketing adjectives,
- “revolutionary,” “game-changing,” etc.,
- asking for GitHub stars,
- asking friends to comment,
- universal percentage claims,
- claiming this reduces actual model billing without checking the exact API/tokenizer path.

---

## Dev.to / Hashnode article distribution

Publish `ARTICLE.md` with the repository and Playground links near the top and again at the end. The article should be the canonical explanation used by people who want more context after seeing a short social post.

Suggested article title:

**ByteToken: What happens when binary transport is designed around the tokenizer?**

Suggested subtitle:

*A research prototype comparing Base64 with tokenizer-aware binary representations, with reproducible benchmarks and an interactive lossless Playground.*

---

## Cross-platform response snippets

### “Isn’t this just compression?”

No. The benchmark measures compression separately. On the deterministic 5 KB random-byte control, LZMA+Base64 is actually slightly worse than Base64 (4,619 vs 4,569 tokens under `o200k_base`), while ByteToken-15 is 2,668. For compressible JSON/log data, LZMA contributes most of the total reduction, which is why those numbers are never presented as ByteToken-only savings.

### “Can the LLM understand this representation?”

That is not a ByteToken claim. The Playground measures transport representation and lossless encode/decode behavior. Model understanding or generative copy-through fidelity is a separate experiment.

### “Can I send Direct-ID to the OpenAI/Anthropic/etc. API?”

Do not assume so. Direct-ID in this repo is a local tokenizer/runtime representation. Hosted APIs generally define their own input serialization and may not expose arbitrary pre-tokenized-ID input.

### “Why not store the artifact and send a reference?”

Often that may be the better architecture. One of the explicit next research questions is to compare Base64, compressed Base64, ByteToken, artifact-store references, selective retrieval/slicing, and combinations of them.

### “Why compare against Base64?”

Because the experiment is about binary payloads crossing text/tokenized interfaces. It is not a proposal to encode ordinary text into ByteToken when the text can simply be sent as text.
