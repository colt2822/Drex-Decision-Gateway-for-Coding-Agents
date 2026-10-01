"""Tests for generic decision primitives: choose, yes_no, rate, batch_decide, and decide_with_escalation."""
import pytest
from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.models import BatchDecisionRequest, ChoiceQuestion, Disposition


@pytest.mark.asyncio
async def test_choose_primitive(gateway: DrexDecisionGateway):
    res = await gateway.choose(
        question="Which verifier should run?",
        choices=["pytest", "npm_test", "cargo_test"],
        context="Python FastAPI application test suite in tests/test_auth.py",
        decision_type="VERIFIER_SELECTION",
    )

    assert res.decision_type == "VERIFIER_SELECTION"
    assert res.selected in ["pytest", "npm_test", "cargo_test"]
    assert 0.0 <= res.confidence <= 1.0
    assert "pytest" in res.probabilities
    assert abs(sum(res.probabilities.values()) - 1.0) < 0.02
    assert res.disposition in [Disposition.ACCEPT, Disposition.ESCALATE, Disposition.ABSTAIN]
    assert res.provider == "REPLAY"
    assert res.latency_ms >= 0.0


@pytest.mark.asyncio
async def test_yes_no_primitive(gateway: DrexDecisionGateway):
    res = await gateway.yes_no(
        question="Is architecture escalation required for this single-line typo fix?",
        context="Fix typo in config comment",
        decision_type="ARCHITECTURE_ESCALATION",
    )

    assert res.decision_type == "ARCHITECTURE_ESCALATION"
    assert res.selected in ["YES", "NO"]
    assert "YES" in res.probabilities
    assert "NO" in res.probabilities
    assert abs(res.probabilities["YES"] + res.probabilities["NO"] - 1.0) < 0.01


@pytest.mark.asyncio
async def test_rate_primitive(gateway: DrexDecisionGateway):
    res = await gateway.rate(
        question="Score the blast radius risk of this patch.",
        criteria=["low", "medium", "high"],
        context="Modified 3 lines in auth helper function",
        decision_type="PATCH_RISK",
    )

    assert res.decision_type == "PATCH_RISK"
    assert "0" in res.probabilities or "low" in str(res.probabilities)
    assert 0.0 <= res.confidence <= 1.0


@pytest.mark.asyncio
async def test_batch_decide_primitive(gateway: DrexDecisionGateway):
    q1 = ChoiceQuestion(
        type="choice",
        instructions="Classify complexity",
        criteria={"trivial": None, "complex": None},
    )
    q2 = ChoiceQuestion(
        type="choice",
        instructions="Target area",
        criteria={"auth": None, "billing": None},
    )

    req = BatchDecisionRequest(
        state="Fix login password hash validation in auth/hasher.py",
        questions={"complexity": q1, "subsystem": q2},
    )

    res = await gateway.batch_decide(req)
    assert len(res.decisions) == 2
    assert "complexity" in res.decisions
    assert "subsystem" in res.decisions
    assert res.decisions["subsystem"].selected == "auth"
    assert res.context_digest is not None
