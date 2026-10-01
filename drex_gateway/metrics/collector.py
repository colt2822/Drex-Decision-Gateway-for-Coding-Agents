"""Metrics collector and economic ROI calculator."""
from __future__ import annotations

from typing import Any
from drex_gateway.storage.db import Database


class MetricsCollector:
    """Aggregates decision, latency, reliability, and economic metrics."""

    def __init__(self, db: Database, cost_per_expensive_call: float | None = None):
        self.db = db
        self.cost_per_expensive_call = cost_per_expensive_call

    def collect(self) -> dict[str, Any]:
        stats = self.db.get_stats()
        total_decisions = stats["total_decisions"]
        avoided = stats["expensive_calls_avoided"]

        # Dollar savings calculation: ONLY if user supplied a cost, otherwise report UNKNOWN / None
        dollar_savings = None
        if self.cost_per_expensive_call is not None:
            dollar_savings = round(avoided * self.cost_per_expensive_call, 2)

        return {
            "decisions_total": total_decisions,
            "decisions_accepted": stats["accepted_count"],
            "decisions_escalated": stats["escalated_count"],
            "decisions_abstained": stats["abstained_count"],
            "expensive_calls_avoided": avoided,
            "escalation_rate": stats["escalation_rate"],
            "accept_rate": stats["accept_rate"],
            "latency_p50_ms": stats["latency_p50_ms"],
            "latency_p95_ms": stats["latency_p95_ms"],
            "provider_latency_p50_ms": stats["provider_latency_p50_ms"],
            "provider_latency_p95_ms": stats["provider_latency_p95_ms"],
            "gateway_overhead_p50_ms": stats["gateway_overhead_p50_ms"],
            "gateway_overhead_p95_ms": stats["gateway_overhead_p95_ms"],
            "decision_types": stats["decision_types"],
            "providers": stats["providers"],
            "models": stats["models"],
            "outcomes_count": stats["outcomes_count"],
            "success_rate": stats["success_rate"],
            "estimated_dollar_savings": dollar_savings if dollar_savings is not None else "UNKNOWN",
        }
