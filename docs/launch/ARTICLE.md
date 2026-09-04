# ByteToken: What happens when binary transport is designed around the tokenizer?

ByteToken started from a transport question rather than a model question.

When binary data has to move through a text-oriented interface, Base64 is the default for good reasons: it is simple, reversible, widely supported, and safe across systems that expect text. But an LLM or agent interface often adds another layer after text serialization: a tokenizer.

That creates a different optimization problem.

Base64 was designed around bytes and text compatibility. It was not designed to minimize the number of BPE tokens produced by `cl100k_base`, `o200k_base`, or another tokenizer. ByteToken is an experiment that asks whether a binary-to-text representation can instead choose its alphabet with the tokenizer in mind.

The project is open source and intentionally still a research preview.

- Playground: `PLAYGROUND_URL`
- Repository: https://github.com/chandanpandeys/bytetoken
- Paper: https://github.com/chandanpandeys/bytetoken/blob/main/paper/bytetoken_paper.md
- Reproducible benchmark: https://github.com/chandanpandeys/bytetoken/blob/main/benchmarks/benchmark_realworld.py

## The problem is not “LLMs are bad at Base64”

That framing would mix together several different questions.

ByteToken is specifically about **representation cost at a tokenizer boundary**.

Imagine an agent system needs to move a binary artifact through an interface that accepts text. A conventional path is:

```text
binary bytes → Base64 text → tokenizer → model/API context
```

The Base64 step expands bytes into a restricted text alphabet. The tokenizer then independently decides how that text becomes tokens. Depending on the tokenizer and the payload, many Base64 characters may not pack into the tokenizer as efficiently as a representation built specifically from vocabulary elements that are known to be atomic.

So ByteToken explores this path instead:

```text
binary bytes → fixed-width bit groups → tokenizer-aware symbols → tokenizer
```

The key idea is not that the model understands binary. It is that the transport representation can be chosen so its symbols have predictable tokenizer behavior.

## Standard ByteToken

The current Standard encoder discovers/uses tokenizer-stable text atoms and maps fixed-width groups of binary data onto them.

In the current measured configuration used by the deterministic benchmark, Standard ByteToken uses a 15-bit symbol width with `o200k_base`.

Conceptually:

1. Take the input bytes.
2. View them as a bit stream.
3. Split the stream into fixed-width chunks.
4. Map each chunk to a selected tokenizer-stable text atom.
5. Serialize those atoms as text.
6. Reverse the process during decoding.

A crucial constraint is that the chosen symbols need to behave as expected when the target tokenizer sees them. This is why tokenizer version and tokenizer identity matter.

ByteToken is not proposing one magic alphabet that automatically works across every tokenizer.

## Shared-alphabet / Universal mode

There is also a shared-alphabet mode intended to explore portability across a tested tokenizer intersection. Because the alphabet has to satisfy more than one tokenizer, it has fewer available symbols and therefore uses a smaller bit width (currently 13-bit in the Playground).

That is a trade-off:

```text
larger tokenizer-specific alphabet → more bits represented per symbol
smaller shared alphabet → more portability, lower density
```

The word “universal” should not be interpreted as “all tokenizers everywhere.” It means a shared set for the specific tested tokenizer set.

## Direct-ID research mode

A tokenizer vocabulary ultimately consists of token IDs, so there is a denser research representation that maps data directly into IDs.

In the current `o200k_base` benchmark this mode uses a 17-bit representation.

But Direct-ID needs a very explicit warning:

**A local array of token IDs is not the same thing as a valid text representation, and it does not prove that a hosted model API accepts arbitrary pre-tokenized input IDs.**

Many hosted APIs accept strings/messages and perform tokenization internally. Direct-ID is therefore best understood as a local tokenizer/runtime experiment unless a specific target interface explicitly supports the required token-ID input path.

The Playground keeps Direct-ID visually separate from text transports for exactly this reason.

## The deterministic benchmark

The repository includes a deterministic synthetic developer-payload benchmark. These are generated payloads, not production traces, and they should be treated accordingly.

The benchmark currently uses `o200k_base` and measures Base64, Standard ByteToken-15, local Direct-ID-17, and separately compressed LZMA variants.

| Payload | Bytes | Base64 | ByteToken-15 | Direct-ID-17* |
|---|---:|---:|---:|---:|
| JSON API (100 users) | 21,547 | 18,252 | 11,493 | 10,141 |
| Pytest-style output | 3,183 | 2,904 | 1,699 | 1,499 |
| CSV analytics (500 rows) | 27,118 | 24,524 | 14,464 | 12,763 |
| Python source | 7,906 | 6,386 | 4,218 | 3,722 |
| Build-log text | 11,199 | 9,804 | 5,974 | 5,272 |
| Embedding vector (768 float32) | 3,072 | 2,589 | 1,640 | 1,447 |
| Deterministic random bytes (5 KB) | 5,000 | 4,569 | 2,668 | 2,354 |

`*` Direct-ID is a local representation count only.

For Standard ByteToken, the measured reductions relative to Base64 range from 33.9% to 41.6% across this particular synthetic set.

A useful headline example is the generated JSON API payload:

```text
Base64:          18,252 tokens
ByteToken-15:    11,493 tokens
Difference:       6,759 tokens
Reduction:           37.0%
```

The build-log sample is similar:

```text
Base64:           9,804 tokens
ByteToken-15:     5,974 tokens
Reduction:           39.1%
```

Those numbers are reproducible for this benchmark configuration. They are not evidence that every real workload, tokenizer, or API receives the same percentage.

## Compression is a different layer

This distinction matters enough to make explicit.

ByteToken is an **encoding/representation** experiment. LZMA is **compression**.

For compressible data such as repetitive JSON, CSV, source, and logs, compression can reduce the payload dramatically before either Base64 or ByteToken sees it. If a chart shows `LZMA + ByteToken` producing a very small token count, most of that result may come from LZMA rather than ByteToken itself.

The benchmark therefore reports the layers separately.

The deterministic random-byte control makes the difference especially clear:

```text
5,000 source bytes

Base64:            4,569 tokens
LZMA + Base64:     4,619 tokens
ByteToken-15:      2,668 tokens
LZMA + ByteToken:  2,700 tokens
```

Compression slightly *hurts* both representations on this high-entropy-ish control. That is expected behavior and is useful because it prevents the experiment from quietly attributing compression gains to the encoding.

For a real system, the decision can be thought of as two independent questions:

```text
Should this payload be compressed?
             ↓
How should the resulting bytes be transported across this interface?
```

## The Playground

A benchmark table is not enough for this kind of claim. Tokenizer behavior is too sensitive to the exact representation and tokenizer.

The ByteToken Playground lets you paste UTF-8 text or supply Base64 bytes, choose either `o200k_base` or `cl100k_base`, and measure several representations on the same payload:

- Base64
- ByteToken Standard 15-bit
- shared-alphabet ByteToken 13-bit
- Direct-ID research representation
- LZMA + Base64
- LZMA + Standard ByteToken

The important part is that it does more than display token counts.

Every transport path is decoded and compared byte-for-byte with the original payload. The result includes a round-trip status and encode/decode timings.

That makes the Playground useful for finding counterexamples. If ByteToken performs poorly on a particular payload, that is a result worth keeping rather than hiding.

## What ByteToken does not prove

### 1. It does not prove model understanding

A transport can be lossless between an encoder and decoder without a model being able to interpret its encoded content.

If an architecture expects the model itself to reason over the raw represented payload, that is a separate experiment involving model behavior, not just tokenizer accounting.

### 2. It does not prove generative copy-through fidelity

Even if a string tokenizes efficiently, asking a model to reproduce it exactly introduces a generative reliability problem. ByteToken's lossless claim concerns deterministic encode/decode operations, not arbitrary LLM transcription.

### 3. It does not prove hosted Direct-ID support

The Direct-ID representation is meaningful only where an interface actually permits explicit token IDs in the required form.

### 4. It does not establish universal tokenizer compatibility

Atomic/stable symbol sets are tokenizer-specific. A representation valid under one tokenizer/version may behave differently under another.

### 5. It does not establish that inline transport is the right architecture

This may be the most important limitation.

If an agent needs a large binary artifact, a better design may be:

```text
artifact → object/artifact store → reference in context
```

Then the model/tool retrieves only the bytes or slices it actually needs.

That can be much more efficient than trying to squeeze the full payload inline, regardless of whether the inline encoding is Base64 or ByteToken.

## The architectural question is more interesting than the percentage

The first version of the project focused on whether tokenizer-aware binary representation can beat Base64 under a defined setup.

The next research question is broader:

> Where does inline token-aware transport actually belong in an agent architecture?

The comparison I want to run is not only Base64 vs ByteToken. It is:

1. raw Base64 transport,
2. compression + Base64,
3. ByteToken text transport,
4. artifact-store + reference,
5. selective retrieval/slicing,
6. combinations where an artifact store is used but payload transfer is still required at a later boundary.

I expect the answer to vary by workload.

For many agent systems, artifact references may win outright. ByteToken becomes more interesting at boundaries where bytes genuinely must be serialized through a tokenizer-aware channel and an artifact indirection is unavailable, undesirable, or itself expensive.

## What would falsify or weaken the idea?

Useful feedback is not “cool project.” Useful feedback includes:

- a tokenizer where the supposedly stable alphabet does not remain stable,
- a real payload distribution where Standard ByteToken consistently loses to Base64,
- tokenizer-version changes that make stored alphabets unsafe,
- security concerns around decoding or symbol-table negotiation,
- protocol overhead that erases the measured density advantage,
- API behavior that makes the transport impossible to use in practice,
- evidence that artifact-store/retrieval patterns dominate the intended use cases.

Those are exactly the results the Playground and benchmark infrastructure are meant to make easier to collect.

## Reproduce it

```bash
python -m pip install -e ".[all,dev]"
python benchmarks/benchmark_realworld.py
```

Run the Playground locally:

```bash
python -m pip install -e ".[playground]"
bytetoken playground
```

The repository is MIT licensed and the current release remains explicitly marked as an experimental research preview.

If you test it, the most valuable thing you can send back is a payload or tokenizer that changes the conclusion.

- Playground: `PLAYGROUND_URL`
- GitHub: https://github.com/chandanpandeys/bytetoken
- Issues / failure cases: https://github.com/chandanpandeys/bytetoken/issues
