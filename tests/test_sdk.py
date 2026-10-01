"""Tests for the Python SDK client."""
import pytest
from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.sdk.client import DrexGateway


def test_sdk_in_process_methods(gateway: DrexDecisionGateway):
    client = DrexGateway(local_gateway=gateway)

    # 1. choose
    dec = client.choose(
        question="Which verifier to run?",
        choices=["pytest", "npm_test"],
        context="Python FastAPI application",
    )
    assert dec.selected in ["pytest", "npm_test"]

    # 2. yes_no
    yn = client.yes_no(
        question="Is architecture escalation needed?",
        context="Typo fix in docstring",
    )
    assert yn.selected in ["YES", "NO"]

    # 3. preflight
    pf = client.preflight(task_description="Fix bug in auth service")
    assert pf.codex_ready_context is not None

    # 4. record outcome
    outcome = client.record_outcome(
        decision_id=dec.decision_id,
        outcome="VERIFIER_PASS",
        success=True,
    )
    assert outcome.outcome == "VERIFIER_PASS"
