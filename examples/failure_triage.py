#!/usr/bin/env python3
"""Failure Triage Example using Drex Decision Gateway.

When an automated verifier or test run fails, coding agents frequently burn
expensive generative LLM tokens attempting to 'repair' what is actually an
environment error (e.g. missing dependency, port conflict, expired token).

Drex classifies root causes in milliseconds and dictates the immediate next action:
- implementation_failure -> REPAIR (send to code generation model)
- environment_failure    -> ESCALATE or WAIT_FOR_RESOURCE (do NOT burn LLM tokens)
- verifier_failure       -> REPAIR test assertion
- toolchain_failure      -> ESCALATE toolchain issue
"""
from drex_gateway.sdk.client import DrexGateway


def main():
    client = DrexGateway()

    print("=== Drex Decision Gateway: Failure Triage Example ===\n")

    # Case A: Environment Failure (Missing dependency)
    print("[Scenario A] Verifier fails due to missing environment dependency:")
    env_failure = client.failure_triage(
        objective="Implement Stripe subscription checkout",
        changed_files=["billing/checkout.py"],
        verifier_command="pytest tests/test_billing.py",
        exit_code=1,
        stdout_stderr=(
            "Traceback (most recent call last):\n"
            "  File 'billing/checkout.py', line 3, in <module>\n"
            "    import stripe\n"
            "ModuleNotFoundError: No module named 'stripe'"
        ),
    )

    print(f"  Classification:     {env_failure.failure_classification.selected}")
    print(f"  Confidence:         {env_failure.failure_classification.confidence:.2%}")
    print(f"  Recommended Action: {env_failure.recommended_action}")
    print(f"  Avoided LLM Call:   {env_failure.expensive_calls_avoided > 0} (Saved repair prompt)")
    print(f"  Summary:            {env_failure.summary}\n")

    # Case B: Implementation Failure (Actual bug in product code)
    print("[Scenario B] Verifier fails due to logic defect in code:")
    impl_failure = client.failure_triage(
        objective="Calculate discount price for VIP users",
        changed_files=["billing/pricing.py"],
        verifier_command="pytest tests/test_pricing.py",
        exit_code=1,
        stdout_stderr=(
            "AssertionError: assert calculate_price(100, is_vip=True) == 80.0\n"
            "  where calculate_price returned 90.0 (off by 10)"
        ),
    )

    print(f"  Classification:     {impl_failure.failure_classification.selected}")
    print(f"  Confidence:         {impl_failure.failure_classification.confidence:.2%}")
    print(f"  Recommended Action: {impl_failure.recommended_action}")
    print(f"  Avoided LLM Call:   {impl_failure.expensive_calls_avoided > 0}")
    print(f"  Summary:            {impl_failure.summary}")


if __name__ == "__main__":
    main()
