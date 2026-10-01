"""Drex Patch Triage Workflow: Post-generation structured triage and gating.

Evaluates generated diffs, test output, and blast radius before costly review steps.
"""
from __future__ import annotations

import uuid
from typing import Any
from pydantic import BaseModel

from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.library.schemas import (
    make_maintainer_risk_question,
    make_patch_risk_question,
    make_patch_scope_class_question,
    make_review_readiness_question,
)
from drex_gateway.models import BatchDecisionRequest, DecisionResult, NoulQuestion


class PatchTriageResult(BaseModel):
    trace_id: str
    patch_scope: DecisionResult
    implementation_complete: DecisionResult
    patch_risk: DecisionResult
    missing_tests: DecisionResult
    review_readiness: DecisionResult
    maintainer_risk: DecisionResult
    gating_action: str  # e.g. PROCEED_TO_SUBMISSION, ESCALATE_DEEP_REVIEW, RETURN_TO_REPAIR
    expensive_calls_avoided: int
    total_drex_latency_ms: float


class PatchTriageWorkflow:
    """Fast gating and structured triage for candidate code patches."""

    def __init__(self, gateway: DrexDecisionGateway):
        self.gateway = gateway

    async def run(
        self,
        task_objective: str,
        patch_diff: str,
        verifier_evidence: str,
        *,
        repo_context: str = "",
        trace_id: str | None = None,
        parent_decision_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PatchTriageResult:
        trace_id = trace_id or f"triage_{uuid.uuid4().hex[:12]}"

        state = (
            f"=== TASK OBJECTIVE ===\n{task_objective}\n\n"
            f"=== PATCH DIFF ===\n{patch_diff[:32768]}\n\n"
            f"=== VERIFIER OUTPUT ===\n{verifier_evidence[:16384]}\n\n"
            f"=== REPO CONTEXT ===\n{repo_context[:8192]}"
        ).strip()

        questions = {
            "patch_scope": make_patch_scope_class_question(),
            "implementation_complete": NoulQuestion(
                type="noul",
                instructions="Is the patch functionally complete and addressing all core requirements of the objective?",
            ),
            "patch_risk": make_patch_risk_question(),
            "missing_tests": NoulQuestion(
                type="noul",
                instructions="Is this patch missing necessary unit/integration tests for the newly added or modified logic?",
            ),
            "review_readiness": make_review_readiness_question(),
            "maintainer_risk": make_maintainer_risk_question(),
        }

        decision_types = {
            "patch_scope": "PATCH_SCOPE_CLASS",
            "implementation_complete": "IMPLEMENTATION_COMPLETE",
            "patch_risk": "PATCH_RISK",
            "missing_tests": "MISSING_TESTS",
            "review_readiness": "REVIEW_READINESS",
            "maintainer_risk": "MAINTAINER_RISK",
        }

        req = BatchDecisionRequest(
            state=state,
            questions=questions,
            decision_types=decision_types,
            trace_id=trace_id,
            parent_decision_id=parent_decision_id,
            would_have_used_expensive_model=True,
            metadata=metadata or {},
        )

        batch_res = await self.gateway.batch_decide(req)

        scope_res = batch_res.decisions["patch_scope"]
        complete_res = batch_res.decisions["implementation_complete"]
        risk_res = batch_res.decisions["patch_risk"]
        tests_res = batch_res.decisions["missing_tests"]
        readiness_res = batch_res.decisions["review_readiness"]
        maint_res = batch_res.decisions["maintainer_risk"]

        # Synthesize gating disposition
        # If review readiness is accepted as "ready", and no missing tests or excessive risk:
        if (
            readiness_res.selected == "ready"
            and complete_res.selected == "YES"
            and tests_res.selected == "NO"
            and scope_res.selected == "appropriate"
        ):
            gating_action = "PROCEED_TO_SUBMISSION"
            avoided = 1  # Avoided human or expensive large-model preliminary review
        elif readiness_res.selected == "needs_deep_review" or risk_res.confidence >= 0.70:
            gating_action = "ESCALATE_DEEP_REVIEW"
            avoided = 0
        else:
            gating_action = "RETURN_TO_REPAIR"
            avoided = 1  # Blocked premature expensive review attempt

        return PatchTriageResult(
            trace_id=trace_id,
            patch_scope=scope_res,
            implementation_complete=complete_res,
            patch_risk=risk_res,
            missing_tests=tests_res,
            review_readiness=readiness_res,
            maintainer_risk=maint_res,
            gating_action=gating_action,
            expensive_calls_avoided=avoided,
            total_drex_latency_ms=batch_res.total_latency_ms,
        )
