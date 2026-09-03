---
name: Playground result or failure case
about: Report an unexpected ByteToken Playground result with enough detail to reproduce it
title: "Playground: "
labels: []
assignees: []
---

## What did you test?

Describe the payload type (JSON, logs, source code, binary/Base64, etc.). Do not paste secrets or private data.

## Tokenizer

- [ ] `o200k_base`
- [ ] `cl100k_base`

## Result

Please include the measured Base64, ByteToken Standard, Shared 13-bit, and Direct-ID counts that matter to the report.

## Round-trip verification

Did the Playground show all encode → decode checks as verified? If not, identify the failing transport.

## Expected behavior

What did you expect to happen instead?

## Reproduction payload

Paste a small public/synthetic reproduction payload when possible. If the original data is sensitive, create a minimal synthetic example with the same behavior.

## Environment / link

Include the Playground URL or ByteToken commit SHA you tested.
