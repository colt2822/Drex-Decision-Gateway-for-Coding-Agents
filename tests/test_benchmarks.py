"""Tests for BenchmarkRunner and EscalationSimulator."""
from pathlib import Path
import pytest
from drex_gateway.benchmarks.runner import BenchmarkRunner
from drex_gateway.benchmarks.simulation import EscalationSimulator
from drex_gateway.gateway import DrexDecisionGateway


@pytest.mark.asyncio
async def test_benchmark_runner_and_simulation(gateway: DrexDecisionGateway):
    dataset_path = Path(__file__).parent.parent / "drex_gateway" / "benchmarks" / "datasets" / "coding_tasks.jsonl"
    assert dataset_path.is_file()

    runner = BenchmarkRunner(gateway)
    report = await runner.run(dataset_path, suite_name="test_coding_suite")

    assert report.total_cases > 0
    assert report.evaluated_cases == report.total_cases
    assert report.accuracy is not None
    assert report.accuracy >= 0.70  # Deterministic replay keyword match is accurate
    assert report.coverage > 0.0
    assert len(report.calibration_bins) == 5

    # Run escalation simulation
    sim = EscalationSimulator.simulate(report)
    assert len(sim.points) == 6  # 0.50, 0.60, 0.70, 0.80, 0.90, 0.95
    # Verify higher threshold leads to <= coverage (monotonic decrease)
    coverages = [p.coverage for p in sim.points]
    for i in range(len(coverages) - 1):
        assert coverages[i] >= coverages[i + 1]
