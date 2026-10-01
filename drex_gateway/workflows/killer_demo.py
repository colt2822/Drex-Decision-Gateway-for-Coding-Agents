"""The Killer Demo: End-to-end coding-agent lifecycle simulation.

Executes:
1. Task Intake
2. Drex Preflight (Complexity, Subsystem, Target Verifier, Arch Escalation)
3. Implementation Model (Placeholder/Replay)
4. Candidate Patch Produced
5. Drex Patch Triage (Scope, Completeness, Risk, Missing Tests, Readiness)
6. First Verifier Attempt (Simulated failure: Missing Import / Environment or Implementation)
7. Drex Failure Triage (Root cause diagnosis -> Targeted Repair)
8. Repair Implementation
9. Second Verifier Attempt (PASS)
10. Final Outcome Record

Measures live or replay decisions, latencies, escalation decisions, and expensive calls avoided.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any
from pydantic import BaseModel

from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.models import OutcomeType, TraceSummary
from drex_gateway.workflows.failure_triage import FailureTriageWorkflow
from drex_gateway.workflows.patch_triage import PatchTriageWorkflow
from drex_gateway.workflows.preflight import PreflightWorkflow


class KillerDemoStep(BaseModel):
    step_number: int
    name: str
    phase: str  # PREFLIGHT, IMPLEMENTATION, PATCH_TRIAGE, VERIFICATION, FAILURE_TRIAGE, OUTCOME
    actor: str  # Drex, Agent, Verifier, Gateway
    summary: str
    latency_ms: float
    details: dict[str, Any]


class KillerDemoReport(BaseModel):
    trace_id: str
    provider_mode: str
    model: str
    steps: list[KillerDemoStep]
    total_drex_decisions: int
    accepted_decisions: int
    escalated_decisions: int
    abstained_decisions: int
    expensive_calls_made: int
    expensive_calls_avoided: int
    total_drex_latency_ms: float
    total_pipeline_time_ms: float
    gateway_overhead_p50_ms: float | None = None
    gateway_overhead_p95_ms: float | None = None
    drex_latency_p50_ms: float | None = None
    drex_latency_p95_ms: float | None = None
    final_status: str  # VERIFIER_PASS
    trace_summary: TraceSummary | None = None


class KillerDemoRunner:
    """Runs the end-to-end coding agent loop demonstration."""

    def __init__(self, gateway: DrexDecisionGateway):
        self.gateway = gateway
        self.preflight_wf = PreflightWorkflow(gateway)
        self.patch_triage_wf = PatchTriageWorkflow(gateway)
        self.failure_triage_wf = FailureTriageWorkflow(gateway)

    async def run(
        self,
        task_objective: str | None = None,
        *,
        trace_id: str | None = None,
        simulate_failure_and_repair: bool = True,
    ) -> KillerDemoReport:
        t_global_start = time.perf_counter()
        trace_id = trace_id or f"demo_trace_{uuid.uuid4().hex[:12]}"
        steps: list[KillerDemoStep] = []

        objective = task_objective or (
            "Add rate-limiting middleware to auth login endpoint to prevent brute-force attacks "
            "with configurable sliding window in Redis or local memory fallback."
        )
        repo_context = (
            "Repository: AcmeSaaS / auth-service\n"
            "Languages: Python 3.12, FastAPI, Redis, Pytest\n"
            "Key paths: auth/routes.py, auth/middleware.py, tests/test_rate_limit.py"
        )

        self.gateway.db.record_trace(
            trace_id,
            agent_name="DemoCodingAgent",
            repo="AcmeSaaS/auth-service",
            commit_sha="a8f19c3",
        )

        # -------------------------------------------------------------
        # STEP 1: Task Intake
        # -------------------------------------------------------------
        steps.append(
            KillerDemoStep(
                step_number=1,
                name="Task Received",
                phase="PREFLIGHT",
                actor="Agent",
                summary=f"Ingested objective: {objective[:80]}...",
                latency_ms=0.5,
                details={"objective": objective, "repo": "AcmeSaaS/auth-service"},
            )
        )

        # -------------------------------------------------------------
        # STEP 2: Drex Preflight
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        preflight_res = await self.preflight_wf.run(
            task_description=objective,
            repo_summary=repo_context,
            trace_id=trace_id,
            subsystems={
                "auth": "Authentication, authorization, session tokens, and login routes",
                "core": "Application config, logging, and database base connection",
                "billing": "Stripe billing and subscription logic",
                "storage": "Redis and Postgres client wrappers",
            },
        )
        preflight_time = (time.perf_counter() - t0) * 1000.0

        steps.append(
            KillerDemoStep(
                step_number=2,
                name="Drex Preflight",
                phase="PREFLIGHT",
                actor="Drex",
                summary=(
                    f"Complexity: {preflight_res.complexity.selected.upper()} ({preflight_res.complexity.confidence:.2f}) | "
                    f"Subsystem: {preflight_res.subsystem.selected.upper()} ({preflight_res.subsystem.confidence:.2f}) | "
                    f"Verifier: {preflight_res.verifier.selected.upper()} | "
                    f"Arch Escalation: {preflight_res.architecture_escalation.selected}"
                ),
                latency_ms=round(preflight_time, 2),
                details={
                    "complexity": preflight_res.complexity.selected,
                    "subsystem": preflight_res.subsystem.selected,
                    "verifier": preflight_res.verifier.selected,
                    "architecture_escalation": preflight_res.architecture_escalation.selected,
                    "codex_ready_context": preflight_res.codex_ready_context,
                },
            )
        )

        # -------------------------------------------------------------
        # STEP 3: Implementation Model Execution (Placeholder / Replay)
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        # Simulated generative call using narrowed context
        await asyncio.sleep(0.05)  # simulate fast model call
        impl_latency = (time.perf_counter() - t0) * 1000.0

        candidate_diff = (
            "diff --git a/auth/middleware.py b/auth/middleware.py\n"
            "--- a/auth/middleware.py\n"
            "+++ b/auth/middleware.py\n"
            "@@ -10,6 +10,18 @@\n"
            "+class RateLimitMiddleware(BaseHTTPMiddleware):\n"
            "+    def __init__(self, app, max_attempts: int = 5, window_seconds: int = 60):\n"
            "+        super().__init__(app)\n"
            "+        self.max_attempts = max_attempts\n"
            "+        self.window_seconds = window_seconds\n"
            "+    async def dispatch(self, request, call_next):\n"
            "+        client_ip = request.client.host\n"
            "+        if not check_rate_limit(client_ip, self.max_attempts, self.window_seconds):\n"
            "+            return JSONResponse(status_code=429, content={'detail': 'Too many requests'})\n"
            "+        return await call_next(request)\n"
        )

        steps.append(
            KillerDemoStep(
                step_number=3,
                name="Implementation Model Call",
                phase="IMPLEMENTATION",
                actor="Agent (Codex/Claude)",
                summary="Generative model generated candidate patch based on Drex Preflight bounds.",
                latency_ms=round(impl_latency, 2),
                details={"diff_lines": len(candidate_diff.splitlines()), "changed_files": ["auth/middleware.py"]},
            )
        )

        # -------------------------------------------------------------
        # STEP 4: Drex Patch Triage
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        patch_triage_res = await self.patch_triage_wf.run(
            task_objective=objective,
            patch_diff=candidate_diff,
            verifier_evidence="Pending initial verification run",
            repo_context=repo_context,
            trace_id=trace_id,
        )
        pt_time = (time.perf_counter() - t0) * 1000.0

        steps.append(
            KillerDemoStep(
                step_number=4,
                name="Drex Patch Triage",
                phase="PATCH_TRIAGE",
                actor="Drex",
                summary=(
                    f"Scope: {patch_triage_res.patch_scope.selected.upper()} ({patch_triage_res.patch_scope.confidence:.2f}) | "
                    f"Completeness: {patch_triage_res.implementation_complete.selected} | "
                    f"Risk: {patch_triage_res.patch_risk.selected} | "
                    f"Gating: {patch_triage_res.gating_action}"
                ),
                latency_ms=round(pt_time, 2),
                details={
                    "scope": patch_triage_res.patch_scope.selected,
                    "implementation_complete": patch_triage_res.implementation_complete.selected,
                    "risk": patch_triage_res.patch_risk.selected,
                    "missing_tests": patch_triage_res.missing_tests.selected,
                    "gating_action": patch_triage_res.gating_action,
                },
            )
        )

        last_decision_id = patch_triage_res.review_readiness.decision_id

        # -------------------------------------------------------------
        # STEP 5 & 6: Verification & Failure Triage (Simulate defect repair)
        # -------------------------------------------------------------
        if simulate_failure_and_repair:
            # First verifier attempt fails due to missing helper import
            err_output = (
                "FAILED tests/test_rate_limit.py::test_login_rate_limiting - "
                "NameError: name 'check_rate_limit' is not defined in auth/middleware.py line 17\n"
                "1 failed, 8 passed in 0.42s"
            )
            steps.append(
                KillerDemoStep(
                    step_number=5,
                    name="Verifier Execution (Attempt 1)",
                    phase="VERIFICATION",
                    actor="Verifier",
                    summary="pytest failed with NameError: name 'check_rate_limit' is not defined.",
                    latency_ms=42.0,
                    details={"exit_code": 1, "error": "NameError: name 'check_rate_limit' is not defined"},
                )
            )

            # Drex Failure Triage
            t0 = time.perf_counter()
            ft_res = await self.failure_triage_wf.run(
                objective=objective,
                changed_files=["auth/middleware.py"],
                verifier_command="pytest tests/test_rate_limit.py",
                exit_code=1,
                stdout_stderr=err_output,
                trace_id=trace_id,
            )
            ft_time = (time.perf_counter() - t0) * 1000.0

            steps.append(
                KillerDemoStep(
                    step_number=6,
                    name="Drex Failure Triage",
                    phase="FAILURE_TRIAGE",
                    actor="Drex",
                    summary=(
                        f"Class: {ft_res.failure_classification.selected.upper()} "
                        f"({ft_res.failure_classification.confidence:.2f}) -> Next Action: {ft_res.recommended_action}"
                    ),
                    latency_ms=round(ft_time, 2),
                    details={
                        "root_cause": ft_res.failure_classification.selected,
                        "confidence": ft_res.failure_classification.confidence,
                        "recommended_action": ft_res.recommended_action,
                        "summary": ft_res.summary,
                    },
                )
            )

            # Targeted Repair step
            steps.append(
                KillerDemoStep(
                    step_number=7,
                    name="Targeted Repair",
                    phase="IMPLEMENTATION",
                    actor="Agent",
                    summary="Applied targeted single-line repair: imported check_rate_limit helper.",
                    latency_ms=18.0,
                    details={"repair": "from auth.limiter import check_rate_limit"},
                )
            )

            last_decision_id = ft_res.failure_classification.decision_id

        # -------------------------------------------------------------
        # STEP 8: Final Verifier Execution (PASS)
        # -------------------------------------------------------------
        steps.append(
            KillerDemoStep(
                step_number=8,
                name="Verifier Execution (Final)",
                phase="VERIFICATION",
                actor="Verifier",
                summary="9 passed in 0.38s. All rate-limiting and auth tests succeeded.",
                latency_ms=38.0,
                details={"exit_code": 0, "status": "VERIFIER_PASS"},
            )
        )

        # -------------------------------------------------------------
        # STEP 9: Outcome Feedback Linked to Decision
        # -------------------------------------------------------------
        self.gateway.record_outcome(
            decision_id=last_decision_id,
            outcome=OutcomeType.VERIFIER_PASS.value,
            success=True,
            expensive_model_actually_used=False,
            metadata={"total_steps": len(steps)},
        )

        steps.append(
            KillerDemoStep(
                step_number=9,
                name="Outcome Feedback Recorded",
                phase="OUTCOME",
                actor="Gateway",
                summary="Recorded VERIFIER_PASS durable outcome linked to decision provenance.",
                latency_ms=1.2,
                details={"outcome": "VERIFIER_PASS", "success": True},
            )
        )

        total_pipeline = (time.perf_counter() - t_global_start) * 1000.0

        # Compile trace summary and statistics from storage
        trace_summary = self.gateway.db.get_trace_summary(trace_id)
        stats = self.gateway.db.get_stats()

        tot_drex = trace_summary.total_drex_decisions if trace_summary else 0
        accepted_cnt = trace_summary.accepted_count if trace_summary else 0
        esc_cnt = trace_summary.escalated_count if trace_summary else 0
        abst_cnt = trace_summary.abstained_count if trace_summary else 0
        avoided_cnt = trace_summary.expensive_calls_avoided if trace_summary else 0
        tot_drex_lat = trace_summary.total_latency_ms if trace_summary else 0.0

        return KillerDemoReport(
            trace_id=trace_id,
            provider_mode=self.gateway.provider_mode,
            model=self.gateway.provider.default_model,
            steps=steps,
            total_drex_decisions=tot_drex,
            accepted_decisions=accepted_cnt,
            escalated_decisions=esc_cnt,
            abstained_decisions=abst_cnt,
            expensive_calls_made=2 if simulate_failure_and_repair else 1,
            expensive_calls_avoided=avoided_cnt,
            total_drex_latency_ms=round(tot_drex_lat, 2),
            total_pipeline_time_ms=round(total_pipeline, 2),
            gateway_overhead_p50_ms=stats.get("gateway_overhead_p50_ms"),
            gateway_overhead_p95_ms=stats.get("gateway_overhead_p95_ms"),
            drex_latency_p50_ms=stats.get("provider_latency_p50_ms") or stats.get("latency_p50_ms"),
            drex_latency_p95_ms=stats.get("provider_latency_p95_ms") or stats.get("latency_p95_ms"),
            final_status="VERIFIER_PASS",
            trace_summary=trace_summary,
        )
