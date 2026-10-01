"""Escalation Simulation & Economic Tradeoff Analysis.

Evaluates how varying confidence acceptance thresholds affects accuracy,
coverage, escalation rate, and expensive LLM calls avoided.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel
from drex_gateway.benchmarks.runner import BenchmarkSuiteReport


class ThresholdPoint(BaseModel):
    threshold: float
    coverage: float  # fraction of decisions accepted
    accuracy_among_accepted: float | None  # accuracy of Drex when accepted
    escalation_rate: float  # decisions falling in escalation band
    abstention_rate: float  # decisions falling below escalation band
    accepted_count: int
    escalated_count: int
    abstained_count: int
    expensive_calls_avoided: int  # accepted calls where model was avoided


class EscalationSimulationReport(BaseModel):
    suite_name: str
    total_decisions: int
    points: list[ThresholdPoint]
    optimal_threshold_for_high_accuracy: float
    optimal_threshold_for_max_throughput: float


class EscalationSimulator:
    """Simulates economic and precision tradeoffs across varying thresholds."""

    @classmethod
    def simulate(
        cls,
        benchmark_report: BenchmarkSuiteReport,
        thresholds: list[float] | None = None,
        escalation_delta: float = 0.20,
    ) -> EscalationSimulationReport:
        if thresholds is None:
            thresholds = [0.50, 0.60, 0.70, 0.80, 0.90, 0.95]

        results = benchmark_report.results
        total = len(results)
        points: list[ThresholdPoint] = []

        for th in thresholds:
            esc_floor = max(0.40, th - escalation_delta)

            accepted = []
            escalated = []
            abstained = []

            for r in results:
                if r.confidence >= th:
                    accepted.append(r)
                elif r.confidence >= esc_floor:
                    escalated.append(r)
                else:
                    abstained.append(r)

            cov = round(len(accepted) / total, 4) if total > 0 else 0.0
            esc_rate = round(len(escalated) / total, 4) if total > 0 else 0.0
            abst_rate = round(len(abstained) / total, 4) if total > 0 else 0.0

            labeled_acc = [r for r in accepted if r.correct is not None]
            acc_val = (
                round(sum(1 for r in labeled_acc if r.correct) / len(labeled_acc), 4)
                if labeled_acc
                else None
            )

            points.append(
                ThresholdPoint(
                    threshold=th,
                    coverage=cov,
                    accuracy_among_accepted=acc_val,
                    escalation_rate=esc_rate,
                    abstention_rate=abst_rate,
                    accepted_count=len(accepted),
                    escalated_count=len(escalated),
                    abstained_count=len(abstained),
                    expensive_calls_avoided=len(accepted),
                )
            )

        # Identify sweet-spot points
        opt_acc = 0.85
        opt_through = 0.70
        for p in points:
            if p.accuracy_among_accepted and p.accuracy_among_accepted >= 0.95:
                opt_acc = p.threshold
                break
        for p in points:
            if p.coverage >= 0.75:
                opt_through = p.threshold

        return EscalationSimulationReport(
            suite_name=benchmark_report.suite_name,
            total_decisions=total,
            points=points,
            optimal_threshold_for_high_accuracy=opt_acc,
            optimal_threshold_for_max_throughput=opt_through,
        )
