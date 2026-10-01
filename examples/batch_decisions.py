#!/usr/bin/env python3
"""Batch Decisions Example using Drex Decision Gateway.

Demonstrates evaluating multiple heterogeneous typed questions in a single
network roundtrip against a shared context buffer.

Instead of sending 3 separate API calls, we batch:
- Question 1 (choice): Classify task complexity
- Question 2 (choice): Target repository subsystem
- Question 3 (noul): Architecture escalation requirement
"""
from drex_gateway.models import ChoiceQuestion, NoulQuestion
from drex_gateway.sdk.client import DrexGateway


def main():
    client = DrexGateway()

    shared_context = (
        "Task objective: Implement WebAuthn / Passkey registration flow in api/v1/webauthn.py. "
        "Store public key credentials in auth_credentials table. Do not alter existing password auth."
    )

    questions = {
        "complexity": ChoiceQuestion(
            instructions="Classify task complexity.",
            criteria={
                "trivial": "Single-line typo or config fix",
                "standard": "Targeted fix or new feature in 1-3 files",
                "large_context": "Cross-cutting change across many modules",
                "architecture_heavy": "Fundamental protocol or schema overhaul",
            },
        ),
        "subsystem": ChoiceQuestion(
            instructions="Which subsystem owns this task?",
            criteria={
                "auth": "Authentication, tokens, credentials, sessions",
                "billing": "Stripe, invoices, credit card payments",
                "core": "Shared configuration and telemetry",
                "frontend": "Web dashboard UI",
            },
        ),
        "arch_escalation": NoulQuestion(
            instructions="Does this task require senior architecture escalation?",
        ),
    }

    print("=== Drex Decision Gateway: Batch Decisions Example ===\n")
    print(f"Context: {shared_context}\n")
    print("Evaluating 3 questions in a single Drex roundtrip...")

    batch_result = client.batch_decide(
        state=shared_context,
        questions=questions,
        decision_types={
            "complexity": "TASK_COMPLEXITY",
            "subsystem": "REPOSITORY_AREA",
            "arch_escalation": "ARCHITECTURE_ESCALATION",
        },
    )

    print(f"\nTrace ID:             {batch_result.trace_id}")
    print(f"Total Latency:        {batch_result.total_latency_ms:.1f}ms")
    print(f"Server Eval Latency:  {batch_result.provider_latency_ms:.1f}ms" if batch_result.provider_latency_ms else "Server Eval Latency: N/A")
    print(f"All Accepted:         {batch_result.all_accepted}")
    print(f"Any Escalated:        {batch_result.any_escalated}")

    print("\nResults:")
    for q_id, dec in batch_result.decisions.items():
        print(f"\n  [{q_id.upper()}]")
        print(f"    Selected:    {dec.selected}")
        print(f"    Confidence:  {dec.confidence:.2%}")
        print(f"    Disposition: {dec.disposition.value}")
        print(f"    Escalated:   {dec.escalation_required}")
        print(f"    Top Probs:   {dec.probabilities}")


if __name__ == "__main__":
    main()
