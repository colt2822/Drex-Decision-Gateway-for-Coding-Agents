"""Tests for Confidence Policies and threshold evaluation."""
import pytest
from drex_gateway.config import PolicyConfig
from drex_gateway.models import Disposition
from drex_gateway.policies.confidence import PolicyEngine


def test_confidence_policy_thresholds():
    engine = PolicyEngine(default_accept_threshold=0.85, default_escalation_threshold=0.60)

    # 1. High confidence >= 0.85 => ACCEPT
    disp, esc = engine.evaluate(0.92, "generic")
    assert disp == Disposition.ACCEPT
    assert esc is False

    # 2. Borderline confidence 0.60 <= conf < 0.85 => ESCALATE
    disp, esc = engine.evaluate(0.74, "generic")
    assert disp == Disposition.ESCALATE
    assert esc is True

    # 3. Low confidence < 0.60 => ABSTAIN
    disp, esc = engine.evaluate(0.45, "generic")
    assert disp == Disposition.ABSTAIN
    assert esc is False


def test_per_decision_type_policies():
    custom = {
        "CRITICAL_DEPLOY": PolicyConfig(accept_threshold=0.98, escalation_threshold=0.90),
        "LOW_STAKES_LINT": PolicyConfig(accept_threshold=0.65, escalation_threshold=0.40),
    }
    engine = PolicyEngine(custom_policies=custom)

    # 0.70 confidence is ACCEPT for low stakes lint, but ABSTAIN for critical deploy
    disp_lint, esc_lint = engine.evaluate(0.70, "LOW_STAKES_LINT")
    assert disp_lint == Disposition.ACCEPT

    disp_crit, esc_crit = engine.evaluate(0.70, "CRITICAL_DEPLOY")
    assert disp_crit == Disposition.ABSTAIN


def test_policy_overrides():
    engine = PolicyEngine(default_accept_threshold=0.85, default_escalation_threshold=0.60)

    # With accept_override=0.95, a 0.90 confidence escalates instead of accepts
    disp, esc = engine.evaluate(0.90, "generic", accept_override=0.95)
    assert disp == Disposition.ESCALATE
    assert esc is True
