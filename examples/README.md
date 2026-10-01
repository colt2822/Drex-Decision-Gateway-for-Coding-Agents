# Drex Decision Gateway Examples

Executable examples showing how to integrate Drex into coding agents, CI/CD pipelines, and developer workflows.

Each example works out-of-the-box in deterministic offline **REPLAY mode** without credentials, and automatically upgrades to **LIVE Drex** when an API key is provided.

## Available Examples

| Script | Purpose | Key Gateway APIs |
| :--- | :--- | :--- |
| [`basic_decision.py`](basic_decision.py) | Discrete choices & binary verification | `choose()`, `yes_no()` |
| [`coding_preflight.py`](coding_preflight.py) | Task bounding & prompt context injection | `preflight()` |
| [`patch_triage.py`](patch_triage.py) | Diff review, risk scoring & gating | `patch_triage()` |
| [`failure_triage.py`](failure_triage.py) | Root-cause diagnosis & repair avoidance | `failure_triage()` |
| [`batch_decisions.py`](batch_decisions.py) | Multi-question single roundtrip evaluation | `batch_decide()` |
| [`outcome_feedback.py`](outcome_feedback.py) | Attaching ground-truth verifier outcomes | `record_outcome()` |
| [`mcp_agent_demo.py`](mcp_agent_demo.py) | Model Context Protocol integration | JSON-RPC 2.0 tools |

---

## Running the Examples

### 1. Replay Mode (Zero Credentials Required)

```bash
# Force replay mode via environment variable
export DREX_PROVIDER_MODE=REPLAY
python examples/basic_decision.py
python examples/coding_preflight.py
python examples/failure_triage.py
python examples/patch_triage.py
python examples/batch_decisions.py
python examples/outcome_feedback.py
python examples/mcp_agent_demo.py
```

### 2. Live Drex Mode

Provide your API key via environment variable or secure config file:

```bash
export DREX_API_KEY="nace_sk_..."
python examples/basic_decision.py
```

Or via secure key file with `0600` permissions:
```bash
mkdir -p ~/.config/drex
echo -n "nace_sk_..." > ~/.config/drex/api.key
chmod 0600 ~/.config/drex/api.key
python examples/basic_decision.py
```

---

## MCP Server Configuration

To use Drex Decision Gateway with Claude Desktop, Cursor, or any MCP-compatible agent client, configure `claude_desktop_config.json` or your MCP client settings:

```json
{
  "mcpServers": {
    "drex-gateway": {
      "command": "drex-gateway",
      "args": ["serve"],
      "env": {
        "DREX_API_KEY": "nace_sk_...",
        "DREX_MODEL": "drex-latest"
      }
    }
  }
}
```
