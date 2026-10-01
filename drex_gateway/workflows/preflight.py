"""Drex Preflight Workflow: Fast structured preflight before expensive generative model calls.

Narrows context, targets verifiers, classifies complexity, and gates architecture escalation.
"""
from __future__ import annotations

import uuid
from typing import Any
from pydantic import BaseModel, Field

from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.library.schemas import (
    make_architecture_escalation_question,
    make_repository_area_question,
    make_task_complexity_question,
    make_verifier_selection_question,
)
from drex_gateway.models import BatchDecisionRequest, DecisionResult


class PreflightResult(BaseModel):
    trace_id: str
    complexity: DecisionResult
    subsystem: DecisionResult
    verifier: DecisionResult
    architecture_escalation: DecisionResult
    codex_ready_context: str
    expensive_calls_avoided: int = 1
    total_drex_latency_ms: float
    all_accepted: bool


class PreflightWorkflow:
    """Pre-generative task structuring and scoping powered by Drex."""

    def __init__(self, gateway: DrexDecisionGateway):
        self.gateway = gateway

    async def run(
        self,
        task_description: str,
        repo_summary: str = "",
        *,
        subsystems: dict[str, str] | None = None,
        verifiers: dict[str, str] | None = None,
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PreflightResult:
        trace_id = trace_id or f"preflight_{uuid.uuid4().hex[:12]}"
        state = f"Task Description:\n{task_description}\n\nRepository Context:\n{repo_summary}".strip()

        subsystem_map = subsystems or {
            "core": "Core logic, domain models, and shared utilities",
            "api": "HTTP endpoints, route handlers, and request serializers",
            "storage": "Database models, migrations, and persistence adapters",
            "auth": "Authentication, authorization, and permission enforcement",
            "tests": "Test suite, fixtures, and CI automation harness",
        }

        # Pack structured questions into a single batch call for minimum latency
        questions = {
            "task_complexity": make_task_complexity_question(),
            "repository_area": make_repository_area_question(subsystem_map),
            "verifier_selection": make_verifier_selection_question(verifiers),
            "architecture_escalation": make_architecture_escalation_question(),
        }

        decision_types = {
            "task_complexity": "TASK_COMPLEXITY",
            "repository_area": "REPOSITORY_AREA",
            "verifier_selection": "VERIFIER_SELECTION",
            "architecture_escalation": "ARCHITECTURE_ESCALATION",
        }

        req = BatchDecisionRequest(
            state=state,
            questions=questions,
            decision_types=decision_types,
            trace_id=trace_id,
            would_have_used_expensive_model=True,
            metadata=metadata or {},
        )

        batch_res = await self.gateway.batch_decide(req)

        complexity_res = batch_res.decisions["task_complexity"]
        subsystem_res = batch_res.decisions["repository_area"]
        verifier_res = batch_res.decisions["verifier_selection"]
        arch_res = batch_res.decisions["architecture_escalation"]

        # Synthesize a compact, structured prompt for Codex / generative model
        codex_ready_context = (
            f"=== TARGET SUBSYSTEM: {subsystem_res.selected.upper()} (confidence: {subsystem_res.confidence:.2f}) ===\n"
            f"=== COMPLEXITY TIER: {complexity_res.selected.upper()} ===\n"
            f"=== TARGET VERIFIER: {verifier_res.selected.upper()} ===\n"
            f"=== ARCHITECTURE ESCALATION NEEDED: {arch_res.selected} ===\n\n"
            f"TASK OBJECTIVE:\n{task_description}\n\n"
            f"EXECUTION BOUNDS:\n"
            f"1. Confine modifications strictly to the '{subsystem_res.selected}' area.\n"
            f"2. Validate against '{verifier_res.selected}'. Do not perform sprawling codebase edits.\n"
        )

        all_acc = all(d.accepted for d in [complexity_res, subsystem_res, verifier_res, arch_res])

        return PreflightResult(
            trace_id=trace_id,
            complexity=complexity_res,
            subsystem=subsystem_res,
            verifier=verifier_res,
            architecture_escalation=arch_res,
            codex_ready_context=codex_ready_context,
            expensive_calls_avoided=1,
            total_drex_latency_ms=batch_res.total_latency_ms,
            all_accepted=all_acc,
        )
