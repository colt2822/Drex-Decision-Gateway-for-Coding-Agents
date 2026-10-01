#!/usr/bin/env python3
"""Outcome Feedback Example using Drex Decision Gateway.

Calibration without closed feedback loops is blind.
Drex Decision Gateway links every micro-decision to downstream outcomes:
- VERIFIER_PASS / VERIFIER_FAIL
- REPAIR_SUCCESS / REPAIR_FAIL
- PR_MERGED / PR_REJECTED

This provenance allows tracking calibration over time, verifying whether
confidence scores match real-world success rates, and calculating actual
avoided expensive model calls.
"""
from drex_gateway.sdk.client import DrexGateway


def main():
    client = DrexGateway()

    print("=== Drex Decision Gateway: Outcome Feedback Example ===\n")

    # Step 1: Decision Gateway evaluates if a patch is ready for review
    print("[1] Evaluating patch review readiness with Drex...")
    decision = client.choose(
        question="Is this patch ready for merge or review?",
        choices={
            "ready": "All tests pass, clean diff, documentation updated",
            "needs_repair": "Test failures or unhandled edge cases remain",
            "needs_deep_review": "Security sensitive change requiring senior human review",
        },
        context=(
            "Diff adds validation for webhook payload signature in api/v1/webhooks.py. "
            "Includes 3 new unit tests with mock signatures. All 18 tests in suite pass."
        ),
        decision_type="REVIEW_READINESS",
    )

    print(f"Decision ID: {decision.decision_id}")
    print(f"Selected:    {decision.selected}")
    print(f"Confidence:  {decision.confidence:.2%}")
    print(f"Disposition: {decision.disposition.value}\n")

    # Step 2: Downstream verifier or CI executes and confirms success
    print("[2] CI verifier finishes running test matrix...")
    verifier_passed = True
    ci_runtime_seconds = 14.8

    # Step 3: Record outcome linked directly to the decision ID
    print("[3] Attaching ground-truth outcome back to decision provenance...")
    outcome = client.record_outcome(
        decision_id=decision.decision_id,
        outcome="VERIFIER_PASS" if verifier_passed else "VERIFIER_FAIL",
        success=verifier_passed,
        expensive_model_actually_used=False,
        metadata={
            "ci_runtime_seconds": ci_runtime_seconds,
            "commit_sha": "a1b2c3d4e5f6",
            "verifier": "pytest",
        },
    )

    print(f"Outcome Recorded:   {outcome.outcome}")
    print(f"Success Flag:       {outcome.success}")
    print(f"Recorded At:        {outcome.recorded_at}")
    print(f"Expensive Avoided:  {outcome.expensive_model_actually_used is False}")
    print(f"Attached Metadata:  {outcome.metadata}")


if __name__ == "__main__":
    main()
