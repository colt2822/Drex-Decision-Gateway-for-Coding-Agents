"""Developer CLI for Drex Decision Gateway."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click

from drex_gateway.benchmarks.runner import BenchmarkRunner
from drex_gateway.benchmarks.simulation import EscalationSimulator
from drex_gateway.config import GatewayConfig
from drex_gateway.gateway import DrexDecisionGateway
from drex_gateway.metrics.collector import MetricsCollector
from drex_gateway.workflows.killer_demo import KillerDemoRunner


@click.group()
@click.option("--db", default=None, help="Path to SQLite database file.")
@click.option("--replay", is_flag=True, help="Force deterministic REPLAY mode.")
@click.pass_context
def cli(ctx: click.Context, db: str | None, replay: bool):
    """Drex Decision Gateway: Fast, calibrated decision layer for coding agents."""
    cfg = GatewayConfig.from_env()
    if db:
        cfg.db_path = db
    if replay:
        cfg.force_provider = "REPLAY"
    ctx.ensure_object(dict)
    ctx.obj["config"] = cfg
    ctx.obj["gateway"] = DrexDecisionGateway(config=cfg)


@cli.command()
@click.pass_context
def health(ctx: click.Context):
    """Check gateway health, active provider, and model alias."""
    gateway: DrexDecisionGateway = ctx.obj["gateway"]
    click.echo(f"Gateway Status: HEALTHY")
    click.echo(f"Provider:       {gateway.provider.provider_name} [{gateway.provider_mode}]")
    click.echo(f"Default Model:  {gateway.provider.default_model}")
    click.echo(f"Database Path:  {gateway.config.db_path}")

    try:
        models = gateway.provider.sync_list_models()
        click.echo(f"Available Models ({len(models)}):")
        for m in models:
            click.echo(f"  - {m.get('name')}: {m.get('description', '')[:60]}")
    except Exception as exc:
        click.echo(f"Model lookup warning: {exc}", err=True)


@cli.command()
@click.argument("question")
@click.option("--choices", "-c", required=True, help="Comma-separated choices (e.g. 'auth,billing,core').")
@click.option("--context", "-x", default="", help="Context string or diff.")
@click.option("--type", "-t", default="choose", help="Decision type label.")
@click.pass_context
def choose(ctx: click.Context, question: str, choices: str, context: str, type: str):
    """Execute a structured discrete choice decision."""
    gateway: DrexDecisionGateway = ctx.obj["gateway"]
    choice_list = [c.strip() for c in choices.split(",") if c.strip()]

    res = asyncio.run(
        gateway.choose(
            question=question,
            choices=choice_list,
            context=context or "CLI invocation",
            decision_type=type,
        )
    )

    click.echo(f"\nDecision Result [{res.disposition.value}]:")
    click.echo(f"  Selected:    {res.selected}")
    click.echo(f"  Confidence:  {res.confidence:.4f}")
    click.echo(f"  Escalation:  {'YES' if res.escalation_required else 'NO'}")
    click.echo(f"  Provider:    {res.provider} ({res.model})")
    click.echo(f"  Latency:     {res.latency_ms:.1f}ms (Gateway overhead: {res.gateway_overhead_ms:.1f}ms)")
    click.echo(f"  Trace ID:    {res.trace_id}")
    click.echo("\nProbability Distribution:")
    for opt, prob in sorted(res.probabilities.items(), key=lambda kv: kv[1], reverse=True):
        bar = "█" * int(prob * 30)
        click.echo(f"  {opt:<20} {prob:>6.2%} {bar}")


@cli.command()
@click.pass_context
def stats(ctx: click.Context):
    """Display gateway metrics, latency percentiles, and expensive calls avoided."""
    gateway: DrexDecisionGateway = ctx.obj["gateway"]
    collector = MetricsCollector(gateway.db)
    data = collector.collect()

    click.echo("\n=======================================================")
    click.echo("            DREX DECISION GATEWAY METRICS              ")
    click.echo("=======================================================")
    click.echo(f"Total Decisions:          {data['decisions_total']}")
    click.echo(f"  Accepted:               {data['decisions_accepted']} ({data['accept_rate']:.1%})")
    click.echo(f"  Escalated:              {data['decisions_escalated']} ({data['escalation_rate']:.1%})")
    click.echo(f"  Abstained:              {data['decisions_abstained']}")
    click.echo(f"Expensive Calls Avoided:  {data['expensive_calls_avoided']}")
    click.echo(f"Latency P50 / P95:        {data['latency_p50_ms']}ms / {data['latency_p95_ms']}ms")
    click.echo(f"Gateway Overhead P50/P95: {data['gateway_overhead_p50_ms']}ms / {data['gateway_overhead_p95_ms']}ms")
    click.echo(f"Outcomes Feedback Tracked: {data['outcomes_count']} (Success Rate: {data['success_rate']})")
    if data["estimated_dollar_savings"] != "UNKNOWN":
        click.echo(f"Estimated Savings:        ${data['estimated_dollar_savings']}")
    click.echo("=======================================================\n")


@cli.command()
@click.argument("trace_id")
@click.pass_context
def trace(ctx: click.Context, trace_id: str):
    """View complete decision provenance and timeline for a trace."""
    gateway: DrexDecisionGateway = ctx.obj["gateway"]
    summary = gateway.db.get_trace_summary(trace_id)
    if not summary:
        click.echo(f"Trace not found: {trace_id}", err=True)
        sys.exit(1)

    click.echo(f"\nTrace: {summary.trace_id}")
    click.echo(f"Created: {summary.created_at} | Total Latency: {summary.total_latency_ms:.1f}ms")
    click.echo(f"Decisions: {summary.total_drex_decisions} | Avoided Calls: {summary.expensive_calls_avoided}\n")

    for i, dec in enumerate(summary.decisions, start=1):
        click.echo(f"[{i}] {dec.decision_type:<24} -> {dec.selected:<18} (conf: {dec.confidence:.2f}, {dec.disposition.value}) {dec.latency_ms:.1f}ms")

    if summary.outcomes:
        click.echo("\nRecorded Outcomes:")
        for o in summary.outcomes:
            click.echo(f"  - {o.outcome}: success={o.success} (at {o.recorded_at})")


@cli.command()
@click.option("--dataset", "-d", default=None, help="Path to JSONL benchmark file.")
@click.option("--suite", "-s", default="coding_tasks", help="Benchmark suite name.")
@click.pass_context
def benchmark(ctx: click.Context, dataset: str | None, suite: str):
    """Run benchmark test suite and escalation simulation."""
    gateway: DrexDecisionGateway = ctx.obj["gateway"]
    runner = BenchmarkRunner(gateway)

    if dataset is None:
        dataset_path = Path(__file__).parent.parent / "benchmarks" / "datasets" / "coding_tasks.jsonl"
    else:
        dataset_path = Path(dataset)

    click.echo(f"Running benchmark suite '{suite}' from {dataset_path}...")
    report = asyncio.run(runner.run(dataset_path, suite_name=suite))

    click.echo("\n=======================================================")
    click.echo(f"BENCHMARK RESULTS: {report.suite_name}")
    click.echo("=======================================================")
    click.echo(f"Provider:                {report.provider} ({report.model})")
    click.echo(f"Cases Evaluated:         {report.evaluated_cases} / {report.total_cases}")
    click.echo(f"Accuracy:                {report.accuracy:.2%}" if report.accuracy is not None else "Accuracy: N/A")
    click.echo(f"Coverage (Accepted):     {report.coverage:.2%}")
    click.echo(f"Escalation Rate:         {report.escalation_rate:.2%}")
    click.echo(f"Latency P50 / P95:       {report.latency_p50_ms:.1f}ms / {report.latency_p95_ms:.1f}ms")
    click.echo(f"Expensive Calls Avoided: {report.expensive_calls_avoided}")

    # Escalation simulation across threshold sweep
    sim = EscalationSimulator.simulate(report)
    click.echo("\n-------------------------------------------------------")
    click.echo("THRESHOLD ESCALATION SIMULATION (Economic Tradeoffs)")
    click.echo("Threshold | Coverage | Accuracy | Escalation | Abstention | Calls Avoided")
    for pt in sim.points:
        acc_str = f"{pt.accuracy_among_accepted:.1%}" if pt.accuracy_among_accepted else "N/A"
        click.echo(f"  {pt.threshold:>5.2f}   |  {pt.coverage:>6.1%}  |  {acc_str:>7} |   {pt.escalation_rate:>6.1%}   |   {pt.abstention_rate:>6.1%}   | {pt.expensive_calls_avoided:>5}")
    click.echo("=======================================================\n")


@cli.command()
@click.option("--objective", "-o", default=None, help="Task objective for demo.")
@click.pass_context
def demo(ctx: click.Context, objective: str | None):
    """Run killer end-to-end coding agent simulation."""
    gateway: DrexDecisionGateway = ctx.obj["gateway"]
    runner = KillerDemoRunner(gateway)
    click.echo(f"Starting Drex Coding Agent Loop Simulation [{gateway.provider_mode}]...\n")

    report = asyncio.run(runner.run(task_objective=objective))

    for s in report.steps:
        click.echo(f"[Step {s.step_number}] {s.phase:<15} ({s.actor}): {s.summary} [{s.latency_ms:.1f}ms]")

    click.echo("\n=======================================================")
    click.echo("KILLER DEMO EXECUTION SUMMARY")
    click.echo("=======================================================")
    click.echo(f"Total Drex Decisions:     {report.total_drex_decisions}")
    click.echo(f"Accepted Decisions:       {report.accepted_decisions}")
    click.echo(f"Escalated Decisions:      {report.escalated_decisions}")
    click.echo(f"Abstained Decisions:      {report.abstained_decisions}")
    click.echo(f"Expensive Calls Made:     {report.expensive_calls_made}")
    click.echo(f"Expensive Calls Avoided:  {report.expensive_calls_avoided}")
    click.echo(f"Total Drex Latency:       {report.total_drex_latency_ms:.1f}ms")
    click.echo(f"Total Pipeline Runtime:   {report.total_pipeline_time_ms:.1f}ms")
    click.echo(f"Final Verifier Outcome:   {report.final_status}")
    click.echo(f"Trace ID:                 {report.trace_id}")
    click.echo("=======================================================\n")


@cli.command()
@click.option("--host", default="127.0.0.1", help="Bind host.")
@click.option("--port", default=8000, help="Bind port.")
@click.pass_context
def serve(ctx: click.Context, host: str, port: int):
    """Start the Drex Decision Gateway HTTP server."""
    import uvicorn
    from drex_gateway.api.app import create_app

    gateway = ctx.obj["gateway"]
    app = create_app(gateway)
    click.echo(f"Starting Drex Decision Gateway on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
