"""Prometheus metrics exporter for Drex Decision Gateway."""
from __future__ import annotations

from drex_gateway.metrics.collector import MetricsCollector


def generate_prometheus_text(collector: MetricsCollector) -> str:
    """Format gateway metrics in standard Prometheus exposition format."""
    data = collector.collect()
    lines = []

    # HELP and TYPE definitions
    lines.append("# HELP drex_decisions_total Total number of decisions processed by gateway")
    lines.append("# TYPE drex_decisions_total counter")
    lines.append(f"drex_decisions_total {data['decisions_total']}")

    lines.append("# HELP drex_decisions_by_disposition Decisions grouped by disposition")
    lines.append("# TYPE drex_decisions_by_disposition gauge")
    lines.append(f'drex_decisions_by_disposition{{disposition="ACCEPT"}} {data["decisions_accepted"]}')
    lines.append(f'drex_decisions_by_disposition{{disposition="ESCALATE"}} {data["decisions_escalated"]}')
    lines.append(f'drex_decisions_by_disposition{{disposition="ABSTAIN"}} {data["decisions_abstained"]}')

    lines.append("# HELP drex_expensive_calls_avoided_total Number of expensive LLM calls avoided by Drex decisions")
    lines.append("# TYPE drex_expensive_calls_avoided_total counter")
    lines.append(f"drex_expensive_calls_avoided_total {data['expensive_calls_avoided']}")

    lines.append("# HELP drex_escalation_rate Fraction of decisions requiring escalation")
    lines.append("# TYPE drex_escalation_rate gauge")
    lines.append(f"drex_escalation_rate {data['escalation_rate']}")

    if data["latency_p50_ms"] is not None:
        lines.append("# HELP drex_latency_ms Drex request latency percentiles")
        lines.append("# TYPE drex_latency_ms gauge")
        lines.append(f'drex_latency_ms{{quantile="0.50"}} {data["latency_p50_ms"]}')
        if data["latency_p95_ms"] is not None:
            lines.append(f'drex_latency_ms{{quantile="0.95"}} {data["latency_p95_ms"]}')

    if data["gateway_overhead_p50_ms"] is not None:
        lines.append("# HELP drex_gateway_overhead_ms Gateway processing overhead percentiles")
        lines.append("# TYPE drex_gateway_overhead_ms gauge")
        lines.append(f'drex_gateway_overhead_ms{{quantile="0.50"}} {data["gateway_overhead_p50_ms"]}')
        if data["gateway_overhead_p95_ms"] is not None:
            lines.append(f'drex_gateway_overhead_ms{{quantile="0.95"}} {data["gateway_overhead_p95_ms"]}')

    for dec_type, count in data["decision_types"].items():
        lines.append(f'drex_decisions_by_type{{type="{dec_type}"}} {count}')

    lines.append("")
    return "\n".join(lines)
