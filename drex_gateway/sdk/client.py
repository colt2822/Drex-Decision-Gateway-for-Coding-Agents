"""Clean, high-ergonomics Python SDK for Drex Decision Gateway."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from drex_gateway.config import GatewayConfig
from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.models import (
    BatchDecisionRequest,
    BatchDecisionResult,
    DecisionResult,
    OutcomeRecord,
)
from drex_gateway.workflows.failure_triage import FailureTriageResult, FailureTriageWorkflow
from drex_gateway.workflows.patch_triage import PatchTriageResult, PatchTriageWorkflow
from drex_gateway.workflows.preflight import PreflightResult, PreflightWorkflow


class DrexGateway:
    """Client for Drex Decision Gateway with both in-process and remote HTTP modes."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_key: str | None = None,
        provider_mode: str | None = None,
        db_path: str = "drex_gateway.db",
        local_gateway: DrexDecisionGateway | None = None,
    ):
        self.remote_url = base_url.rstrip("/") if base_url else None
        if self.remote_url:
            self._client = httpx.Client(base_url=self.remote_url, timeout=30.0)
            self._local = None
        else:
            if local_gateway is not None:
                self._local = local_gateway
            else:
                cfg = GatewayConfig.from_env()
                if api_key:
                    # Allow programmatic credential injection
                    cfg.force_provider = "LIVE"
                if provider_mode:
                    cfg.force_provider = provider_mode.upper()
                cfg.db_path = db_path
                self._local = DrexDecisionGateway(config=cfg)
            self._client = None

    # -------------------------------------------------------------------------
    # PRIMITIVES (SYNCHRONOUS ERGONOMICS)
    # -------------------------------------------------------------------------

    def choose(
        self,
        question: str,
        choices: list[str] | dict[str, str | None],
        context: str,
        *,
        decision_type: str = "choose",
        trace_id: str | None = None,
        parent_decision_id: str | None = None,
        confidence_threshold: float | None = None,
        escalation_threshold: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionResult:
        """Choose between discrete choices."""
        if self._local:
            return asyncio.run(
                self._local.choose(
                    question=question,
                    choices=choices,
                    context=context,
                    decision_type=decision_type,
                    trace_id=trace_id,
                    parent_decision_id=parent_decision_id,
                    confidence_threshold=confidence_threshold,
                    escalation_threshold=escalation_threshold,
                    metadata=metadata,
                )
            )
        else:
            payload = {
                "question": question,
                "choices": choices if isinstance(choices, list) else list(choices.keys()),
                "context": context,
                "decision_type": decision_type,
                "trace_id": trace_id,
                "parent_decision_id": parent_decision_id,
                "confidence_threshold": confidence_threshold,
                "escalation_threshold": escalation_threshold,
                "metadata": metadata or {},
            }
            resp = self._client.post("/v1/decide/choose", json=payload)
            resp.raise_for_status()
            return DecisionResult(**resp.json())

    def yes_no(
        self,
        question: str,
        context: str,
        *,
        decision_type: str = "yes_no",
        trace_id: str | None = None,
        parent_decision_id: str | None = None,
        confidence_threshold: float | None = None,
        escalation_threshold: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionResult:
        """Binary YES/NO decision."""
        if self._local:
            return asyncio.run(
                self._local.yes_no(
                    question=question,
                    context=context,
                    decision_type=decision_type,
                    trace_id=trace_id,
                    parent_decision_id=parent_decision_id,
                    confidence_threshold=confidence_threshold,
                    escalation_threshold=escalation_threshold,
                    metadata=metadata,
                )
            )
        else:
            payload = {
                "question": question,
                "context": context,
                "decision_type": decision_type,
                "trace_id": trace_id,
                "parent_decision_id": parent_decision_id,
                "confidence_threshold": confidence_threshold,
                "escalation_threshold": escalation_threshold,
                "metadata": metadata or {},
            }
            resp = self._client.post("/v1/decide/yes-no", json=payload)
            resp.raise_for_status()
            return DecisionResult(**resp.json())

    def rate(
        self,
        question: str,
        criteria: list[str],
        context: str,
        *,
        decision_type: str = "rate",
        trace_id: str | None = None,
        parent_decision_id: str | None = None,
        confidence_threshold: float | None = None,
        escalation_threshold: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionResult:
        """Bounded scale rating."""
        if self._local:
            return asyncio.run(
                self._local.rate(
                    question=question,
                    criteria=criteria,
                    context=context,
                    decision_type=decision_type,
                    trace_id=trace_id,
                    parent_decision_id=parent_decision_id,
                    confidence_threshold=confidence_threshold,
                    escalation_threshold=escalation_threshold,
                    metadata=metadata,
                )
            )
        else:
            payload = {
                "question": question,
                "criteria": criteria,
                "context": context,
                "decision_type": decision_type,
                "trace_id": trace_id,
                "parent_decision_id": parent_decision_id,
                "confidence_threshold": confidence_threshold,
                "escalation_threshold": escalation_threshold,
                "metadata": metadata or {},
            }
            resp = self._client.post("/v1/decide/rate", json=payload)
            resp.raise_for_status()
            return DecisionResult(**resp.json())

    def batch_decide(
        self,
        state: str,
        questions: dict[str, AnyQuestion],
        *,
        decision_types: dict[str, str] | None = None,
        trace_id: str | None = None,
        parent_decision_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BatchDecisionResult:
        """Execute multiple structured questions against a shared context in a single roundtrip."""
        req = BatchDecisionRequest(
            state=state,
            questions=questions,
            decision_types=decision_types or {},
            trace_id=trace_id,
            parent_decision_id=parent_decision_id,
            metadata=metadata or {},
        )
        if self._local:
            return asyncio.run(self._local.batch_decide(req))
        else:
            resp = self._client.post("/v1/decide/batch", json=req.model_dump())
            resp.raise_for_status()
            return BatchDecisionResult(**resp.json())

    def record_outcome(
        self,
        decision_id: str,
        outcome: str,
        success: bool,
        *,
        expensive_model_actually_used: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OutcomeRecord:
        """Attach verified outcome feedback to a previously made decision."""
        if self._local:
            return self._local.record_outcome(
                decision_id=decision_id,
                outcome=outcome,
                success=success,
                expensive_model_actually_used=expensive_model_actually_used,
                metadata=metadata,
            )
        else:
            payload = {
                "outcome": outcome,
                "success": success,
                "expensive_model_actually_used": expensive_model_actually_used,
                "metadata": metadata or {},
            }
            resp = self._client.post(f"/v1/decisions/{decision_id}/outcome", json=payload)
            resp.raise_for_status()
            return OutcomeRecord(**resp.json())

    # -------------------------------------------------------------------------
    # HIGH-LEVEL CODING AGENT WORKFLOW HELPERS
    # -------------------------------------------------------------------------

    def preflight(
        self,
        task_description: str,
        repo_summary: str = "",
        *,
        subsystems: dict[str, str] | None = None,
        trace_id: str | None = None,
    ) -> PreflightResult:
        """Drex Preflight before generative coding calls."""
        if self._local:
            wf = PreflightWorkflow(self._local)
            return asyncio.run(
                wf.run(
                    task_description=task_description,
                    repo_summary=repo_summary,
                    subsystems=subsystems,
                    trace_id=trace_id,
                )
            )
        else:
            payload = {
                "task_description": task_description,
                "repo_summary": repo_summary,
                "subsystems": subsystems,
                "trace_id": trace_id,
            }
            resp = self._client.post("/v1/coding/preflight", json=payload)
            resp.raise_for_status()
            return PreflightResult(**resp.json())

    def patch_triage(
        self,
        task_objective: str,
        patch_diff: str,
        verifier_evidence: str,
        *,
        repo_context: str = "",
        trace_id: str | None = None,
    ) -> PatchTriageResult:
        """Drex Patch Triage after generative coding calls."""
        if self._local:
            wf = PatchTriageWorkflow(self._local)
            return asyncio.run(
                wf.run(
                    task_objective=task_objective,
                    patch_diff=patch_diff,
                    verifier_evidence=verifier_evidence,
                    repo_context=repo_context,
                    trace_id=trace_id,
                )
            )
        else:
            payload = {
                "task_objective": task_objective,
                "patch_diff": patch_diff,
                "verifier_evidence": verifier_evidence,
                "repo_context": repo_context,
                "trace_id": trace_id,
            }
            resp = self._client.post("/v1/coding/patch-triage", json=payload)
            resp.raise_for_status()
            return PatchTriageResult(**resp.json())

    def failure_triage(
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
    ) -> FailureTriageResult:
        """Drex Failure Triage for root cause diagnosis and optimal action routing."""
        if self._local:
            wf = FailureTriageWorkflow(self._local)
            return asyncio.run(
                wf.run(
                    objective=objective,
                    changed_files=changed_files,
                    verifier_command=verifier_command,
                    exit_code=exit_code,
                    stdout_stderr=stdout_stderr,
                    env_facts=env_facts,
                    previous_attempt_outcome=previous_attempt_outcome,
                    trace_id=trace_id,
                )
            )
        else:
            payload = {
                "objective": objective,
                "changed_files": changed_files,
                "verifier_command": verifier_command,
                "exit_code": exit_code,
                "stdout_stderr": stdout_stderr,
                "env_facts": env_facts,
                "previous_attempt_outcome": previous_attempt_outcome,
                "trace_id": trace_id,
            }
            resp = self._client.post("/v1/coding/failure-triage", json=payload)
            resp.raise_for_status()
            return FailureTriageResult(**resp.json())
