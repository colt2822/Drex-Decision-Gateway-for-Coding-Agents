"""Benchmark runner for evaluating Drex decisions and calibration."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.models import ChoiceQuestion, NoulQuestion, ScoreQuestion


class BenchmarkCase(BaseModel):
    id: str
    context: str
    question_type: str  # choice, noul, score
    instructions: str
    criteria: Any = None
    expected_answer: str | None = None
    decision_type: str = "generic"
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkCaseResult(BaseModel):
    case_id: str
    decision_id: str
    selected: Any
    expected: str | None
    correct: bool | None
    confidence: float
    disposition: str
    probabilities: dict[str, float]
    latency_ms: float


class BenchmarkSuiteReport(BaseModel):
    run_id: str
    suite_name: str
    provider: str
    model: str
    total_cases: int
    evaluated_cases: int
    accuracy: float | None = None
    coverage: float
    escalation_rate: float
    latency_p50_ms: float
    latency_p95_ms: float
    expensive_calls_avoided: int
    calibration_bins: list[dict[str, Any]]
    results: list[BenchmarkCaseResult]
    created_at: str


class BenchmarkRunner:
    """Executes JSONL benchmark test suites against Drex Decision Gateway."""

    def __init__(self, gateway: DrexDecisionGateway):
        self.gateway = gateway

    def load_dataset(self, file_path: str | Path) -> list[BenchmarkCase]:
        cases = []
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Benchmark file not found: {file_path}")

        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            data = json.loads(line)
            cases.append(BenchmarkCase(**data))
        return cases

    async def run(
        self,
        cases_or_path: list[BenchmarkCase] | str | Path,
        suite_name: str = "coding_tasks",
    ) -> BenchmarkSuiteReport:
        if isinstance(cases_or_path, (str, Path)):
            cases = self.load_dataset(cases_or_path)
        else:
            cases = cases_or_path

        run_id = f"bench_{uuid.uuid4().hex[:12]}"
        results: list[BenchmarkCaseResult] = []
        latencies: list[float] = []

        total_cases = len(cases)
        correct_count = 0
        labeled_count = 0
        accepted_count = 0
        escalated_count = 0

        for case in cases:
            # Build appropriate question object
            q_obj: Any
            if case.question_type == "choice":
                crit = {k.lower(): v for k, v in case.criteria.items()}
                q_obj = ChoiceQuestion(type="choice", instructions=case.instructions, criteria=crit)
            elif case.question_type == "noul":
                q_obj = NoulQuestion(type="noul", instructions=case.instructions)
            elif case.question_type == "score":
                crit_list = case.criteria if isinstance(case.criteria, list) else list(case.criteria.keys())
                q_obj = ScoreQuestion(type="score", instructions=case.instructions, criteria=crit_list)
            else:
                continue

            t0 = time.perf_counter()
            dec = await self.gateway.choose(
                question=case.instructions,
                choices=case.criteria if case.question_type == "choice" else ["yes", "no"],
                context=case.context,
                decision_type=case.decision_type,
                question_id=case.id,
                metadata={"benchmark_run_id": run_id, "case_id": case.id},
            )
            elapsed = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed)

            correct = None
            if case.expected_answer is not None:
                labeled_count += 1
                exp_clean = case.expected_answer.strip().lower()
                got_clean = str(dec.selected).strip().lower()
                correct = (exp_clean == got_clean)
                if correct:
                    correct_count += 1

            if dec.accepted:
                accepted_count += 1
            elif dec.escalated:
                escalated_count += 1

            results.append(
                BenchmarkCaseResult(
                    case_id=case.id,
                    decision_id=dec.decision_id,
                    selected=dec.selected,
                    expected=case.expected_answer,
                    correct=correct,
                    confidence=dec.confidence,
                    disposition=dec.disposition.value,
                    probabilities=dec.probabilities,
                    latency_ms=round(elapsed, 2),
                )
            )

        latencies.sort()
        p50 = round(latencies[len(latencies) // 2], 2) if latencies else 0.0
        p95 = round(latencies[int(len(latencies) * 0.95)], 2) if latencies else 0.0

        accuracy = round(correct_count / labeled_count, 4) if labeled_count > 0 else None
        coverage = round(accepted_count / total_cases, 4) if total_cases > 0 else 0.0
        escalation_rate = round(escalated_count / total_cases, 4) if total_cases > 0 else 0.0

        # Compute calibration bins (confidence ranges: 0.5-0.6, 0.6-0.7, 0.7-0.8, 0.8-0.9, 0.9-1.0)
        bins = []
        for low, high in [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]:
            bin_items = [r for r in results if low <= r.confidence < high and r.correct is not None]
            if bin_items:
                bin_acc = round(sum(1 for r in bin_items if r.correct) / len(bin_items), 3)
                bin_conf = round(sum(r.confidence for r in bin_items) / len(bin_items), 3)
            else:
                bin_acc = None
                bin_conf = None
            bins.append({
                "range": f"{low:.1f}-{min(1.0, high):.1f}",
                "count": len(bin_items),
                "accuracy": bin_acc,
                "confidence": bin_conf,
            })

        report = BenchmarkSuiteReport(
            run_id=run_id,
            suite_name=suite_name,
            provider=self.gateway.provider.provider_name,
            model=self.gateway.provider.default_model,
            total_cases=total_cases,
            evaluated_cases=len(results),
            accuracy=accuracy,
            coverage=coverage,
            escalation_rate=escalation_rate,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            expensive_calls_avoided=accepted_count,
            calibration_bins=bins,
            results=results,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        # Store in database
        self.gateway.db.record_benchmark_run(
            run_id=run_id,
            suite_name=suite_name,
            provider=self.gateway.provider.provider_name,
            model=self.gateway.provider.default_model,
            total_cases=total_cases,
            accuracy=accuracy,
            coverage=coverage,
            escalation_rate=escalation_rate,
            latency_p50=p50,
            latency_p95=p95,
            expensive_calls_avoided=accepted_count,
            report_json=report.model_dump_json(),
        )

        return report
