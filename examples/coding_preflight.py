#!/usr/bin/env python3
"""Coding Agent Preflight Example using Drex Decision Gateway.

Before invoking an expensive generative model (like Claude 3.5 Sonnet or GPT-4o),
the coding agent runs a fast Drex preflight to:
1. Classify task complexity (trivial, standard, large, architecture).
2. Identify the target subsystem (routing).
3. Select the minimal adequate verifier (saving test runtime).
4. Guard against architectural drift (early escalation).
5. Generate a bounded, pre-formatted prompt context block for the LLM.
"""
from drex_gateway.sdk.client import DrexGateway


def main():
    client = DrexGateway()

    task_desc = (
        "Add IP-based rate limiting to the /auth/login endpoint in api/v1/auth.py "
        "to prevent brute-force attacks. Reject exceeding requests with HTTP 429."
    )
    repo_summary = (
        "FastAPI backend. Subsystems include 'auth' (authentication & JWT tokens), "
        "'billing' (Stripe payments), and 'core' (database & config). "
        "Tests located in tests/test_auth.py."
    )

    print("=== Drex Decision Gateway: Coding Agent Preflight ===\n")
    print(f"Task: {task_desc}\n")

    preflight = client.preflight(
        task_description=task_desc,
        repo_summary=repo_summary,
    )

    print(f"Trace ID:          {preflight.trace_id}")
    print(f"Subsystem:         {preflight.subsystem.selected} (conf: {preflight.subsystem.confidence:.2%})")
    print(f"Complexity:        {preflight.complexity.selected} (conf: {preflight.complexity.confidence:.2%})")
    print(f"Recommended Test:  {preflight.verifier.selected} (conf: {preflight.verifier.confidence:.2%})")
    print(f"Arch Escalation:   {preflight.architecture_escalation.selected}")
    print(f"Avoided Calls:     {preflight.expensive_calls_avoided}")
    print(f"Preflight Latency: {preflight.total_drex_latency_ms:.1f}ms\n")

    print("--- INJECTABLE CODEX/CLAUDE SYSTEM PROMPT CONTEXT ---")
    print(preflight.codex_ready_context)
    print("-----------------------------------------------------")


if __name__ == "__main__":
    main()
