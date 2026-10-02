"""Base provider abstraction for Drex and interchangeable decision backends."""
from __future__ import annotations

import abc
import asyncio
import math
import re
from dataclasses import dataclass, field
from typing import Any

from drex_gateway.errors import ProviderError, ProviderErrorKind, ValidationError
from drex_gateway.models import AnyQuestion, ChoiceQuestion, NoulQuestion, ScoreQuestion


@dataclass
class ProviderResponse:
    provider_name: str
    model: str
    answers: dict[str, Any]
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_latency_ms: float | None = None
    request_id: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


class BaseDecisionProvider(abc.ABC):
    """Abstract provider interface."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Name of provider (e.g. 'Drex', 'REPLAY')."""
        pass

    @property
    @abc.abstractmethod
    def default_model(self) -> str:
        """Default model identifier."""
        pass

    @abc.abstractmethod
    async def list_models(self) -> list[dict[str, Any]]:
        """List available models."""
        pass

    @abc.abstractmethod
    async def decide(
        self,
        state: str,
        questions: dict[str, AnyQuestion],
        *,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> ProviderResponse:
        """Execute decision(s) against state context."""
        pass

    def sync_list_models(self) -> list[dict[str, Any]]:
        return asyncio.run(self.list_models())

    def sync_decide(
        self,
        state: str,
        questions: dict[str, AnyQuestion],
        *,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> ProviderResponse:
        return asyncio.run(self.decide(state, questions, model=model, trace_id=trace_id))

    def validate_request(self, state: str, questions: dict[str, AnyQuestion]) -> None:
        """Preflight validation to prevent malformed requests and enforce documented bounds."""
        if not isinstance(state, str) or not state.strip():
            raise ValidationError("State must be non-empty text")
        if not isinstance(questions, dict) or not 1 <= len(questions) <= 512:
            raise ValidationError("Questions must contain between 1 and 512 items")

        for q_id, q in questions.items():
            if not isinstance(q_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", q_id):
                raise ValidationError(f"Question id {q_id!r} must be an alphanumeric identifier (1-64 chars)")

            if isinstance(q, ChoiceQuestion) or (isinstance(q, dict) and q.get("type") == "choice"):
                crit = q.criteria if isinstance(q, ChoiceQuestion) else q.get("criteria")
                if not isinstance(crit, dict) or not 2 <= len(crit) <= 64:
                    raise ValidationError(f"Choice question {q_id!r} requires 2 to 64 options in criteria")
                for opt_k in crit:
                    if not isinstance(opt_k, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", opt_k.lower()):
                        raise ValidationError(f"Choice key {opt_k!r} in {q_id!r} must be lowercase alphanumeric")

            elif isinstance(q, ScoreQuestion) or (isinstance(q, dict) and q.get("type") == "score"):
                crit = q.criteria if isinstance(q, ScoreQuestion) else q.get("criteria")
                if not isinstance(crit, list) or not 1 <= len(crit) <= 64:
                    raise ValidationError(f"Score question {q_id!r} requires 1 to 64 ordered levels in criteria")

            elif isinstance(q, NoulQuestion) or (isinstance(q, dict) and q.get("type") == "noul"):
                pass
            else:
                raise ValidationError(f"Unsupported question type for {q_id!r}")

    def validate_response(self, questions: dict[str, AnyQuestion], payload: dict[str, Any]) -> None:
        """Strict validation of provider response format and probability bounds."""
        if not isinstance(payload, dict):
            raise ProviderError(
                ProviderErrorKind.INVALID_RESPONSE,
                "Provider response must be a JSON object",
            )
        answers = payload.get("answers")
        if not isinstance(answers, dict) or set(answers) != set(questions):
            raise ProviderError(
                ProviderErrorKind.INVALID_RESPONSE,
                f"Provider returned answers mismatching requested questions: got {list(answers.keys()) if isinstance(answers, dict) else 'none'}, expected {list(questions.keys())}",
            )

        for q_id, q in questions.items():
            ans = answers[q_id]
            if not isinstance(ans, dict):
                raise ProviderError(
                    ProviderErrorKind.INVALID_RESPONSE,
                    f"Answer for {q_id!r} must be an object",
                )
            q_type = q.type if hasattr(q, "type") else q["type"]
            ans_type = ans.get("type")
            if ans_type != q_type:
                raise ProviderError(
                    ProviderErrorKind.INVALID_RESPONSE,
                    f"Question {q_id!r} expected type {q_type!r} but got {ans_type!r}",
                )

            if q_type == "noul":
                noul_val = ans.get("noul")
                if isinstance(noul_val, bool) or not isinstance(noul_val, (int, float)) or not (0.0 <= noul_val <= 1.0):
                    raise ProviderError(
                        ProviderErrorKind.INVALID_RESPONSE,
                        f"Invalid noul value for {q_id!r}: {noul_val}",
                    )
            elif q_type == "choice":
                crit = q.criteria if hasattr(q, "criteria") else q["criteria"]
                probs = ans.get("probabilities")
                choice = ans.get("choice")
                if not isinstance(choice, str) or choice not in crit:
                    raise ProviderError(
                        ProviderErrorKind.INVALID_RESPONSE,
                        f"Selected choice {choice!r} for {q_id!r} not in criteria {list(crit.keys())}",
                    )
                if not isinstance(probs, dict) or set(probs) != set(crit):
                    raise ProviderError(
                        ProviderErrorKind.INVALID_RESPONSE,
                        f"Probabilities keys for {q_id!r} mismatch criteria",
                    )
                self._validate_probabilities(probs, q_id)
                prob_sum = sum(probs.values())
                if abs(prob_sum - 1.0) > 0.05:
                    raise ProviderError(
                        ProviderErrorKind.INVALID_RESPONSE,
                        f"Probabilities for {q_id!r} do not sum to 1.0 (sum={prob_sum})",
                    )
                if "confidence" in ans:
                    self._validate_unit_interval(ans["confidence"], q_id, "confidence")
            elif q_type == "score":
                crit = q.criteria if hasattr(q, "criteria") else q["criteria"]
                score = ans.get("score")
                if (
                    isinstance(score, bool)
                    or not isinstance(score, (int, float))
                    or not math.isfinite(score)
                    or not 0.0 <= score <= max(0, len(crit) - 1)
                ):
                    raise ProviderError(
                        ProviderErrorKind.INVALID_RESPONSE,
                        f"Invalid score for {q_id!r}: expected a finite score within the requested levels",
                    )
                probs = ans.get("probabilities")
                if not isinstance(probs, dict):
                    raise ProviderError(
                        ProviderErrorKind.INVALID_RESPONSE,
                        f"Missing probabilities dict for score question {q_id!r}",
                    )
                self._validate_probabilities(probs, q_id)
                prob_sum = sum(probs.values())
                if abs(prob_sum - 1.0) > 0.05:
                    raise ProviderError(
                        ProviderErrorKind.INVALID_RESPONSE,
                        f"Score probabilities for {q_id!r} do not sum to 1.0 (sum={prob_sum})",
                    )
                if "confidence" in ans:
                    self._validate_unit_interval(ans["confidence"], q_id, "confidence")

    @staticmethod
    def _validate_unit_interval(value: Any, q_id: str, field_name: str) -> None:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
        ):
            raise ProviderError(
                ProviderErrorKind.INVALID_RESPONSE,
                f"Invalid {field_name} for {q_id!r}: expected a finite number in [0, 1]",
            )

    @classmethod
    def _validate_probabilities(cls, probabilities: dict[str, Any], q_id: str) -> None:
        for key, value in probabilities.items():
            cls._validate_unit_interval(value, q_id, f"probability[{key!r}]")
