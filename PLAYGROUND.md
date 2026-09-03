# ByteToken Playground

The Playground is an optional web surface for measuring ByteToken transport representations on identical input bytes.

## Run locally

```bash
python -m pip install -e ".[playground]"
bytetoken playground
```

Then open `http://127.0.0.1:8000`.

To bind another interface or port:

```bash
bytetoken playground --host 0.0.0.0 --port 8000
```

## What it measures

For the selected `cl100k_base` or `o200k_base` tokenizer, the Playground compares:

- Base64 text;
- ByteToken Standard 15-bit text;
- the shared-alphabet ByteToken 13-bit text mode;
- Direct-ID as a local token-ID representation; and
- LZMA + Base64 versus LZMA + ByteToken Standard.

The token counts for text transports are computed with the selected tokenizer on the exact transport text. Direct-ID is counted as token IDs rather than by tokenizing its JSON debug/storage wrapper.

## Scope

The Playground intentionally keeps compression and encoding results separate. It does not claim that a model can understand encoded binary payloads, that a hosted API accepts pre-tokenized IDs, or that a generative model will copy an encoded sequence losslessly.

The server limits individual Playground payloads to 256 KiB. The feature is additive and does not change the existing `bytetoken.encode` / `bytetoken.decode` APIs.
