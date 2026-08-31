# Publication scope

ByteToken is published as an **experimental research prototype**.

## Supported claims

- Deterministic local encode/decode round-trips for the explicitly tested tokenizer configurations.
- A fixed-width construction over a validated symbol alphabet.
- The elementary bound `floor(log2(|A|))` for the explicitly defined fixed-symbol model.
- Reproducible synthetic developer-payload benchmarks included in the repository.

## Claims not made

- Universal compatibility across LLMs or tokenizer families.
- A global information-theoretic optimum over every possible tokenizer-aware encoding.
- Guaranteed model-mediated copy-through or model understanding of encoded binary data.
- Generic hosted-API support for arbitrary pre-tokenized input IDs.
- Fixed production cost savings or fixed native speedup factors.
- Completed machine-checked verification of concrete tokenizer semantics.

Any future expansion of these claims should be accompanied by versioned evidence and reproducible tests.
