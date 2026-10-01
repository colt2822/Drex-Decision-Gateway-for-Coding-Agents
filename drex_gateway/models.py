"""Pydantic data models, schemas, and typed records for Drex Decision Gateway."""
from __future__ import annotations

import datetime
import hashlib
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class Disposition(str, Enum):
    ACCEPT = "ACCEPT"
    ESCALATE = "ESCALATE"
    ABSTAIN = "ABSTAIN"


class ProviderMode(str, Enum):
    LIVE = "LIVE"
    REPLAY = "REPLAY"


class QuestionKind(str, Enum):
    CHOICE = "choice"
    NOUL = "noul"
    SCORE = "score"


class OutcomeType(str, Enum):
    IMPLEMENTATION_PASS = "IMPLEMENTATION_PASS"
    IMPLEMENTATION_FAIL = "IMPLEMENTATION_FAIL"
    VERIFIER_PASS = "VERIFIER_PASS"
    VERIFIER_FAIL = "VERIFIER_FAIL"
    REPAIR_SUCCESS = "REPAIR_SUCCESS"
    REPAIR_FAIL = "REPAIR_FAIL"
    PR_OPENED = "PR_OPENED"
    PR_MERGED = "PR_MERGED"
    PR_REJECTED = "PR_REJECTED"
    PAYOUT_RECORDED = "PAYOUT_RECORDED"
    OTHER = "OTHER"


class ChoiceQuestion(BaseModel):
    type: Literal["choice"] = "choice"
    instructions: str
    criteria: dict[str, str | None]


class NoulQuestion(BaseModel):
    type: Literal["noul"] = "noul"
    instructions: str


class ScoreQuestion(BaseModel):
    type: Literal["score"] = "score"
    instructions: str
    criteria: list[str]


AnyQuestion = ChoiceQuestion | NoulQuestion | ScoreQuestion


class DecisionRequest(BaseModel):
    state: str = Field(..., description="Context, diff, test output, or task state")
    question_id: str = Field(default="primary_decision", description="Short identifier for this question")
    question: AnyQuestion
    decision_type: str = Field(default="generic", description="Decision type label for policy matching")
    trace_id: str | None = Field(default=None, description="Distributed trace ID linking agent steps")
    parent_decision_id: str | None = Field(default=None, description="Parent decision ID if sequential")
    confidence_threshold: float | None = Field(default=None, description="Optional override for accept threshold")
    escalation_threshold: float | None = Field(default=None, description="Optional override for escalation threshold")
    would_have_used_expensive_model: bool = Field(
        default=True,
        description="Whether an expensive generative call would have been made without this decision",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Generic provenance metadata")


class BatchDecisionRequest(BaseModel):
    state: str = Field(..., description="Shared repository or task context")
    questions: dict[str, AnyQuestion] = Field(..., description="Map of question_id to question spec")
    decision_types: dict[str, str] = Field(
        default_factory=dict,
        description="Optional mapping of question_id to decision_type for policy resolution",
    )
    trace_id: str | None = Field(default=None)
    parent_decision_id: str | None = Field(default=None)
    would_have_used_expensive_model: bool = Field(default=True)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionResult(BaseModel):
    decision_id: str
    trace_id: str
    parent_decision_id: str | None = None
    decision_type: str
    question_id: str
    selected: Any
    confidence: float
    probabilities: dict[str, float]
    disposition: Disposition
    escalation_required: bool
    model: str
    provider: str
    latency_ms: float
    provider_latency_ms: float | None = None
    gateway_overhead_ms: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    context_digest: str
    would_have_used_expensive_model: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    @property
    def accepted(self) -> bool:
        return self.disposition == Disposition.ACCEPT

    @property
    def escalated(self) -> bool:
        return self.disposition == Disposition.ESCALATE

    @property
    def abstained(self) -> bool:
        return self.disposition == Disposition.ABSTAIN


class BatchDecisionResult(BaseModel):
    trace_id: str
    context_digest: str
    decisions: dict[str, DecisionResult]
    total_latency_ms: float
    provider_latency_ms: float | None = None
    gateway_overhead_ms: float = 0.0
    all_accepted: bool = False
    any_escalated: bool = False

    @model_validator(mode="after")
    def compute_summary_flags(self) -> BatchDecisionResult:
        if self.decisions:
            self.all_accepted = all(d.accepted for d in self.decisions.values())
            self.any_escalated = any(d.escalated for d in self.decisions.values())
        return self


class OutcomeRecord(BaseModel):
    outcome_id: str
    decision_id: str
    outcome: str
    success: bool
    expensive_model_actually_used: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class OutcomeFeedbackRequest(BaseModel):
    outcome: str = Field(..., description="e.g. VERIFIER_PASS, IMPLEMENTATION_FAIL, PR_MERGED")
    success: bool = Field(..., description="Whether the downstream action succeeded")
    expensive_model_actually_used: bool | None = Field(
        default=None,
        description="Whether an expensive model was actually called after this decision",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceSummary(BaseModel):
    trace_id: str
    root_decision_id: str | None = None
    decisions: list[DecisionResult] = Field(default_factory=list)
    outcomes: list[OutcomeRecord] = Field(default_factory=list)
    total_drex_decisions: int = 0
    accepted_count: int = 0
    escalated_count: int = 0
    abstained_count: int = 0
    expensive_calls_avoided: int = 0
    total_latency_ms: float = 0.0
    agent_name: str | None = None
    repo: str | None = None
    commit_sha: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


def compute_digest(text: str) -> str:
    """Deterministic SHA-256 digest of input context."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
