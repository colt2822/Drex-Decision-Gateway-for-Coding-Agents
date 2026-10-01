"""Drex Failure Triage Workflow: High-accuracy root-cause triage and loop action routing.

Prevents coding agents from burning expensive generative tokens attempting to fix
environment or toolchain failures with code modifications.
"""
from __future__ import annotations

import json
import uuid
from typing import Any
from pydantic import BaseModel

from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.library.schemas import (
    make_failure_classification_question,
    make_next_action_question,
)
from drex_gateway.models import BatchDecisionRequest, DecisionResult


class FailureTriageResult(BaseModel):
    trace_id: str
    failure_classification: DecisionResult
    recommended_action: str  # REPAIR, REPLAN, WAIT_FOR_RESOURCE, ESCALATE, UNKNOWN
    action_decision: DecisionResult
    expensive_calls_avoided: int
    total_drex_latency_ms: float
    summary: str


class FailureTriageWorkflow:
    """Triage verification and tool failures to select the optimal remediation path."""

    def __init__(self, gateway: DrexDecisionGateway):
        self.gateway = gateway

    async def run(
        self,
        objective: str,
        changed_files: list[str],
        verifier_command: str,
        exit_code: int,
        stdout_stderr: str,
        *,
        env_facts: dict[str, Any] | None = None,
        previous_attempt_outcome: str | None = None,
        trace_id: str | None = None,
        parent_decision_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FailureTriageResult:
        trace_id = trace_id or f"failure_{uuid.uuid4().hex[:12]}"

        state_data = {
            "objective": objective,
            "changed_files": changed_files[:20],
            "verifier_command": verifier_command,
            "exit_code": exit_code,
            "error_output": stdout_stderr[:32768],
            "environment_facts": env_facts or {},
            "previous_attempt_outcome": previous_attempt_outcome,
        }
        state = json.dumps(state_data, indent=2)

        questions = {
            "failure_class": make_failure_classification_question(),
            "next_action": make_next_action_question(),
        }

        decision_types = {
            "failure_class": "FAILURE_CLASSIFICATION",
            "next_action": "NEXT_ACTION",
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

        fc_res = batch_res.decisions["failure_class"]
        na_res = batch_res.decisions["next_action"]

        # Map root cause and confidence to definitive remediation action
        # If confidence is low (< 0.60), gateway abstained/escalated
        root_cause = fc_res.selected
        confidence = fc_res.confidence

        if fc_res.disposition.value == "ABSTAIN":
            recommended_action = "ESCALATE"
            avoided = 0
            summary = "Low confidence root-cause classification; escalating to human or supervisor."
        elif root_cause in ("environment_failure", "toolchain_failure"):
            # Coding agents should NOT run code repairs for environment errors!
            recommended_action = "WAIT_FOR_RESOURCE" if "socket" in stdout_stderr or "lock" in stdout_stderr else "ESCALATE"
            avoided = 1  # Avoided wasted coding model repair attempt!
            summary = f"Identified {root_cause} (confidence: {confidence:.2f}). Prevented wasted code repair attempt."
        elif root_cause == "implementation_failure":
            recommended_action = "REPAIR"
            avoided = 0  # Still need model to repair, but saved expensive diagnosis phase
            summary = f"Confirmed implementation defect (confidence: {confidence:.2f}). Proceeding with targeted repair."
        elif root_cause == "context_stale":
            recommended_action = "REPLAN"
            avoided = 1  # Avoided repetitive doomed repair attempts
            summary = "Assumptions stale relative to workspace; replanning from scratch."
        else:
            recommended_action = na_res.selected.upper()
            avoided = 1 if recommended_action != "ESCALATE" else 0
            summary = f"Root cause {root_cause}; action mapped to {recommended_action}."

        return FailureTriageResult(
            trace_id=trace_id,
            failure_classification=fc_res,
            recommended_action=recommended_action,
            action_decision=na_res,
            expensive_calls_avoided=avoided,
            total_drex_latency_ms=batch_res.total_latency_ms,
            summary=summary,
        )
