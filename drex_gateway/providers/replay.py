"""Deterministic Replay and Mock Provider for offline testing, demos, and CI.

All results from this provider are visibly and durably labeled provider="REPLAY".
"""
from __future__ import annotations

import hashlib
import time
from typing import Any

from drex_gateway.models import AnyQuestion, ChoiceQuestion, NoulQuestion, ScoreQuestion
from drex_gateway.providers.base import BaseDecisionProvider, ProviderResponse


class ReplayProvider(BaseDecisionProvider):
    """Deterministic replay provider for testing, offline demos, and benchmark suites."""

    def __init__(self, canned_fixtures: dict[str, Any] | None = None, latency_sim_ms: float = 8.5):
        self.canned_fixtures = canned_fixtures or {}
        self.latency_sim_ms = latency_sim_ms

    @property
    def provider_name(self) -> str:
        return "REPLAY"

    @property
    def default_model(self) -> str:
        return "drex-latest (replay)"

    async def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "drex-latest (replay)",
                "description": "Deterministic offline replay provider simulating Drex 1.5",
                "release_date": "2026-09-28",
                "alias_for": "drex-v1.5-replay",
            },
            {
                "name": "drex-v1.5-replay",
                "description": "Deterministic offline replay provider for Drex 1.5",
                "release_date": "2026-09-28",
                "alias_for": None,
            },
        ]

    async def decide(
        self,
        state: str,
        questions: dict[str, AnyQuestion],
        *,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> ProviderResponse:
        self.validate_request(state, questions)

        start = time.perf_counter()
        answers: dict[str, Any] = {}

        # Heuristic seed for deterministic pseudo-probabilities
        state_lower = state.lower()

        for q_id, q in questions.items():
            # Check canned fixture first
            if q_id in self.canned_fixtures:
                answers[q_id] = self.canned_fixtures[q_id]
                continue

            q_type = q.type if hasattr(q, "type") else q["type"]
            instructions = q.instructions if hasattr(q, "instructions") else q.get("instructions", "")

            if q_type == "noul":
                prob = self._compute_noul(state_lower, instructions)
                answers[q_id] = {
                    "type": "noul",
                    "noul": prob,
                }

            elif q_type == "choice":
                crit = q.criteria if hasattr(q, "criteria") else q["criteria"]
                ans = self._compute_choice(state_lower, instructions, crit)
                answers[q_id] = ans

            elif q_type == "score":
                crit = q.criteria if hasattr(q, "criteria") else q["criteria"]
                ans = self._compute_score(state_lower, instructions, crit)
                answers[q_id] = ans

        eval_time = self.latency_sim_ms
        in_tokens = max(10, len(state.split()) + 25)
        out_tokens = max(15, len(answers) * 35)

        return ProviderResponse(
            provider_name=self.provider_name,
            model=model or self.default_model,
            answers=answers,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            provider_latency_ms=eval_time,
            request_id=f"replay_req_{hashlib.md5((state + str(sorted(questions.keys()))).encode()).hexdigest()[:16]}",
            headers={"x-provider-mode": "REPLAY", "x-simulated-latency-ms": str(eval_time)},
        )

    def _compute_noul(self, state_lower: str, instructions: str) -> float:
        """Deterministic, keyword-aware probability between 0.0 and 1.0."""
        score = 0.5
        # Look for affirmative vs negative signals
        affirmatives = ["yes", "true", "error", "fail", "broken", "needed", "missing", "escalat", "risk"]
        negatives = ["no", "false", "clean", "pass", "ok", "success", "appropriate", "ready"]

        for w in affirmatives:
            if w in state_lower or w in instructions.lower():
                score += 0.08
        for w in negatives:
            if w in state_lower or w in instructions.lower():
                score -= 0.08

        # Hash salt for reproducible nuance
        h = int(hashlib.sha256((state_lower + instructions).encode()).hexdigest()[:4], 16) / 65535.0
        score = 0.7 * score + 0.3 * h
        return round(min(0.99, max(0.01, score)), 4)

    def _compute_choice(
        self, state_lower: str, instructions: str, criteria: dict[str, str | None]
    ) -> dict[str, Any]:
        """Produce a calibrated probability distribution over choices."""
        options = list(criteria.keys())
        raw_weights: dict[str, float] = {}

        for opt in options:
            weight = 1.0
            opt_lower = opt.lower()
            opt_desc = (criteria.get(opt) or "").lower()

            # Semantic domain keyword affinities
            if "modulenotfounderror" in state_lower or "no module named" in state_lower or "pip install" in state_lower:
                if opt_lower == "environment_failure":
                    weight += 20.0
            if "assertionerror" in state_lower:
                if opt_lower == "implementation_failure":
                    weight += 15.0
            if "syntaxerror" in state_lower:
                if "verifier" in state_lower and "test" in state_lower and opt_lower == "verifier_failure":
                    weight += 15.0
            if "out of memory" in state_lower or "killed" in state_lower or "compiler" in state_lower:
                if opt_lower == "toolchain_failure":
                    weight += 20.0
            if "connection refused" in state_lower or "timeout" in state_lower:
                if opt_lower == "wait_for_resource":
                    weight += 15.0
            if "subsystem" in instructions.lower() or "area" in instructions.lower():
                # For subsystem selection, look at path prefixes and core verbs
                for token in state_lower.replace("/", " ").replace(".", " ").split():
                    if token == opt_lower:
                        weight += 10.0

            # Direct option key match
            if opt_lower in state_lower:
                weight += 3.0

            # Matching descriptive criteria keywords excluding common stopwords
            stopwords = {"in", "to", "and", "or", "of", "for", "with", "a", "an", "the", "is", "code", "test", "tests", "file", "command"}
            for term in opt_desc.split():
                clean_term = term.strip(",.:;\"'()[]{}").lower()
                if len(clean_term) > 3 and clean_term not in stopwords and clean_term in state_lower:
                    weight += 2.0

            # Deterministic hash jitter
            h = int(hashlib.md5((state_lower + opt).encode()).hexdigest()[:4], 16) / 65535.0
            weight += h * 0.2
            raw_weights[opt] = weight

        total_weight = sum(raw_weights.values())
        # Make top choice crisp
        best_opt = max(options, key=lambda o: raw_weights[o])
        raw_weights[best_opt] *= 3.0  # sharpen distribution to reflect Drex certainty
        total_weight = sum(raw_weights.values())

        probabilities = {}
        for opt in options:
            probabilities[opt] = round(raw_weights[opt] / total_weight, 4)

        # Ensure exact sum to 1.0
        diff = round(1.0 - sum(probabilities.values()), 4)
        probabilities[best_opt] = round(probabilities[best_opt] + diff, 4)

        confidence = probabilities[best_opt]
        return {
            "type": "choice",
            "choice": best_opt,
            "confidence": confidence,
            "probabilities": probabilities,
        }

    def _compute_score(
        self, state_lower: str, instructions: str, criteria: list[str]
    ) -> dict[str, Any]:
        """Produce a calibrated probability distribution across ordered score levels."""
        n_levels = len(criteria)
        # Determine center of mass from keywords
        center = 0
        if any(w in state_lower for w in ["complex", "severe", "rewrite", "deep", "high", "hard"]):
            center = n_levels - 1
        elif any(w in state_lower for w in ["moderate", "medium", "standard", "average"]):
            center = n_levels // 2
        else:
            center = 0

        raw_weights = []
        for i in range(n_levels):
            dist = abs(i - center)
            raw_weights.append(1.0 / (1.0 + dist * 2.0))

        tot = sum(raw_weights)
        probs = {str(i): round(w / tot, 4) for i, w in enumerate(raw_weights)}
        best_idx = str(center)
        diff = round(1.0 - sum(probs.values()), 4)
        probs[best_idx] = round(probs[best_idx] + diff, 4)

        return {
            "type": "score",
            "score": float(center),
            "legend": criteria,
            "probabilities": probs,
            "confidence": probs[best_idx],
        }
