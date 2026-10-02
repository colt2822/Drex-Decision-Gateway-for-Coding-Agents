"""Drex Decision Gateway Core Engine.

Coordinates providers, persistence, confidence policies, and provenance tracking.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from typing import Any

from drex_gateway.config import GatewayConfig
from drex_gateway.errors import GatewayError
from drex_gateway.models import (
    AnyQuestion,
    BatchDecisionRequest,
    BatchDecisionResult,
    ChoiceQuestion,
    DecisionRequest,
    DecisionResult,
    Disposition,
    NoulQuestion,
    OutcomeRecord,
    ScoreQuestion,
    compute_digest,
)
from drex_gateway.policies.confidence import PolicyEngine
from drex_gateway.providers.base import BaseDecisionProvider
from drex_gateway.providers.live import DrexProvider
from drex_gateway.providers.replay import ReplayProvider
from drex_gateway.storage.db import Database


class DrexDecisionGateway:
    """The central decision engine for coding agents."""

    def __init__(
        self,
        config: GatewayConfig | None = None,
        provider: BaseDecisionProvider | None = None,
        db: Database | None = None,
        policy_engine: PolicyEngine | None = None,
    ):
        self.config = config or GatewayConfig.from_env()
        self.db = db or Database(self.config.db_path)
        self.policy_engine = policy_engine or PolicyEngine(
            default_accept_threshold=self.config.default_policy.accept_threshold,
            default_escalation_threshold=self.config.default_policy.escalation_threshold,
            custom_policies=self.config.decision_policies,
        )

        if provider is not None:
            self.provider = provider
        else:
            self.provider = self._select_provider()

    def _select_provider(self) -> BaseDecisionProvider:
        force = (self.config.force_provider or "").upper()
        if force == "REPLAY":
            return ReplayProvider()
        if force == "LIVE":
            return DrexProvider(self.config)

        if self.config.has_live_credentials():
            return DrexProvider(self.config)
        return ReplayProvider()

    @property
    def provider_mode(self) -> str:
        return "LIVE" if isinstance(self.provider, DrexProvider) else "REPLAY"

    # =========================================================================
    # CORE DECISION PRIMITIVES
    # =========================================================================

    async def choose(
        self,
        question: str,
        choices: list[str] | dict[str, str | None],
        context: str,
        *,
        question_id: str = "choose_primary",
        decision_type: str = "choose",
        trace_id: str | None = None,
        parent_decision_id: str | None = None,
        confidence_threshold: float | None = None,
        escalation_threshold: float | None = None,
        would_have_used_expensive_model: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionResult:
        """Structured choice primitive over 2 to 64 discrete options."""
        criteria: dict[str, str | None]
        if isinstance(choices, list):
            criteria = {c.lower().replace(" ", "_"): None for c in choices}
        else:
            criteria = {k.lower().replace(" ", "_"): v for k, v in choices.items()}

        q = ChoiceQuestion(type="choice", instructions=question, criteria=criteria)
        req = DecisionRequest(
            state=context,
            question_id=question_id,
            question=q,
            decision_type=decision_type,
            trace_id=trace_id,
            parent_decision_id=parent_decision_id,
            confidence_threshold=confidence_threshold,
            escalation_threshold=escalation_threshold,
            would_have_used_expensive_model=would_have_used_expensive_model,
            metadata=metadata or {},
        )
        return await self.decide(req)

    async def yes_no(
        self,
        question: str,
        context: str,
        *,
        question_id: str = "yes_no_primary",
        decision_type: str = "yes_no",
        trace_id: str | None = None,
        parent_decision_id: str | None = None,
        confidence_threshold: float | None = None,
        escalation_threshold: float | None = None,
        would_have_used_expensive_model: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionResult:
        """Binary YES/NO decision primitive returning calibrated affirmative probability."""
        q = NoulQuestion(type="noul", instructions=question)
        req = DecisionRequest(
            state=context,
            question_id=question_id,
            question=q,
            decision_type=decision_type,
            trace_id=trace_id,
            parent_decision_id=parent_decision_id,
            confidence_threshold=confidence_threshold,
            escalation_threshold=escalation_threshold,
            would_have_used_expensive_model=would_have_used_expensive_model,
            metadata=metadata or {},
        )
        return await self.decide(req)

    async def rate(
        self,
        question: str,
        criteria: list[str],
        context: str,
        *,
        question_id: str = "rate_primary",
        decision_type: str = "rate",
        trace_id: str | None = None,
        parent_decision_id: str | None = None,
        confidence_threshold: float | None = None,
        escalation_threshold: float | None = None,
        would_have_used_expensive_model: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionResult:
        """Bounded rating/scale primitive over 1 to 64 ordered levels."""
        q = ScoreQuestion(type="score", instructions=question, criteria=criteria)
        req = DecisionRequest(
            state=context,
            question_id=question_id,
            question=q,
            decision_type=decision_type,
            trace_id=trace_id,
            parent_decision_id=parent_decision_id,
            confidence_threshold=confidence_threshold,
            escalation_threshold=escalation_threshold,
            would_have_used_expensive_model=would_have_used_expensive_model,
            metadata=metadata or {},
        )
        return await self.decide(req)

    async def decide_with_escalation(
        self,
        state: str,
        question: AnyQuestion,
        *,
        question_id: str = "decide_escalate",
        decision_type: str = "generic",
        trace_id: str | None = None,
        parent_decision_id: str | None = None,
        confidence_threshold: float | None = None,
        escalation_threshold: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionResult:
        """Decide against context and explicitly return ACCEPT, ESCALATE, or ABSTAIN disposition."""
        req = DecisionRequest(
            state=state,
            question_id=question_id,
            question=question,
            decision_type=decision_type,
            trace_id=trace_id,
            parent_decision_id=parent_decision_id,
            confidence_threshold=confidence_threshold,
            escalation_threshold=escalation_threshold,
            metadata=metadata or {},
        )
        return await self.decide(req)

    async def batch_decide(
        self,
        request: BatchDecisionRequest,
    ) -> BatchDecisionResult:
        """Execute multiple structured decisions against a shared context buffer."""
        trace_id = request.trace_id or str(uuid.uuid4())
        context_digest = compute_digest(request.state)
        questions = request.questions

        t0 = time.perf_counter()
        resp = await self.provider.decide(request.state, questions, trace_id=trace_id)
        self.provider.validate_response(questions, {"answers": resp.answers})
        total_time_ms = (time.perf_counter() - t0) * 1000.0

        prov_lat = resp.provider_latency_ms
        overhead_ms = max(0.0, total_time_ms - (prov_lat or 0.0))

        decisions: dict[str, DecisionResult] = {}
        for q_id, q in questions.items():
            ans = resp.answers[q_id]
            q_type = q.type if hasattr(q, "type") else q["type"]
            dec_type = request.decision_types.get(q_id, q_id)

            selected: Any
            confidence: float
            probabilities: dict[str, float]

            if q_type == "noul":
                noul_p = float(ans["noul"])
                probabilities = {"YES": round(noul_p, 4), "NO": round(1.0 - noul_p, 4)}
                selected = "YES" if noul_p >= 0.5 else "NO"
                confidence = max(noul_p, 1.0 - noul_p)
            elif q_type == "choice":
                selected = ans["choice"]
                probabilities = ans["probabilities"]
                confidence = float(ans.get("confidence", probabilities.get(selected, 0.0)))
            elif q_type == "score":
                selected = ans.get("score")
                probabilities = ans.get("probabilities", {})
                confidence = float(ans.get("confidence", max(probabilities.values()) if probabilities else 0.5))
            else:
                selected = str(ans)
                probabilities = {}
                confidence = 0.5

            disposition, esc_req = self.policy_engine.evaluate(
                confidence,
                dec_type,
            )

            dec_id = str(uuid.uuid4())
            res = DecisionResult(
                decision_id=dec_id,
                trace_id=trace_id,
                parent_decision_id=request.parent_decision_id,
                decision_type=dec_type,
                question_id=q_id,
                selected=selected,
                confidence=round(confidence, 4),
                probabilities=probabilities,
                disposition=disposition,
                escalation_required=esc_req,
                model=resp.model,
                provider=resp.provider_name,
                latency_ms=round(total_time_ms, 2),
                provider_latency_ms=round(prov_lat, 2) if prov_lat is not None else None,
                gateway_overhead_ms=round(overhead_ms, 2),
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                context_digest=context_digest,
                would_have_used_expensive_model=request.would_have_used_expensive_model,
                metadata=request.metadata,
            )
            decisions[q_id] = res

        self.db.record_decisions(list(decisions.values()), state_text=request.state)

        return BatchDecisionResult(
            trace_id=trace_id,
            context_digest=context_digest,
            decisions=decisions,
            total_latency_ms=round(total_time_ms, 2),
            provider_latency_ms=round(prov_lat, 2) if prov_lat is not None else None,
            gateway_overhead_ms=round(overhead_ms, 2),
        )

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        """Internal dispatch for a single DecisionRequest."""
        trace_id = request.trace_id or str(uuid.uuid4())
        context_digest = compute_digest(request.state)
        questions = {request.question_id: request.question}

        t0 = time.perf_counter()
        resp = await self.provider.decide(request.state, questions, trace_id=trace_id)
        self.provider.validate_response(questions, {"answers": resp.answers})
        total_time_ms = (time.perf_counter() - t0) * 1000.0

        prov_lat = resp.provider_latency_ms
        overhead_ms = max(0.0, total_time_ms - (prov_lat or 0.0))

        ans = resp.answers[request.question_id]
        q_type = request.question.type if hasattr(request.question, "type") else request.question["type"]

        selected: Any
        confidence: float
        probabilities: dict[str, float]

        if q_type == "noul":
            noul_p = float(ans["noul"])
            probabilities = {"YES": round(noul_p, 4), "NO": round(1.0 - noul_p, 4)}
            selected = "YES" if noul_p >= 0.5 else "NO"
            confidence = max(noul_p, 1.0 - noul_p)
        elif q_type == "choice":
            selected = ans["choice"]
            probabilities = ans["probabilities"]
            confidence = float(ans.get("confidence", probabilities.get(selected, 0.0)))
        elif q_type == "score":
            selected = ans.get("score")
            probabilities = ans.get("probabilities", {})
            confidence = float(ans.get("confidence", max(probabilities.values()) if probabilities else 0.5))
        else:
            selected = str(ans)
            probabilities = {}
            confidence = 0.5

        disposition, esc_req = self.policy_engine.evaluate(
            confidence,
            request.decision_type,
            accept_override=request.confidence_threshold,
            escalate_override=request.escalation_threshold,
        )

        dec_id = str(uuid.uuid4())
        res = DecisionResult(
            decision_id=dec_id,
            trace_id=trace_id,
            parent_decision_id=request.parent_decision_id,
            decision_type=request.decision_type,
            question_id=request.question_id,
            selected=selected,
            confidence=round(confidence, 4),
            probabilities=probabilities,
            disposition=disposition,
            escalation_required=esc_req,
            model=resp.model,
            provider=resp.provider_name,
            latency_ms=round(total_time_ms, 2),
            provider_latency_ms=round(prov_lat, 2) if prov_lat is not None else None,
            gateway_overhead_ms=round(overhead_ms, 2),
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            context_digest=context_digest,
            would_have_used_expensive_model=request.would_have_used_expensive_model,
            metadata=request.metadata,
        )

        self.db.record_decision(res, state_text=request.state)
        return res

    # =========================================================================
    # OUTCOME FEEDBACK & PROVENANCE
    # =========================================================================

    def record_outcome(
        self,
        decision_id: str,
        outcome: str,
        success: bool,
        *,
        expensive_model_actually_used: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OutcomeRecord:
        """Attach verified downstream outcome feedback to a previously recorded decision."""
        return self.db.record_outcome(
            decision_id,
            outcome,
            success,
            expensive_model_actually_used=expensive_model_actually_used,
            metadata=metadata or {},
        )
