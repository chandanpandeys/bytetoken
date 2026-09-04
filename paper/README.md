# Paper sources

This directory contains the publication-oriented ByteToken manuscript.

- [`bytetoken_paper.pdf`](bytetoken_paper.pdf) — stable compiled PDF for reading, sharing, and citation.
- `bytetoken_paper.md` — readable canonical narrative for GitHub.
- `bytetoken_paper.tex` — LaTeX manuscript kept substantively aligned with the Markdown version.
- `references.bib` — bibliography entries that were retained after reference verification.
- `figures/` — historical/research figures; figures are not required to build the current manuscript.

The PDF is a generated publication artifact and is intentionally committed so the repository has a stable public paper link. Other LaTeX build products (`.aux`, `.bbl`, `.blg`, `.log`, `.out`, etc.) remain uncommitted.

## Build locally

From this directory:

```bash
pdflatex -interaction=nonstopmode -halt-on-error bytetoken_paper.tex
bibtex bytetoken_paper
pdflatex -interaction=nonstopmode -halt-on-error bytetoken_paper.tex
pdflatex -interaction=nonstopmode -halt-on-error bytetoken_paper.tex
```

The GitHub paper workflow runs the same build, uploads the result as a workflow artifact, and refreshes the stable `bytetoken_paper.pdf` file on `main` whenever the manuscript sources change.

## Publication policy

Claims in the paper must distinguish:

- deterministic encode/decode correctness from model-mediated copy-through;
- binary compression from binary-to-token representation;
- tested tokenizer configurations from cross-model generalization;
- the fixed-symbol density bound from global information-theoretic optimality; and
- local Direct-ID experiments from hosted-API support.

Do not add launch copy, social-media drafts, private planning notes, or local build logs to this directory.
