# Contributing to ByteToken

Thank you for your interest in contributing to **ByteToken**! We welcome contributions to both the Python engine and the TypeScript/JavaScript SDK.

---

## Development Setup

### 1. Python Environment

```bash
git clone https://github.com/chandanpandeys/bytetoken.git
cd bytetoken
pip install -e .[dev,all]
```

Run tests:
```bash
python -m pytest tests.py -v
```

Run real-world benchmarks:
```bash
python benchmarks/benchmark_realworld.py
```

### 2. TypeScript / Node.js Environment

```bash
cd js
node --experimental-strip-types tests/index.test.ts
```

---

## Code Style & Standards

- **Python**: Follow PEP 8. Type hints are encouraged across public APIs.
- **Rust Backend**: All performance-critical native extensions live in `rust_core/`. Use `cargo fmt` and `cargo clippy`.
- **TypeScript**: Strict TypeScript in `js/src/`. Add or update tests for encoding/decoding changes.

---

## Pull Request Guidelines

1. Fork the repo and create your branch from `main`.
2. Ensure all tests pass locally before submitting.
3. If you add new tokenizer support or encoding features, include unit tests and update benchmark tables if applicable.

---

## License

By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
