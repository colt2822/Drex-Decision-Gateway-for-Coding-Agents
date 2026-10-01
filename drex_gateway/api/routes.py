"""API routes and endpoint implementations for Drex Decision Gateway."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.metrics.collector import MetricsCollector
from drex_gateway.metrics.prometheus import generate_prometheus_text
from drex_gateway.models import (
    BatchDecisionRequest,
    BatchDecisionResult,
    DecisionResult,
    OutcomeFeedbackRequest,
    OutcomeRecord,
    TraceSummary,
)
from drex_gateway.workflows.failure_triage import FailureTriageResult, FailureTriageWorkflow
from drex_gateway.workflows.killer_demo import KillerDemoReport, KillerDemoRunner
from drex_gateway.workflows.patch_triage import PatchTriageResult, PatchTriageWorkflow
from drex_gateway.workflows.preflight import PreflightResult, PreflightWorkflow


class ChooseApiRequest(BaseModel):
    question: str
    choices: list[str] | dict[str, str | None]
    context: str
    decision_type: str = "choose"
    trace_id: str | None = None
    parent_decision_id: str | None = None
    confidence_threshold: float | None = None
    escalation_threshold: float | None = None
    would_have_used_expensive_model: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class YesNoApiRequest(BaseModel):
    question: str
    context: str
    decision_type: str = "yes_no"
    trace_id: str | None = None
    parent_decision_id: str | None = None
    confidence_threshold: float | None = None
    escalation_threshold: float | None = None
    would_have_used_expensive_model: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class RateApiRequest(BaseModel):
    question: str
    criteria: list[str]
    context: str
    decision_type: str = "rate"
    trace_id: str | None = None
    parent_decision_id: str | None = None
    confidence_threshold: float | None = None
    escalation_threshold: float | None = None
    would_have_used_expensive_model: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class PreflightApiRequest(BaseModel):
    task_description: str
    repo_summary: str = ""
    subsystems: dict[str, str] | None = None
    verifiers: dict[str, str] | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PatchTriageApiRequest(BaseModel):
    task_objective: str
    patch_diff: str
    verifier_evidence: str
    repo_context: str = ""
    trace_id: str | None = None
    parent_decision_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FailureTriageApiRequest(BaseModel):
    objective: str
    changed_files: list[str]
    verifier_command: str
    exit_code: int
    stdout_stderr: str
    env_facts: dict[str, Any] | None = None
    previous_attempt_outcome: str | None = None
    trace_id: str | None = None
    parent_decision_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DemoApiRequest(BaseModel):
    task_objective: str | None = None
    simulate_failure_and_repair: bool = True


def create_router(gateway: DrexDecisionGateway) -> APIRouter:
    router = APIRouter()
    metrics_collector = MetricsCollector(gateway.db)
    preflight_wf = PreflightWorkflow(gateway)
    patch_triage_wf = PatchTriageWorkflow(gateway)
    failure_triage_wf = FailureTriageWorkflow(gateway)
    demo_runner = KillerDemoRunner(gateway)

    # -------------------------------------------------------------
    # HEALTH & SYSTEM STATUS
    # -------------------------------------------------------------
    @router.get("/healthz")
    async def healthz():
        return {
            "status": "healthy",
            "provider_mode": gateway.provider_mode,
            "provider_name": gateway.provider.provider_name,
            "model": gateway.provider.default_model,
        }

    @router.get("/readyz")
    async def readyz():
        return {
            "ready": True,
            "database": "connected",
            "provider": gateway.provider.provider_name,
        }

    @router.get("/metrics")
    async def metrics():
        text = generate_prometheus_text(metrics_collector)
        return Response(content=text, media_type="text/plain; version=0.0.4; charset=utf-8")

    @router.get("/v1/providers")
    async def list_providers():
        return {
            "active_provider": gateway.provider.provider_name,
            "active_mode": gateway.provider_mode,
            "available_providers": ["Drex", "REPLAY"],
            "live_credentials_available": gateway.config.has_live_credentials(),
        }

    @router.get("/v1/models")
    async def list_models():
        try:
            models = await gateway.provider.list_models()
        except Exception as exc:
            models = [{"name": gateway.provider.default_model, "error": str(exc)}]
        return {
            "provider": gateway.provider.provider_name,
            "default_model": gateway.provider.default_model,
            "models": models,
        }

    @router.get("/v1/stats")
    async def get_stats():
        return metrics_collector.collect()

    # -------------------------------------------------------------
    # CORE PRIMITIVES
    # -------------------------------------------------------------
    @router.post("/v1/decide/choose", response_model=DecisionResult)
    async def decide_choose(payload: ChooseApiRequest):
        return await gateway.choose(
            question=payload.question,
            choices=payload.choices,
            context=payload.context,
            decision_type=payload.decision_type,
            trace_id=payload.trace_id,
            parent_decision_id=payload.parent_decision_id,
            confidence_threshold=payload.confidence_threshold,
            escalation_threshold=payload.escalation_threshold,
            would_have_used_expensive_model=payload.would_have_used_expensive_model,
            metadata=payload.metadata,
        )

    @router.post("/v1/decide/yes-no", response_model=DecisionResult)
    async def decide_yes_no(payload: YesNoApiRequest):
        return await gateway.yes_no(
            question=payload.question,
            context=payload.context,
            decision_type=payload.decision_type,
            trace_id=payload.trace_id,
            parent_decision_id=payload.parent_decision_id,
            confidence_threshold=payload.confidence_threshold,
            escalation_threshold=payload.escalation_threshold,
            would_have_used_expensive_model=payload.would_have_used_expensive_model,
            metadata=payload.metadata,
        )

    @router.post("/v1/decide/rate", response_model=DecisionResult)
    async def decide_rate(payload: RateApiRequest):
        return await gateway.rate(
            question=payload.question,
            criteria=payload.criteria,
            context=payload.context,
            decision_type=payload.decision_type,
            trace_id=payload.trace_id,
            parent_decision_id=payload.parent_decision_id,
            confidence_threshold=payload.confidence_threshold,
            escalation_threshold=payload.escalation_threshold,
            would_have_used_expensive_model=payload.would_have_used_expensive_model,
            metadata=payload.metadata,
        )

    @router.post("/v1/decide/batch", response_model=BatchDecisionResult)
    async def decide_batch(payload: BatchDecisionRequest):
        return await gateway.batch_decide(payload)

    # -------------------------------------------------------------
    # CODING WORKFLOWS
    # -------------------------------------------------------------
    @router.post("/v1/coding/preflight", response_model=PreflightResult)
    async def coding_preflight(payload: PreflightApiRequest):
        return await preflight_wf.run(
            task_description=payload.task_description,
            repo_summary=payload.repo_summary,
            subsystems=payload.subsystems,
            verifiers=payload.verifiers,
            trace_id=payload.trace_id,
            metadata=payload.metadata,
        )

    @router.post("/v1/coding/patch-triage", response_model=PatchTriageResult)
    async def coding_patch_triage(payload: PatchTriageApiRequest):
        return await patch_triage_wf.run(
            task_objective=payload.task_objective,
            patch_diff=payload.patch_diff,
            verifier_evidence=payload.verifier_evidence,
            repo_context=payload.repo_context,
            trace_id=payload.trace_id,
            parent_decision_id=payload.parent_decision_id,
            metadata=payload.metadata,
        )

    @router.post("/v1/coding/failure-triage", response_model=FailureTriageResult)
    async def coding_failure_triage(payload: FailureTriageApiRequest):
        return await failure_triage_wf.run(
            objective=payload.objective,
            changed_files=payload.changed_files,
            verifier_command=payload.verifier_command,
            exit_code=payload.exit_code,
            stdout_stderr=payload.stdout_stderr,
            env_facts=payload.env_facts,
            previous_attempt_outcome=payload.previous_attempt_outcome,
            trace_id=payload.trace_id,
            parent_decision_id=payload.parent_decision_id,
            metadata=payload.metadata,
        )

    @router.post("/v1/demo/run", response_model=KillerDemoReport)
    async def run_killer_demo(payload: DemoApiRequest):
        return await demo_runner.run(
            task_objective=payload.task_objective,
            simulate_failure_and_repair=payload.simulate_failure_and_repair,
        )

    # -------------------------------------------------------------
    # DECISIONS & PROVENANCE
    # -------------------------------------------------------------
    @router.get("/v1/decisions", response_model=list[DecisionResult])
    async def list_decisions(
        limit: int = Query(default=50, le=200),
        offset: int = Query(default=0, ge=0),
        decision_type: str | None = None,
        disposition: str | None = None,
    ):
        return gateway.db.list_decisions(
            limit=limit,
            offset=offset,
            decision_type=decision_type,
            disposition=disposition,
        )

    @router.get("/v1/decisions/{decision_id}", response_model=DecisionResult)
    async def get_decision(decision_id: str):
        dec = gateway.db.get_decision(decision_id)
        if not dec:
            raise HTTPException(status_code=404, detail="Decision not found")
        return dec

    @router.post("/v1/decisions/{decision_id}/outcome", response_model=OutcomeRecord)
    async def record_decision_outcome(decision_id: str, payload: OutcomeFeedbackRequest):
        dec = gateway.db.get_decision(decision_id)
        if not dec:
            raise HTTPException(status_code=404, detail="Decision not found")
        return gateway.record_outcome(
            decision_id=decision_id,
            outcome=payload.outcome,
            success=payload.success,
            expensive_model_actually_used=payload.expensive_model_actually_used,
            metadata=payload.metadata,
        )

    @router.get("/v1/traces/{trace_id}", response_model=TraceSummary)
    async def get_trace(trace_id: str):
        summary = gateway.db.get_trace_summary(trace_id)
        if not summary:
            raise HTTPException(status_code=404, detail="Trace not found")
        return summary

    @router.get("/v1/benchmarks")
    async def list_benchmarks():
        return gateway.db.list_benchmark_runs()

    return router
