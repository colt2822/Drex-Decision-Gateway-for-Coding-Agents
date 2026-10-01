# Contributing to Drex Decision Gateway

Thank you for your interest in contributing to **Drex Decision Gateway**!

We welcome contributions: bug fixes, benchmark datasets, coding-agent workflow schemas, client libraries, documentation, and performance optimizations.

---

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/colt2822/Drex-Decision-Gateway-for-Coding-Agents.git
   cd Drex-Decision-Gateway-for-Coding-Agents
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies in editable mode:**
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

4. **Verify the test suite (zero credentials required):**
   ```bash
   pytest
   ```

---

## Development Guidelines

- **No Secrets in Code or Diffs:** Never commit live API keys or internal environment paths.
- **Offline Parity:** All core primitives and workflows must work deterministically in `REPLAY` mode so contributors without live Drex credentials can test and build features.
- **Probabilistic Fidelity:** Decisions must preserve full probability distributions across choices rather than collapsing prematurely to arbitrary strings.
- **Calibrated Policies:** Any changes to confidence thresholds or escalation mechanics must include corresponding unit tests and benchmark evaluation.

---

## Running Quality Checks

Before submitting a Pull Request, run:

```bash
# Run unit and integration tests
pytest

# Test replay mode
drex-gateway --replay demo

# Run benchmark evaluation
drex-gateway --replay benchmark

# Test all examples
DREX_PROVIDER_MODE=REPLAY python examples/basic_decision.py
```

---

## Submitting Pull Requests

1. Fork the repo and create your feature branch: `git checkout -b feature/my-feature`.
2. Commit your changes with descriptive, conventional commit messages (`feat: ...`, `fix: ...`, `docs: ...`).
3. Ensure all tests pass.
4. Push your branch and open a Pull Request against `main`.
