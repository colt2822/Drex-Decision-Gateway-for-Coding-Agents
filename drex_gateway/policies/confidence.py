"""First-class confidence policies and threshold evaluation."""
from __future__ import annotations

from typing import Any
from drex_gateway.config import PolicyConfig
from drex_gateway.models import Disposition

# Standard default thresholds for coding-agent decision library
LIBRARY_POLICIES: dict[str, PolicyConfig] = {
    "TASK_COMPLEXITY": PolicyConfig(accept_threshold=0.80, escalation_threshold=0.55),
    "TOOL_SELECTION": PolicyConfig(accept_threshold=0.80, escalation_threshold=0.55),
    "REPOSITORY_AREA": PolicyConfig(accept_threshold=0.80, escalation_threshold=0.55),
    "TEST_SELECTION": PolicyConfig(accept_threshold=0.85, escalation_threshold=0.60),
    "VERIFIER_SELECTION": PolicyConfig(accept_threshold=0.85, escalation_threshold=0.60),
    "FAILURE_CLASSIFICATION": PolicyConfig(accept_threshold=0.85, escalation_threshold=0.60),
    "NEXT_ACTION": PolicyConfig(accept_threshold=0.80, escalation_threshold=0.60),
    "PATCH_RISK": PolicyConfig(accept_threshold=0.80, escalation_threshold=0.60),
    "REVIEW_READINESS": PolicyConfig(accept_threshold=0.90, escalation_threshold=0.75),
    "CI_FAILURE_ATTRIBUTION": PolicyConfig(accept_threshold=0.85, escalation_threshold=0.60),
    "ARCHITECTURE_ESCALATION": PolicyConfig(accept_threshold=0.85, escalation_threshold=0.65),
    "MORE_CONTEXT_REQUIRED": PolicyConfig(accept_threshold=0.80, escalation_threshold=0.60),
    "PATCH_SCOPE_CLASS": PolicyConfig(accept_threshold=0.80, escalation_threshold=0.60),
    "MAINTAINER_RISK": PolicyConfig(accept_threshold=0.85, escalation_threshold=0.65),
}


class PolicyEngine:
    """Evaluates decision confidence against global and per-decision-type policies."""

    def __init__(
        self,
        default_accept_threshold: float = 0.85,
        default_escalation_threshold: float = 0.60,
        custom_policies: dict[str, PolicyConfig] | None = None,
    ):
        self.default_policy = PolicyConfig(
            accept_threshold=default_accept_threshold,
            escalation_threshold=default_escalation_threshold,
        )
        self.policies = dict(LIBRARY_POLICIES)
        if custom_policies:
            self.policies.update(custom_policies)

    def get_policy(self, decision_type: str) -> PolicyConfig:
        return self.policies.get(decision_type, self.default_policy)

    def evaluate(
        self,
        confidence: float,
        decision_type: str = "generic",
        *,
        accept_override: float | None = None,
        escalate_override: float | None = None,
    ) -> tuple[Disposition, bool]:
        """Evaluate confidence against threshold policy.

        Returns (disposition, escalation_required).
        Rule:
          confidence >= accept_threshold => ACCEPT (escalation_required = False)
          escalation_threshold <= confidence < accept_threshold => ESCALATE (escalation_required = True)
          confidence < escalation_threshold => ABSTAIN (escalation_required = False / caller must decide)
        """
        policy = self.get_policy(decision_type)
        accept_thresh = accept_override if accept_override is not None else policy.accept_threshold
        escalate_thresh = escalate_override if escalate_override is not None else policy.escalation_threshold

        if confidence >= accept_thresh:
            return Disposition.ACCEPT, False
        elif confidence >= escalate_thresh:
            return Disposition.ESCALATE, True
        else:
            return Disposition.ABSTAIN, False
