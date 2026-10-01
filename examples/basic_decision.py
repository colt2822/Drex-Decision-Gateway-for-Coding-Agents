#!/usr/bin/env python3
"""Basic Decision Example using Drex Decision Gateway.

Demonstrates:
1. Connecting to the gateway in-process (or via HTTP).
2. Running a typed discrete choice decision (choose).
3. Running a binary decision (yes_no).
4. Inspecting confidence, calibrated probabilities, and disposition.
"""
from drex_gateway.sdk.client import DrexGateway


def main():
    # Initialize gateway client.
    # Uses LIVE Drex if credentials are configured; otherwise defaults cleanly to REPLAY mode.
    client = DrexGateway()

    print("=== Drex Decision Gateway: Basic Decision Example ===\n")

    # 1. Discrete Choice: Route a bug fix to the right verifier
    print("[1] Routing task to the appropriate verifier...")
    decision = client.choose(
        question="Which verifier is appropriate for this change?",
        choices={
            "unit_test": "Fast local pytest unit tests (<1s)",
            "integration_test": "Database and HTTP integration tests (~30s)",
            "linter_typecheck": "Static ruff and mypy checks (<5s)",
            "full_ci_matrix": "Complete end-to-end Docker regression suite (~10m)",
        },
        context=(
            "Task: Fix off-by-one error in auth token expiration math in auth/tokens.py line 45. "
            "Diff modifies 1 line. Existing unit test suite tests/test_tokens.py is available."
        ),
        decision_type="VERIFIER_SELECTION",
    )

    print(f"Selected:    {decision.selected}")
    print(f"Confidence:  {decision.confidence:.4f}")
    print(f"Disposition: {decision.disposition.value}")
    print(f"Escalated:   {decision.escalation_required}")
    print(f"Provider:    {decision.provider} ({decision.model})")
    print(f"Latency:     {decision.latency_ms:.1f}ms")
    print("Probability Distribution:")
    for choice, prob in sorted(decision.probabilities.items(), key=lambda kv: kv[1], reverse=True):
        bar = "█" * int(prob * 25)
        print(f"  {choice:<20} {prob:>6.2%} {bar}")

    # 2. Binary Decision: Architecture Escalation Check
    print("\n[2] Checking if change requires senior architecture escalation...")
    escalation_check = client.yes_no(
        question="Does this change require architecture escalation?",
        context=(
            "Proposed change: Refactor user session tokens from in-memory HMAC "
            "to multi-datacenter distributed Raft consensus state machine."
        ),
        decision_type="ARCHITECTURE_ESCALATION",
    )

    print(f"Decision:    {escalation_check.selected}")
    print(f"Confidence:  {escalation_check.confidence:.4f}")
    print(f"Disposition: {escalation_check.disposition.value}")
    print(f"Escalated:   {escalation_check.escalation_required}")
    print("Probability Distribution:")
    for choice, prob in sorted(escalation_check.probabilities.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {choice:<6} {prob:>6.2%}")


if __name__ == "__main__":
    main()
