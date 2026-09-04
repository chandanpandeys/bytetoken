# ByteToken Playground

The Playground is an optional web surface for measuring ByteToken transport representations on identical input bytes.

**Public deployment:** https://bytetoken-playground-kcwc.vercel.app

## Verify it in the browser

A quick reproducible walkthrough:

1. Open the public Playground.
2. Select the **JSON** example.
3. Keep `o200k_base` selected.
4. Click **Analyze + verify transport**.
5. Compare Base64 with ByteToken Standard 15-bit using the measured token counts.
6. Confirm the lossless round-trip badges.
7. Scroll to the compression section and treat LZMA results as a separate layer from the ByteToken representation.

The exact result depends on the payload, tokenizer, and tokenizer-library version. The Playground is intended to make those variables visible rather than imply a universal savings percentage.

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

Every displayed transport is decoded after measurement and compared byte-for-byte with the original input. The UI surfaces an explicit lossless round-trip result and decode latency rather than assuming reversibility from the encoder implementation.

## Public deployment

The canonical public Playground is https://bytetoken-playground-kcwc.vercel.app.

The repository includes a Vercel FastAPI entrypoint in `pyproject.toml` and a root `requirements.txt` that installs the optional `playground` dependency set. A Vercel project imported from this repository can therefore serve the same FastAPI app and packaged static UI without changing the core ByteToken dependency set for library users.

The Vercel deployment entrypoint is the physical repository module:

```text
playground.app:app
```

The installed CLI can still import the packaged module as `bytetoken.playground.app` through the setuptools package mapping.

[Deploy your own Playground to Vercel](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fchandanpandeys%2Fbytetoken&repository-name=bytetoken-playground) after the Playground changes are on `main`.

The application itself has no database or persistent user state. Do not paste secrets or private payloads into a public deployment.

## Feedback

The Playground links to `.github/ISSUE_TEMPLATE/playground-report.md` so unexpected token counts or round-trip failures can be reported with the tokenizer, measured values, commit/deployment, and a minimal public reproduction payload.

## Scope

The Playground intentionally keeps compression and encoding results separate. It does not claim that a model can understand encoded binary payloads, that a hosted API accepts pre-tokenized IDs, or that a generative model will copy an encoded sequence losslessly.

The server limits individual Playground payloads to 256 KiB. The feature is additive and does not change the existing `bytetoken.encode` / `bytetoken.decode` APIs.
