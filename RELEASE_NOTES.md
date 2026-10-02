# Release Notes: Drex Decision Gateway

## v0.1.1 — Security and correctness patch

- Includes provider validation, atomic SQLite writes, typed benchmark dispatch and accounting, strict provider-mode validation, and protected SDK/API key handling.
- Restricts browser cross-origin access to explicitly configured exact origins. The API remains unauthenticated and binds to loopback by default.
- Validation: 40 tests passed; replay benchmark evaluated 20 cases with 100% accepted accuracy and 40% coverage.

## v0.1.0

**Drex Decision Gateway v0.1.0** is the first public open-source release of the decision-control and evaluation layer for coding-agent loops powered by Drex.

Drex Decision Gateway inserts fast, typed probabilistic micro-decisions into autonomous agent loops so expensive generative models (such as Claude 3.5 Sonnet, GPT-4o, or Gemini 1.5 Pro) are invoked only where code generation is truly needed.

---

## What's Included in v0.1.0

### Core Decision Primitives
- **Typed Discrete Choice (`choose`)**: Select between 2 and 64 discrete options with full probability distributions.
- **Binary Verification (`yes_no`)**: High-accuracy `noul` decisions for architectural gating and risk boundaries.
- **Ordered Rating (`rate`)**: Bounded numeric or level scoring with probability distributions across ratings.
- **Heterogeneous Batching (`batch_decide`)**: Evaluate multiple questions in a single roundtrip against a shared context buffer.

### Providers & Dual-Mode Architecture
- **Live Drex Provider**: Native integration with `https://drex.nace.ai` supporting `drex-latest`, `drex-v1.5`, and `drex-v1.0`. Features secure API key resolution from environment variables or `chmod 0600` key files.
- **Deterministic Replay Provider**: Complete offline provider requiring zero credentials. Enables local development, deterministic CI pipelines, and unit test suites with zero external dependencies.

### Agent Workflow Schemas
- **Coding Agent Preflight (`preflight`)**: Scopes task complexity, routes to repository subsystems, picks minimal adequate verifiers, and injects bounded context into generative model prompts.
- **Patch Triage (`patch_triage`)**: Multi-point post-generation evaluation assessing patch scope, completeness, risk, and missing tests before expensive verifier or human review passes.
- **Failure Triage (`failure_triage`)**: Instant root-cause diagnosis of failed test runs (implementation defect vs. environment missing dependency vs. assertion bug vs. toolchain crash), preventing agents from burning generative tokens attempting to "fix" environment bugs.

### Policy Engine & Provenance
- **Calibrated Confidence Policies**: Configurable acceptance ($\tau_{\text{accept}} = 0.85$) and escalation ($\tau_{\text{escalate}} = 0.60$) thresholds. Ambiguous decisions escalate rather than failing silently.
- **Closed-Loop Outcome Tracking**: Record verified verifier outcomes (`VERIFIER_PASS`, `VERIFIER_FAIL`, `PR_MERGED`) linked directly to decision IDs to track empirical calibration over time.
- **Durable SQLite Persistence**: High-throughput SQLite storage with Write-Ahead Logging (WAL) and thread concurrency safety. Preserves complete probability distributions, latencies, tokens, and digests.

### Interfaces & Tooling
- **Python SDK (`drex_gateway.sdk`)**: Ergonomic synchronous client supporting both remote HTTP and in-process local execution.
- **HTTP API (FastAPI)**: Fully typed REST endpoints with OpenAPI/Swagger documentation at `/docs` and `/redoc`.
- **Model Context Protocol (MCP)**: JSON-RPC 2.0 tools server enabling direct integration into Cursor, Claude Desktop, and MCP-compatible agent runtimes.
- **Developer CLI (`drex-gateway`)**: Rich CLI commands for `choose`, `stats`, `trace`, `demo`, `benchmark`, and `serve`.
- **Web Dashboard**: Lightweight real-time dashboard for throughput monitoring, live decision inspection, interactive agent demo, trace inspection, and benchmark visualization. Responsive on desktop (1440x900) and mobile (390x844).
- **Observability**: Prometheus metrics endpoint (`/metrics`) tracking decision counts, disposition rates, avoided calls, and latency percentiles.

### Benchmarking & Threshold Simulation
- **Benchmark Runner**: JSONL test suite evaluating accuracy, coverage, and calibration across coding task scenarios.
- **Escalation Simulator**: Simulates economic tradeoffs across a threshold sweep ($0.50$ to $0.95$), quantifying the boundary between agent autonomy and error escape rate.

---

## Verified Demo Measurements

### Live Drex Provider (`drex-latest` ➔ `drex-v1.5`)
- **Drex Micro-Decisions**: 12
- **Accepted by Policy**: 7
- **Escalated for Review**: 4
- **Abstained**: 1
- **Calls Classified as Avoidable by Policy**: 7
- **Drex Server Inference Evaluation (P50)**: ~11.6ms
- **Client WAN End-to-End Latency (P50)**: ~328.4ms
- **Client WAN End-to-End Latency (P95)**: ~376.9ms

### Offline Replay Provider (Deterministic Fixture)
- **Drex Micro-Decisions**: 12
- **Accepted by Policy**: 1
- **Escalated for Review**: 5
- **Abstained**: 6
- **Local Replay Latency (P50)**: ~0.3ms

---

## Known Limitations

1. **Not a Generative Model**: Drex is a System One typed decision engine. It does not write arbitrary code, author PR descriptions, or replace Codex/Claude/Gemini.
2. **WAN Latency**: While Drex server inference takes ~10–15ms, public HTTPS roundtrips from client to server add ~300ms depending on geographic distance and network routing.
3. **Early Developer Release**: v0.1.0 is an initial open-source release. APIs and schema libraries may evolve based on community feedback.

---

## Quick Start

```bash
git clone https://github.com/colt2822/Drex-Decision-Gateway-for-Coding-Agents.git
cd Drex-Decision-Gateway-for-Coding-Agents
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Run demo in offline replay mode (zero credentials required)
drex-gateway --replay demo

# Run with Live Drex
export DREX_API_KEY="nace_sk_..."
drex-gateway demo
```
